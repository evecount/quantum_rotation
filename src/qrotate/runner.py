"""Execution backends for Q-Rotate SWAP-test circuits.

One interface, three kinds of backend:

* ``statevector`` wraps the in-repo numpy simulator
  (`circuits.simulate_swap_test_statevector`) plus binomial shot sampling, so
  its numbers are bit-for-bit the ones every benchmark in this repo reports.
* ``selene`` runs the compiled pytket circuit on Quantinuum's local Selene
  emulator through guppylang (``selene-sim``), when that package is installed.
* ``nexus:<target>`` submits the compiled circuit to Quantinuum Nexus through
  ``aqora.QPU`` (``H2-Emulator``, ``H2-1E``, ``H2-2E``, ``H2-1SC``, ``H2-2SC``,
  ``H2-1``). This is the path the Grand Challenge scores: it needs a team
  login (``aqora login``) and the costed targets spend HQCs.

Every backend returns a `RunResult` with the same fields, so the evidence
writer (`evidence.py`) does not care where the counts came from.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Sequence

import numpy as np

from .circuits import (
    HAS_PYTKET,
    build_pytket_swap_test_circuit,
    rebase_to_h2_gateset,
    simulate_swap_test_statevector,
    simulate_shot_sampling,
)
from .metrics import compute_circuit_hqc_cost, _wilson_interval


# =====================================================================
# Errors
# =====================================================================

class CredentialsRequired(RuntimeError):
    """A Nexus backend was asked to run without an aqora login.

    The message tells the team exactly what to do; the evidence CLI prints it
    verbatim instead of a traceback.
    """


class BackendUnavailable(RuntimeError):
    """The requested backend's package is not installed or cannot start."""


# =====================================================================
# Targets
# =====================================================================

#: Nexus provider platforms the Grand Challenge exposes through aqora.
NEXUS_TARGETS: tuple[str, ...] = (
    "H2-Emulator", "H2-1E", "H2-2E", "H2-1SC", "H2-2SC", "H2-1",
)

#: Syntax checkers validate and cost a program without executing it.
SYNTAX_CHECKERS: tuple[str, ...] = ("H2-1SC", "H2-2SC")

#: What each target bills, so a run file says what it spent.
NEXUS_COST_UNIT: dict[str, str] = {
    "H2-Emulator": "seconds",
    "H2-1E": "HQC",
    "H2-2E": "HQC",
    "H2-1": "HQC",
    "H2-1SC": "free (syntax check)",
    "H2-2SC": "free (syntax check)",
}

#: The one command the team runs after `aqora login`, quoted in the error.
LOGIN_COMMAND = "aqora login"
EVIDENCE_COMMAND = (
    "python -m src.qrotate.evidence --backend nexus:H2-2E --systems all --sites 4 --shots 100"
)


# =====================================================================
# Program and result containers
# =====================================================================

@dataclass
class SwapTestProgram:
    """One blind-parity SWAP-test circuit together with the inputs that built
    it, so a backend can run the circuit *and* a reader can rebuild it.

    `circuit` is the pytket circuit as `build_pytket_swap_test_circuit` emits
    it (H, CX, CCX, Ry, Rz); `compiled` is the same circuit after
    `rebase_to_h2_gateset` (PhasedX, Rz, ZZPhase), which is what gets
    submitted to any Quantinuum target.
    """

    pocket_phases: list[float]
    ligand_phases: list[float]
    tau: float
    omega: tuple[float, float, float]
    label: str = ""
    circuit: Any = None
    compiled: Any = None

    @classmethod
    def build(
        cls,
        pocket_phases: Sequence[float],
        ligand_phases: Sequence[float],
        tau: float = 0.25,
        omega: tuple[float, float, float] = (1.0, 0.5, 0.25),
        label: str = "",
    ) -> "SwapTestProgram":
        pocket = [float(p) for p in pocket_phases]
        ligand = [float(p) for p in ligand_phases]
        if len(pocket) != len(ligand):
            raise ValueError("pocket and ligand registers must have the same number of sites")
        circuit = build_pytket_swap_test_circuit(pocket, ligand, tau, omega)
        compiled = rebase_to_h2_gateset(circuit) if HAS_PYTKET else circuit
        return cls(pocket, ligand, float(tau), tuple(float(w) for w in omega), label, circuit, compiled)

    @property
    def n_sites(self) -> int:
        return len(self.pocket_phases)

    @property
    def n_qubits(self) -> int:
        return 2 * self.n_sites + 1

    def exact_prob_zero(self) -> float:
        """Ground-truth P(ancilla = 0) from the dense statevector simulator."""
        return simulate_swap_test_statevector(self.pocket_phases, self.ligand_phases, self.tau, self.omega)

    def circuit_json(self) -> Optional[dict]:
        return self.compiled.to_dict() if HAS_PYTKET and self.compiled is not None else None

    def hqc_estimate(self, shots: int) -> Optional[dict]:
        if not HAS_PYTKET or self.compiled is None:
            return None
        return compute_circuit_hqc_cost(self.compiled, shots=shots)


@dataclass
class RunResult:
    """What one execution of one circuit produced, whatever ran it."""

    backend: str
    shots: int
    counts: dict[str, int]
    prob_zero: float
    ci_low: float
    ci_high: float
    job_id: Optional[str] = None
    wall_time_s: float = 0.0
    hqc: Optional[dict] = None
    seed: Optional[int] = None
    #: Dense-statevector P(0) for the same circuit, as a reference line.
    prob_zero_exact: Optional[float] = None
    #: Anything backend-specific worth keeping (job status, raw payloads).
    extra: dict = field(default_factory=dict)

    @property
    def counts_zero(self) -> int:
        return int(self.counts.get("0", 0))

    @property
    def counts_one(self) -> int:
        return int(self.counts.get("1", 0))

    def to_dict(self) -> dict:
        return asdict(self)


def _result_from_counts(
    backend: str,
    counts: dict[str, int],
    shots: int,
    *,
    job_id: Optional[str],
    wall_time_s: float,
    hqc: Optional[dict],
    seed: Optional[int],
    prob_zero_exact: Optional[float],
    extra: Optional[dict] = None,
) -> RunResult:
    """Builds the common result fields from a 1-bit counts dictionary.

    The SWAP test measures one classical bit, so counts keys are "0"/"1"
    (anything longer is reduced to its first bit, which is the ancilla's).
    """
    merged: dict[str, int] = {"0": 0, "1": 0}
    for key, value in counts.items():
        bit = str(key).strip()[:1] or "0"
        merged[bit] = merged.get(bit, 0) + int(value)
    n = merged["0"] + merged["1"]
    p0 = merged["0"] / n if n else float("nan")
    low, high = _wilson_interval(merged["0"], n) if n else (float("nan"), float("nan"))
    return RunResult(
        backend=backend,
        shots=int(shots),
        counts=merged,
        prob_zero=float(p0),
        ci_low=float(low),
        ci_high=float(high),
        job_id=job_id,
        wall_time_s=float(wall_time_s),
        hqc=hqc,
        seed=seed,
        prob_zero_exact=prob_zero_exact,
        extra=dict(extra or {}),
    )


# =====================================================================
# Backend interface
# =====================================================================

class Backend(ABC):
    """Common interface: `run(program, shots, seed) -> RunResult`."""

    name: str = "abstract"
    #: True for Quantinuum H-series targets, where the HQC formula applies.
    is_h_series: bool = False
    #: Where the numbers come from, for the manifest.
    kind: str = "abstract"

    @abstractmethod
    def run(self, program: SwapTestProgram, shots: int, seed: Optional[int] = None) -> RunResult:
        ...

    def cost(self, program: SwapTestProgram, shots: int) -> Optional[dict]:
        """HQC estimate from the published formula, for H-series targets."""
        if not self.is_h_series:
            return None
        return program.hqc_estimate(shots)

    def describe(self) -> dict:
        return {"name": self.name, "kind": self.kind, "is_h_series": self.is_h_series}


# ---------------------------------------------------------------------
# 1. Statevector (the simulator every benchmark in this repo used)
# ---------------------------------------------------------------------

def _pytket_prob_zero(circuit, bit_index: int = 0) -> float:
    """P(measured bit = 0) of an arbitrary pytket circuit, from pytket's own
    statevector. Used to check that a compiled circuit still computes what the
    hand-written simulator says; the measure is stripped and the qubit it
    read is marginalised."""
    from pytket.circuit import Circuit, OpType

    measured_qubit = None
    unitary = Circuit(circuit.n_qubits)
    for cmd in circuit.get_commands():
        if cmd.op.type == OpType.Measure:
            if cmd.args[1].index[0] == bit_index:
                measured_qubit = cmd.args[0].index[0]
            continue
        if cmd.op.type == OpType.Barrier:
            continue
        unitary.add_gate(cmd.op, [q.index[0] for q in cmd.args])
    if measured_qubit is None:
        raise ValueError(f"circuit has no Measure into bit {bit_index}")
    state = unitary.get_statevector()  # ILO-BE: qubit 0 is the most significant bit
    n = circuit.n_qubits
    idx = np.arange(len(state))
    mask = ((idx >> (n - 1 - measured_qubit)) & 1) == 0
    return float(np.sum(np.abs(state[mask]) ** 2))


class StatevectorBackend(Backend):
    """Dense numpy statevector + binomial shot sampling.

    Identical to what `metrics.run_molecular_showdown` and the RUS loop do:
    P(0) from `simulate_swap_test_statevector`, then `simulate_shot_sampling`
    with the given seed. Pass a bare pytket circuit instead of a
    `SwapTestProgram` and pytket's own statevector is used instead.
    """

    name = "statevector"
    kind = "local_simulator"
    is_h_series = False

    def run(self, program, shots: int, seed: Optional[int] = None) -> RunResult:
        t0 = time.perf_counter()
        if isinstance(program, SwapTestProgram):
            p0 = program.exact_prob_zero()
        elif HAS_PYTKET and hasattr(program, "get_commands"):
            p0 = _pytket_prob_zero(program)
        else:
            raise TypeError("statevector backend needs a SwapTestProgram or a pytket Circuit")
        sample = simulate_shot_sampling(p0, n_shots=int(shots), seed=seed)
        counts = {"0": int(sample["counts_0"]), "1": int(sample["counts_1"])}
        return _result_from_counts(
            self.name, counts, shots,
            job_id=None, wall_time_s=time.perf_counter() - t0,
            hqc=None, seed=seed, prob_zero_exact=float(p0),
            extra={"sampling": "numpy binomial", "simulator": "qrotate.circuits.simulate_swap_test_statevector"},
        )


# ---------------------------------------------------------------------
# 2. Selene (Quantinuum's local emulator, through guppylang)
# ---------------------------------------------------------------------

def selene_available() -> tuple[bool, str]:
    """Whether the local Selene emulator can be imported, and why not if not."""
    try:
        import selene_sim  # noqa: F401
    except ImportError as exc:
        return False, (
            "selene-sim is not installed. Install it with `pip install selene-sim` "
            f"(import error: {exc})."
        )
    try:
        from guppylang import guppy  # noqa: F401
        from guppylang.emulator import EmulatorBuilder  # noqa: F401
    except ImportError as exc:
        return False, f"guppylang with emulator support is required for Selene (import error: {exc})."
    if not HAS_PYTKET:
        return False, "pytket is required to load the compiled circuit into guppylang."
    return True, "selene-sim and guppylang imported"


class SeleneBackend(Backend):
    """Runs the compiled circuit on Selene via guppylang's `load_pytket`.

    The pytket circuit becomes a Guppy function; a Guppy `main` allocates the
    qubits, calls it, reports the ancilla bit under the register name "c" and
    discards the qubits. `simulator` picks Selene's statevector ("quest"),
    "stim" (stabilizer, not applicable to these rotations) or "coinflip".
    """

    name = "selene"
    kind = "local_emulator"
    is_h_series = False

    def __init__(self, simulator: str = "statevector", n_processes: int = 1, verbose: bool = False):
        ok, why = selene_available()
        if not ok:
            raise BackendUnavailable(why)
        self.simulator = simulator
        self.n_processes = n_processes
        self.verbose = verbose

    def _guppy_main(self, program: SwapTestProgram):
        from guppylang import guppy
        from guppylang.std.quantum import qubit, discard
        try:
            from guppylang.std.builtins import output
        except ImportError:  # guppylang < 1.0 called it `result`
            from guppylang.std.builtins import result as output

        n_qubits = program.n_qubits
        circuit_fn = guppy.load_pytket("circuit_fn", program.compiled, use_arrays=False)

        @guppy.comptime
        def main() -> None:
            qs = [qubit() for _ in range(n_qubits)]
            bit = circuit_fn(*qs)
            output("c", bit)
            for q in qs:
                discard(q)

        return main

    def run(self, program: SwapTestProgram, shots: int, seed: Optional[int] = None) -> RunResult:
        from guppylang.emulator import EmulatorBuilder

        t0 = time.perf_counter()
        main = self._guppy_main(program)
        builder = EmulatorBuilder().with_verbose(self.verbose)
        instance = main.emulator(n_qubits=program.n_qubits, builder=builder)
        instance = instance.with_shots(int(shots)).with_n_processes(self.n_processes)
        if seed is not None:
            instance = instance.with_seed(int(seed))
        if self.simulator == "statevector":
            instance = instance.statevector_sim()
        elif self.simulator == "stabilizer":
            instance = instance.stabilizer_sim()
        elif self.simulator == "coinflip":
            instance = instance.coinflip_sim()
        else:
            raise ValueError(f"unknown Selene simulator {self.simulator!r}")
        t_build = time.perf_counter() - t0

        emu_result = instance.run()
        registers = emu_result.register_counts()
        if "c" not in registers:
            raise RuntimeError(f"Selene returned registers {sorted(registers)}, expected 'c'")
        counts = {k: int(v) for k, v in registers["c"].items()}
        return _result_from_counts(
            self.name, counts, shots,
            job_id=None, wall_time_s=time.perf_counter() - t0,
            hqc=None, seed=seed, prob_zero_exact=program.exact_prob_zero(),
            extra={
                "simulator": f"selene:{self.simulator}",
                "build_time_s": round(t_build, 3),
                "selene_sim_version": _package_version("selene-sim"),
                "guppylang_version": _package_version("guppylang"),
            },
        )


# ---------------------------------------------------------------------
# 3. Nexus (Quantinuum emulators, syntax checkers and hardware via aqora)
# ---------------------------------------------------------------------

def _viewer_username(client) -> str:
    """Asks aqora who the stored login is. Raises `aqora.ClientError` when
    there is no login (the server answers "Missing Authorization")."""
    import asyncio

    async def _query() -> str:
        if not client.authenticated:
            await client.authenticate()
        data = await client.send("query { viewer { username } }")
        return str(data["viewer"]["username"])

    return asyncio.run(_query())


def check_credentials() -> str:
    """Returns the aqora username of the stored login, or raises
    `CredentialsRequired` with the exact steps to take."""
    try:
        from aqora import Client, ClientError
    except ImportError as exc:
        raise BackendUnavailable(
            f"aqora is not installed (`pip install aqora`): {exc}"
        ) from exc
    try:
        return _viewer_username(Client())
    except ClientError as exc:
        raise CredentialsRequired(_credentials_message(str(exc))) from None
    except Exception as exc:  # network down, bad URL, ...
        raise CredentialsRequired(_credentials_message(f"{type(exc).__name__}: {exc}")) from None


def _credentials_message(detail: str) -> str:
    return (
        "No aqora login found on this machine, so nothing can be submitted to "
        f"Quantinuum Nexus (server said: {detail}).\n"
        "\n"
        "What the team must do, once, on this machine:\n"
        f"  1. {LOGIN_COMMAND}\n"
        "     (opens the browser; sign in with the team account that holds the\n"
        "      Grand Challenge quota)\n"
        "  2. Re-run the evidence command, for example:\n"
        f"     {EVIDENCE_COMMAND}\n"
        "\n"
        "Validate and cost every circuit for free first with:\n"
        "     python -m src.qrotate.evidence --syntax-check --systems all --sites 4 --shots 100\n"
    )


class NexusBackend(Backend):
    """Submits the compiled pytket circuit to a Nexus platform via `aqora.QPU`.

    `target` is one of `NEXUS_TARGETS`. `as_entity` attributes the job to a
    team organisation for quota tracking (see `aqora.QPU`). `timeout` bounds
    the wait for results in seconds.
    """

    kind = "quantinuum_nexus"
    is_h_series = True

    def __init__(self, target: str = "H2-2E", timeout: float = 600.0, as_entity: Optional[str] = None,
                 poll_interval: float = 5.0):
        canonical = {t.lower(): t for t in NEXUS_TARGETS}.get(target.lower())
        if canonical is None:
            raise ValueError(f"unknown Nexus target {target!r}; choose one of {', '.join(NEXUS_TARGETS)}")
        self.target = canonical
        self.name = f"nexus:{canonical}"
        self.timeout = timeout
        self.as_entity = as_entity
        self.poll_interval = poll_interval
        self._qpu = None

    @property
    def is_syntax_checker(self) -> bool:
        return self.target in SYNTAX_CHECKERS

    @property
    def cost_unit(self) -> str:
        return NEXUS_COST_UNIT[self.target]

    def describe(self) -> dict:
        info = super().describe()
        info.update({"target": self.target, "cost_unit": self.cost_unit, "syntax_checker": self.is_syntax_checker})
        return info

    def qpu(self):
        if self._qpu is None:
            from aqora import QPU
            check_credentials()
            self._qpu = QPU(platform=self.name, as_entity=self.as_entity)
        return self._qpu

    def run(self, program: SwapTestProgram, shots: int, seed: Optional[int] = None) -> RunResult:
        t0 = time.perf_counter()
        qpu = self.qpu()
        job = qpu.run(program.compiled, shots=int(shots))
        job_id = str(job.job_id)
        job.wait(timeout=self.timeout, poll_interval=self.poll_interval)
        payload = dict(job.refresh())
        items = job.results(raise_on_item_error=False)
        counts, raw = _counts_from_provider_results(items)
        extra = {
            "target": self.target,
            "cost_unit": self.cost_unit,
            "syntax_checker": self.is_syntax_checker,
            "job_status": payload.get("status"),
            "job_error": payload.get("error"),
            "job_payload": _jsonable(payload),
            "result_items": raw,
            "aqora_version": _package_version("aqora"),
        }
        if self.is_syntax_checker and counts is None:
            # A syntax checker validates and costs; it executes nothing, so
            # there are no counts and P(0) is NaN by design.
            return _result_from_counts(
                self.name, {}, 0,
                job_id=job_id, wall_time_s=time.perf_counter() - t0,
                hqc=self.cost(program, shots), seed=None,
                prob_zero_exact=program.exact_prob_zero(), extra=extra,
            )
        if counts is None:
            raise RuntimeError(
                f"Nexus job {job_id} on {self.target} finished with status "
                f"{payload.get('status')!r} but returned no counts; see result_items"
            )
        return _result_from_counts(
            self.name, counts, shots,
            job_id=job_id, wall_time_s=time.perf_counter() - t0,
            hqc=self.cost(program, shots), seed=None,
            prob_zero_exact=program.exact_prob_zero(), extra=extra,
        )


def _counts_from_provider_results(items) -> tuple[Optional[dict[str, int]], list[dict]]:
    """Reads 1-bit counts out of aqora `ProviderResult`s, keeping the raw
    payload beside them. Returns (counts or None, raw items)."""
    raw: list[dict] = []
    counts: Optional[dict[str, int]] = None
    for item in items:
        entry = {
            "index": item.index,
            "serialization_format": item.serialization_format,
            "error": item.error,
            "raw": item.raw[:20000] if isinstance(item.raw, str) else None,
        }
        raw.append(entry)
        if item.error or counts is not None:
            continue
        try:
            parsed = item.counts()
        except Exception as exc:  # unexpected format: keep raw, no counts
            entry["counts_error"] = f"{type(exc).__name__}: {exc}"
            continue
        if parsed:
            counts = {"".join(str(b) for b in (k if isinstance(k, (tuple, list)) else [k])): int(v)
                      for k, v in parsed.items()}
    return counts, raw


# =====================================================================
# Factory and helpers
# =====================================================================

def available_backends() -> list[str]:
    names = ["statevector"]
    if selene_available()[0]:
        names.append("selene")
    names.extend(f"nexus:{t}" for t in NEXUS_TARGETS)
    return names


def get_backend(name: str, **kwargs) -> Backend:
    """`statevector`, `selene`, `nexus:H2-2E` (or a bare target like `H2-2SC`)."""
    key = name.strip()
    lowered = key.lower()
    if lowered == "statevector":
        return StatevectorBackend()
    if lowered == "selene":
        return SeleneBackend(**kwargs)
    if lowered.startswith("nexus:"):
        return NexusBackend(key.split(":", 1)[1], **kwargs)
    if lowered in {t.lower() for t in NEXUS_TARGETS}:
        return NexusBackend(key, **kwargs)
    raise ValueError(
        f"unknown backend {name!r}; choose statevector, selene or nexus:<{'|'.join(NEXUS_TARGETS)}>"
    )


def _package_version(dist_name: str) -> Optional[str]:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version(dist_name)
    except PackageNotFoundError:
        return None


def _jsonable(value):
    """Best-effort conversion of provider payloads to JSON-safe values."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
