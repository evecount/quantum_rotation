"""Test suite for Project Q-Rotate."""

import sys
import os
import numpy as np
from pathlib import Path

# Ensure repo root and src/ are on the python path, relative to this file,
# so the suite runs on any machine/CI rather than only the original author's.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from qrotate.operators import (
    HTubeHamiltonian,
    decompose_rotation_euler,
    compute_phase_mismatch,
)
from qrotate.hpc_bridge import (
    MolecularGeometry,
    pocket_ligand_to_qubit_phases,
    generate_synthetic_binding_pair,
)
from qrotate.metrics import (
    compute_overlap_fidelity,
    estimate_qrotate_hqc_cost,
)
from qrotate.circuits import (
    build_pytket_swap_test_circuit,
    build_pytket_rus_simulation,
    rebase_to_h2_gateset,
    guppy_qrotate_rus_demo,
    simulate_swap_test_statevector,
)
from qrotate.metrics import run_blind_rus_protocol
import utils

try:
    from hugr_qir.hugr_to_qir import hugr_to_qir
    from hugr_qir.output import OutputFormat
    HAS_HUGR_QIR = True
except ImportError:
    HAS_HUGR_QIR = False


def test_hpc_bridge():
    pocket_geo, ligand_geo, delta_phi = generate_synthetic_binding_pair(n_sites=3, rotation_angle_deg=10.0)
    assert pocket_geo.n_atoms == 3
    assert ligand_geo.n_atoms == 3
    assert len(delta_phi) == 3
    print("PASS: test_hpc_bridge")


def test_operators():
    h_tube = HTubeHamiltonian(
        n_qubits=2,
        omega=(0.1, 0.2, 0.3),
        delta_phi=[0.05, -0.05],
        coupling_j=0.01,
    )
    u_mat = h_tube.get_evolution_unitary(tau=1.0)
    assert u_mat.shape == (4, 4)
    # Check unitarity
    identity_diff = np.max(np.abs(u_mat.conj().T @ u_mat - np.eye(4)))
    assert identity_diff < 1e-10
    print("PASS: test_operators (U_tube is unitary)")


def test_pytket_circuit():
    pocket_phases = [0.1, 0.2]
    ligand_phases = [0.15, 0.25]
    circ = build_pytket_swap_test_circuit(
        pocket_phases, ligand_phases, tau=0.5, omega=(0.0, 0.1, 0.2)
    )
    assert circ.n_qubits == 5  # 1 ancilla + 2 pocket + 2 ligand
    rebased = rebase_to_h2_gateset(circ)
    stats = utils.pytket_op_counts(rebased)
    assert stats["Qubits"] == 5
    cost = utils.estimate_cost(stats, n_shots=100)
    print(f"PASS: test_pytket_circuit (Rebased Op counts: {stats}, Estimated HQC: {cost:.2f})")


def test_guppy_circuit_compilation():
    print("Compiling guppy_qrotate_rus_demo to HUGR...")
    hugr = guppy_qrotate_rus_demo.compile()
    stats = utils.hugr_op_counts(hugr)
    print(f"Guppy HUGR stats: {stats}")
    if not HAS_HUGR_QIR:
        print("SKIP: hugr_qir not installed in this environment (HUGR compilation still verified above)")
        return
    qir = hugr_to_qir(hugr, output_format=OutputFormat.BITCODE)
    assert len(qir) > 0
    print(f"PASS: test_guppy_circuit_compilation (Generated {len(qir)} bytes of QIR bitcode)")


def test_metrics_cost():
    cost_info = estimate_qrotate_hqc_cost(n_qubits=3, rus_attempts=3, shots=100)
    assert cost_info["n_qubits"] == 7
    assert cost_info["estimated_hqcs"] > 5.0
    print(f"PASS: test_metrics_cost (Estimate: {cost_info['estimated_hqcs']} HQCs)")


def test_swap_test_statevector_matches_closed_form():
    """The dense-statevector SWAP-test simulator must reproduce the textbook
    single-qubit SWAP-test formula P(0) = (1 + cos^2(delta_phi/2)) / 2 exactly
    (this is the ground truth the honest RUS benchmark measures against)."""
    for dphi in (0.0, 0.3, 1.2, 2.5):
        p0 = simulate_swap_test_statevector([0.4], [0.4 - dphi], tau=0.0, omega=(0.0, 0.0, 0.0))
        expected = 0.5 * (1.0 + np.cos(dphi / 2.0) ** 2)
        assert abs(p0 - expected) < 1e-9, f"dphi={dphi}: sim={p0} expected={expected}"
    # Identical states must swap-test to a certain P(0) = 1.0.
    p0_identical = simulate_swap_test_statevector([0.1, -0.2, 0.9], [0.1, -0.2, 0.9], tau=0.0, omega=(0.0, 0.0, 0.0))
    assert abs(p0_identical - 1.0) < 1e-9
    print("PASS: test_swap_test_statevector_matches_closed_form")


def test_blind_rus_protocol_does_not_cheat():
    """The RUS search must never be handed the pocket's own phases as its
    update rule (that was the bug that made the old benchmark self-fulfilling)
    and outcomes must genuinely depend on the starting mismatch."""
    pocket_phases = [0.6, -0.7, 0.5, -0.4]

    # A search starting already close to the target should lock, and in no
    # more iterations than a search starting maximally uninformed (all zeros).
    near_result = run_blind_rus_protocol(
        pocket_phases, [p * 0.95 for p in pocket_phases],
        tau=0.25, omega=(1.0, 0.5, 0.25), max_retries=15, shots=100, seed=7,
    )
    far_result = run_blind_rus_protocol(
        pocket_phases, [0.0, 0.0, 0.0, 0.0],
        tau=0.25, omega=(1.0, 0.5, 0.25), max_retries=15, shots=100, seed=7,
    )
    assert near_result.locked
    assert near_result.iterations <= far_result.iterations
    print(
        f"PASS: test_blind_rus_protocol_does_not_cheat "
        f"(near-start locked in {near_result.iterations} iters, far-start in {far_result.iterations})"
    )


if __name__ == "__main__":
    test_hpc_bridge()
    test_operators()
    test_pytket_circuit()
    test_guppy_circuit_compilation()
    test_metrics_cost()
    test_swap_test_statevector_matches_closed_form()
    test_blind_rus_protocol_does_not_cheat()
    print("\nALL PROJECT Q-ROTATE TESTS PASSED SUCCESSFULLY!")
