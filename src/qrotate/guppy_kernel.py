r"""Native Guppy repeat-until-success (RUS) kernel for Project Q-Rotate.

This module is the real, n-site version of the loop that `docs/04` sketches:
one Guppy program that prepares both phase registers, applies the U_tube
rotation, runs the ancilla SWAP test, measures the ancilla *mid-circuit*, and
on failure resets, kicks the ligand register and tests again, up to
`max_iters` times. The loop compiles to a HUGR control-flow graph, runs on
Selene with the loop intact, and lowers through `hugr-qir` to QIR for the
Quantinuum hardware target.

What runs where
===============

ON THE QPU (inside the compiled kernel; one shot = one run of this program):

* allocation of 2n+1 qubits (ancilla, pocket register, ligand register);
* state preparation of both registers from the phase lists, unrolled at
  compile time (`@guppy.comptime`), so every angle is a constant in the
  program, not a runtime argument;
* the U_tube rotation on the ligand register (comptime-unrolled);
* the SWAP test: H on the ancilla, then per site CX / CCX / CX, then H;
* a mid-circuit Z measurement of the ancilla (`project_z`, then `reset`),
  read back as a classical bit by the controller;
* the branch on that bit: accept, or reset the registers, apply the next
  phase kick to the ligand and test again;
* the phase kick: a table baked in at compile time
  (`kick_mode="deterministic"`, default: a global z-rotation sweep) or a
  +/- random walk drawn from the qsystem RNG extension (`kick_mode="rng"`);
* `output(...)` of the test count, the kick index the shot stopped on, the
  final ancilla bit, the first ancilla bit and the lock flag.

CLASSICALLY (host Python, after the shots come back):

* anything that needs a *probability*. One SWAP test yields one bit with
  P(0) = (1 + |<pocket|ligand>|^2) / 2, never below 1/2, so a single
  ancilla=0 is **not** evidence of a match: two orthogonal registers pass
  half the time. The kernel therefore cannot decide "locked" in the sense
  the search uses (`metrics.run_blind_rus_protocol` needs the lower
  confidence bound on P(0) across hundreds of shots to clear 0.90). What one
  shot *can* do is the per-shot RUS: stop at the first pass (or at
  `lock_threshold_shots` consecutive passes, which drives the false-accept
  rate of an orthogonal pair down to 2^-threshold) and report which kick it
  stopped on. Across shots, `first_parity` estimates P(0) of the starting
  pose, and `kick_index` is the histogram the host reads to pick a pose.
* the SPSA-style search over poses, which compares P(0) estimates between
  candidate kicks, stays in `metrics.py`. `estimate_first_test_p0` is the
  drop-in that reads that estimate from kernel shots instead of the numpy
  statevector.

Honest caveats:

* "locked" as reported by the kernel means "the per-shot stopping rule
  fired", not "the pose is right". The host must aggregate shots.
* By default a failed test is followed by a reset and re-preparation of
  both registers (`reprepare_on_failure=True`). After a failed SWAP test the
  registers are left entangled in the antisymmetric subspace; a phase kick
  on that state is not a phase kick on a fresh ligand. Re-preparing makes
  every test an independent Bernoulli trial with the P(0) the rest of the
  project computes. The literal sketch from the docs (reset the ancilla
  only, kick the live ligand register) is `reprepare_on_failure=False`.
* `op_counts()` are *static* program counts: the loop body is counted once,
  so a RUS kernel shows two state preparations (the initial one and the
  one in the loop body). Executed gate counts per shot grow with the number
  of tests that shot ran. `build_single_test_kernel` is the straight-line
  twin of the Pytket circuit for like-for-like counts.

Toolchain limits hit while building this (guppylang 1.1.1, hugr-qir 0.3.0,
selene-sim 0.3.2):

* hugr-qir lowers only loops whose trip count is known at compile time, and
  fully unrolls them (the QIR adaptive profile has no backward branches).
  A `while not locked` loop is rejected. The kernel is therefore written as
  a static `for` over `max_iters * lock_threshold_shots` test slots with an
  `if row:` guard carrying the data-dependent exit; this is the bounded RUS
  the hardware runs anyway.
* for the quantinuum-hardware target hugr-qir rejects any rotation whose
  angle does not fold to a constant ("Program may panic:
  tket2.rotation.from_halfturns_unchecked"). Kick angles are therefore read
  from a comptime table by the *static* row index; a runtime float cannot
  reach an Rz. `RandomFloat` is also unsupported, so the RNG kick draws
  signs with `random_int_bounded`.
* qubit *arrays* (`array[qubit, n]`) lower to `alloca` instructions in the
  QIR, which `quantinuum_qircheck` rejects, and they also trip hugr-qir's
  unroller on loop phi blocks ("Phi block tail cannot be lowered") once the
  control flow has streaks or RNG state. The registers are therefore tuples
  of qubits threaded through the comptime helpers as owned values; with that
  change every variant (deterministic or rng kick, any threshold) lowers for
  n = 1 to 8 and validates with qircheck 0.9.0.
* `quantinuum_qircheck` (hugr-qir's import-time dependency) has no release
  for CPython >= 3.13. On this machine (3.14) `to_qir` installs a stub and
  lowers with `validate_qir=False`; the bitcode is identical, only the
  validation step is skipped. `qir_validation_status()` says which path
  ran, and `validate_qir_externally` can hand the bitcode to another
  interpreter that has qircheck.

Requires guppylang >= 1.0 (lazy `Measurement`, `comptime`, `type_alias`).
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import types
import zlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Sequence

import numpy as np

try:
    import guppylang
    from guppylang import guppy
    from guppylang.std.angles import angle
    from guppylang.std.builtins import comptime, output, owned
    from guppylang.std.quantum import (
        cx,
        h,
        measure,
        project_z,
        qubit,
        reset,
        ry,
        rz,
        toffoli,
    )
    from guppylang.std.qsystem.random import RNG

    HAS_GUPPY = True
except ImportError:  # pragma: no cover - exercised only without guppylang
    guppy = None
    HAS_GUPPY = False


KickMode = Literal["deterministic", "rng"]

# Result tags written by the kernel with output(...).
TAG_FIRST_PARITY = "first_parity"
TAG_ITERATIONS = "iterations"
TAG_KICK_INDEX = "kick_index"
TAG_LOCKED = "locked"
TAG_PARITY = "parity"


def _require_guppy() -> None:
    if not HAS_GUPPY:
        raise ImportError("guppylang is not installed; the native RUS kernel needs guppylang >= 1.0")
    major = int(str(getattr(guppylang, "__version__", "0")).split(".")[0])
    if major < 1:
        raise RuntimeError(
            f"guppylang {guppylang.__version__} is too old for the RUS kernel "
            "(needs the 1.x lazy-measurement, comptime and type_alias APIs)"
        )


def default_kick_schedule(
    n_sites: int,
    max_iters: int,
    kick_step: Optional[float] = None,
) -> list[list[float]]:
    """Deterministic blind kick table, one row per test row, in radians.

    Row k is the *absolute* ligand phase offset used by kick index k (row 0
    is zero: the first test is the unkicked ligand). The default is a global
    z-rotation sweep: every site is shifted by the same k * kick_step, which
    is what rotating the ligand about z does to the shell encoding
    (`hpc_bridge.molecular_shell_phases` is rotation-equivariant). The table
    never looks at the pocket phases, so the search stays blind.
    """
    if max_iters < 1:
        raise ValueError("max_iters must be >= 1")
    step = (2.0 * math.pi / max_iters) if kick_step is None else float(kick_step)
    return [[k * step] * n_sites for k in range(max_iters)]


@dataclass
class RusShotSummary:
    """Host-side aggregation of kernel shots. This is the classical half."""

    n_shots: int
    lock_rate: float
    mean_iterations: float
    first_test_p0_hat: float
    first_test_p0_stderr: float
    iterations_hist: dict[int, int]
    kick_index_hist: dict[int, int]
    final_parity_hist: dict[int, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_shots": self.n_shots,
            "lock_rate": self.lock_rate,
            "mean_iterations": self.mean_iterations,
            "first_test_p0_hat": self.first_test_p0_hat,
            "first_test_p0_stderr": self.first_test_p0_stderr,
            "iterations_hist": {str(k): v for k, v in sorted(self.iterations_hist.items())},
            "kick_index_hist": {str(k): v for k, v in sorted(self.kick_index_hist.items())},
            "final_parity_hist": {str(k): v for k, v in sorted(self.final_parity_hist.items())},
        }


def summarize_shots(shots: Sequence[dict[str, int]]) -> RusShotSummary:
    """Aggregates per-shot output dicts (one per kernel run) into the
    statistics the classical search needs. The kernel never computes these."""
    n = len(shots)
    if n == 0:
        raise ValueError("no shots to summarise")
    first_bits = np.array([int(s[TAG_FIRST_PARITY]) for s in shots], dtype=float)
    p0_hat = float(1.0 - first_bits.mean())
    stderr = float(math.sqrt(max(1e-12, p0_hat * (1.0 - p0_hat) / n)))
    return RusShotSummary(
        n_shots=n,
        lock_rate=float(np.mean([int(s[TAG_LOCKED]) for s in shots])),
        mean_iterations=float(np.mean([int(s[TAG_ITERATIONS]) for s in shots])),
        first_test_p0_hat=p0_hat,
        first_test_p0_stderr=stderr,
        iterations_hist=dict(Counter(int(s[TAG_ITERATIONS]) for s in shots)),
        kick_index_hist=dict(Counter(int(s[TAG_KICK_INDEX]) for s in shots)),
        final_parity_hist=dict(Counter(int(s[TAG_PARITY]) for s in shots)),
    )


# ---------------------------------------------------------------------------
# QIR lowering
# ---------------------------------------------------------------------------

_QIRCHECK_STUBBED = False


def _ensure_hugr_qir():
    """Imports hugr_qir, stubbing `quantinuum_qircheck` when that package is
    missing (it has no release for CPython >= 3.13). With the stub in place
    QIR is emitted but not validated; see `qir_validation_status`."""
    global _QIRCHECK_STUBBED
    try:
        import quantinuum_qircheck  # noqa: F401
    except ImportError:
        if "quantinuum_qircheck" not in sys.modules:
            stub = types.ModuleType("quantinuum_qircheck")
            sub = types.ModuleType("quantinuum_qircheck.qircheck")

            class ValidationError(Exception):
                pass

            def qircheck(*_a, **_k):
                raise RuntimeError("quantinuum_qircheck is not installed; QIR was not validated")

            sub.ValidationError = ValidationError
            sub.qircheck = qircheck
            stub.qircheck = sub
            stub.ValidationError = ValidationError
            sys.modules["quantinuum_qircheck"] = stub
            sys.modules["quantinuum_qircheck.qircheck"] = sub
        _QIRCHECK_STUBBED = True
    from hugr_qir.hugr_to_qir import hugr_to_qir
    from hugr_qir.output import OutputFormat

    return hugr_to_qir, OutputFormat


def qir_validation_status() -> str:
    """'validated' when the real quantinuum_qircheck ran inside `to_qir`,
    'unvalidated (...)' when the stub was needed, 'unknown' before any lowering."""
    if _QIRCHECK_STUBBED:
        return "unvalidated (quantinuum_qircheck has no CPython >= 3.13 release; stubbed)"
    return "validated" if "hugr_qir" in sys.modules else "unknown"


def validate_qir_externally(bitcode: bytes, python_exe: Optional[str] = None) -> dict[str, Any]:
    """Runs quantinuum_qircheck on `bitcode` in another interpreter.

    `python_exe` defaults to the QROTATE_QIRCHECK_PYTHON environment variable
    (a CPython <= 3.12 with quantinuum-qircheck installed). Returns a dict
    with `ok`, `detail` and the interpreter used; `ok` is None when no
    interpreter was given.
    """
    exe = python_exe or os.environ.get("QROTATE_QIRCHECK_PYTHON")
    if not exe:
        return {"ok": None, "detail": "no external qircheck interpreter configured", "python": None}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "kernel.bc")
        with open(path, "wb") as fh:
            fh.write(bitcode)
        code = (
            "import sys; from quantinuum_qircheck import qircheck; "
            "from importlib.metadata import version; "
            "qircheck(open(sys.argv[1], 'rb').read()); "
            "print('qircheck', version('quantinuum-qircheck'), 'ok')"
        )
        proc = subprocess.run([exe, "-I", "-c", code, path], capture_output=True, text=True, timeout=600)
    ok = proc.returncode == 0
    detail = (proc.stdout if ok else proc.stderr).strip().splitlines()
    return {"ok": ok, "detail": detail[-1] if detail else "", "python": exe}


# ---------------------------------------------------------------------------
# Native op counting (same recipe as utils.hugr_op_counts, without marimo)
# ---------------------------------------------------------------------------

NATIVE_OPS = ("PhasedX", "ZZMax", "ZZPhase", "Measure", "Reset")


def hugr_native_op_counts(package) -> dict[str, int]:
    """Counts qubits and H-series native ops in a compiled HUGR package after
    rebasing into the QSystem gate set and inlining calls. Static counts: a
    loop body is counted once."""
    from hugr.package import Package

    try:
        from tket.passes import InlineFunctions, QSystemRebasePass
    except ImportError:
        from tket.passes import InlineFunctions, QSystemPass as QSystemRebasePass
    from tket.passes.inline_funcs import All

    qsystem_ops = {
        "TryQAlloc": ("Qubits",),
        "PhasedX": ("PhasedX",),
        "ZZPhase": ("ZZPhase",),
        "ZZMax": ("ZZMax",),
        "LazyMeasure": ("Measure",),
        "LazyMeasureLeaked": ("Measure",),
        "LazyMeasureReset": ("Measure", "Reset"),
        "Reset": ("Reset",),
    }
    counts = dict.fromkeys(("Qubits", *NATIVE_OPS), 0)
    modules = package.modules if isinstance(package, Package) else [package]
    for module in modules:
        lowered = QSystemRebasePass().run(module, inplace=False).hugr
        InlineFunctions(All()).run(lowered)
        for node in lowered.descendants(lowered.entrypoint):
            name = lowered[node].op.name().rsplit(".", 1)[-1]
            for key in qsystem_ops.get(name, ()):
                counts[key] += 1
    return counts


def pytket_native_op_counts(circuit) -> dict[str, int]:
    """Native op counts of a Pytket circuit already rebased into the H-series
    gate set (`circuits.rebase_to_h2_gateset`)."""
    from pytket.circuit import OpType

    counts = {"Qubits": circuit.n_qubits}
    for op in NATIVE_OPS:
        counts[op] = circuit.n_gates_of_type(getattr(OpType, op))
    return counts


# ---------------------------------------------------------------------------
# The kernel
# ---------------------------------------------------------------------------


@dataclass
class RusKernel:
    """A built Guppy RUS program plus the metadata needed to interpret it."""

    main: Any
    n_sites: int
    max_iters: int
    lock_threshold_shots: int
    kick_mode: str
    kick_schedule: list[list[float]]  # radians; row k = absolute offset for kick index k
    pocket_phases: list[float]
    ligand_phases_init: list[float]
    tau: float
    omega: tuple[float, float, float]
    reprepare_on_failure: bool
    rng_seed: int
    kick_step: list[float]
    straight_line: bool = False
    _package: Any = field(default=None, repr=False)

    @property
    def n_qubits(self) -> int:
        return 2 * self.n_sites + 1

    @property
    def hardware_lowerable(self) -> bool:
        """Every variant currently lowers to hardware-target QIR and validates
        with quantinuum_qircheck (deterministic and rng kicks, any threshold)."""
        return True

    def compile(self):
        """Guppy -> HUGR package (cached)."""
        if self._package is None:
            self._package = self.main.compile()
        return self._package

    def to_qir(self, output_format: str = "bitcode"):
        """HUGR -> QIR. `output_format` is 'bitcode', 'llvm-ir' or 'base64'."""
        hugr_to_qir, OutputFormat = _ensure_hugr_qir()
        fmt = OutputFormat(output_format)
        return hugr_to_qir(self.compile(), validate_qir=not _QIRCHECK_STUBBED, output_format=fmt)

    def op_counts(self) -> dict[str, int]:
        """Static H-series native op counts of the whole program."""
        return hugr_native_op_counts(self.compile())

    def emulate(
        self,
        shots: int = 100,
        seed: Optional[int] = 0,
        n_processes: Optional[int] = None,
    ) -> list[dict[str, int]]:
        """Runs the kernel on Selene via guppylang's emulator and returns one
        output dict per shot. Aggregate with `summarize_shots`; the kernel
        itself does not know P(0)."""
        inst = self.main.emulator(n_qubits=self.n_qubits).with_shots(shots)
        if seed is not None:
            inst = inst.with_seed(int(seed))
        if n_processes:
            inst = inst.with_n_processes(int(n_processes))
        result = inst.run()
        return [shot.as_dict() for shot in result]

    def ligand_phases_for_kick(self, kick_index: int) -> list[float]:
        """Absolute ligand phases a shot that stopped on `kick_index` was
        testing (deterministic mode only; RNG kicks are not reported)."""
        if self.kick_mode != "deterministic":
            raise ValueError("kick phases are only known for the deterministic schedule")
        row = self.kick_schedule[kick_index]
        return [float(l + k) for l, k in zip(self.ligand_phases_init, row)]


def _make_helpers(n: int, POCKET_HT, LIGAND_HT, UTUBE_Y_HT, UTUBE_Z_HT, STEP_HT):
    """Comptime helpers: each call is unrolled over the n sites at compile
    time, with every angle a constant. Same gate order as
    `circuits.build_pytket_swap_test_circuit`.

    Registers are *tuples* of qubits, threaded through the helpers as owned
    values, not `array[qubit, n]`: borrow arrays lower to `alloca`
    instructions that `quantinuum_qircheck` rejects, and they also trip
    hugr-qir's unroller on the loop's phi blocks. Tuples lower to plain SSA
    values and the resulting QIR validates.
    """
    # A 1-tuple of qubits is just a qubit to Guppy, so n == 1 uses the bare
    # type and the helpers wrap/unwrap it.
    REG = guppy.type_alias(f"Reg{n}", "qubit" if n == 1 else "tuple[" + ", ".join(["qubit"] * n) + "]")

    def _tup(r):
        return (r,) if n == 1 else r

    def _reg(t):
        return t[0] if n == 1 else t

    @guppy.comptime
    def alloc_registers() -> tuple[REG, REG]:
        return _reg(tuple(qubit() for _ in range(n))), _reg(tuple(qubit() for _ in range(n)))

    @guppy.comptime
    def encode(pocket: REG @ owned, ligand: REG @ owned) -> tuple[REG, REG]:
        pocket, ligand = _tup(pocket), _tup(ligand)
        for i in range(n):
            ry(pocket[i], angle(0.5))
            rz(pocket[i], angle(POCKET_HT[i]))
            ry(ligand[i], angle(0.5))
            rz(ligand[i], angle(LIGAND_HT[i]))
        return _reg(pocket), _reg(ligand)

    @guppy.comptime
    def apply_u_tube(ligand: REG @ owned) -> REG:
        ligand = _tup(ligand)
        for i in range(n):
            ry(ligand[i], angle(UTUBE_Y_HT))
            rz(ligand[i], angle(UTUBE_Z_HT))
        return _reg(ligand)

    @guppy.comptime
    def reset_registers(pocket: REG @ owned, ligand: REG @ owned) -> tuple[REG, REG]:
        pocket, ligand = _tup(pocket), _tup(ligand)
        for i in range(n):
            reset(pocket[i])
            reset(ligand[i])
        return _reg(pocket), _reg(ligand)

    @guppy.comptime
    def kick_plus(ligand: REG @ owned) -> REG:
        ligand = _tup(ligand)
        for i in range(n):
            rz(ligand[i], angle(STEP_HT[i]))
        return _reg(ligand)

    @guppy.comptime
    def kick_minus(ligand: REG @ owned) -> REG:
        ligand = _tup(ligand)
        for i in range(n):
            rz(ligand[i], -angle(STEP_HT[i]))
        return _reg(ligand)

    @guppy.comptime
    def swap_test(anc: qubit, pocket: REG @ owned, ligand: REG @ owned) -> tuple[REG, REG]:
        pocket, ligand = _tup(pocket), _tup(ligand)
        h(anc)
        for i in range(n):
            cx(ligand[i], pocket[i])
            toffoli(anc, pocket[i], ligand[i])
            cx(ligand[i], pocket[i])
        h(anc)
        return _reg(pocket), _reg(ligand)

    @guppy.comptime
    def release(pocket: REG @ owned, ligand: REG @ owned) -> None:
        pocket, ligand = _tup(pocket), _tup(ligand)
        for i in range(n):
            measure(pocket[i])
            measure(ligand[i])

    return alloc_registers, encode, apply_u_tube, reset_registers, kick_plus, kick_minus, swap_test, release


def _constants(pocket_phases, ligand_phases, tau, omega):
    n = int(len(pocket_phases))
    if n < 1:
        raise ValueError("need at least one site")
    if len(ligand_phases) != n:
        raise ValueError("pocket and ligand phase lists must have the same length")
    _wx, wy, wz = omega
    return (
        n,
        [float(p) / math.pi for p in pocket_phases],  # Guppy angle(x) = x half-turns
        [float(l) / math.pi for l in ligand_phases],
        float(wy * tau) / math.pi,
        float(wz * tau) / math.pi,
    )


def build_rus_kernel(
    pocket_phases: Sequence[float],
    ligand_phases_init: Sequence[float],
    tau: float,
    omega: tuple[float, float, float],
    max_iters: int = 8,
    lock_threshold_shots: int = 1,
    *,
    kick_mode: KickMode = "deterministic",
    kick_step: Optional[float | Sequence[float]] = None,
    rng_seed: int = 0xC0FFEE,
    reprepare_on_failure: bool = True,
) -> RusKernel:
    r"""Builds the native Guppy RUS program for n = len(pocket_phases) sites.

    Args:
        pocket_phases: n encoding phases (radians) for the pocket register.
        ligand_phases_init: n starting phases (radians) for the ligand.
        tau, omega: U_tube rotation; per site Ry(omega_y * tau) Rz(omega_z * tau)
            on the ligand, the same gates `build_pytket_swap_test_circuit` applies.
        max_iters: maximum number of kick rows one shot may try. Each row runs
            up to `lock_threshold_shots` tests, so a shot runs at most
            max_iters * lock_threshold_shots SWAP tests.
        lock_threshold_shots: consecutive ancilla=0 results required, within
            one shot and at the same kick, before the kernel declares `locked`.
            1 is the plain repeat-until-success rule. A streak of t passes has
            probability ((1+F)/2)^t, i.e. 2^-t for orthogonal registers: the
            only per-shot handle on false accepts. It does not replace the
            shot-aggregated confidence bound the classical search uses.
        kick_mode: "deterministic" walks a linear sweep, kick row j = j *
            kick_step (every angle a compile-time constant); "rng" draws one
            sign per failed row from the qsystem RNG (seeded with `rng_seed`)
            on the controller and moves the whole register by +/- kick_step:
            a blind random walk of the pose.
        kick_step: radians per kick, a scalar (same for every site, i.e. a
            rotation of the whole ligand about z, which is what the shell
            encoder maps a pose rotation to) or one value per site. Default
            2*pi/max_iters so the deterministic sweep covers a full turn.
        reprepare_on_failure: True resets and re-encodes both registers before
            every repeat (independent trials; default). False follows the
            docs' sketch literally: reset the ancilla only and apply the kick
            increment to the live ligand register.

    Returns:
        A `RusKernel`. Nothing is compiled until `.compile()` / `.emulate()`.
    """
    _require_guppy()
    if max_iters < 1:
        raise ValueError("max_iters must be >= 1")
    if not 1 <= lock_threshold_shots <= max_iters:
        raise ValueError("lock_threshold_shots must be in [1, max_iters]")
    if kick_mode not in ("deterministic", "rng"):
        raise ValueError("kick_mode must be 'deterministic' or 'rng'")

    n, POCKET_HT, LIGAND_HT, UTUBE_Y_HT, UTUBE_Z_HT = _constants(pocket_phases, ligand_phases_init, tau, omega)

    if kick_step is None:
        step = [2.0 * math.pi / max_iters] * n
    elif np.isscalar(kick_step):
        step = [float(kick_step)] * n
    else:
        step = [float(v) for v in kick_step]
        if len(step) != n:
            raise ValueError("kick_step must be a scalar or one value per site")
    schedule = [[j * s for s in step] for j in range(max_iters)]

    STEP_HT = [s / math.pi for s in step]
    MAX_ITERS = int(max_iters)
    THRESHOLD = int(lock_threshold_shots)
    T = MAX_ITERS * THRESHOLD
    RNG_SEED = int(rng_seed)
    REPREPARE = bool(reprepare_on_failure)
    USE_RNG = kick_mode == "rng"

    alloc_registers, encode, apply_u_tube, reset_registers, kick_plus, kick_minus, swap_test, release = _make_helpers(
        n, POCKET_HT, LIGAND_HT, UTUBE_Y_HT, UTUBE_Z_HT, STEP_HT
    )

    # The RUS loop. hugr-qir only lowers loops with a compile-time trip count
    # (it unrolls them: the QIR adaptive profile has no backward branches) and
    # only constant rotation angles, so the loop is a static `for` over the
    # test slots, the data-dependent exit is the `if row:` guard, and the kick
    # for row j is j applications of the constant step (a static-bound loop
    # with a guard). Selene executes the same HUGR with the loop intact. The
    # controller branches on the mid-circuit bit at every slot either way.

    if not USE_RNG:

        @guppy
        def qrotate_rus() -> None:
            anc = qubit()
            pocket, ligand = alloc_registers()
            pocket, ligand = encode(pocket, ligand)
            ligand = apply_u_tube(ligand)
            tests = 0
            k = 0
            locked = False
            bit = False
            first_bit = False
            row = True
            for t in range(comptime(T)):
                j = t // comptime(THRESHOLD)
                s = t % comptime(THRESHOLD)
                if s == 0:
                    row = not locked
                    if row:
                        k = j
                if row:
                    if t > 0:
                        reset(anc)
                        if comptime(REPREPARE):
                            pocket, ligand = reset_registers(pocket, ligand)
                            pocket, ligand = encode(pocket, ligand)
                            for m in range(comptime(MAX_ITERS)):
                                if m < j:
                                    ligand = kick_plus(ligand)
                            ligand = apply_u_tube(ligand)
                        elif s == 0:
                            # live-register sketch: one more kick on the
                            # post-measurement state, ancilla reset only
                            ligand = kick_plus(ligand)
                    pocket, ligand = swap_test(anc, pocket, ligand)
                    bit = project_z(anc).read()
                    if t == 0:
                        first_bit = bit
                    tests += 1
                    if bit:
                        row = False
                    elif s == comptime(THRESHOLD) - 1:
                        locked = True
                        row = False
            output(TAG_ITERATIONS, tests)
            output(TAG_KICK_INDEX, k)
            output(TAG_LOCKED, locked)
            output(TAG_PARITY, bit)
            output(TAG_FIRST_PARITY, first_bit)
            measure(anc)
            release(pocket, ligand)

    else:

        @guppy
        def qrotate_rus() -> None:
            anc = qubit()
            pocket, ligand = alloc_registers()
            rng = RNG(comptime(RNG_SEED))
            mask = 0  # bit j-1: sign of the kick drawn after row j-1 failed
            pocket, ligand = encode(pocket, ligand)
            ligand = apply_u_tube(ligand)
            tests = 0
            k = 0
            locked = False
            bit = False
            first_bit = False
            row = True
            for t in range(comptime(T)):
                j = t // comptime(THRESHOLD)
                s = t % comptime(THRESHOLD)
                if s == 0:
                    row = not locked
                    if row:
                        k = j
                        if j > 0:
                            if rng.random_int_bounded(2) == 1:
                                mask = mask | (1 << (j - 1))
                if row:
                    if t > 0:
                        reset(anc)
                        if comptime(REPREPARE):
                            pocket, ligand = reset_registers(pocket, ligand)
                            pocket, ligand = encode(pocket, ligand)
                            # replay the random walk so far (static bound, guarded)
                            for m in range(comptime(MAX_ITERS)):
                                if m < j:
                                    if (mask >> m) & 1 == 1:
                                        ligand = kick_plus(ligand)
                                    else:
                                        ligand = kick_minus(ligand)
                            ligand = apply_u_tube(ligand)
                        elif s == 0:
                            if (mask >> (j - 1)) & 1 == 1:
                                ligand = kick_plus(ligand)
                            else:
                                ligand = kick_minus(ligand)
                    pocket, ligand = swap_test(anc, pocket, ligand)
                    bit = project_z(anc).read()
                    if t == 0:
                        first_bit = bit
                    tests += 1
                    if bit:
                        row = False
                    elif s == comptime(THRESHOLD) - 1:
                        locked = True
                        row = False
            output(TAG_ITERATIONS, tests)
            output(TAG_KICK_INDEX, k)
            output(TAG_LOCKED, locked)
            output(TAG_PARITY, bit)
            output(TAG_FIRST_PARITY, first_bit)
            rng.discard()
            measure(anc)
            release(pocket, ligand)

    return RusKernel(
        main=qrotate_rus,
        n_sites=n,
        max_iters=MAX_ITERS,
        lock_threshold_shots=THRESHOLD,
        kick_mode=kick_mode,
        kick_schedule=schedule,
        pocket_phases=[float(p) for p in pocket_phases],
        ligand_phases_init=[float(l) for l in ligand_phases_init],
        tau=float(tau),
        omega=tuple(float(w) for w in omega),
        reprepare_on_failure=REPREPARE,
        rng_seed=RNG_SEED,
        kick_step=step,
    )


def build_single_test_kernel(
    pocket_phases: Sequence[float],
    ligand_phases: Sequence[float],
    tau: float,
    omega: tuple[float, float, float],
) -> RusKernel:
    """One SWAP test, straight-line, no loop: the Guppy twin of
    `circuits.build_pytket_swap_test_circuit`, for like-for-like native op
    counts and for the host-side P(0) estimate. Emits the same output tags
    as the RUS kernel (iterations = 1, kick_index = 0)."""
    _require_guppy()
    n, POCKET_HT, LIGAND_HT, UTUBE_Y_HT, UTUBE_Z_HT = _constants(pocket_phases, ligand_phases, tau, omega)
    alloc_registers, encode, apply_u_tube, _reset, _plus, _minus, swap_test, release = _make_helpers(
        n, POCKET_HT, LIGAND_HT, UTUBE_Y_HT, UTUBE_Z_HT, [0.0] * n
    )

    @guppy
    def qrotate_single_test() -> None:
        anc = qubit()
        pocket, ligand = alloc_registers()
        pocket, ligand = encode(pocket, ligand)
        ligand = apply_u_tube(ligand)
        pocket, ligand = swap_test(anc, pocket, ligand)
        bit = project_z(anc).read()
        output(TAG_ITERATIONS, 1)
        output(TAG_KICK_INDEX, 0)
        output(TAG_LOCKED, not bit)
        output(TAG_PARITY, bit)
        output(TAG_FIRST_PARITY, bit)
        measure(anc)
        release(pocket, ligand)

    return RusKernel(
        main=qrotate_single_test,
        n_sites=n,
        max_iters=1,
        lock_threshold_shots=1,
        kick_mode="deterministic",
        kick_schedule=[[0.0] * n],
        pocket_phases=[float(p) for p in pocket_phases],
        ligand_phases_init=[float(l) for l in ligand_phases],
        tau=float(tau),
        omega=tuple(float(w) for w in omega),
        reprepare_on_failure=True,
        rng_seed=0,
        kick_step=[0.0] * n,
        straight_line=True,
    )


# ---------------------------------------------------------------------------
# Host-side glue for the classical search
# ---------------------------------------------------------------------------


def estimate_first_test_p0(
    pocket_phases: Sequence[float],
    ligand_phases: Sequence[float],
    tau: float,
    omega: tuple[float, float, float],
    shots: int = 200,
    seed: Optional[int] = 0,
) -> dict[str, float | int]:
    """P(ancilla = 0) of one SWAP test, estimated from kernel shots on Selene.

    This is the quantity `metrics.run_blind_rus_protocol` consumes per
    candidate; it is a host-side average over shots, which is why the search
    loop stays classical. Returns empirical_prob, std_err and n_shots in the
    same shape `circuits.simulate_shot_sampling` uses.
    """
    kernel = build_single_test_kernel(pocket_phases, ligand_phases, tau, omega)
    summary = summarize_shots(kernel.emulate(shots=shots, seed=seed))
    return {
        "empirical_prob": summary.first_test_p0_hat,
        "std_err": summary.first_test_p0_stderr,
        "n_shots": summary.n_shots,
        "counts_0": int(round(summary.first_test_p0_hat * summary.n_shots)),
    }


# ---------------------------------------------------------------------------
# Selene benchmark over the six real systems
# ---------------------------------------------------------------------------


def _versions() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    out = {"python": sys.version.split()[0], "platform": sys.platform}
    for pkg in ("guppylang", "hugr", "hugr-qir", "selene-sim", "selene-core", "pytket", "tket", "pyqir"):
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            out[pkg] = "not installed"
    return out


def run_selene_benchmark(
    output_json_path: Optional[str] = None,
    n_sites: int = 4,
    shots: int = 200,
    max_iters: int = 12,
    tau: float = 0.25,
    omega: tuple[float, float, float] = (1.0, 0.5, 0.25),
    seed: int = 7,
    count_sizes: Sequence[int] = (1, 2, 4, 8),
    systems: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Compiles and runs the kernel on Selene for the six benchmark systems.

    For each system the target is the ligand in its deposited pose and the
    probe is the same ligand rotated off that pose by the system's
    `optimal_angle_deg` (as in `metrics.run_molecular_showdown`), both
    encoded with `hpc_bridge.molecular_shell_phases`. Three runs per system:

    * `single_test`: the straight-line kernel at the probe pose; its
      first-test P(0) estimate is checked against the exact statevector.
    * `rus_sweep`: the RUS kernel with the default global-rotation sweep
      (2*pi / max_iters per kick); the kick-index histogram is reported next
      to the exact P(0) of every row so the reader can see which rows the
      per-shot rule stops on.
    * `self_overlap_control`: probe == target and tau = 0, where P(0) must be 1.

    Op counts and QIR sizes for `count_sizes` are reported alongside the
    Pytket single-shot circuit. Writes JSON when `output_json_path` is given.
    """
    from .circuits import build_pytket_swap_test_circuit, rebase_to_h2_gateset, simulate_swap_test_statevector
    from .hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases
    from .metrics import REAL_MOLECULE_SYSTEMS, _system_coordinates
    from .structures import site_elements

    report: dict[str, Any] = {
        "generated_by": "python -m qrotate.guppy_kernel",
        "environment": _versions(),
        "settings": {
            "n_sites": n_sites, "shots": shots, "max_iters": max_iters, "tau": tau,
            "omega": list(omega), "seed": seed, "kick_mode": "deterministic",
            "kick_step_deg": 360.0 / max_iters,  # kick row j = j * step "lock_threshold_shots": 1,
            "reprepare_on_failure": True, "emulator": "selene (guppylang emulator, statevector)",
        },
        "op_counts": [],
        "systems": [],
        "notes": [
            "op counts are static HUGR counts after QSystem rebase; the RUS loop body is counted once "
            "(two state preparations: initial and in-loop).",
            "first_test_p0_hat is a host-side average over shots; one shot cannot estimate P(0).",
            "lock_rate is the per-shot stopping rule (first ancilla=0), which fires with probability "
            ">= 1/2 per test even for orthogonal registers.",
            "Guppy kernels measure every qubit at the end (release), the Pytket circuit measures only the ancilla, "
            "hence Measure = 2n+1 vs 1.",
        ],
    }

    rng = np.random.default_rng(seed)
    for n in count_sizes:
        pocket = list(rng.uniform(-math.pi, math.pi, n))
        ligand = list(rng.uniform(-math.pi, math.pi, n))
        single = build_single_test_kernel(pocket, ligand, tau, omega)
        rus = build_rus_kernel(pocket, ligand, tau, omega, max_iters=max_iters)
        circ = rebase_to_h2_gateset(build_pytket_swap_test_circuit(pocket, ligand, tau, omega))
        single_qir = single.to_qir("bitcode")
        rus_qir = rus.to_qir("bitcode")
        report["op_counts"].append({
            "n_sites": n,
            "guppy_single_test": single.op_counts(),
            "guppy_rus_static": rus.op_counts(),
            "pytket_single_shot": pytket_native_op_counts(circ),
            "qir_bytes_single_test": len(single_qir),
            "qir_bytes_rus": len(rus_qir),
            "qir_validation": qir_validation_status(),
            "qir_external_validation": validate_qir_externally(rus_qir),
        })

    wanted = set(systems) if systems else None
    for sysd in REAL_MOLECULE_SYSTEMS:
        if wanted and sysd["id"] not in wanted:
            continue
        # Per-system seed so shot noise is not correlated across systems.
        sys_seed = (seed + zlib.crc32(sysd["id"].encode())) % (2**31)
        target_coords, probe_coords = _system_coordinates(
            sysd["id"], sysd["n_atoms_proxy"], sysd["optimal_angle_deg"], sys_seed)
        elements = site_elements(sysd["id"]) or ["C"] * len(target_coords)
        target_phases = pocket_ligand_to_qubit_phases(
            MolecularGeometry(f"{sysd['id']}_target", elements, target_coords), n_qubits=n_sites)
        probe_phases = pocket_ligand_to_qubit_phases(
            MolecularGeometry(f"{sysd['id']}_probe", elements, probe_coords), n_qubits=n_sites)

        single = build_single_test_kernel(target_phases, probe_phases, tau, omega)
        single_sum = summarize_shots(single.emulate(shots=shots, seed=sys_seed))
        p0_exact = simulate_swap_test_statevector(target_phases, probe_phases, tau, omega)

        rus = build_rus_kernel(target_phases, probe_phases, tau, omega, max_iters=max_iters)
        rus_sum = summarize_shots(rus.emulate(shots=shots, seed=sys_seed + 1))
        sweep = []
        for k in range(max_iters):
            kicked = rus.ligand_phases_for_kick(k)
            sweep.append({
                "kick_index": k,
                "kick_deg": math.degrees(rus.kick_schedule[k][0]),
                "p0_exact": simulate_swap_test_statevector(target_phases, kicked, tau, omega),
                "shots_stopped_here": rus_sum.kick_index_hist.get(k, 0),
            })

        control = build_single_test_kernel(target_phases, target_phases, 0.0, omega)
        control_sum = summarize_shots(control.emulate(shots=shots, seed=sys_seed + 2))

        report["systems"].append({
            "id": sysd["id"],
            "name": sysd["name"],
            "seed": sys_seed,
            "n_atoms": int(len(target_coords)),
            "optimal_angle_deg": sysd["optimal_angle_deg"],
            "target_phases": [float(p) for p in target_phases],
            "probe_phases": [float(p) for p in probe_phases],
            "single_test": {
                "p0_exact": p0_exact,
                "p0_hat": single_sum.first_test_p0_hat,
                "p0_stderr": single_sum.first_test_p0_stderr,
                # Binomial sigma at the exact P(0), so an estimate of exactly 1.0 is not judged with sigma = 0.
                "within_2sigma": abs(single_sum.first_test_p0_hat - p0_exact)
                <= 2.0 * math.sqrt(max(p0_exact * (1.0 - p0_exact), 1e-6) / single_sum.n_shots) + 1e-9,
                "n_shots": single_sum.n_shots,
            },
            "rus_sweep": {"summary": rus_sum.as_dict(), "rows": sweep},
            "self_overlap_control": {
                "tau": 0.0,
                "p0_hat": control_sum.first_test_p0_hat,
                "n_shots": control_sum.n_shots,
            },
        })

    if output_json_path:
        with open(output_json_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    return report


def _main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the Q-Rotate Guppy RUS kernel on Selene.")
    parser.add_argument("--out", default=os.path.join("benchmarks", "guppy_rus_selene.json"))
    parser.add_argument("--shots", type=int, default=200)
    parser.add_argument("--max-iters", type=int, default=12)
    parser.add_argument("--n-sites", type=int, default=4)
    parser.add_argument("--systems", nargs="*", default=None)
    args = parser.parse_args(argv)
    report = run_selene_benchmark(
        args.out, n_sites=args.n_sites, shots=args.shots, max_iters=args.max_iters, systems=args.systems)
    for row in report["op_counts"]:
        print(f"n={row['n_sites']}: single {row['guppy_single_test']} | pytket {row['pytket_single_shot']} | "
              f"rus static {row['guppy_rus_static']} | QIR {row['qir_bytes_rus']} B")
    for s in report["systems"]:
        st, rs = s["single_test"], s["rus_sweep"]["summary"]
        print(f"{s['id']:<11} p0 exact {st['p0_exact']:.3f} hat {st['p0_hat']:.3f} | lock {rs['lock_rate']:.2f} "
              f"mean tests {rs['mean_iterations']:.2f} | control p0 {s['self_overlap_control']['p0_hat']:.3f}")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(_main())


__all__ = [
    "HAS_GUPPY",
    "RusKernel",
    "RusShotSummary",
    "build_rus_kernel",
    "build_single_test_kernel",
    "default_kick_schedule",
    "estimate_first_test_p0",
    "hugr_native_op_counts",
    "pytket_native_op_counts",
    "qir_validation_status",
    "run_selene_benchmark",
    "summarize_shots",
    "validate_qir_externally",
]
