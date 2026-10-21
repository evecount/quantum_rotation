"""Hardware-noise study for the Q-Rotate blind RUS pose search.

Every published robustness number (benchmarks/statistical_robustness.json)
comes from an ideal statevector plus binomial shot noise. This module puts a
depolarizing noise model on the *compiled* H2 circuit and re-runs the blind
pose search under it:

* the Pytket SWAP-test circuit is rebased to the H-series gate set
  (PhasedX, Rz, ZZPhase) and the noise is attached to the native gates the
  hardware would run, not to the abstract CX/CCX. One CSWAP per site compiles
  to 8 ZZPhase gates (2 from the CX pair, 6 from the Toffoli), so a 4-site
  circuit carries 32 two-qubit gates and an 8-site circuit 64;
* after every ZZPhase a two-qubit depolarizing error fires with probability
  p2, after every PhasedX a one-qubit depolarizing error with probability p1,
  and the ancilla readout flips with probability p_ro. Rz is a virtual frame
  change on H-series and carries no error. "Probability p of a uniformly
  random non-identity Pauli" is the convention used, which for a two-qubit
  gate equals its average gate infidelity (for one qubit the infidelity is
  2p/3);
* at 9 qubits (4 sites) the noisy circuit can be simulated exactly as a
  512 x 512 density matrix, and that is how the noisy P(0) ceiling at the
  true pose is computed and how the trajectory engine is validated. It is
  too slow for the search itself on this machine (3-7 s per circuit, and a
  sweep needs ~20,000 circuits), and impossible at 17 qubits (8 sites), so
  the RUS runs at both register sizes draw each of their 100 shots as one
  Pauli-trajectory sample: the error pattern is sampled gate by gate, the
  trajectory is simulated exactly, and the ancilla bit is drawn from its
  P(0) and then flipped with p_ro. That is a sample from the same channel
  the density matrix evaluates, with no approximation beyond the finite
  shots the protocol takes anyway. The trajectory engine exploits the
  circuit's structure: the ancilla is the only qubit shared between site
  pairs, so a trajectory is a short sum of product states and costs
  microseconds per gate at any register size. tests/test_noise_study.py
  checks it against a dense statevector on identical error patterns (to
  1e-15) and its mean against the density matrix.

Quantinuum's H2 product data sheet (v2.00, October 2024) specifies two-qubit
gate infidelity 1.3e-3 (min) / 1.5e-3 (typical) / 3e-3 (max), one-qubit
infidelity ~3e-5, and SPAM error 1.5e-3 typical; the published per-device
validation pages show 0.8e-3 to 1.1e-3 for two-qubit gates on H2-1/H2-2
(docs.quantinuum.com, hardware user guide, "Performance Validation"). The
sweep therefore brackets the spec: p2 in {0, 1e-3, 2e-3, 5e-3, 1e-2}.

`python -m src.qrotate.noise_study` writes benchmarks/noise_study.json.
"""

from __future__ import annotations

import json
import os
import string
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import numpy as np

try:
    from .hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases, has_180_degree_ambiguity, is_encoding_degenerate
    from .structures import load_active_sites, site_elements
    from .circuits import build_pytket_swap_test_circuit, rebase_to_h2_gateset, simulate_swap_test_statevector, HAS_PYTKET
    from .metrics import (
        REAL_MOLECULE_SYSTEMS, _system_coordinates, _wilson_interval, pose_error_deg,
        run_blind_rus_pose_recovery,
    )
except ImportError:  # pragma: no cover - script execution
    from src.qrotate.hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases, has_180_degree_ambiguity, is_encoding_degenerate
    from src.qrotate.structures import load_active_sites, site_elements
    from src.qrotate.circuits import build_pytket_swap_test_circuit, rebase_to_h2_gateset, simulate_swap_test_statevector, HAS_PYTKET
    from src.qrotate.metrics import (
        REAL_MOLECULE_SYSTEMS, _system_coordinates, _wilson_interval, pose_error_deg,
        run_blind_rus_pose_recovery,
    )

TAU, OMEGA = 0.25, (1.0, 0.5, 0.25)

P2_SWEEP = (0.0, 1e-3, 2e-3, 5e-3, 1e-2)
P_RO_DEFAULT = 2e-3
P1_RATIO = 0.1              # p1 = p2 / 10
LOCK_RATE_FLOOR = 0.80

H2_SPEC = {
    "source": "Quantinuum System Model H2 Product Data Sheet v2.00 (October 2024), docs.quantinuum.com",
    "two_qubit_gate_infidelity": {"min": 1.3e-3, "typical": 1.5e-3, "max": 3e-3},
    "one_qubit_gate_infidelity_typical": 3e-5,
    "spam_error": {"min": 1e-3, "typical": 1.5e-3, "max": 5e-3},
    "device_validation_two_qubit_2025": "0.8e-3 to 1.1e-3 (H2-1 / H2-2 performance-validation pages)",
}

_PAULI = [
    np.eye(2, dtype=complex),
    np.array([[0, 1], [1, 0]], dtype=complex),
    np.array([[0, -1j], [1j, 0]], dtype=complex),
    np.array([[1, 0], [0, -1]], dtype=complex),
]

# Density matrices beyond this many qubits are not attempted.
DENSITY_MATRIX_MAX_QUBITS = 11


# =====================================================================
# 1. The compiled gate stream
# =====================================================================

@dataclass
class Gate:
    kind: str                       # 'PhasedX', 'Rz', 'ZZPhase'
    qubits: tuple[int, ...]
    unitary: np.ndarray             # 2x2 or 4x4, pytket big-endian qubit order
    noise: str                      # 'none', '1q' or '2q'


@dataclass
class CompiledCircuit:
    n_sites: int
    n_qubits: int
    gates: list[Gate]
    ideal_p0: float

    @property
    def counts(self) -> dict:
        c: dict = {}
        for g in self.gates:
            c[g.kind] = c.get(g.kind, 0) + 1
        return c


_TEMPLATE_CACHE: dict = {}


def _symbolic_template(n_sites: int, tau: float, omega) -> tuple:
    """The rebased circuit with the 2n phases left symbolic, compiled once per
    register size. Rebasing costs 0.3-0.5 s; substituting numbers into the
    template costs ~20 ms and yields exactly the gates a numeric rebase gives
    (checked in tests)."""
    key = (n_sites, float(tau), tuple(float(w) for w in omega))
    if key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[key]
    from sympy import Symbol
    pocket = [Symbol(f"qrot_p{i}") for i in range(n_sites)]
    ligand = [Symbol(f"qrot_l{i}") for i in range(n_sites)]
    # build_pytket_swap_test_circuit divides the phases by pi for pytket's
    # half-turn convention; sympy symbols go through that arithmetic too.
    rebased = rebase_to_h2_gateset(build_pytket_swap_test_circuit(pocket, ligand, tau, omega))
    _TEMPLATE_CACHE[key] = (rebased, pocket, ligand)
    return _TEMPLATE_CACHE[key]


def compile_noisy_circuit(pocket_phases: Sequence[float], ligand_phases: Sequence[float],
                          tau: float = TAU, omega=OMEGA) -> CompiledCircuit:
    """Rebases the SWAP-test circuit to the H2 gate set and records every
    native gate with its unitary, so both simulators walk the same stream
    the hardware would execute. Measurement is left to the simulators."""
    if not HAS_PYTKET:
        raise RuntimeError("pytket is required for the noise study")
    from pytket.circuit import OpType

    n_sites = len(pocket_phases)
    template, sym_p, sym_l = _symbolic_template(n_sites, tau, omega)
    circ = template.copy()
    circ.symbol_substitution({**{s: float(v) for s, v in zip(sym_p, pocket_phases)},
                              **{s: float(v) for s, v in zip(sym_l, ligand_phases)}})
    gates = []
    for cmd in circ.get_commands():
        t = cmd.op.type
        if t == OpType.Measure:
            continue
        qubits = tuple(q.index[0] for q in cmd.qubits)
        if t == OpType.PhasedX:
            noise = "1q"
        elif t in (OpType.ZZPhase, OpType.ZZMax, OpType.TK2):
            noise = "2q"
        elif t == OpType.Rz:
            noise = "none"
        else:
            raise ValueError(f"unexpected gate {t.name} in the rebased circuit")
        gates.append(Gate(t.name, qubits, np.asarray(cmd.op.get_unitary(), dtype=complex), noise))
    compiled = CompiledCircuit(n_sites, circ.n_qubits, gates, 0.0)
    # The ideal P(0): dense statevector where it is cheap, otherwise the
    # structured engine with no errors (exact, microseconds per gate).
    if compiled.n_qubits <= DENSITY_MATRIX_MAX_QUBITS:
        compiled.ideal_p0 = simulate_swap_test_statevector(pocket_phases, ligand_phases, tau, omega)
    else:
        compiled.ideal_p0 = trajectory_p0(compiled, {})
    return compiled


def noise_locations(circuit: CompiledCircuit, p1: float, p2: float) -> list[tuple[int, float]]:
    """(gate index, error probability) for every noisy gate."""
    out = []
    for i, g in enumerate(circuit.gates):
        if g.noise == "1q" and p1 > 0:
            out.append((i, p1))
        elif g.noise == "2q" and p2 > 0:
            out.append((i, p2))
    return out


def apply_readout_flip(p0: float, p_ro: float) -> float:
    return p0 * (1.0 - p_ro) + (1.0 - p0) * p_ro


# =====================================================================
# 2. Exact density-matrix simulation (9 qubits)
# =====================================================================

class DensityMatrixSimulator:
    """rho as a dense 2^n x 2^n matrix (4 MB at 9 qubits).

    Every operation keeps the long contiguous axis innermost, because numpy
    is pathologically slow at transposing tensors whose inner stride is 2.
    U rho U^dag is done as two row operations: A = U rho, then U A^dag.
    Diagonal gates (Rz, ZZPhase) are elementwise masks and consecutive ones
    are merged. Depolarizing is applied through the identity
    I/2 (x) Tr_q rho = (sigma + X sigma X) / 2 with sigma = (rho + Z rho Z) / 2,
    which costs four elementwise passes instead of a partial trace.
    """

    def __init__(self, n_qubits: int):
        if n_qubits > DENSITY_MATRIX_MAX_QUBITS:
            raise ValueError(f"{n_qubits} qubits is too many for a dense density matrix")
        self.n = n_qubits
        self.dim = 1 << n_qubits
        self.rho = np.zeros((self.dim, self.dim), dtype=complex)
        self.rho[0, 0] = 1.0
        idx = np.arange(self.dim)
        # bits[q, i]: value of qubit q (qubit 0 = most significant) in index i
        self.bits = np.array([(idx >> (n_qubits - 1 - q)) & 1 for q in range(n_qubits)])
        self._pending_diag: Optional[np.ndarray] = None

    # -- unitaries --------------------------------------------------------
    def _left_1q(self, u: np.ndarray, q: int, m: np.ndarray) -> np.ndarray:
        s = m.reshape(1 << q, 2, -1)
        out = np.empty_like(s)
        out[:, 0] = u[0, 0] * s[:, 0] + u[0, 1] * s[:, 1]
        out[:, 1] = u[1, 0] * s[:, 0] + u[1, 1] * s[:, 1]
        return out.reshape(self.dim, self.dim)

    def _left_2q(self, u: np.ndarray, q1: int, q2: int, m: np.ndarray) -> np.ndarray:
        u4 = u.reshape(2, 2, 2, 2)
        if q1 > q2:
            q1, q2 = q2, q1
            u4 = u4.transpose(1, 0, 3, 2)
        s = m.reshape(1 << q1, 2, 1 << (q2 - q1 - 1), 2, -1)
        out = np.einsum("klij,xiyjz->xkylz", u4, s)
        return out.reshape(self.dim, self.dim)

    def diagonal_of(self, u: np.ndarray, qubits: Sequence[int]) -> Optional[np.ndarray]:
        """The gate as a length-2^n diagonal vector, or None if not diagonal."""
        if not np.allclose(u, np.diag(np.diag(u)), atol=1e-12):
            return None
        d = np.diag(u)
        if len(qubits) == 1:
            return d[self.bits[qubits[0]]]
        return d[2 * self.bits[qubits[0]] + self.bits[qubits[1]]]

    def apply_unitary(self, u: np.ndarray, qubits: Sequence[int]) -> None:
        d = self.diagonal_of(u, qubits)
        if d is not None:
            self._pending_diag = d if self._pending_diag is None else self._pending_diag * d
            return
        self.flush()
        if len(qubits) == 1:
            a = self._left_1q(u, qubits[0], self.rho)
            self.rho = self._left_1q(u, qubits[0], a.conj().T)
        else:
            a = self._left_2q(u, qubits[0], qubits[1], self.rho)
            self.rho = self._left_2q(u, qubits[0], qubits[1], a.conj().T)

    def flush(self) -> None:
        if self._pending_diag is not None:
            d = self._pending_diag
            self.rho = (self.rho * d[:, None]) * d.conj()[None, :]
            self._pending_diag = None

    # -- channels ---------------------------------------------------------
    def _fully_depolarize(self, q: int, m: np.ndarray) -> np.ndarray:
        s = 1.0 - 2.0 * self.bits[q]
        sigma = 0.5 * (m + (m * s[:, None]) * s[None, :])
        r = 1 << (self.n - 1 - q)
        flipped = sigma.reshape(1 << q, 2, r, 1 << q, 2, r)[:, ::-1, :, :, ::-1, :].reshape(self.dim, self.dim)
        return 0.5 * (sigma + flipped)

    def depolarize(self, qubits: Sequence[int], p: float) -> None:
        """With probability p a uniformly random non-identity Pauli on
        `qubits`: rho -> (1 - lam) rho + lam (I / 2^k) (x) Tr_Q rho, where
        lam = p 4^k / (4^k - 1)."""
        if p <= 0:
            return
        self.flush()
        k = len(qubits)
        lam = p * 4 ** k / (4 ** k - 1)
        mixed = self.rho
        for q in qubits:
            mixed = self._fully_depolarize(q, mixed)
        self.rho = (1.0 - lam) * self.rho + lam * mixed

    # -- readout ----------------------------------------------------------
    def prob_zero(self, qubit: int = 0) -> float:
        self.flush()
        diag = np.real(np.diagonal(self.rho))
        return float(np.sum(diag[self.bits[qubit] == 0]))

    def trace(self) -> float:
        self.flush()
        return float(np.real(np.trace(self.rho)))


def noisy_p0_density_matrix(circuit: CompiledCircuit, p1: float, p2: float, p_ro: float = 0.0) -> float:
    """Exact P(ancilla = 0) of the compiled circuit under the noise model."""
    sim = DensityMatrixSimulator(circuit.n_qubits)
    for g in circuit.gates:
        sim.apply_unitary(g.unitary, g.qubits)
        if g.noise == "1q":
            sim.depolarize(g.qubits, p1)
        elif g.noise == "2q":
            sim.depolarize(g.qubits, p2)
    return apply_readout_flip(sim.prob_zero(0), p_ro)


# =====================================================================
# 3. Structured Pauli-trajectory simulation (any register size)
# =====================================================================

class BranchState:
    """A pure state of the SWAP-test register written as a sum of branches,
    each branch a product of a 3-qubit block (ancilla + the site pair the
    ancilla is currently interacting with) and 2-qubit states for every
    other site pair.

    Every gate in the compiled circuit acts on one site pair, on the ancilla,
    or on the ancilla and one qubit of a single pair, so this form is closed
    under the gate stream and under Pauli errors. Moving the ancilla's
    attention to another pair splits each branch by the ancilla's basis
    value; without errors that leaves exactly two branches for the whole
    circuit, and each error can at most double the count.
    """

    def __init__(self, n_sites: int):
        self.s = n_sites
        self.active = 0
        block = np.zeros((2, 2, 2), dtype=complex)
        block[0, 0, 0] = 1.0
        pairs = np.zeros((n_sites, 2, 2), dtype=complex)
        pairs[:, 0, 0] = 1.0
        self.branches: list[tuple[np.ndarray, np.ndarray]] = [(block, pairs)]

    def _locate(self, q: int) -> tuple[int, int]:
        """(site, member) for a register qubit; member 0 = pocket, 1 = ligand."""
        if q == 0:
            raise ValueError("ancilla has no site")
        return (q - 1) % self.s, (q - 1) // self.s

    def apply_1q(self, u: np.ndarray, q: int) -> None:
        if q == 0:
            self.branches = [((u @ b.reshape(2, 4)).reshape(2, 2, 2), p) for b, p in self.branches]
            return
        site, member = self._locate(q)
        if site == self.active:
            if member == 0:
                self.branches = [(np.einsum("ab,cbd->cad", u, b), p) for b, p in self.branches]
            else:
                self.branches = [(b @ u.T, p) for b, p in self.branches]
        else:
            new = []
            for b, p in self.branches:
                p = p.copy()
                p[site] = u @ p[site] if member == 0 else p[site] @ u.T
                new.append((b, p))
            self.branches = new

    def switch(self, site: int) -> None:
        if site == self.active:
            return
        new = []
        for b, p in self.branches:
            for c in (0, 1):
                v = b[c]
                w = float(np.linalg.norm(v))
                if w < 1e-14:
                    continue
                p2 = p.copy()
                p2[self.active] = v / w
                b2 = np.zeros((2, 2, 2), dtype=complex)
                b2[c] = w * p[site]
                new.append((b2, p2))
        self.branches = new
        self.active = site

    def apply_2q(self, u: np.ndarray, q1: int, q2: int) -> None:
        u4 = u.reshape(2, 2, 2, 2)
        if q1 == 0 or q2 == 0:
            other = q2 if q1 == 0 else q1
            site, member = self._locate(other)
            self.switch(site)
            axes = (0, 1 + member) if q1 == 0 else (1 + member, 0)
            self.branches = [(self._apply_block(u4, b, axes), p) for b, p in self.branches]
            return
        s1, m1 = self._locate(q1)
        s2, m2 = self._locate(q2)
        if s1 != s2:
            raise ValueError(f"two-qubit gate across sites {s1} and {s2} is outside the SWAP-test structure")
        if s1 == self.active:
            self.branches = [(self._apply_block(u4, b, (1 + m1, 1 + m2)), p) for b, p in self.branches]
        else:
            new = []
            for b, p in self.branches:
                p = p.copy()
                pair = p[s1]
                if (m1, m2) == (1, 0):
                    pair = pair.T
                pair = (u @ pair.reshape(4)).reshape(2, 2)
                p[s1] = pair.T if (m1, m2) == (1, 0) else pair
                new.append((b, p))
            self.branches = new

    @staticmethod
    def _apply_block(u4: np.ndarray, block: np.ndarray, axes: tuple[int, int]) -> np.ndarray:
        t = np.tensordot(u4, block, axes=([2, 3], list(axes)))
        return np.moveaxis(t, [0, 1], list(axes))

    def _gram(self, blocks: list[np.ndarray]) -> float:
        n = len(self.branches)
        total = 0.0
        pairs = [p for _, p in self.branches]
        for i in range(n):
            for j in range(n):
                g = np.vdot(blocks[i].ravel(), blocks[j].ravel())
                for k in range(self.s):
                    if k == self.active:
                        continue
                    g *= np.vdot(pairs[i][k].ravel(), pairs[j][k].ravel())
                total += g
        return float(np.real(total))

    def norm_squared(self) -> float:
        return self._gram([b for b, _ in self.branches])

    def prob_zero(self) -> float:
        return self._gram([b[0:1] for b, _ in self.branches])


def trajectory_p0(circuit: CompiledCircuit, errors: dict[int, int]) -> float:
    """P(ancilla = 0) for one trajectory with the given Pauli errors:
    {gate index: Pauli code}, code in 1..3 for a one-qubit error, 1..15 for
    a two-qubit error (code = 4 * pauli_a + pauli_b)."""
    st = BranchState(circuit.n_sites)
    for i, g in enumerate(circuit.gates):
        if len(g.qubits) == 1:
            st.apply_1q(g.unitary, g.qubits[0])
        else:
            st.apply_2q(g.unitary, g.qubits[0], g.qubits[1])
        code = errors.get(i)
        if code:
            if len(g.qubits) == 1:
                st.apply_1q(_PAULI[code], g.qubits[0])
            else:
                a, b = divmod(code, 4)
                if a:
                    st.apply_1q(_PAULI[a], g.qubits[0])
                if b:
                    st.apply_1q(_PAULI[b], g.qubits[1])
    return st.prob_zero()


def sample_error_pattern(locations: Sequence[tuple[int, float]], circuit: CompiledCircuit,
                         rng: np.random.Generator) -> dict[int, int]:
    """Independently fires each noisy gate with its probability and draws a
    uniformly random non-identity Pauli for each that fired."""
    if not locations:
        return {}
    probs = np.fromiter((p for _, p in locations), dtype=float, count=len(locations))
    fired = np.flatnonzero(rng.random(len(locations)) < probs)
    errors = {}
    for j in fired:
        idx = locations[j][0]
        n_paulis = 3 if len(circuit.gates[idx].qubits) == 1 else 15
        errors[idx] = int(rng.integers(1, n_paulis + 1))
    return errors


def dense_trajectory_p0(circuit: CompiledCircuit, errors: dict[int, int]) -> float:
    """Reference: the same trajectory on a dense statevector. Slow beyond
    ~11 qubits; exists to validate `trajectory_p0` in tests."""
    dim = 1 << circuit.n_qubits

    def apply1(st, u, q):
        s = st.reshape(1 << q, 2, -1)
        out = np.empty_like(s)
        out[:, 0] = u[0, 0] * s[:, 0] + u[0, 1] * s[:, 1]
        out[:, 1] = u[1, 0] * s[:, 0] + u[1, 1] * s[:, 1]
        return out.reshape(-1)

    def apply2(st, u, q1, q2):
        u4 = u.reshape(2, 2, 2, 2)
        if q1 > q2:
            q1, q2 = q2, q1
            u4 = u4.transpose(1, 0, 3, 2)
        s = st.reshape(1 << q1, 2, 1 << (q2 - q1 - 1), 2, -1)
        return np.einsum("klij,xiyjz->xkylz", u4, s).reshape(-1)

    st = np.zeros(dim, dtype=complex)
    st[0] = 1.0
    for i, g in enumerate(circuit.gates):
        st = apply1(st, g.unitary, g.qubits[0]) if len(g.qubits) == 1 else apply2(st, g.unitary, *g.qubits)
        code = errors.get(i)
        if code:
            if len(g.qubits) == 1:
                st = apply1(st, _PAULI[code], g.qubits[0])
            else:
                a, b = divmod(code, 4)
                if a:
                    st = apply1(st, _PAULI[a], g.qubits[0])
                if b:
                    st = apply1(st, _PAULI[b], g.qubits[1])
    return float(np.sum(np.abs(st.reshape(2, -1)[0]) ** 2))


def noisy_p0_trajectories(circuit: CompiledCircuit, p1: float, p2: float, p_ro: float = 0.0,
                          n_trajectories: int = 1000, seed: Optional[int] = None) -> float:
    """Monte-Carlo estimate of the noisy P(0) by averaging trajectories."""
    rng = np.random.default_rng(seed)
    locs = noise_locations(circuit, p1, p2)
    total = 0.0
    for _ in range(n_trajectories):
        errors = sample_error_pattern(locs, circuit, rng)
        total += circuit.ideal_p0 if not errors else trajectory_p0(circuit, errors)
    return apply_readout_flip(total / n_trajectories, p_ro)


# =====================================================================
# 4. Noisy shot samplers for the RUS protocol
# =====================================================================

def _shot_result(counts_0: int, n_shots: int) -> dict:
    """Same fields and formulas as `circuits.simulate_shot_sampling`."""
    p = counts_0 / n_shots
    std_err = float(np.sqrt(max(1e-9, p * (1.0 - p) / n_shots)))
    return {
        "mode": "noisy_shots", "n_shots": n_shots, "counts_0": counts_0, "counts_1": n_shots - counts_0,
        "empirical_prob": p, "std_err": std_err,
        "ci_95_low": float(np.clip(p - 1.96 * std_err, 0, 1)), "ci_95_high": float(np.clip(p + 1.96 * std_err, 0, 1)),
        "is_locked": bool(p >= 0.90),
    }


def make_noisy_sampler(p1: float, p2: float, p_ro: float, method: str = "auto",
                       tau: float = TAU, omega=OMEGA) -> Callable:
    """A `sampler` for `metrics.run_blind_rus_pose_recovery`: given target and
    probe phases, shots and a seed, returns (ideal P(0), noisy shot result).

    method 'density_matrix': exact noisy P(0), then binomial shots (exact
    but seconds per circuit at 9 qubits on this machine).
    method 'trajectories' (the 'auto' default): one Pauli-trajectory sample
    per shot, at any register size.
    """
    def sampler(target_phases, probe_phases, shots: int, seed: int):
        circuit = compile_noisy_circuit(target_phases, probe_phases, tau, omega)
        rng = np.random.default_rng(seed)
        use_dm = method == "density_matrix"
        if p1 == 0 and p2 == 0:
            p0 = apply_readout_flip(circuit.ideal_p0, p_ro)
            counts_0 = int(rng.binomial(shots, p0))
        elif use_dm:
            p0 = noisy_p0_density_matrix(circuit, p1, p2, p_ro)
            counts_0 = int(rng.binomial(shots, p0))
        else:
            locs = noise_locations(circuit, p1, p2)
            counts_0 = 0
            for _ in range(shots):
                errors = sample_error_pattern(locs, circuit, rng)
                p0 = circuit.ideal_p0 if not errors else trajectory_p0(circuit, errors)
                counts_0 += int(rng.random() < apply_readout_flip(p0, p_ro))
        return circuit.ideal_p0, _shot_result(counts_0, shots)

    sampler.p1, sampler.p2, sampler.p_ro, sampler.method = p1, p2, p_ro, method  # type: ignore[attr-defined]
    return sampler


# =====================================================================
# 5. The sweep
# =====================================================================

def _system_task(args: tuple) -> dict:
    """One (register size, p2, system) cell: `n_trials` blind RUS runs under
    noise. Top-level so ProcessPoolExecutor can pickle it."""
    system_id, n_sites, p2, p_ro, n_trials, method = args
    system = next(s for s in REAL_MOLECULE_SYSTEMS if s["id"] == system_id)
    p1 = p2 * P1_RATIO
    base_seed = zlib.crc32(system_id.encode()) % (2 ** 31)
    target_coords, probe_coords = _system_coordinates(system_id, system["n_atoms_proxy"], system["optimal_angle_deg"], base_seed)
    elements = site_elements(system_id) or ["C"] * len(probe_coords)
    target_geom = MolecularGeometry("t", elements, target_coords)
    target_phases = pocket_ligand_to_qubit_phases(target_geom, n_qubits=n_sites)
    ambiguous = has_180_degree_ambiguity(target_geom, n_qubits=n_sites)
    degenerate = is_encoding_degenerate(target_geom, n_qubits=n_sites)
    sampler = make_noisy_sampler(p1, p2, p_ro, method=method)

    # The ceiling: noisy P(0) with the probe exactly at the deposited pose.
    aligned = pocket_ligand_to_qubit_phases(MolecularGeometry("a", elements, target_coords), n_qubits=n_sites)
    circuit = compile_noisy_circuit(target_phases, aligned)
    if p2 == 0 and p1 == 0:
        ceiling = apply_readout_flip(circuit.ideal_p0, p_ro)
        ceiling_method = "ideal"
    elif circuit.n_qubits <= DENSITY_MATRIX_MAX_QUBITS:
        ceiling = noisy_p0_density_matrix(circuit, p1, p2, p_ro)
        ceiling_method = "density_matrix"
    else:
        ceiling = noisy_p0_trajectories(circuit, p1, p2, p_ro, n_trajectories=1000, seed=base_seed)
        ceiling_method = "trajectories_1000"

    t0 = time.perf_counter()
    locks, iters_locked, evals, errs = [], [], [], []
    for trial in range(n_trials):
        seed = (base_seed * 1_000_003 + trial) % (2 ** 31)
        r = run_blind_rus_pose_recovery(
            target_phases, probe_coords, n_qubits=n_sites, tau=TAU, omega=OMEGA,
            max_retries=15, shots=100, seed=seed, elements=elements, sampler=sampler)
        locks.append(r.locked)
        evals.append(r.circuit_evaluations)
        if r.locked:
            iters_locked.append(r.iterations)
            errs.append(pose_error_deg(r.final_angle_deg, system["optimal_angle_deg"], ambiguous))
    n_locked = int(sum(locks))
    lo, hi = _wilson_interval(n_locked, n_trials)
    return {
        "system_id": system_id, "system_name": system["name"], "n_sites": n_sites, "n_qubits": circuit.n_qubits,
        "p2": p2, "p1": p1, "p_ro": p_ro,
        "noise_method": "ideal_plus_readout_flip" if p2 == 0 else (
            "density_matrix" if method == "density_matrix" else "one_trajectory_per_shot"),
        "gate_counts": circuit.counts,
        "encoding_degenerate": bool(degenerate), "ambiguous_180_deg": bool(ambiguous),
        "ideal_p0_at_true_pose": round(circuit.ideal_p0, 4),
        "noisy_p0_at_true_pose": round(ceiling, 4), "noisy_p0_method": ceiling_method,
        "n_trials": n_trials, "n_locked": n_locked, "lock_rate": round(n_locked / n_trials, 4),
        "lock_rate_95ci": [round(lo, 4), round(hi, 4)],
        "iterations_mean_locked": round(float(np.mean(iters_locked)), 2) if iters_locked else None,
        "circuit_evaluations_mean": round(float(np.mean(evals)), 2),
        "pose_error_deg_mean_locked": round(float(np.mean(errs)), 2) if errs else None,
        "wall_clock_sec": round(time.perf_counter() - t0, 1),
    }


def lock_threshold(p2_rows: list[dict], floor: float = LOCK_RATE_FLOOR) -> dict:
    """First swept p2 whose overall lock rate is below `floor`, and the
    linearly interpolated crossing between it and the previous point."""
    ordered = sorted(p2_rows, key=lambda r: r["p2"])
    for prev, cur in zip([None] + ordered[:-1], ordered):
        if cur["overall_lock_rate"] < floor:
            crossing = None
            if prev is not None and prev["overall_lock_rate"] >= floor:
                f = (prev["overall_lock_rate"] - floor) / (prev["overall_lock_rate"] - cur["overall_lock_rate"])
                crossing = prev["p2"] + f * (cur["p2"] - prev["p2"])
            return {"first_p2_below_floor": cur["p2"], "interpolated_crossing_p2": crossing,
                    "floor": floor, "last_p2_at_or_above_floor": prev["p2"] if prev else None}
    return {"first_p2_below_floor": None, "interpolated_crossing_p2": None, "floor": floor,
            "last_p2_at_or_above_floor": ordered[-1]["p2"] if ordered else None}


def run_noise_sweep(
    p2_values: Sequence[float] = P2_SWEEP,
    p_ro: float = P_RO_DEFAULT,
    trials_by_sites: Optional[dict] = None,
    output_json_path: Optional[str] = "benchmarks/noise_study.json",
    n_workers: Optional[int] = None,
    method: str = "auto",
    verbose: bool = True,
) -> dict:
    trials_by_sites = trials_by_sites or {4: 30, 8: 10}
    tasks = [(s["id"], n_sites, float(p2), p_ro, n_trials, method)
             for n_sites, n_trials in trials_by_sites.items()
             for p2 in p2_values
             for s in REAL_MOLECULE_SYSTEMS]
    print("=" * 80)
    print(f"Q-ROTATE NOISE STUDY: depolarizing p2 in {list(p2_values)}, p1 = p2/10, p_ro = {p_ro}")
    print(f"{len(tasks)} cells, {n_workers or os.cpu_count()} workers")
    print("=" * 80)
    t0 = time.perf_counter()
    if (n_workers or os.cpu_count() or 1) > 1:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            cells = list(pool.map(_system_task, tasks))
    else:
        cells = [_system_task(t) for t in tasks]

    by_size = {}
    for n_sites in trials_by_sites:
        rows = []
        for p2 in p2_values:
            sub = [c for c in cells if c["n_sites"] == n_sites and c["p2"] == float(p2)]
            usable = [c for c in sub if not c["encoding_degenerate"]]
            n_locked = sum(c["n_locked"] for c in usable)
            n_trials = sum(c["n_trials"] for c in usable)
            lo, hi = _wilson_interval(n_locked, n_trials)
            all_iters = [c["iterations_mean_locked"] * c["n_locked"] for c in usable if c["n_locked"]]
            rows.append({
                "p2": float(p2), "p1": float(p2) * P1_RATIO, "p_ro": p_ro,
                "n_trials": n_trials, "n_locked": n_locked,
                "overall_lock_rate": round(n_locked / n_trials, 4) if n_trials else None,
                "overall_lock_rate_95ci": [round(lo, 4), round(hi, 4)],
                "iterations_mean_locked": round(sum(all_iters) / n_locked, 2) if n_locked else None,
                "circuit_evaluations_mean": round(float(np.mean([c["circuit_evaluations_mean"] for c in usable])), 2),
                "noisy_p0_at_true_pose_mean": round(float(np.mean([c["noisy_p0_at_true_pose"] for c in usable])), 4),
                "per_system": sub,
            })
            if verbose:
                r = rows[-1]
                print(f"[{2 * n_sites + 1:2d} qubits] p2={p2:<7.4g} lock {n_locked:3d}/{n_trials} = {r['overall_lock_rate']*100:5.1f}% "
                      f"(95% CI {lo*100:.1f}-{hi*100:.1f}) | iters {r['iterations_mean_locked']} | "
                      f"P0 ceiling {r['noisy_p0_at_true_pose_mean']:.3f}")
                for c in sub:
                    print(f"      {c['system_id']:10s} {c['n_locked']:3d}/{c['n_trials']} ceiling {c['noisy_p0_at_true_pose']:.3f} "
                          f"err {c['pose_error_deg_mean_locked']} [{c['noise_method']}, {c['wall_clock_sec']}s]")
        by_size[str(n_sites)] = {
            "n_sites": n_sites, "n_qubits": 2 * n_sites + 1,
            "n_trials_per_system": trials_by_sites[n_sites],
            "gate_counts_per_circuit": rows[0]["per_system"][0]["gate_counts"],
            "sweep": rows,
            "lock_threshold": lock_threshold(rows),
        }
        if verbose:
            print(f"   -> {2 * n_sites + 1}-qubit threshold: {by_size[str(n_sites)]['lock_threshold']}")

    payload = {
        "noise_model": {
            "two_qubit_depolarizing_after_each_ZZPhase": "p2",
            "one_qubit_depolarizing_after_each_PhasedX": "p1 = p2 / 10",
            "readout_flip_on_ancilla": p_ro,
            "rz_is_virtual_and_noiseless": True,
            "pauli_convention": ("with probability p a uniformly random non-identity Pauli is applied; "
                                 "for a two-qubit gate p equals the average gate infidelity, for a one-qubit gate "
                                 "the infidelity is 2p/3"),
            "simulation": {
                "rus_runs": "one Pauli-trajectory sample per shot at both register sizes (structured branch "
                            "simulator, validated against a dense statevector per error pattern and against "
                            "the exact density matrix in the mean)",
                "noisy_p0_at_true_pose": "exact 512x512 density matrix at 9 qubits; 1000-trajectory mean at 17 qubits",
            },
            "shots_per_circuit": 100, "max_rus_iterations": 15,
            "lock_rule": "lower one-sided 95% bound on the measured P(0) >= 0.90",
        },
        "h2_spec": H2_SPEC,
        "p2_sweep": list(map(float, p2_values)),
        "lock_rate_floor": LOCK_RATE_FLOOR,
        "by_register_size": by_size,
        "total_wall_clock_sec": round(time.perf_counter() - t0, 1),
        "generated_by": "src/qrotate/noise_study.py::run_noise_sweep",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\n[Saved noise study to {output_json_path}]")
    return payload


if __name__ == "__main__":
    run_noise_sweep()
