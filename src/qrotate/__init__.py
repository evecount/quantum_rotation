"""Project Q-Rotate: Efficient Molecular Pattern Matching for Biomolecular Simulation.

Translates 3D structural alignment and ligand-protein pocket lock-and-key matching
into an information-theoretic quantum blind parity check with adaptive RUS loops.
"""

from .operators import (
    HTubeHamiltonian,
    decompose_rotation_euler,
    compute_phase_mismatch,
)
from .hpc_bridge import (
    MolecularGeometry,
    pocket_ligand_to_qubit_phases,
    generate_synthetic_binding_pair,
)
from .metrics import (
    compute_overlap_fidelity,
    estimate_qrotate_hqc_cost,
)

__all__ = [
    "HTubeHamiltonian",
    "decompose_rotation_euler",
    "compute_phase_mismatch",
    "MolecularGeometry",
    "pocket_ligand_to_qubit_phases",
    "generate_synthetic_binding_pair",
    "compute_overlap_fidelity",
    "estimate_qrotate_hqc_cost",
]
