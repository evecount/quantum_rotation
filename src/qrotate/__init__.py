"""Project Q-Rotate: Efficient Molecular Pattern Matching for Biomolecular Simulation.

Translates 3D structural alignment and ligand-protein pocket lock-and-key matching
into an information-theoretic quantum blind parity check with adaptive RUS loops.
"""

from .operators import (
    HTubeHamiltonian,
    decompose_rotation_euler,
    compute_phase_mismatch,
    compute_flexible_overlap_unitary,
    verify_lie_algebra_closure,
)
from .hpc_bridge import (
    MolecularGeometry,
    pocket_ligand_to_qubit_phases,
    pocket_ligand_to_multi_shell_phases,
    generate_synthetic_binding_pair,
)
from .circuits import (
    simulate_shot_sampling,
    compile_h2_native_gates,
    calculate_exact_hqc_budget,
    build_pytket_swap_test_circuit,
    build_pytket_rus_simulation,
    rebase_to_h2_gateset,
)
from .metrics import (
    compute_overlap_fidelity,
    estimate_qrotate_hqc_cost,
    compute_circuit_hqc_cost,
)

__all__ = [
    "HTubeHamiltonian",
    "decompose_rotation_euler",
    "compute_phase_mismatch",
    "compute_flexible_overlap_unitary",
    "verify_lie_algebra_closure",
    "MolecularGeometry",
    "pocket_ligand_to_qubit_phases",
    "pocket_ligand_to_multi_shell_phases",
    "generate_synthetic_binding_pair",
    "simulate_shot_sampling",
    "compile_h2_native_gates",
    "calculate_exact_hqc_budget",
    "build_pytket_swap_test_circuit",
    "build_pytket_rus_simulation",
    "rebase_to_h2_gateset",
    "compute_overlap_fidelity",
    "estimate_qrotate_hqc_cost",
    "compute_circuit_hqc_cost",
]
