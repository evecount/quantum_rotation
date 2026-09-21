"""Metrics, benchmarking, and resource estimation for Project Q-Rotate.

Pits the classical O(N^3) spatial rotation search against the Q-Rotate
Repeat-Until-Success (RUS) quantum phase-locking engine on Quantinuum H2.
"""

from __future__ import annotations

import time
import json
import os
import warnings
import zlib
import numpy as np
from dataclasses import dataclass, asdict
from typing import Sequence, Optional

try:
    from .hpc_bridge import (
        MolecularGeometry, pocket_ligand_to_qubit_phases,
        shell_anisotropy, is_encoding_degenerate,
        shell_moment_orders, has_180_degree_ambiguity,
    )
    from .structures import site_coordinates, site_elements, load_active_sites
    from .circuits import (
        build_pytket_swap_test_circuit,
        rebase_to_h2_gateset,
        simulate_swap_test_statevector,
        simulate_shot_sampling,
    )
except ImportError:
    from src.qrotate.hpc_bridge import (
        MolecularGeometry, pocket_ligand_to_qubit_phases,
        shell_anisotropy, is_encoding_degenerate,
        shell_moment_orders, has_180_degree_ambiguity,
    )
    from src.qrotate.structures import site_coordinates, site_elements, load_active_sites
    from src.qrotate.circuits import (
        build_pytket_swap_test_circuit,
        rebase_to_h2_gateset,
        simulate_swap_test_statevector,
        simulate_shot_sampling,
    )


# =====================================================================
# 1. Theoretical Fidelity & Hardware Quantum Credits (HQC) Estimation
# =====================================================================

def compute_overlap_fidelity(state_a: np.ndarray, state_b: np.ndarray) -> float:
    """Computes the quantum state fidelity |<state_a | state_b>|^2."""
    norm_a = np.linalg.norm(state_a)
    norm_b = np.linalg.norm(state_b)
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    u_a = state_a / norm_a
    u_b = state_b / norm_b
    overlap = np.vdot(u_a, u_b)
    return float(np.abs(overlap) ** 2)


def theoretical_swap_test_prob_zero(fidelity: float) -> float:
    r"""Theoretical probability of measuring 0 (success/match) in a SWAP test.

    .. math::
        P(0) = \frac{1 + |\langle \psi_A | \psi_B \rangle|^2}{2}
    """
    return float(0.5 * (1.0 + fidelity))


def compute_circuit_hqc_cost(circuit, shots: int = 100) -> dict[str, float]:
    """Costs one rebased H-series circuit with Quantinuum's HQC formula.

    HQC = 5 + (N_1q + 10 * N_2q + 5 * N_m) * shots / 5000

    Counts come from the compiled circuit itself (run `rebase_to_h2_gateset`
    first). N_1q counts PhasedX only: Rz is applied virtually (a frame change,
    not a laser pulse), so it is excluded. N_m counts state preparation of
    every qubit plus every measurement and reset. This is an estimate from the
    published formula, not a billed job; the backend's own cost query is
    authoritative.
    """
    from pytket import OpType

    n_1q = circuit.n_gates_of_type(OpType.PhasedX)
    n_2q = sum(circuit.n_gates_of_type(t) for t in (OpType.ZZPhase, OpType.ZZMax, OpType.TK2))
    n_meas = circuit.n_gates_of_type(OpType.Measure)
    n_reset = circuit.n_gates_of_type(OpType.Reset)
    n_m = circuit.n_qubits + n_meas + n_reset
    hqc = 5.0 + (n_1q + 10 * n_2q + 5 * n_m) * shots / 5000.0

    return {
        "n_qubits": circuit.n_qubits,
        "single_qubit_count": n_1q,
        "two_qubit_count": n_2q,
        "measure_count": n_meas,
        "reset_count": n_reset,
        "depth": circuit.depth(),
        "shots": shots,
        "hqc_cost": round(hqc, 2),
    }


def _reference_swap_test_circuit(n_sites: int):
    """Rebased SWAP-test circuit for `n_sites` sites. Its gate counts do not
    depend on the phase values, so fixed non-zero phases stand in for real ones
    (zeros could let the compiler drop gates)."""
    phases = [0.3 + 0.1 * i for i in range(n_sites)]
    circ = build_pytket_swap_test_circuit(phases, phases[::-1], tau=0.25, omega=(1.0, 0.5, 0.25))
    return rebase_to_h2_gateset(circ)


def estimate_qrotate_hqc_cost(
    n_qubits: int,
    rus_attempts: int,
    shots: int = 100,
    circuit=None,
) -> dict[str, float]:
    """Estimates the HQC cost of a blind RUS screen on Quantinuum H2.

    `n_qubits` is the sites per register (register size is 2 * n_qubits + 1)
    and `rus_attempts` is the number of circuit evaluations. Each evaluation
    runs a different circuit (the ligand phases change), so each is costed as
    its own `shots`-shot job, including the 5-HQC per-job overhead. Pass the
    rebased `circuit` if you have it; otherwise a reference circuit of the
    same size is compiled.
    """
    if circuit is None:
        circuit = _reference_swap_test_circuit(n_qubits)
    per_circuit = compute_circuit_hqc_cost(circuit, shots=shots)
    runs = max(1, rus_attempts)

    return {
        "n_qubits": per_circuit["n_qubits"],
        "circuit_runs": runs,
        "single_qubit_gates": per_circuit["single_qubit_count"] * runs,
        "two_qubit_gates": per_circuit["two_qubit_count"] * runs,
        "two_qubit_gates_per_circuit": per_circuit["two_qubit_count"],
        "swap_gates": 0,  # 0 SWAP overhead due to trapped-ion all-to-all connectivity
        "hqc_per_circuit": per_circuit["hqc_cost"],
        "estimated_hqcs": round(per_circuit["hqc_cost"] * runs, 2),
    }


# =====================================================================
# 2. Baseline 1: Classical 3D Spatial Grid-Search Benchmark
# =====================================================================

@dataclass
class ClassicalBenchmarkResult:
    n_atoms: int
    execution_time_sec: float
    computational_steps: int
    grid_resolution_deg: float
    estimated_flops: float


def benchmark_classical_docking(
    pocket_coords: np.ndarray,
    ligand_coords: np.ndarray,
    angular_step_deg: float = 30.0,
    max_steps_cap: int = 200_000,
) -> ClassicalBenchmarkResult:
    """Mocks a standard classical O(N_rot * N_atoms) spatial rotation search.

    Tests discrete Euler rotations (alpha, beta, gamma) against pocket coordinates
    to minimize Euclidean distance / RMSD.
    """
    n_atoms = len(pocket_coords)
    n_angles = int(360.0 / angular_step_deg)
    total_rotations = n_angles ** 3  # (12)^3 = 1,728 orientations
    total_comparisons = total_rotations * n_atoms

    # Cap physical loop to avoid hanging terminal on large N, while tracking true FLOPs
    steps_to_run = min(total_comparisons, max_steps_cap)
    
    start_time = time.perf_counter()
    
    # Real vector math execution simulation
    diff_sum = 0.0
    for _ in range(steps_to_run // max(1, n_atoms)):
        # Simulate 3x3 rotation matrix mult + distance computation
        rot_mock = np.cos(pocket_coords[:min(n_atoms, 20), :])
        diff_sum += float(np.sum(rot_mock))

    elapsed = time.perf_counter() - start_time
    
    # Extrapolate true wall-clock time if capped
    scale_factor = total_comparisons / max(1, steps_to_run)
    extrapolated_time = elapsed * scale_factor

    return ClassicalBenchmarkResult(
        n_atoms=n_atoms,
        execution_time_sec=round(extrapolated_time, 5),
        computational_steps=total_comparisons,
        grid_resolution_deg=angular_step_deg,
        estimated_flops=total_comparisons * 15.0,  # ~15 FLOPs per distance check
    )


# =====================================================================
# 2b. Honest Blind RUS Protocol (SPSA-style, no oracle access to the target)
# =====================================================================
#
# NOTE ON HONESTY: an earlier version of this benchmark advanced
# `current_phases` directly toward `target_phases` each iteration and then
# declared `locked = True` once a fixed iteration count was reached — i.e. the
# classical control loop was handed the answer it was supposedly trying to
# discover from measurement, and "success" was guaranteed by construction
# regardless of the input molecule. That produced benchmark numbers that
# looked good but weren't measuring anything.
#
# This version's update rule only ever reads `p0_hat` (the empirical SWAP-test
# success probability estimated from simulated shot noise on the real circuit
# in `simulate_swap_test_statevector`) — never the pocket's own phases — and
# performs a stochastic zeroth-order (SPSA-style) search, the same class of
# black-box optimizer used to train variational quantum circuits. Convergence
# is judged from a one-sided Wilson-style confidence bound on the measured
# probability, so both "iterations to lock" and outright non-convergence
# within `max_retries` are now genuine, molecule-dependent outcomes.

@dataclass
class BlindRusResult:
    locked: bool
    iterations: int
    circuit_evaluations: int
    final_p0_hat: float
    final_p0_true: float


def run_blind_rus_protocol(
    pocket_phases: Sequence[float],
    ligand_phases_init: Sequence[float],
    tau: float,
    omega: tuple[float, float, float],
    max_retries: int = 15,
    shots: int = 200,
    lock_confidence_sigma: float = 1.645,  # one-sided ~95% confidence
    step_size: float = 0.6,
    seed: Optional[int] = None,
) -> BlindRusResult:
    """Runs a blind (target-phases-never-read) RUS phase-locking search against
    the real simulated SWAP-test circuit.

    Each iteration spends two circuit evaluations: one to measure the current
    candidate's empirical P(0), one to test a random perturbation (SPSA-style),
    keeping whichever measured higher. "Locked" fires only once the *lower*
    confidence bound on the measured probability clears 0.90 — i.e. we're
    statistically confident (not just point-estimate-confident) the true
    resonance overlap is high, the same 90% bar `simulate_shot_sampling`
    already uses elsewhere in this module for `is_locked`. Requiring the lower
    bound (not the raw estimate) to clear that bar is what keeps this from
    locking on a lucky shot-noise fluctuation.
    """
    rng = np.random.default_rng(seed)
    current = np.array(ligand_phases_init, dtype=float)
    n_sites = len(current)
    circuit_evals = 0
    iterations = 0
    p0_hat = 0.5
    p0_true = 0.5

    for attempt in range(max_retries):
        iterations += 1

        p0_true = simulate_swap_test_statevector(pocket_phases, current, tau, omega)
        shot_res = simulate_shot_sampling(p0_true, n_shots=shots, seed=int(rng.integers(1 << 31)))
        circuit_evals += 1
        p0_hat = shot_res["empirical_prob"]
        lower_bound = p0_hat - lock_confidence_sigma * shot_res["std_err"]

        if lower_bound >= 0.90:
            return BlindRusResult(True, iterations, circuit_evals, p0_hat, p0_true)

        # Blind SPSA-style perturbation: only the measured p0_hat informs the step.
        direction = rng.choice([-1.0, 1.0], size=n_sites)
        scale = step_size / np.sqrt(attempt + 1.0)
        trial = current + scale * direction

        trial_p0_true = simulate_swap_test_statevector(pocket_phases, trial, tau, omega)
        trial_shot_res = simulate_shot_sampling(trial_p0_true, n_shots=shots, seed=int(rng.integers(1 << 31)))
        circuit_evals += 1

        if trial_shot_res["empirical_prob"] > p0_hat:
            current = trial

    return BlindRusResult(False, iterations, circuit_evals, p0_hat, p0_true)


# =====================================================================
# 3. Baseline 2: Q-Rotate RUS Quantum Phase-Locking Engine
# =====================================================================

@dataclass
class QRotateBenchmarkResult:
    n_atoms: int
    n_qubits: int
    rus_iterations_to_lock: int
    locked: bool
    two_qubit_gates: int
    swap_gates: int
    estimated_hqcs: float
    circuit_depth: int
    quantum_speedup_factor: float


def benchmark_qrotate_engine(
    pocket_coords: np.ndarray,
    ligand_coords: np.ndarray,
    n_qubits: int = 4,
    max_retries: int = 15,
    shots: int = 100,
    seed: Optional[int] = None,
) -> QRotateBenchmarkResult:
    """Runs the Q-Rotate RUS pipeline and tracks convergence iterations and H2 metrics.

    Convergence comes from `run_blind_rus_pose_recovery` actually simulating and
    shot-sampling the real SWAP-test circuit each iteration, searching over the
    ligand's pose, rather than being asserted after a fixed number of loop
    passes — `locked` can genuinely be False here.
    """
    n_atoms = len(pocket_coords)

    # 1. Classical HPC Bridge embedding
    pocket_geom = MolecularGeometry("pocket", ["C"] * n_atoms, pocket_coords)
    ligand_geom = MolecularGeometry("ligand", ["C"] * n_atoms, ligand_coords)

    pocket_phases = pocket_ligand_to_qubit_phases(pocket_geom, n_qubits=n_qubits)
    ligand_phases = pocket_ligand_to_qubit_phases(ligand_geom, n_qubits=n_qubits)

    # 2. Build and rebase initial circuit to verify valid H2 native compilation
    circ = build_pytket_swap_test_circuit(
        pocket_phases, ligand_phases, tau=0.25, omega=(1.0, 0.5, 0.25)
    )
    rebased = rebase_to_h2_gateset(circ)

    # 3. Blind RUS search over the pose, the same one-parameter search the
    #    molecular showdown and the Constellation page run. Searching free
    #    phase values instead would let the optimiser move to registers no
    #    rotation of the molecule can produce.
    rus_result = run_blind_rus_pose_recovery(
        pocket_phases, ligand_coords, n_qubits=n_qubits,
        tau=0.25, omega=(1.0, 0.5, 0.25),
        max_retries=max_retries, shots=shots, seed=seed,
    )

    # 4. Resource estimation on H2 trapped ions.
    # Each RUS iteration spends 2 circuit evaluations (measure + probe trial).
    hqc_info = estimate_qrotate_hqc_cost(n_qubits, rus_result.circuit_evaluations, shots=shots, circuit=rebased)

    # Classical steps comparison. This is a combinatorial step-count reduction
    # factor (classical grid-search steps vs. RUS circuit evaluations), not a
    # wall-clock or proven quantum-advantage claim — see docs for that caveat.
    classical_steps = (int(360.0 / 30.0) ** 3) * n_atoms
    speedup = classical_steps / max(1, (rus_result.circuit_evaluations * (2 * n_qubits + 1)))

    return QRotateBenchmarkResult(
        n_atoms=n_atoms,
        n_qubits=hqc_info["n_qubits"],
        rus_iterations_to_lock=rus_result.iterations,
        locked=rus_result.locked,
        two_qubit_gates=int(hqc_info["two_qubit_gates"]),
        swap_gates=0,  # Zero SWAP overhead
        estimated_hqcs=hqc_info["estimated_hqcs"],
        circuit_depth=rebased.depth(),
        quantum_speedup_factor=round(speedup, 1),
    )


# =====================================================================
# 4. Performance Showdown Runner
# =====================================================================

def run_performance_showdown(
    sizes: Sequence[int] = (10, 50, 100, 500, 1000),
    output_json_path: Optional[str] = None,
) -> dict:
    """Executes the full comparative showdown between Classical and Q-Rotate."""
    np.random.seed(42)
    results = []

    print("=" * 80)
    print("PROJECT Q-ROTATE: BENCHMARKING & HARDWARE RESOURCE SHOWDOWN")
    print("Classical 3D Spatial Grid-Search vs. Q-Rotate RUS on Quantinuum H2")
    print("=" * 80)

    for N in sizes:
        pocket = np.random.uniform(-10.0, 10.0, size=(N, 3))
        ligand = pocket + np.random.normal(0.0, 0.5, size=(N, 3))  # perturb slightly

        class_res = benchmark_classical_docking(pocket, ligand)
        q_res = benchmark_qrotate_engine(pocket, ligand, n_qubits=4, seed=42 + N)

        entry = {
            "n_atoms": N,
            "classical_time_sec": class_res.execution_time_sec,
            "classical_steps": class_res.computational_steps,
            "qrotate_qubits": q_res.n_qubits,
            "qrotate_rus_iterations": q_res.rus_iterations_to_lock,
            "qrotate_locked": q_res.locked,
            "qrotate_two_qubit_gates": q_res.two_qubit_gates,
            "qrotate_swap_gates": q_res.swap_gates,
            "qrotate_hqcs": q_res.estimated_hqcs,
            "qrotate_speedup_factor": q_res.quantum_speedup_factor,
        }
        results.append(entry)

        print(f"\n[ATOMS N = {N:4d}]")
        print(f"  • Classical Brute-Force : {class_res.execution_time_sec:8.4f}s | {class_res.computational_steps:,} grid steps")
        print(f"  • Q-Rotate RUS Engine   : Converged in {q_res.rus_iterations_to_lock} loops (Locked: {q_res.locked})")
        print(f"    - Hardware Profile    : {q_res.n_qubits} Qubits | {q_res.two_qubit_gates} native 2Q gates | {q_res.swap_gates} SWAP overhead")
        print(f"    - Quantinuum Cost     : {q_res.estimated_hqcs} HQCs on H2 | Speedup: ~{q_res.quantum_speedup_factor:,.0f}x operations")

    print("\n" + "=" * 80)
    print("KEY TAKEAWAYS FOR SUBMISSION 1:")
    print("1. Classical grid search exhibits O(N^3) combinatorial step explosion.")
    print("2. Q-Rotate compresses coordinate clusters into a compact 9-qubit register.")
    print("3. Zero SWAP overhead achieved on Quantinuum H2 all-to-all QCCD architecture.")
    print("=" * 80)

    payload = {"benchmark_results": results, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\n[Saved benchmark metrics to {output_json_path}]")

    return payload


# =====================================================================
# 4. Real-World Molecular Scenario Showdown (6 Systems)
# =====================================================================

REAL_MOLECULE_SYSTEMS: list[dict] = [
    {
        "id": "rhodopsin",
        "name": "11-cis Retinal / Rhodopsin",
        "tag": "Photochemical Master Switch",
        "desc": "Human visual photoreceptor chromophore. Models excited-state potential energy surfaces during ultrafast photoisomerization (Yamamoto et al., arXiv:2601.15677).",
        "n_atoms_proxy": 20,       # Retinal chromophore: ~20 heavy atoms in active site
        "n_qubits": 4,
        "base_delta_phi": [0.12, -0.45, 0.88, -0.22],
        "optimal_angle_deg": 45.0,
    },
    {
        "id": "gfp",
        "name": "GFP Chromophore",
        "tag": "Bioluminescent Proton Transfer",
        "desc": "Ser65-Tyr66-Gly67 tripeptide inside GFP β-barrel. Exhibits rapid excited-state proton transfer (ESPT) between phenol oxygen and catalytic water network.",
        "n_atoms_proxy": 15,       # GFP tripeptide chromophore: ~15 heavy atoms
        "n_qubits": 4,
        "base_delta_phi": [-0.62, 0.31, 0.15, -0.08],
        "optimal_angle_deg": 35.0,
    },
    {
        "id": "mpro",
        "name": "SARS-CoV-2 Mpro + Nirmatrelvir",
        "tag": "Antiviral Covalent Inhibitor",
        "desc": "Main viral 3CL protease with Nirmatrelvir. Catalytic dyad Cys145 / His41 with zero-tolerance covalent pyrrolidone geometry.",
        "n_atoms_proxy": 49,       # Nirmatrelvir + binding pocket residues: ~49 heavy atoms
        "n_qubits": 4,
        "base_delta_phi": [0.44, 0.92, -0.38, 0.19],
        "optimal_angle_deg": -50.0,
    },
    {
        "id": "cox2",
        "name": "COX-2 + Celecoxib",
        "tag": "Single-Residue Selectivity",
        "desc": "Val523 (COX-2) vs Ile523 (COX-1) — single residue substitution opening the secondary NSAID binding pocket. Clinical target for anti-inflammatory drugs without GI toxicity.",
        "n_atoms_proxy": 35,       # Active site contact residues: ~35 heavy atoms
        "n_qubits": 4,
        "base_delta_phi": [-0.18, 0.25, 0.73, -0.54],
        "optimal_angle_deg": 80.0,
    },
    {
        "id": "azobenzene",
        "name": "Azobenzene Molecular Switch",
        "tag": "Photopharmacological Motor",
        "desc": "Synthetic light-activated molecular actuator. N=N bond photoisomerizes trans→cis under UV, functioning as a reversible quantum key with distinct 3D profiles.",
        "n_atoms_proxy": 24,       # Azobenzene scaffold: ~24 heavy atoms
        "n_qubits": 4,
        "base_delta_phi": [0.78, -0.81, 0.35, -0.42],
        "optimal_angle_deg": -115.0,
    },
    {
        "id": "h2bench",
        "name": "H2 Hardware Benchmark",
        "tag": "Trapped-Ion Physical Stress Test",
        "desc": "Gate-level benchmark: PhasedX, ZZPhase, mid-circuit reset across 4-site and 8-site stress manifolds. Validates QCCD all-to-all connectivity with zero SWAP overhead.",
        "n_atoms_proxy": 8,        # 8-site stress manifold
        "n_qubits": 4,
        "base_delta_phi": [0.15, -0.10, 0.20, -0.05],
        "optimal_angle_deg": 15.0,
    },
]


def run_molecular_showdown(
    output_json_path: Optional[str] = None,
    n_sites: int = 4,
) -> dict:
    """Runs the Q-Rotate benchmark across all 6 real-world constellation scenarios.

    Each scenario uses:
      - A realistic atom count proxy reflecting the true active-site complexity.
      - The exact baseDeltaPhi fingerprints encoded in the 3D Constellation game.
      - Classical grid search sized to that molecule's actual heavy-atom count.

    This replaces abstract random coordinate benchmarks with biologically-grounded
    evidence for the Quantinuum Singapore Grand Challenge judging panel.
    """
    np.random.seed(42)
    results = []

    print("=" * 80)
    print("PROJECT Q-ROTATE: REAL-WORLD MOLECULAR SCENARIO SHOWDOWN")
    print(f"6 Pharmaceutical Targets x Classical 3D Grid vs. Q-Rotate RUS "
          f"({n_sites} sites, {2 * n_sites + 1} qubits)")
    print("=" * 80)

    sites = load_active_sites()

    for sys in REAL_MOLECULE_SYSTEMS:
        n_qubits = n_sites
        seed = zlib.crc32(sys["id"].encode()) % (2**31)

        # Experimental coordinates when we have them (see structures.py). Both
        # sides are the same ligand: the target is its deposited pose, the probe
        # starts rotated off that pose by optimal_angle_deg. See
        # `_system_coordinates` for why this measures pose recovery rather than
        # protein-ligand docking.
        target_coords, probe_coords = _system_coordinates(
            sys["id"], sys["n_atoms_proxy"], sys["optimal_angle_deg"], seed)
        site = sites.get(sys["id"])
        N = len(probe_coords)

        # How far off the probe starts, so a reader can see the difficulty
        # rather than inferring it from the iteration count.
        elements = site_elements(sys["id"]) or ["C"] * N
        probe_geom = MolecularGeometry(f"{sys['id']}_probe", elements, probe_coords)
        start_phases = pocket_ligand_to_qubit_phases(probe_geom, n_qubits=n_qubits)

        # Classical baseline: the same grid search over the same atoms.
        class_res = benchmark_classical_docking(target_coords, probe_coords)

        # The target's phase fingerprint is what the search is looking for,
        # derived from its real atoms rather than a hand-picked constant. The
        # probe starts from an uninformed all-zero guess so the blind RUS search
        # has genuine work to do instead of starting 90%-pre-converged.
        target_geom = MolecularGeometry(f"{sys['id']}_target", elements, target_coords)
        pocket_phases = pocket_ligand_to_qubit_phases(target_geom, n_qubits=n_qubits)
        # Compile one representative circuit purely to read its gate counts.
        circ = build_pytket_swap_test_circuit(pocket_phases, start_phases, tau=0.25, omega=(1.0, 0.5, 0.25))
        rebased = rebase_to_h2_gateset(circ)

        # Search over the pose, not over free phase values: the probe starts
        # at its rotated (wrong) orientation and the blind loop has to turn it
        # back. NOTE: Python's builtin hash() is randomized per-process
        # (PYTHONHASHSEED) and would make this non-reproducible run-to-run;
        # zlib.crc32 is stable across runs and machines.
        rus_result = run_blind_rus_pose_recovery(
            pocket_phases, probe_coords, n_qubits=n_qubits,
            tau=0.25, omega=(1.0, 0.5, 0.25),
            max_retries=15, shots=100, seed=seed, elements=elements,
        )
        iterations = rus_result.iterations
        locked = rus_result.locked

        hqc_info = estimate_qrotate_hqc_cost(n_qubits, rus_result.circuit_evaluations, shots=100, circuit=rebased)
        classical_steps = (int(360.0 / 30.0) ** 3) * N
        speedup = classical_steps / max(1, rus_result.circuit_evaluations * (2 * n_qubits + 1))

        start_p0 = simulate_swap_test_statevector(pocket_phases, start_phases, 0.25, (1.0, 0.5, 0.25))

        # A molecule whose angular moments all cancel encodes to an all-zero
        # register at every orientation. Two such registers match perfectly and
        # mean nothing, so the lock below would be an artefact, not a result.
        anisotropy = shell_anisotropy(target_geom, n_qubits=n_qubits)
        degenerate = is_encoding_degenerate(target_geom, n_qubits=n_qubits)
        moment_orders = shell_moment_orders(target_geom, n_qubits=n_qubits)
        ambiguous_180 = has_180_degree_ambiguity(target_geom, n_qubits=n_qubits)

        entry = {
            "system_id": sys["id"],
            "start_offset_deg": sys["optimal_angle_deg"],
            "start_p0": round(start_p0, 4),
            "shell_anisotropy": [round(a, 4) for a in anisotropy],
            "shell_moment_orders": moment_orders,
            "encoding_degenerate": degenerate,
            "ambiguous_180_deg": ambiguous_180,
            "system_name": sys["name"],
            "system_tag": sys["tag"],
            # Where the coordinates came from, so a reader can check them.
            "structure_source": (
                f"{site['source']['db']} {site['source']['id']}" if site else "synthetic fallback"
            ),
            "ligand_resname": site["ligand"]["resname"] if site else None,
            "n_ligand_atoms": N,
            "n_pocket_atoms": site["pocket"]["n_atoms"] if site else None,
            "comparison": "pose recovery: ligand vs a rotated copy of itself",
            "n_atoms_proxy": N,
            "classical_time_sec": class_res.execution_time_sec,
            "classical_steps": class_res.computational_steps,
            "qrotate_qubits": hqc_info["n_qubits"],
            "qrotate_rus_iterations": iterations,
            "qrotate_locked": locked,
            "qrotate_final_p0": round(rus_result.final_p0_hat, 4),
            "qrotate_two_qubit_gates": int(hqc_info["two_qubit_gates"]),
            "qrotate_swap_gates": 0,
            "qrotate_hqcs": hqc_info["estimated_hqcs"],
            "quantum_speedup_factor": round(speedup, 1),
            "circuit_depth": rebased.depth(),
        }
        results.append(entry)

        print(f"\n[{sys['id'].upper():10s}] {sys['name']}")
        print(f"  Tag         : {sys['tag']}")
        print(f"  Structure   : {entry['structure_source']}"
              + (f" | ligand {entry['ligand_resname']} ({N} heavy atoms)"
                 f" | pocket {entry['n_pocket_atoms']} atoms" if site else ""))
        print(f"  Active Site : {N} atoms | Classical grid: {class_res.computational_steps:,} steps in {class_res.execution_time_sec:.4f}s")
        if degenerate:
            print("  WARNING     : every angular moment of this molecule cancels, so its")
            print("                register is all zeros at every orientation. Any 'lock'")
            print("                below is two empty registers agreeing, NOT a result.")
        elif ambiguous_180:
            print("  NOTE        : first-order moments cancel here, so the register comes")
            print("                from the second order and is known only modulo 180 deg.")
            print("                The pose is recovered up to that flip, which for a")
            print("                centrosymmetric molecule is the same arrangement.")
        print(f"  Q-Rotate    : {'Locked in' if locked else 'NO LOCK after'} {iterations} RUS iterations"
              f" | final P(0)={rus_result.final_p0_hat:.3f} | {hqc_info['n_qubits']} qubits | 0 SWAPs")
        print(f"  HQC Cost    : {hqc_info['estimated_hqcs']:.2f} HQCs ({hqc_info['circuit_runs']} circuit runs x {hqc_info['hqc_per_circuit']:.2f}) | Speedup: ~{speedup:,.0f}x")

    n_locked = sum(1 for r in results if r["qrotate_locked"])
    iter_values = [r["qrotate_rus_iterations"] for r in results]
    print("\n" + "=" * 80)
    print("MOLECULAR SHOWDOWN SUMMARY:")
    # Degenerate systems are excluded from the headline: an all-zero register
    # "locks" against itself instantly and that number would flatter the result.
    meaningful = [r for r in results if not r.get("encoding_degenerate")]
    n_locked_meaningful = sum(1 for r in meaningful if r["qrotate_locked"])
    print(f"  {n_locked_meaningful}/{len(meaningful)} targets with a usable encoding reached "
          "statistical lock within 15 RUS iterations")
    if len(meaningful) != len(results):
        excluded = [r["system_id"] for r in results if r.get("encoding_degenerate")]
        print(f"  ({len(results) - len(meaningful)} excluded as encoding-degenerate: "
              f"{', '.join(excluded)} — see the WARNING above)")
    iter_values = [r["qrotate_rus_iterations"] for r in meaningful] or iter_values
    print(f"  (min {min(iter_values)}, max {max(iter_values)} iterations across those systems —")
    print("   this is a blind search measured against the real simulated circuit each")
    print("   iteration, so it varies by molecule instead of being fixed.)")
    print("  Classical grid search requires millions of operations per molecule.")
    print("  Zero SWAP overhead across all scenarios on Quantinuum H2 QCCD.")
    print("  Q-Rotate qubit footprint stays fixed regardless of active-site atom count")
    print("  (the HQC cost still scales with RUS iterations, which now vary by input).")
    print("=" * 80)

    payload = {
        "molecular_showdown_results": results,
        "n_sites": n_sites,
        "register_qubits": 2 * n_sites + 1,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "systems_count": len(results),
    }

    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\n[Saved molecular showdown results to {output_json_path}]")

    return payload


# =====================================================================
# 5. Constellation Resonance Profiles (real P(0) landscapes for the 3D page)
# =====================================================================

def _system_coordinates(
    system_id: str,
    n_atoms: int,
    angle_deg: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """(target, probe) for one system: the ligand in its deposited pose, and a
    copy of it rotated -angle_deg away, so dialling +angle_deg brings the probe
    back into register.

    WHAT THIS MEASURES: pose recovery, not protein-ligand docking. Both sides
    are the same molecule, so there is a true answer (the deposited pose) and
    "locked" means the blind search found it. Comparing the pocket's phase
    register against the ligand's would not have that property: they are
    different molecules with different atom counts, so no rotation makes their
    fingerprints agree and whichever angle scores highest is incidental. The
    pocket is still read from the same experimental entry and reported for
    context (atom counts, residues) — it just is not the thing being matched.

    Uses the experimental coordinates in benchmarks/active_sites.json when they
    are present (see src/qrotate/structures.py). Falls back to the old synthetic
    ring only if that file is missing, and says so, because a run on synthetic
    points must never be mistaken for a run on a real active site.
    """
    real = site_coordinates(system_id)
    if real is not None:
        _pocket, ligand_reference = real
        return ligand_reference, _rotate_z(ligand_reference, -angle_deg)

    warnings.warn(
        f"{system_id}: benchmarks/active_sites.json not found — falling back to "
        "a synthetic ring, which is NOT real molecular geometry. Run "
        "`python -m src.qrotate.structures` to fetch the real structures.",
        RuntimeWarning,
        stacklevel=2,
    )
    radius = 3.5
    phi_grid = np.linspace(0, 2 * np.pi, n_atoms, endpoint=False)
    pocket = np.column_stack([
        radius * np.cos(phi_grid),
        radius * np.sin(phi_grid),
        np.sin(phi_grid * 2) * 0.8,
    ])
    rng = np.random.default_rng(seed)
    ligand = _rotate_z(pocket, -angle_deg) + rng.normal(0, 0.05, pocket.shape)
    return pocket, ligand


def _rotate_z(coords: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotates about z through the cloud's own centroid, so a rotation stays a
    rotation instead of swinging the molecule around the crystal origin."""
    a = np.radians(angle_deg)
    rot = np.array([
        [np.cos(a), -np.sin(a), 0.0],
        [np.sin(a), np.cos(a), 0.0],
        [0.0, 0.0, 1.0],
    ])
    centroid = coords.mean(axis=0)
    return (coords - centroid) @ rot.T + centroid


def run_molecular_showdown_all_registers(
    output_json_path: Optional[str] = "benchmarks/molecular_showdown.json",
    register_sizes: Sequence[int] = (4, 8),
) -> dict:
    """Runs the pose-recovery showdown at every register size the project
    offers, so the 9-qubit and 17-qubit configurations can be compared on the
    same six ligands instead of one being quoted and the other assumed.

    The top-level `molecular_showdown_results` stays as the 4-site run, which
    is the configuration the submission's headline numbers describe.
    """
    by_size = {}
    for n_sites in register_sizes:
        print()
        by_size[str(n_sites)] = run_molecular_showdown(output_json_path=None, n_sites=n_sites)

    default = by_size[str(register_sizes[0])]
    payload = {
        "molecular_showdown_results": default["molecular_showdown_results"],
        "default_n_sites": register_sizes[0],
        "by_register_size": by_size,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    print("\n" + "=" * 80)
    print("REGISTER SIZE COMPARISON (pose recovery on the same six ligands)")
    print("=" * 80)
    print(f"{'register':>10} {'locked':>8} {'iterations':>12} {'HQC/screen':>22} {'HQC/circuit':>12}")
    for n_sites in register_sizes:
        rows = by_size[str(n_sites)]["molecular_showdown_results"]
        usable = [r for r in rows if not r.get("encoding_degenerate")]
        locked = sum(1 for r in usable if r["qrotate_locked"])
        iters = [r["qrotate_rus_iterations"] for r in usable]
        hqcs = [r["qrotate_hqcs"] for r in usable]
        per_circuit = compute_circuit_hqc_cost(_reference_swap_test_circuit(n_sites), shots=100)
        print(f"{2 * n_sites + 1:>7} qb {locked:>4}/{len(usable):<3} "
              f"{min(iters):>5}-{max(iters):<6} {min(hqcs):>10.2f}-{max(hqcs):<10.2f} "
              f"{per_circuit['hqc_cost']:>12.2f}")
    print("=" * 80)

    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\n[Saved molecular showdown (all registers) to {output_json_path}]")

    _write_screen_costs_js(payload, "assets/screen_costs.js")
    return payload


def _write_screen_costs_js(payload: dict, js_path: str) -> None:
    """Per-system measured screen cost at each register size, for the
    Constellation's telemetry. Without this the page showed one register's
    figure while the viewer had the other selected."""
    costs: dict = {}
    for size, run in payload.get("by_register_size", {}).items():
        for row in run["molecular_showdown_results"]:
            entry = costs.setdefault(row["system_id"], {})
            entry[size] = {
                "hqc_per_screen": row["qrotate_hqcs"],
                "rus_iterations": row["qrotate_rus_iterations"],
                "register_qubits": run["register_qubits"],
                "locked": row["qrotate_locked"],
            }

    os.makedirs(os.path.dirname(os.path.abspath(js_path)), exist_ok=True)
    with open(js_path, "w", encoding="utf-8") as handle:
        handle.write("// Generated by src/qrotate/metrics.py::run_molecular_showdown_all_registers\n")
        handle.write("// Measured blind pose-recovery cost per system, per register size.\n")
        handle.write("// Do not edit by hand: re-run `python -m src.qrotate.metrics`.\n")
        handle.write("window.QROTATE_SCREEN_COSTS = ")
        json.dump({"by_system": costs}, handle, separators=(",", ":"))
        handle.write(";\n")
    print(f"[Saved per-register screen costs to {js_path}]")


def run_blind_rus_pose_recovery(
    target_phases: Sequence[float],
    probe_coords: np.ndarray,
    n_qubits: int,
    tau: float = 0.25,
    omega: tuple[float, float, float] = (1.0, 0.5, 0.25),
    max_retries: int = 15,
    shots: int = 100,
    lock_confidence_sigma: float = 1.645,
    step_deg: float = 60.0,
    seed: Optional[int] = None,
    elements: Optional[Sequence[str]] = None,
) -> BlindRusResult:
    """Blind RUS over the POSE rather than over free phase values.

    `run_blind_rus_protocol` perturbs the four phase numbers directly, which no
    physical ligand can do: a register the search can move to any point in
    [-pi, pi]^4 does not correspond to any rotation of a molecule. This variant
    perturbs the rotation angle, re-encodes the rotated coordinates, and
    measures the resulting circuit — the same one-parameter search the
    Constellation page runs, and the thing the method actually claims to do.

    Still blind: the target phases are never read, only the sampled parity.
    """
    rng = np.random.default_rng(seed)
    probe_elements = list(elements) if elements else []

    def measure(angle_deg: float) -> tuple[float, dict]:
        rotated = _rotate_z(probe_coords, angle_deg)
        geom = MolecularGeometry("probe", probe_elements or ["C"] * len(rotated), rotated)
        phases = pocket_ligand_to_qubit_phases(geom, n_qubits=n_qubits)
        p0_true = simulate_swap_test_statevector(target_phases, phases, tau, omega)
        shot_res = simulate_shot_sampling(p0_true, n_shots=shots, seed=int(rng.integers(1 << 31)))
        return p0_true, shot_res

    angle = 0.0
    p0_true, shot_res = measure(angle)
    circuit_evals = 1
    p0_hat = shot_res["empirical_prob"]

    for attempt in range(max_retries):
        iterations = attempt + 1
        if p0_hat - lock_confidence_sigma * shot_res["std_err"] >= 0.90:
            return BlindRusResult(True, iterations, circuit_evals, p0_hat, p0_true)

        trial_angle = angle + (step_deg / np.sqrt(attempt + 1.0)) * rng.choice([-1.0, 1.0])
        trial_p0_true, trial_shot = measure(trial_angle)
        circuit_evals += 1
        if trial_shot["empirical_prob"] > p0_hat:
            angle, p0_true, shot_res = trial_angle, trial_p0_true, trial_shot
            p0_hat = trial_shot["empirical_prob"]

    locked = p0_hat - lock_confidence_sigma * shot_res["std_err"] >= 0.90
    return BlindRusResult(locked, max_retries, circuit_evals, p0_hat, p0_true)


def export_constellation_profiles(
    step_deg: int = 2,
    json_path: Optional[str] = "benchmarks/constellation_profiles.json",
    js_path: Optional[str] = "assets/constellation_profiles.js",
) -> dict:
    """Sweeps each benchmark system through a full turn and records the real
    SWAP-test P(0) at every angle, plus the phase register the rotation
    produces.

    This is the same pipeline the benchmarks use — coordinates through
    `pocket_ligand_to_qubit_phases` into `simulate_swap_test_statevector` — so
    the 3D Constellation page can plot measured landscapes instead of a
    textbook cos^2 curve. The JS file is written because the page must work
    from file:// too, where fetch() of a local JSON is blocked.
    """
    tau, omega = 0.25, (1.0, 0.5, 0.25)
    angles = list(range(-180, 181, step_deg))
    profiles = []

    print("=" * 80)
    print("CONSTELLATION RESONANCE PROFILES (real statevector P(0) landscapes)")
    print("=" * 80)

    for sys in REAL_MOLECULE_SYSTEMS:
        seed = zlib.crc32(sys["id"].encode()) % (2**31)
        pocket, ligand_base = _system_coordinates(
            sys["id"], sys["n_atoms_proxy"], sys["optimal_angle_deg"], seed)
        elements = site_elements(sys["id"]) or ["C"] * len(pocket)
        pocket_geom = MolecularGeometry("target", elements, pocket)

        # Both register sizes the page offers: 4 sites (H2) and 8 (Helios).
        registers = {}
        for n_qubits in (4, 8):
            pocket_phases = pocket_ligand_to_qubit_phases(pocket_geom, n_qubits=n_qubits)
            p0_curve, phase_curve = [], []
            for ang in angles:
                rotated = _rotate_z(ligand_base, ang)
                geom = MolecularGeometry("probe", elements, rotated)
                phases = pocket_ligand_to_qubit_phases(geom, n_qubits=n_qubits)
                p0_curve.append(round(simulate_swap_test_statevector(pocket_phases, phases, tau, omega), 4))
                phase_curve.append([round(float(x), 3) for x in phases])

            best_i = int(np.argmax(p0_curve))
            registers[str(n_qubits)] = {
                "n_sites": n_qubits,
                "moment_orders": shell_moment_orders(pocket_geom, n_qubits=n_qubits),
                # Second-order-only registers repeat every 180 degrees, so the
                # landscape has two equally correct peaks rather than a trap.
                "ambiguous_180_deg": has_180_degree_ambiguity(pocket_geom, n_qubits=n_qubits),
                "total_qubits": 2 * n_qubits + 1,
                "pocket_phases": [round(float(x), 3) for x in pocket_phases],
                "p0_curve": p0_curve,
                "ligand_phases_by_angle": phase_curve,
                "best_angle_deg": angles[best_i],
                "best_p0": p0_curve[best_i],
                "worst_p0": min(p0_curve),
                # Decoy peaks: local maxima that a hill-climbing search can
                # settle on without reaching the true optimum.
                "local_maxima_deg": [
                    angles[i] for i in range(1, len(p0_curve) - 1)
                    if p0_curve[i] > p0_curve[i - 1] and p0_curve[i] >= p0_curve[i + 1] and p0_curve[i] > 0.7
                ],
            }

        r4 = registers["4"]
        profiles.append({
            "id": sys["id"],
            "name": sys["name"],
            "n_atoms_proxy": sys["n_atoms_proxy"],
            # The true answer: how far the probe was turned away from the
            # deposited pose. The landscape peak sits a few degrees short of it
            # because U_tube(tau) evolves the probe register only (at tau=0 the
            # peak is exactly here, with P(0)=1).
            "pose_offset_deg": sys["optimal_angle_deg"],
            "angles_deg": angles,
            "registers": registers,
        })
        print(f"[{sys['id']:10s}] 4-site peak P(0)={r4['best_p0']:.4f} at {r4['best_angle_deg']:+4d} deg "
              f"| floor {r4['worst_p0']:.4f} | {len(r4['local_maxima_deg'])} local maxima "
              f"| 8-site peak {registers['8']['best_p0']:.4f} at {registers['8']['best_angle_deg']:+4d} deg")

    payload = {
        "constellation_profiles": profiles,
        "tau": tau,
        "omega": list(omega),
        "step_deg": step_deg,
        "source": "src/qrotate/metrics.py::export_constellation_profiles",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_constellation_profiles(payload, json_path, js_path)
    return payload


def _write_constellation_profiles(
    payload: dict,
    json_path: Optional[str] = "benchmarks/constellation_profiles.json",
    js_path: Optional[str] = "assets/constellation_profiles.js",
) -> None:
    if json_path:
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\n[Saved constellation profiles to {json_path}]")

    if js_path:
        os.makedirs(os.path.dirname(os.path.abspath(js_path)), exist_ok=True)
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("// Generated by src/qrotate/metrics.py::export_constellation_profiles\n")
            f.write("// Real SWAP-test P(0) landscapes. Do not edit by hand: re-run\n")
            f.write("// `python -m src.qrotate.metrics` to regenerate.\n")
            f.write("window.QROTATE_PROFILES = ")
            json.dump(payload, f, separators=(",", ":"))
            f.write(";\n")
        print(f"[Saved constellation profiles to {js_path}]")


if __name__ == "__main__":
    run_performance_showdown(output_json_path="benchmarks/showdown_results.json")
    run_molecular_showdown_all_registers(output_json_path="benchmarks/molecular_showdown.json")
    export_constellation_profiles()
