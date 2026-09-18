"""Classical HPC Embedding Bridge for Project Q-Rotate.

Parses 3D molecular coordinates and electrostatic potential features into
qubit quantum states and phase vectors for the Q-Rotate quantum engine.
Supports single-shell O(1) invariant encoding (4 qubits, H2) and
multi-resolution dual-shell encoding (8 qubits, Helios-ready).
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

    def apply_dihedral_torsion(
        self,
        torsion_angle_deg: float,
        split_ratio: float = 0.5,
    ) -> "MolecularGeometry":
        """Applies internal torsional rotation to sidechain rotamers.

        Simulates flexible SO(3) x U(1) induced-fit docking by rotating
        exterior sidechain atoms around an internal dihedral bond vector.
        """
        com = self.center_of_mass()
        rel_coords = self.coordinates - com
        r = np.linalg.norm(rel_coords, axis=1)
        r_cutoff = np.median(r) if len(r) > 0 else 0.0

        rad = np.radians(torsion_angle_deg)
        c, s = np.cos(rad), np.sin(rad)
        rot_z = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])

        new_coords = self.coordinates.copy()
        for idx in range(len(self.coordinates)):
            if r[idx] > r_cutoff:
                # Exterior sidechain atom: apply internal rotamer torsion
                rel = new_coords[idx] - com
                new_coords[idx] = com + rel @ rot_z.T

        return MolecularGeometry(
            name=f"{self.name}_torsion_{torsion_angle_deg}deg",
            atom_names=self.atom_names,
            coordinates=new_coords,
            charges=self.charges,
        )


def pocket_ligand_to_qubit_phases(
    geometry: MolecularGeometry,
    n_qubits: int = 4,
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
    phi = np.arctan2(rel_coords[:, 1], rel_coords[:, 0])

    phases = []
    chunk_size = max(1, len(coords) // n_qubits)
    for q in range(n_qubits):
        start_idx = q * chunk_size
        end_idx = min(len(coords), (q + 1) * chunk_size) if q < n_qubits - 1 else len(coords)
        if start_idx >= len(coords):
            phases.append(0.0)
            continue

        spatial_phase = np.mean(phi[start_idx:end_idx])
        charge_weight = np.mean(charges[start_idx:end_idx]) if len(charges) > 0 else 0.0
        combined = (spatial_phase + feature_scale * charge_weight) % (2.0 * np.pi)
        if combined > np.pi:
            combined -= 2.0 * np.pi
        phases.append(float(combined))

    return phases


def pocket_ligand_to_multi_shell_phases(
    geometry: MolecularGeometry,
    n_shells: int = 2,
    qubits_per_shell: int = 4,
    feature_scale: float = 1.0,
) -> list[float]:
    r"""Multi-Resolution Dual-Shell Spherical Harmonic Phase Encoding.

    Decomposes the molecular cluster into concentric radial shells:
    - Shell 0: Core Pharmacophore Cavity (r <= r_median)
    - Shell 1: Flexible Sidechain Rotamer Envelope (r > r_median)

    Returns a total of (n_shells * qubits_per_shell) continuous phases (8 qubits for Helios).
    """
    coords = geometry.coordinates
    charges = geometry.charges
    total_qubits = n_shells * qubits_per_shell

    if len(coords) == 0:
        return [0.0] * total_qubits

    com = np.mean(coords, axis=0)
    rel_coords = coords - com
    r = np.linalg.norm(rel_coords, axis=1)
    phi = np.arctan2(rel_coords[:, 1], rel_coords[:, 0])

    # Compute radial median threshold
    r_med = float(np.median(r))

    inner_mask = r <= r_med
    outer_mask = r > r_med

    # Handle edge case where all points fall in one shell
    if not np.any(inner_mask):
        inner_mask = np.ones(len(coords), dtype=bool)
    if not np.any(outer_mask):
        outer_mask = inner_mask

    all_phases = []
    for shell_idx, mask in enumerate([inner_mask, outer_mask][:n_shells]):
        shell_coords = coords[mask]
        shell_charges = charges[mask]
        shell_phi = phi[mask]

        chunk = max(1, len(shell_coords) // qubits_per_shell)
        for q in range(qubits_per_shell):
            s_idx = q * chunk
            e_idx = min(len(shell_coords), (q + 1) * chunk) if q < qubits_per_shell - 1 else len(shell_coords)
            if s_idx >= len(shell_coords):
                all_phases.append(0.0)
                continue

            sp = np.mean(shell_phi[s_idx:e_idx])
            cw = np.mean(shell_charges[s_idx:e_idx]) if len(shell_charges) > 0 else 0.0
            comb = (sp + feature_scale * cw) % (2.0 * np.pi)
            if comb > np.pi:
                comb -= 2.0 * np.pi
            all_phases.append(float(comb))

    while len(all_phases) < total_qubits:
        all_phases.append(0.0)

    return all_phases[:total_qubits]


def generate_synthetic_binding_pair(
    n_sites: int = 4,
    rotation_angle_deg: float = 15.0,
    noise_sigma: float = 0.05,
    torsion_angle_deg: float = 0.0,
) -> tuple[MolecularGeometry, MolecularGeometry, list[float]]:
    """Generates a synthetic complementary pocket-ligand pair for testing."""
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

    rot_rad = np.radians(rotation_angle_deg)
    rot_matrix = np.array([
        [np.cos(rot_rad), -np.sin(rot_rad), 0.0],
        [np.sin(rot_rad),  np.cos(rot_rad), 0.0],
        [0.0,             0.0,             1.0],
    ])

    ligand_coords = pocket_coords @ rot_matrix.T + np.random.normal(0, noise_sigma, pocket_coords.shape)
    ligand_charges = -pocket_charges

    ligand_geo = MolecularGeometry(
        name="Candidate_Ligand",
        atom_names=[f"L_{i}" for i in range(n_sites)],
        coordinates=ligand_coords,
        charges=ligand_charges,
    )

    if abs(torsion_angle_deg) > 1e-6:
        ligand_geo = ligand_geo.apply_dihedral_torsion(torsion_angle_deg)

    pocket_phases = pocket_ligand_to_qubit_phases(pocket_geo, n_sites)
    ligand_phases = pocket_ligand_to_qubit_phases(ligand_geo, n_sites)
    delta_phi = [p - l for p, l in zip(pocket_phases, ligand_phases)]

    return pocket_geo, ligand_geo, delta_phi
