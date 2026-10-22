"""Project Q-Rotate: Coordinate-Free Molecular Pose Search for Biomolecular Simulation.

Translates 3D structural alignment and ligand-protein pocket lock-and-key matching
into an information-theoretic quantum blind parity check with adaptive RUS loops.
"""

__version__ = "0.1.0"

# Submodule exports are resolved lazily (PEP 562). `qrotate.circuits` pulls in
# guppylang and the aqora backend, which takes tens of seconds on a cold
# machine; `qrotate.client` and `qrotate fingerprint` do not need them.
_EXPORTS = {
    "HTubeHamiltonian": ".operators",
    "decompose_rotation_euler": ".operators",
    "compute_phase_mismatch": ".operators",
    "compute_flexible_overlap_unitary": ".operators",
    "verify_lie_algebra_closure": ".operators",
    "MolecularGeometry": ".hpc_bridge",
    "pocket_ligand_to_qubit_phases": ".hpc_bridge",
    "pocket_ligand_to_multi_shell_phases": ".hpc_bridge",
    "generate_synthetic_binding_pair": ".hpc_bridge",
    "simulate_shot_sampling": ".circuits",
    "compile_h2_native_gates": ".circuits",
    "calculate_exact_hqc_budget": ".circuits",
    "build_pytket_swap_test_circuit": ".circuits",
    "build_pytket_rus_simulation": ".circuits",
    "rebase_to_h2_gateset": ".circuits",
    "compute_overlap_fidelity": ".metrics",
    "estimate_qrotate_hqc_cost": ".metrics",
    "compute_circuit_hqc_cost": ".metrics",
}


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module 'qrotate' has no attribute {name!r}")
    from importlib import import_module
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))


__all__ = [
    "__version__",
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
