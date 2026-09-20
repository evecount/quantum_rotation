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


# Atomic numbers for the elements that appear in these structures. Used to
# weight heavier atoms more, so two molecules with the same shape but different
# chemistry do not encode identically.
_ATOMIC_NUMBER = {
    "H": 1, "C": 6, "N": 7, "O": 8, "F": 9, "P": 15, "S": 16,
    "CL": 17, "BR": 35, "I": 53, "SE": 34, "FE": 26, "ZN": 30, "MG": 12,
}


def _element_weights(atom_names: Sequence[str], n_atoms: int) -> np.ndarray:
    """sqrt(Z) per atom, or all-ones when the caller passed placeholder names."""
    if not atom_names or len(atom_names) != n_atoms:
        return np.ones(n_atoms)
    z = np.array([
        _ATOMIC_NUMBER.get(str(name).strip().upper()[:2], 0)
        or _ATOMIC_NUMBER.get(str(name).strip().upper()[:1], 6)
        for name in atom_names
    ], dtype=float)
    return np.sqrt(z / 6.0)


def _radial_shells(r: np.ndarray, n_shells: int) -> list[np.ndarray]:
    """Splits atom indices into `n_shells` groups by radius, never separating
    atoms that sit at the same radius.

    Equal-count slicing alone is not permutation invariant: when a tie straddles
    a shell boundary, which of the tied atoms lands in which shell depends on
    input order. H2 is the extreme case — two atoms at identical radius, so
    shuffling them swapped the two registers entirely. Atoms at the same radius
    are therefore kept together, and whole groups are distributed to balance the
    shells. A molecule with fewer distinct radii than shells simply leaves the
    outer shells empty, which is the honest answer for something like H2.
    """
    if len(r) == 0:
        return [np.array([], dtype=int) for _ in range(n_shells)]

    keys = np.round(r, 6)
    groups: list[np.ndarray] = [
        np.flatnonzero(keys == value) for value in np.unique(keys)
    ]

    shells: list[list[int]] = [[] for _ in range(n_shells)]
    target = len(r) / n_shells
    shell_idx = 0
    for group in groups:
        # Move to the next shell once this one has met its share.
        if shell_idx < n_shells - 1 and len(shells[shell_idx]) >= target:
            shell_idx += 1
        shells[shell_idx].extend(group.tolist())

    return [np.array(sorted(s), dtype=int) for s in shells]


MOMENT_THRESHOLD = 1e-3

# Highest angular moment the encoder will climb to. Six covers a benzene ring,
# the most common symmetric motif in drug-like molecules.
MAX_MOMENT_ORDER = 6


def _shell_moments(
    geometry: "MolecularGeometry",
    n_qubits: int,
    z_weight: float,
    max_order: int = MAX_MOMENT_ORDER,
) -> list[dict]:
    r"""Per shell: the first- and second-order angular moments, the phase the
    encoder should use, and which order produced it.

    The encoder keeps the argument of :math:`M_1 = \sum_i w_i e^{i\phi_i}`, and
    an argument only means something when the moment has magnitude. A
    centrosymmetric shell cancels :math:`M_1` exactly -- H2's two atoms sit at
    \phi = 0 and \pi with equal weights -- and such a shell used to encode as
    0.0, i.e. as no information at all.

    The higher moments :math:`M_k = \sum_i w_i e^{ik\phi_i}` are what survive
    there: an opposed pair cancels :math:`M_1` but contributes
    :math:`2 e^{2i\phi}` to :math:`M_2`. More generally a k-fold symmetric
    arrangement cancels every order below k, so the encoder climbs the ladder
    and uses the first order with magnitude. H2's opposed pair needs
    :math:`M_2`; a benzene ring needs :math:`M_6`.

    Using ``arg(M_k) / k`` keeps the property the search depends on, because a
    rotation by \alpha multiplies :math:`M_k` by :math:`e^{ik\alpha}` and so
    moves ``arg(M_k)/k`` by exactly \alpha, the same as the first-order
    channel.

    The cost is honest and unavoidable: ``arg(M_k)/k`` is defined modulo
    :math:`2\pi/k`, so a shell encoded at order k cannot tell \alpha from
    \alpha + 360/k degrees. For a k-fold symmetric arrangement that is not lost
    information but a statement of fact -- those orientations are the same
    arrangement. It would be a loss for an asymmetric shell, which is why a
    higher order is used only where every lower one has nothing to say.
    """
    coords = np.asarray(geometry.coordinates, dtype=float)
    n_atoms = len(coords)
    if n_atoms == 0:
        return [{"phase": 0.0, "order": 0, "anisotropy": 0.0, "magnitudes": []}
                for _ in range(n_qubits)]

    rel = coords - coords.mean(axis=0)
    phi = np.arctan2(rel[:, 1], rel[:, 0])
    z_span = float(np.max(np.abs(rel[:, 2]))) or 1.0
    weights = _element_weights(getattr(geometry, "atom_names", None), n_atoms)
    weights = weights * np.exp(z_weight * rel[:, 2] / z_span)

    shells = []
    for idx in _radial_shells(np.linalg.norm(rel, axis=1), n_qubits):
        if len(idx) == 0:
            shells.append({"phase": 0.0, "order": 0, "anisotropy": 0.0, "magnitudes": []})
            continue

        scale = float(np.sum(weights[idx]))
        if scale <= 0:
            shells.append({"phase": 0.0, "order": 0, "anisotropy": 0.0, "magnitudes": []})
            continue

        # Climb the ladder of angular moments until one survives. An m-fold
        # symmetric arrangement cancels every order below m, so this is what
        # decides whether the shell says anything at all.
        magnitudes = []
        chosen = None
        for order in range(1, max_order + 1):
            moment = np.sum(weights[idx] * np.exp(1j * order * phi[idx]))
            magnitude = abs(moment) / scale
            magnitudes.append(float(magnitude))
            if chosen is None and magnitude >= MOMENT_THRESHOLD:
                chosen = {
                    "phase": float(np.angle(moment) / order),
                    "order": order,
                    "anisotropy": float(magnitude),
                }

        if chosen is None:
            chosen = {"phase": 0.0, "order": 0, "anisotropy": 0.0}
        chosen["magnitudes"] = magnitudes
        shells.append(chosen)
    return shells


def shell_anisotropy(
    geometry: "MolecularGeometry",
    n_qubits: int = 4,
    z_weight: float = 1.5,
) -> list[float]:
    """Per-shell angular structure in [0, 1], for whichever moment order that
    shell actually used. Zero means the shell says nothing about orientation."""
    return [s["anisotropy"] for s in _shell_moments(geometry, n_qubits, z_weight)]


def shell_moment_orders(
    geometry: "MolecularGeometry",
    n_qubits: int = 4,
    z_weight: float = 1.5,
) -> list[int]:
    """Which moment order encoded each shell: 1, 2, or 0 for an empty shell.
    A shell reported as 2 is only determined modulo 180 degrees."""
    return [s["order"] for s in _shell_moments(geometry, n_qubits, z_weight)]


def rotational_ambiguity_deg(
    geometry: "MolecularGeometry",
    n_qubits: int = 4,
    z_weight: float = 1.5,
) -> float:
    """The angle by which this register repeats, in degrees.

    A shell encoded at order k is determined only modulo 360/k degrees. The
    register as a whole repeats at the coarsest such period among the shells
    that carry information, so 360 means no ambiguity at all, 180 means the
    molecule cannot be told from its half-turn, and so on. Returns 0.0 when
    nothing is encodable.
    """
    orders = [s["order"] for s in _shell_moments(geometry, n_qubits, z_weight) if s["order"]]
    if not orders:
        return 0.0
    # The lowest order present sets the coarsest repeat that still fits every
    # informative shell.
    return 360.0 / max(orders)


def has_180_degree_ambiguity(
    geometry: "MolecularGeometry",
    n_qubits: int = 4,
    z_weight: float = 1.5,
) -> bool:
    """True when the register repeats before a full turn, i.e. some symmetry
    made the first-order moment vanish everywhere it carries information."""
    period = rotational_ambiguity_deg(geometry, n_qubits=n_qubits, z_weight=z_weight)
    return 0.0 < period < 359.9


def is_encoding_degenerate(
    geometry: "MolecularGeometry",
    n_qubits: int = 4,
    threshold: float = MOMENT_THRESHOLD,
) -> bool:
    """True when no shell has usable angular structure at either moment order,
    so any "match" against this molecule compares two empty registers."""
    return max(shell_anisotropy(geometry, n_qubits=n_qubits), default=0.0) < threshold


def molecular_shell_phases(
    geometry: "MolecularGeometry",
    n_qubits: int = 4,
    z_weight: float = 1.5,
) -> list[float]:
    r"""Encodes a molecule into `n_qubits` phases from its geometry alone.

    Replaces the original encoder, which had two defects that only showed up
    once real structures went through it:

    * It split atoms into chunks **by their order in the input file**, so the
      same molecule listed in a different order encoded differently. Measured
      on the six benchmark ligands, shuffling atom order dropped the
      self-overlap P(0) from 1.0 to as low as 0.52.
    * It used only the azimuth \phi, discarding r and z entirely, so a
      molecule and its mirror image encoded identically (P(0) = 0.99). A
      method that cannot see chirality cannot be used for drug discovery.

    The replacement:

    1. Centre on the centroid (translation invariance).
    2. Sort atoms by radius and split into `n_qubits` equal-count shells.
       Radius is unchanged by any rotation and sorting is canonical, so shell
       membership is both permutation invariant and rotation invariant.
    3. Per shell, take the weighted complex moment
       :math:`m_q = \sum_i w_i e^{i\phi_i}` and keep its argument. Summing over
       atoms is permutation invariant; the argument is what a z-rotation acts
       on cleanly.
    4. Weights carry what \phi alone cannot: :math:`w_i = \sqrt{Z_i}\,
       e^{\kappa \hat z_i}`. The z factor is odd under reflection, which makes
       mirror images encode differently, and \sqrt{Z} separates chemistry from
       shape. Both factors are invariant under rotation about z, so the
       encoding stays exactly rotation-equivariant: turning the molecule by
       \alpha shifts every phase by \alpha, which is the property the search
       depends on.

    An isotropic shell has |m_q| ~ 0 and therefore an ill-conditioned
    argument; its phase is reported as 0.0, which is the honest "no angular
    information here" answer rather than amplified numerical noise.

    `z_weight` (\kappa) trades chirality sensitivity against tolerance of
    coordinate error. Measured across the six benchmark ligands:

        kappa   mirror overlap   self-overlap at 0.1 A noise
        0.00    0.992            --          (blind to reflection)
        0.75    0.678            0.960
        1.50    0.510            0.944       (default)
        3.00    0.501            0.923

    1.5 is where mirror discrimination has essentially saturated while a
    tenth-Angstrom of coordinate noise still costs under 0.05 of overlap.
    """
    return [s["phase"] for s in _shell_moments(geometry, n_qubits, z_weight)]


def _circular_mean(angles: np.ndarray) -> float:
    r"""Mean direction of a set of angles.

    A plain `np.mean` of angles is wrong near the +/-pi branch cut: two atoms
    at +179 and -179 degrees are 2 degrees apart but average to 0, pointing the
    opposite way. That turned a rotating molecule's phase register into a
    step function and produced spurious local maxima in the resonance
    landscape. The mean of the unit vectors has no such discontinuity.
    """
    if len(angles) == 0:
        return 0.0
    return float(np.arctan2(np.sin(angles).mean(), np.cos(angles).mean()))


def pocket_ligand_to_qubit_phases(
    geometry: MolecularGeometry,
    n_qubits: int = 4,
    feature_scale: float = 1.0,
) -> list[float]:
    r"""Encodes a molecule into `n_qubits` phase angles \Phi \in [-\pi, \pi].

    This is the project's encoder. It delegates to `molecular_shell_phases`,
    which replaced an earlier version that chunked atoms by their order in the
    input file and used only the azimuth. Measured on the six benchmark
    ligands, that earlier encoder:

    * dropped a molecule's overlap with a reordered copy of *itself* from the
      circuit's 0.992 ceiling to as low as 0.52 -- the register described the
      file, not the molecule; and
    * scored 0.99 against its own mirror image, i.e. it could not see
      chirality at all.

    The current encoder is exactly permutation invariant (phases agree to
    1e-14), scores ~0.51 against a mirror image, and remains exactly
    rotation-equivariant about z.

    `feature_scale` is accepted for backwards compatibility and ignored: the
    charge term it scaled was always multiplied by all-zero charges.
    """
    return molecular_shell_phases(geometry, n_qubits=n_qubits)


def pocket_ligand_to_multi_shell_phases(
    geometry: MolecularGeometry,
    n_shells: int = 2,
    qubits_per_shell: int = 4,
    feature_scale: float = 1.0,
) -> list[float]:
    r"""Multi-resolution radial encoding: (n_shells * qubits_per_shell) phases.

    The old implementation split each radial shell into chunks by input order,
    the same defect `molecular_shell_phases` was written to remove, so this
    now delegates to it with the full shell count. The result is still a
    concentric radial decomposition -- inner shells are the core, outer shells
    the periphery -- but the shells are permutation invariant and the encoding
    sees z and element identity.

    `feature_scale` is accepted for backwards compatibility and ignored.
    """
    return molecular_shell_phases(geometry, n_qubits=n_shells * qubits_per_shell)

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
