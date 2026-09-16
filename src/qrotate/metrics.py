"""Metrics and resource estimation for Project Q-Rotate."""

from __future__ import annotations

import numpy as np
from typing import Sequence


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


def estimate_qrotate_hqc_cost(
    n_qubits: int,
    rus_attempts: int,
    shots: int = 100,
) -> dict[str, float]:
    """Estimates Hardware Quantum Credits (HQCs) on Quantinuum H2.

    Based on the official Quantinuum H-series costing model in utils.py:
    Gating Cost = PhasedX + 10*(ZZMax + ZZPhase) + 5*(Qubits + Measure + Reset)
    HQC = 5 + GatingCost * Shots / 5000
    """
    # Per attempt operations:
    # Ancilla H (2), CSWAP / Fredkin (approx 2 CX + 1 Toffoli -> 7 native 2Q gates)
    # Single-qubit rotations: Rz, Ry per qubit
    single_q_gates = (2 * n_qubits + 2) * rus_attempts
    two_q_gates = (3 * n_qubits) * rus_attempts  # ZZPhase equivalents
    measures = rus_attempts
    resets = max(0, rus_attempts - 1)
    total_qubits = 2 * n_qubits + 1  # pocket register + ligand register + ancilla

    gating_cost = (
        single_q_gates
        + 10 * two_q_gates
        + 5 * (total_qubits + measures + resets)
    )

    hqc = 5.0 + gating_cost * shots / 5000.0

    return {
        "n_qubits": total_qubits,
        "single_qubit_gates": single_q_gates,
        "two_qubit_gates": two_q_gates,
        "measures": measures,
        "resets": resets,
        "gating_cost": gating_cost,
        "estimated_hqcs": round(hqc, 2),
    }
