"""Mathematical operators and Lie algebra generators for Project Q-Rotate.

Defines the dimensional rotation evolution operator U_tube(tau) and its
decomposition into spatial rotation (H_rot) and phase cascading mismatch (H_phase).
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Sequence
import scipy.linalg


@dataclass
class HTubeHamiltonian:
    r"""Generates the H_tube Hamiltonian for Project Q-Rotate.

    .. math::
        \hat{H}_{\text{tube}} = \hat{H}_{\text{rot}} + \hat{H}_{\text{phase}}

    where:
        \hat{H}_{\text{rot}} = \sum_{k=1}^N (\omega_x \hat{X}_k + \omega_y \hat{Y}_k + \omega_z \hat{Z}_k)
        \hat{H}_{\text{phase}} = \sum_{m=1}^N \Delta \Phi_m \hat{Z}_m + \sum_{\langle j, k \rangle} J_{jk} (\hat{X}_j \hat{X}_k + \hat{Y}_j \hat{Y}_k)
    """

    n_qubits: int
    omega: tuple[float, float, float]  # (omega_x, omega_y, omega_z)
    delta_phi: Sequence[float]         # Phase mismatch per coordinate site
    coupling_j: float = 0.0            # Inter-site exchange coupling J_jk

    def __post_init__(self):
        if len(self.delta_phi) != self.n_qubits:
            raise ValueError(f"delta_phi length ({len(self.delta_phi)}) must equal n_qubits ({self.n_qubits})")

    def build_dense_matrix(self) -> np.ndarray:
        """Constructs the exact 2^N x 2^N Hamiltonian matrix for classical verification."""
        dim = 1 << self.n_qubits
        h_matrix = np.zeros((dim, dim), dtype=complex)

        # Pauli matrices
        sx = np.array([[0, 1], [1, 0]], dtype=complex)
        sy = np.array([[0, -1j], [1j, 0]], dtype=complex)
        sz = np.array([[1, 0], [0, -1]], dtype=complex)
        eye = np.eye(2, dtype=complex)

        def get_single_pauli(op: np.ndarray, target: int) -> np.ndarray:
            res = 1
            for q in range(self.n_qubits):
                cur = op if q == target else eye
                res = np.kron(res, cur) if not isinstance(res, int) else cur
            return res

        # 1. Spatial rotation term H_rot
        wx, wy, wz = self.omega
        for k in range(self.n_qubits):
            h_matrix += wx * get_single_pauli(sx, k)
            h_matrix += wy * get_single_pauli(sy, k)
            h_matrix += wz * get_single_pauli(sz, k)

        # 2. Phase cascading mismatch term H_phase
        for m in range(self.n_qubits):
            h_matrix += self.delta_phi[m] * get_single_pauli(sz, m)

        # 3. Inter-qubit exchange coupling J_jk
        if abs(self.coupling_j) > 1e-12 and self.n_qubits > 1:
            for j in range(self.n_qubits - 1):
                xx = np.kron(
                    np.kron(np.eye(1 << j), sx),
                    np.kron(sx, np.eye(1 << (self.n_qubits - j - 2)))
                )
                yy = np.kron(
                    np.kron(np.eye(1 << j), sy),
                    np.kron(sy, np.eye(1 << (self.n_qubits - j - 2)))
                )
                h_matrix += self.coupling_j * (xx + yy)

        return h_matrix

    def get_evolution_unitary(self, tau: float) -> np.ndarray:
        """Calculates U_tube(tau) = exp(-i * tau * H_tube)."""
        h_mat = self.build_dense_matrix()
        return scipy.linalg.expm(-1j * tau * h_mat)


def decompose_rotation_euler(omega: tuple[float, float, float], tau: float) -> tuple[float, float, float]:
    """Decomposes a 3D angular rotation vector omega * tau into Euler rotation angles (alpha, beta, gamma).

    Returns:
        (theta_z1, theta_y, theta_z2) corresponding to Rz(theta_z1) Ry(theta_y) Rz(theta_z2).
    """
    wx, wy, wz = omega
    theta = np.sqrt(wx**2 + wy**2 + wz**2) * tau
    if theta < 1e-14:
        return (0.0, 0.0, 0.0)

    nx, ny, nz = wx / (theta / tau), wy / (theta / tau), wz / (theta / tau)
    # Convert axis-angle to ZYZ Euler angles
    cos_half = np.cos(theta / 2.0)
    sin_half = np.sin(theta / 2.0)

    # Quaternion representation
    qw = cos_half
    qx = nx * sin_half
    qy = ny * sin_half
    qz = nz * sin_half

    # Euler angles Z-Y-Z
    beta = 2.0 * np.arccos(np.clip(np.sqrt(qw**2 + qz**2), 0.0, 1.0))
    if np.sin(beta) > 1e-7:
        alpha = np.arctan2(qz, qw) + np.arctan2(qx, qy)
        gamma = np.arctan2(qz, qw) - np.arctan2(qx, qy)
    else:
        alpha = 2.0 * np.arctan2(qz, qw)
        beta = 0.0
        gamma = 0.0

    return float(alpha), float(beta), float(gamma)


def compute_phase_mismatch(pocket_phases: Sequence[float], ligand_phases: Sequence[float]) -> list[float]:
    """Calculates site-wise phase discrepancy delta_phi = (phi_pocket - phi_ligand)."""
    if len(pocket_phases) != len(ligand_phases):
        raise ValueError("Pocket and ligand phase vectors must have identical dimensions.")
    return [float(p - l) for p, l in zip(pocket_phases, ligand_phases)]
