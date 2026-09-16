"""Test suite for Project Q-Rotate."""

import sys
import os
import numpy as np

# Ensure root and src are on python path
sys.path.insert(0, r"d:\Quantinuum_GrandChallenge")
sys.path.insert(0, r"d:\Quantinuum_GrandChallenge\src")

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
)
import utils
from hugr_qir.hugr_to_qir import hugr_to_qir
from hugr_qir.output import OutputFormat


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
    qir = hugr_to_qir(hugr, output_format=OutputFormat.BITCODE)
    assert len(qir) > 0
    print(f"PASS: test_guppy_circuit_compilation (Generated {len(qir)} bytes of QIR bitcode)")


def test_metrics_cost():
    cost_info = estimate_qrotate_hqc_cost(n_qubits=3, rus_attempts=3, shots=100)
    assert cost_info["n_qubits"] == 7
    assert cost_info["estimated_hqcs"] > 5.0
    print(f"PASS: test_metrics_cost (Estimate: {cost_info['estimated_hqcs']} HQCs)")


if __name__ == "__main__":
    test_hpc_bridge()
    test_operators()
    test_pytket_circuit()
    test_guppy_circuit_compilation()
    test_metrics_cost()
    print("\nALL PROJECT Q-ROTATE TESTS PASSED SUCCESSFULLY!")
