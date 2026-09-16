"""Classical HPC Embedding Bridge for Project Q-Rotate.

Parses 3D molecular coordinates and electrostatic potential features into
qubit quantum states and phase vectors for the Q-Rotate quantum engine.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class MolecularGeometry:
    """Represents a set of atoms with 3D coordinates and optional partial charges."""
    name: str
    atom_names: list[str]
    coordinates: np.ndarray  # Shape: (N, 3) in Angstroms
    charges: np.ndarray = field(default_factory=lambda: np.zeros(0))

    def __post_init__(self):
        self.coordinates = np.asarray(self.coordinates, dtype=float)
        if len(self.charges) == 0:
            self.charges = np.zeros(len(self.coordinates))
        else:
            self.charges = np.asarray(self.charges, dtype=float)

    @property
    def n_atoms(self) -> int:
        return len(self.coordinates)

    def center_of_mass(self) -> np.ndarray:
        return np.mean(self.coordinates, axis=0)

    def translate(self, vector: np.ndarray) -> "MolecularGeometry":
        return MolecularGeometry(
            name=f"{self.name}_translated",
            atom_names=self.atom_names,
            coordinates=self.coordinates + vector,
            charges=self.charges,
        )

    def rotate_3d(self, rot_matrix: np.ndarray) -> "MolecularGeometry":
        com = self.center_of_mass()
        centered = self.coordinates - com
        rotated = centered @ rot_matrix.T + com
        return MolecularGeometry(
            name=f"{self.name}_rotated",
            atom_names=self.atom_names,
            coordinates=rotated,
            charges=self.charges,
        )


def pocket_ligand_to_qubit_phases(
    geometry: MolecularGeometry,
    n_qubits: int,
    feature_scale: float = 1.0,
) -> list[float]:
    r"""Encodes spatial coordinates and electrostatic charges into qubit phase angles \Phi \in [-\pi, \pi].

    Uses spherical harmonic or radial-polar projections to map N-atom clusters
    into compact n-qubit phase registers.
    """
    coords = geometry.coordinates
    charges = geometry.charges

    if len(coords) == 0:
        return [0.0] * n_qubits

    # Radial distances from center of geometry
    com = np.mean(coords, axis=0)
    rel_coords = coords - com
    r = np.linalg.norm(rel_coords, axis=1)

    # Angular spherical components
    theta = np.arccos(np.clip(rel_coords[:, 2] / (r + 1e-10), -1.0, 1.0))
    phi = np.arctan2(rel_coords[:, 1], rel_coords[:, 0])

    phases = []
    chunk_size = max(1, len(coords) // n_qubits)
    for q in range(n_qubits):
        start_idx = q * chunk_size
        end_idx = min(len(coords), (q + 1) * chunk_size) if q < n_qubits - 1 else len(coords)
        if start_idx >= len(coords):
            phases.append(0.0)
            continue

        # Combine weighted spatial angles and partial charge polarities
        spatial_phase = np.mean(phi[start_idx:end_idx])
        charge_weight = np.mean(charges[start_idx:end_idx]) if len(charges) > 0 else 0.0
        combined = (spatial_phase + feature_scale * charge_weight) % (2.0 * np.pi)
        # Normalize to [-pi, pi]
        if combined > np.pi:
            combined -= 2.0 * np.pi
        phases.append(float(combined))

    return phases


def generate_synthetic_binding_pair(
    n_sites: int = 4,
    rotation_angle_deg: float = 15.0,
    noise_sigma: float = 0.05,
) -> tuple[MolecularGeometry, MolecularGeometry, list[float]]:
    """Generates a synthetic complementary pocket-ligand pair for testing.

    Args:
        n_sites: Number of binding contact points.
        rotation_angle_deg: Misalignment angle around Z-axis in degrees.
        noise_sigma: Random perturbation magnitude.

    Returns:
        (pocket_geo, ligand_geo, true_delta_phi)
    """
    # Create pocket contact sites on a sphere
    phi_grid = np.linspace(0, 2 * np.pi, n_sites, endpoint=False)
    radius = 3.5  # Angstroms typical for pocket radius
    x = radius * np.cos(phi_grid)
    y = radius * np.sin(phi_grid)
    z = np.sin(phi_grid * 2) * 0.8
    pocket_coords = np.column_stack([x, y, z])
    pocket_charges = np.array([0.2 if i % 2 == 0 else -0.2 for i in range(n_sites)])

    pocket_geo = MolecularGeometry(
        name="Target_Binding_Pocket",
        atom_names=[f"P_{i}" for i in range(n_sites)],
        coordinates=pocket_coords,
        charges=pocket_charges,
    )

    # Generate ligand with misalignment rotation
    rot_rad = np.radians(rotation_angle_deg)
    rot_matrix = np.array([
        [np.cos(rot_rad), -np.sin(rot_rad), 0.0],
        [np.sin(rot_rad),  np.cos(rot_rad), 0.0],
        [0.0,             0.0,             1.0],
    ])

    ligand_coords = pocket_coords @ rot_matrix.T + np.random.normal(0, noise_sigma, pocket_coords.shape)
    ligand_charges = -pocket_charges  # Complementary electrostatic charges

    ligand_geo = MolecularGeometry(
        name="Candidate_Ligand",
        atom_names=[f"L_{i}" for i in range(n_sites)],
        coordinates=ligand_coords,
        charges=ligand_charges,
    )

    pocket_phases = pocket_ligand_to_qubit_phases(pocket_geo, n_sites)
    ligand_phases = pocket_ligand_to_qubit_phases(ligand_geo, n_sites)
    delta_phi = [p - l for p, l in zip(pocket_phases, ligand_phases)]

    return pocket_geo, ligand_geo, delta_phi
