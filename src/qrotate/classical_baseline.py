"""Fair classical baselines for the Q-Rotate pose-recovery benchmark.

The published "classical baseline" in `metrics.benchmark_classical_docking`
is a brute-force 30-degree Euler grid, and the 1,920x-3,360x figures in the
showdown are step counts against that grid. A computational chemist would
not run that grid. The standard tools for "do these two shapes match, and
in what orientation?" are:

* **USR** (Ultrafast Shape Recognition, Ballester & Richards 2007): twelve
  moments of the atom-distance distributions to four reference points. It is
  rotation *invariant*, so it answers "same shape?" in microseconds with no
  search at all, and by the same token it cannot return a pose.
* **Gaussian volume overlap** (Grant, Gallardo & Pickup 1996; the score behind
  ROCS): each atom is a Gaussian, the overlap integral has a closed form, and
  shape similarity is the Tanimoto of self and cross overlaps. It depends on
  orientation, so it is optimised: here by a grid about z at the resolution
  the quantum RUS schedule reaches, by an unconstrained scipy minimisation
  over three Euler angles, and by the ROCS-style principal-axes start.

This module runs those on the same six ligands, the same start misalignments
and the same success criteria as the quantum runs, and measures how well the
4- and 8-phase quantum fingerprint preserves the ranking the classical scores
give across ligand pairs. `python -m src.qrotate.classical_baseline` writes
benchmarks/classical_baseline.json.
"""

from __future__ import annotations

import json
import os
import time
import zlib
from dataclasses import dataclass, asdict
from typing import Callable, Optional, Sequence

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import spearmanr

try:
    from .hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases, has_180_degree_ambiguity
    from .structures import load_active_sites, site_elements
    from .circuits import simulate_swap_test_statevector, simulate_shot_sampling
    from .metrics import (
        REAL_MOLECULE_SYSTEMS, _rotate_z, _wrap_deg, pose_error_deg,
        run_blind_rus_pose_recovery, _wilson_interval,
    )
except ImportError:  # pragma: no cover - script execution
    from src.qrotate.hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases, has_180_degree_ambiguity
    from src.qrotate.structures import load_active_sites, site_elements
    from src.qrotate.circuits import simulate_swap_test_statevector, simulate_shot_sampling
    from src.qrotate.metrics import (
        REAL_MOLECULE_SYSTEMS, _rotate_z, _wrap_deg, pose_error_deg,
        run_blind_rus_pose_recovery, _wilson_interval,
    )

TAU, OMEGA = 0.25, (1.0, 0.5, 0.25)

# The RUS pose search steps 60/sqrt(k+1) degrees at iteration k and runs 15
# iterations, so the finest step it ever takes is 60/sqrt(15) = 15.5 degrees.
# A 15-degree grid about z (24 evaluations) is the classical search at that
# resolution.
QUANTUM_EFFECTIVE_STEP_DEG = 60.0 / np.sqrt(15.0)
Z_GRID_STEP_DEG = 15.0

# Standard docking success criterion: heavy-atom RMSD within 2.0 A of the
# deposited pose. 1.0 A is also reported as the stricter bar.
RMSD_SUCCESS_A = 2.0
RMSD_STRICT_A = 1.0

# Bondi van der Waals radii in Angstrom.
_VDW_RADIUS = {
    "H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "F": 1.47, "P": 1.80,
    "S": 1.80, "CL": 1.75, "BR": 1.85, "I": 1.98, "SE": 1.90,
}
# Grant & Pickup Gaussian prefactor: a Gaussian of height p = 2.7 with
# alpha = pi (3p / (4 pi r^3))^(2/3) has the same volume as a hard sphere of
# radius r.
GAUSSIAN_P = 2.7


# =====================================================================
# 1. USR: twelve rotation-invariant distance moments
# =====================================================================

def _moments(d: np.ndarray) -> tuple[float, float, float]:
    mu = float(d.mean())
    c = d - mu
    m2 = float(np.mean(c ** 2))
    m3 = float(np.mean(c ** 3))
    return mu, float(np.sqrt(m2)), float(np.cbrt(m3))


def usr_descriptor(coords: np.ndarray) -> np.ndarray:
    """Ballester & Richards' 12 USR moments: mean, standard deviation and
    cube-root skew of the distances from every atom to (1) the centroid,
    (2) the atom closest to it, (3) the atom farthest from it and (4) the
    atom farthest from that one. Only distances enter, so the descriptor is
    exactly invariant to rotation and translation."""
    c = np.asarray(coords, dtype=float)
    ctd = c.mean(axis=0)
    d_ctd = np.linalg.norm(c - ctd, axis=1)
    cst = c[int(np.argmin(d_ctd))]
    fct = c[int(np.argmax(d_ctd))]
    d_fct = np.linalg.norm(c - fct, axis=1)
    ftf = c[int(np.argmax(d_fct))]
    out = []
    for ref in (ctd, cst, fct, ftf):
        out.extend(_moments(np.linalg.norm(c - ref, axis=1)))
    return np.array(out)


def usr_similarity(coords_a: np.ndarray, coords_b: np.ndarray) -> float:
    """USR similarity in (0, 1]: 1 / (1 + mean |descriptor difference|)."""
    return float(1.0 / (1.0 + np.mean(np.abs(usr_descriptor(coords_a) - usr_descriptor(coords_b)))))


# =====================================================================
# 2. Gaussian volume overlap (ROCS-style shape Tanimoto)
# =====================================================================

def _alphas(elements: Sequence[str], n_atoms: int) -> np.ndarray:
    if not elements or len(elements) != n_atoms:
        radii = np.full(n_atoms, _VDW_RADIUS["C"])
    else:
        radii = np.array([_VDW_RADIUS.get(str(e).strip().upper(), _VDW_RADIUS["C"]) for e in elements])
    return np.pi * (3.0 * GAUSSIAN_P / (4.0 * np.pi * radii ** 3)) ** (2.0 / 3.0)


def gaussian_overlap(coords_a, alpha_a, coords_b, alpha_b) -> float:
    """Sum over atom pairs of the overlap integral of two atom Gaussians,
    p exp(-alpha_i |r - R_i|^2): the first-order term of Grant & Pickup's
    Gaussian volume overlap, which is the ROCS shape score."""
    a = np.asarray(coords_a, dtype=float)
    b = np.asarray(coords_b, dtype=float)
    d2 = np.sum((a[:, None, :] - b[None, :, :]) ** 2, axis=2)
    s = alpha_a[:, None] + alpha_b[None, :]
    k = alpha_a[:, None] * alpha_b[None, :] / s
    return float(GAUSSIAN_P ** 2 * np.sum((np.pi / s) ** 1.5 * np.exp(-k * d2)))


class GaussianShape:
    """A molecule as a sum of atom Gaussians, with its self-overlap cached."""

    def __init__(self, coords: np.ndarray, elements: Sequence[str] = ()):
        self.coords = np.asarray(coords, dtype=float)
        self.alpha = _alphas(elements, len(self.coords))
        self.self_overlap = gaussian_overlap(self.coords, self.alpha, self.coords, self.alpha)

    def tanimoto(self, other: "GaussianShape") -> float:
        cross = gaussian_overlap(self.coords, self.alpha, other.coords, other.alpha)
        return cross / (self.self_overlap + other.self_overlap - cross)


def gaussian_tanimoto(coords_a, elements_a, coords_b, elements_b) -> float:
    return GaussianShape(coords_a, elements_a).tanimoto(GaussianShape(coords_b, elements_b))


# =====================================================================
# 3. Rotations and pose error
# =====================================================================

def rotation_z(deg: float) -> np.ndarray:
    a = np.radians(deg)
    return np.array([[np.cos(a), -np.sin(a), 0.0], [np.sin(a), np.cos(a), 0.0], [0.0, 0.0, 1.0]])


def rotation_y(deg: float) -> np.ndarray:
    a = np.radians(deg)
    return np.array([[np.cos(a), 0.0, np.sin(a)], [0.0, 1.0, 0.0], [-np.sin(a), 0.0, np.cos(a)]])


def rotation_euler(alpha: float, beta: float, gamma: float) -> np.ndarray:
    """z-y-z Euler rotation, angles in degrees."""
    return rotation_z(alpha) @ rotation_y(beta) @ rotation_z(gamma)


def rotate_about_centroid(coords: np.ndarray, rot: np.ndarray) -> np.ndarray:
    centroid = coords.mean(axis=0)
    return (coords - centroid) @ rot.T + centroid


def rotation_angle_deg(rot: np.ndarray) -> float:
    """Geodesic angle of a rotation matrix, in degrees."""
    return float(np.degrees(np.arccos(np.clip((np.trace(rot) - 1.0) / 2.0, -1.0, 1.0))))


def rotation_error_deg(found: np.ndarray, true: np.ndarray, ambiguous_180: bool = False) -> float:
    """Angle between a found rotation and the true one. For a molecule whose
    register repeats every 180 degrees about z, the half-turn partner counts
    as right, the same allowance the quantum benchmark gets."""
    err = rotation_angle_deg(found @ true.T)
    if ambiguous_180:
        err = min(err, rotation_angle_deg(found @ (rotation_z(180.0) @ true).T))
    return err


def ligand_rmsd(coords: np.ndarray, reference: np.ndarray, ambiguous_180: bool = False) -> float:
    """Heavy-atom RMSD with the deposited atom correspondence. A 180-degree
    ambiguous molecule (H2) also gets the reversed correspondence, since its
    half-turn is the same arrangement with the labels swapped."""
    rmsd = float(np.sqrt(np.mean(np.sum((coords - reference) ** 2, axis=1))))
    if ambiguous_180:
        rmsd = min(rmsd, float(np.sqrt(np.mean(np.sum((coords - reference[::-1]) ** 2, axis=1)))))
    return rmsd


# =====================================================================
# 4. Pose searches
# =====================================================================

@dataclass
class ClassicalPoseResult:
    method: str
    rotation: np.ndarray
    score: float
    evaluations: int
    wall_clock_sec: float
    recovered_coords: np.ndarray
    detail: dict


class _Counter:
    def __init__(self, fn: Callable[[np.ndarray], float]):
        self.fn, self.n = fn, 0

    def __call__(self, rot: np.ndarray) -> float:
        self.n += 1
        return self.fn(rot)


def _make_scorer(reference: GaussianShape, probe_coords: np.ndarray, probe_alpha: np.ndarray):
    probe_centroid = probe_coords.mean(axis=0)
    centred = probe_coords - probe_centroid
    # Self-overlap is rotation invariant, so it is computed once.
    probe_self = gaussian_overlap(probe_coords, probe_alpha, probe_coords, probe_alpha)

    def score(rot: np.ndarray) -> float:
        moved = centred @ rot.T + probe_centroid
        cross = gaussian_overlap(reference.coords, reference.alpha, moved, probe_alpha)
        return cross / (reference.self_overlap + probe_self - cross)

    return score


def search_z_grid(
    reference: GaussianShape, probe_coords: np.ndarray, probe_alpha: np.ndarray,
    step_deg: float = Z_GRID_STEP_DEG, refine: bool = True,
) -> ClassicalPoseResult:
    """Gaussian Tanimoto on a grid of rotations about z, optionally polished
    by a bounded 1-D minimisation within one grid cell of the best point."""
    t0 = time.perf_counter()
    scorer = _Counter(_make_scorer(reference, probe_coords, probe_alpha))
    angles = np.arange(-180.0, 180.0, step_deg)
    scores = [scorer(rotation_z(a)) for a in angles]
    best_i = int(np.argmax(scores))
    best_angle, best_score = float(angles[best_i]), scores[best_i]
    if refine:
        res = minimize_scalar(lambda a: -scorer(rotation_z(a)),
                              bounds=(best_angle - step_deg, best_angle + step_deg), method="bounded",
                              options={"xatol": 1e-3})
        if -res.fun > best_score:
            best_angle, best_score = float(res.x), -res.fun
    rot = rotation_z(best_angle)
    return ClassicalPoseResult(
        method="gaussian_z_grid_refined" if refine else "gaussian_z_grid",
        rotation=rot, score=best_score, evaluations=scorer.n,
        wall_clock_sec=time.perf_counter() - t0,
        recovered_coords=rotate_about_centroid(probe_coords, rot),
        detail={"best_angle_deg": _wrap_deg(best_angle), "grid_step_deg": step_deg, "grid_points": len(angles)},
    )


def search_euler_unconstrained(
    reference: GaussianShape, probe_coords: np.ndarray, probe_alpha: np.ndarray,
    start: tuple[float, float, float] = (0.0, 0.0, 0.0), method: str = "Nelder-Mead",
) -> ClassicalPoseResult:
    """scipy.optimize.minimize of -Tanimoto over three z-y-z Euler angles,
    from a single start (the identity by default: no grid, no prior)."""
    t0 = time.perf_counter()
    scorer = _Counter(_make_scorer(reference, probe_coords, probe_alpha))
    res = minimize(lambda e: -scorer(rotation_euler(*e)), np.array(start, dtype=float),
                   method=method, options={"xatol": 1e-3, "fatol": 1e-9, "maxiter": 2000})
    rot = rotation_euler(*res.x)
    return ClassicalPoseResult(
        method="gaussian_euler_unconstrained", rotation=rot, score=-res.fun, evaluations=scorer.n,
        wall_clock_sec=time.perf_counter() - t0,
        recovered_coords=rotate_about_centroid(probe_coords, rot),
        detail={"start_euler_deg": list(start), "euler_deg": [float(x) for x in res.x],
                "optimizer": method, "converged": bool(res.success)},
    )


def _principal_axes(coords: np.ndarray) -> np.ndarray:
    c = coords - coords.mean(axis=0)
    _, vecs = np.linalg.eigh(c.T @ c)
    if np.linalg.det(vecs) < 0:
        vecs[:, 0] *= -1.0
    return vecs


def search_principal_axes(
    reference: GaussianShape, probe_coords: np.ndarray, probe_alpha: np.ndarray,
) -> ClassicalPoseResult:
    """What ROCS does: align the probe's inertial frame to the reference's,
    try the four proper sign choices, keep the best and polish it with a
    local Euler minimisation."""
    t0 = time.perf_counter()
    scorer = _Counter(_make_scorer(reference, probe_coords, probe_alpha))
    v_ref, v_probe = _principal_axes(reference.coords), _principal_axes(probe_coords)
    best_rot, best_score = None, -1.0
    for flips in ((1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)):
        rot = (v_ref * np.array(flips)) @ v_probe.T
        s = scorer(rot)
        if s > best_score:
            best_rot, best_score = rot, s
    starts = scorer.n
    # Polish in the aligned frame: optimise a small Euler correction.
    res = minimize(lambda e: -scorer(rotation_euler(*e) @ best_rot), np.zeros(3),
                   method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-9, "maxiter": 2000})
    rot = rotation_euler(*res.x) @ best_rot
    score = -res.fun if -res.fun > best_score else best_score
    if -res.fun <= best_score:
        rot = best_rot
    return ClassicalPoseResult(
        method="gaussian_principal_axes", rotation=rot, score=score, evaluations=scorer.n,
        wall_clock_sec=time.perf_counter() - t0,
        recovered_coords=rotate_about_centroid(probe_coords, rot),
        detail={"start_evaluations": starts, "polish_evaluations": scorer.n - starts},
    )


# =====================================================================
# 5. The benchmark
# =====================================================================

def _ligand(system_id: str) -> tuple[np.ndarray, list[str]]:
    site = load_active_sites().get(system_id)
    if site is None:
        raise FileNotFoundError("benchmarks/active_sites.json is missing: run `python -m src.qrotate.structures`")
    return np.array(site["ligand"]["coords"], dtype=float), list(site["ligand"]["elements"])


def _timed_median(fn: Callable[[], object], repeats: int = 5) -> tuple[object, float]:
    """Runs fn `repeats` times and returns (last result, median wall-clock)."""
    times, out = [], None
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t0)
    return out, float(np.median(times))


def _pose_row(res: ClassicalPoseResult, reference: np.ndarray, true_rot: np.ndarray,
              ambiguous_180: bool, wall: float) -> dict:
    rmsd = ligand_rmsd(res.recovered_coords, reference, ambiguous_180)
    return {
        "method": res.method,
        "recovered_2A": bool(rmsd <= RMSD_SUCCESS_A),
        "recovered_1A": bool(rmsd <= RMSD_STRICT_A),
        "pose_error_deg": round(rotation_error_deg(res.rotation, true_rot, ambiguous_180), 2),
        "ligand_rmsd_A": round(rmsd, 3),
        "score": round(res.score, 4),
        "score_evaluations": res.evaluations,
        "wall_clock_sec": round(wall, 6),
        **res.detail,
    }


def _closed_form_sampler(target_phases, probe_phases, shots: int, seed: int):
    p0 = product_state_p0(target_phases, probe_phases)
    return p0, simulate_shot_sampling(p0, n_shots=shots, seed=seed)


def quantum_pose_rows(system: dict, reference: np.ndarray, elements: list[str], probe: np.ndarray,
                      n_sites: int, n_trials: int, ambiguous_180: bool) -> dict:
    """The quantum method on the same ligand, scored the same way: RMSD of the
    probe turned by the RUS search's final angle, over `n_trials` shot-noise
    seeds (the first seed is the one the molecular showdown reports)."""
    base_seed = zlib.crc32(system["id"].encode()) % (2 ** 31)
    target_phases = pocket_ligand_to_qubit_phases(MolecularGeometry("t", elements, reference), n_qubits=n_sites)
    true_rot = rotation_z(system["optimal_angle_deg"])
    # At 17 qubits the dense statevector costs ~0.8 s per circuit; the
    # closed-form product-state P(0) is the same number (test-checked to
    # 1e-12) and feeds the identical binomial draw.
    sampler = None if n_sites <= 4 else _closed_form_sampler
    rmsds, errs, evals, locks, walls = [], [], [], [], []
    for trial in range(n_trials):
        seed = base_seed if trial == 0 else (base_seed * 1_000_003 + trial) % (2 ** 31)
        t0 = time.perf_counter()
        r = run_blind_rus_pose_recovery(target_phases, probe, n_qubits=n_sites, tau=TAU, omega=OMEGA,
                                        max_retries=15, shots=100, seed=seed, elements=elements, sampler=sampler)
        walls.append(time.perf_counter() - t0)
        moved = _rotate_z(probe, r.final_angle_deg)
        rmsds.append(ligand_rmsd(moved, reference, ambiguous_180))
        errs.append(rotation_error_deg(rotation_z(r.final_angle_deg), true_rot, ambiguous_180))
        evals.append(r.circuit_evaluations)
        locks.append(r.locked)
    rmsds, errs = np.array(rmsds), np.array(errs)
    n2 = int(np.sum(rmsds <= RMSD_SUCCESS_A))
    return {
        "method": f"quantum_rus_{n_sites}_sites",
        "n_trials": n_trials,
        "locked_rate": round(float(np.mean(locks)), 4),
        "recovered_2A_rate": round(n2 / n_trials, 4),
        "recovered_2A_95ci": [round(x, 4) for x in _wilson_interval(n2, n_trials)],
        "recovered_1A_rate": round(float(np.mean(rmsds <= RMSD_STRICT_A)), 4),
        "pose_error_deg_mean": round(float(errs.mean()), 2),
        "pose_error_deg_std": round(float(errs.std()), 2),
        "ligand_rmsd_A_mean": round(float(rmsds.mean()), 3),
        "ligand_rmsd_A_std": round(float(rmsds.std()), 3),
        "circuit_evaluations_mean": round(float(np.mean(evals)), 2),
        "shots_per_evaluation": 100,
        "simulator_wall_clock_sec_mean": round(float(np.mean(walls)), 4),
        "showdown_seed_trial": {
            "recovered_2A": bool(rmsds[0] <= RMSD_SUCCESS_A),
            "pose_error_deg": round(float(errs[0]), 2),
            "ligand_rmsd_A": round(float(rmsds[0]), 3),
            "circuit_evaluations": int(evals[0]),
            "locked": bool(locks[0]),
        },
    }


def run_pose_recovery_baseline(n_quantum_trials: int = 30, quantum_sizes: Sequence[int] = (4, 8),
                               verbose: bool = True) -> list[dict]:
    rows = []
    for system in REAL_MOLECULE_SYSTEMS:
        reference, elements = _ligand(system["id"])
        angle = system["optimal_angle_deg"]
        probe = _rotate_z(reference, -angle)
        true_rot = rotation_z(angle)
        geom = MolecularGeometry(system["id"], elements, reference)
        ambiguous = has_180_degree_ambiguity(geom, n_qubits=4)

        ref_shape = GaussianShape(reference, elements)
        probe_alpha = _alphas(elements, len(probe))

        entry = {
            "system_id": system["id"],
            "system_name": system["name"],
            "n_ligand_atoms": int(len(reference)),
            "start_offset_deg": angle,
            "ambiguous_180_deg": bool(ambiguous),
            "start_ligand_rmsd_A": round(ligand_rmsd(probe, reference, ambiguous), 3),
            "classical": [],
            "quantum": [],
        }

        # USR: invariant, so no search. Score at the misaligned start and at
        # the true pose, to show it cannot tell them apart.
        usr_start, usr_wall = _timed_median(lambda: usr_similarity(reference, probe), repeats=20)
        usr_true = usr_similarity(reference, rotate_about_centroid(probe, true_rot))
        entry["classical"].append({
            "method": "usr",
            "recovered_2A": None,
            "recovered_1A": None,
            "pose_error_deg": None,
            "ligand_rmsd_A": None,
            "score_at_start_pose": round(usr_start, 6),
            "score_at_true_pose": round(usr_true, 6),
            "score_evaluations": 1,
            "wall_clock_sec": round(usr_wall, 6),
            "note": "rotation invariant: identifies the shape without a search and returns no pose",
        })

        for name, fn in (
            ("gaussian_z_grid", lambda: search_z_grid(ref_shape, probe, probe_alpha, refine=False)),
            ("gaussian_z_grid_refined", lambda: search_z_grid(ref_shape, probe, probe_alpha, refine=True)),
            ("gaussian_euler_unconstrained", lambda: search_euler_unconstrained(ref_shape, probe, probe_alpha)),
            ("gaussian_principal_axes", lambda: search_principal_axes(ref_shape, probe, probe_alpha)),
        ):
            res, wall = _timed_median(fn, repeats=5)
            entry["classical"].append(_pose_row(res, reference, true_rot, ambiguous, wall))

        for n_sites in quantum_sizes:
            entry["quantum"].append(quantum_pose_rows(system, reference, elements, probe, n_sites,
                                                      n_quantum_trials, ambiguous))
        rows.append(entry)

        if verbose:
            print(f"[{system['id']:10s}] start {angle:+.0f} deg, start RMSD {entry['start_ligand_rmsd_A']:.2f} A")
            for c in entry["classical"]:
                if c["method"] == "usr":
                    print(f"   {c['method']:28s} S(start)={c['score_at_start_pose']:.4f} S(true)={c['score_at_true_pose']:.4f} "
                          f"| {c['wall_clock_sec']*1e6:7.0f} us | no pose")
                else:
                    print(f"   {c['method']:28s} err {c['pose_error_deg']:6.2f} deg | RMSD {c['ligand_rmsd_A']:.3f} A | "
                          f"{c['score_evaluations']:4d} evals | {c['wall_clock_sec']*1e3:8.2f} ms | "
                          f"{'recovered' if c['recovered_2A'] else 'MISSED'}")
            for q in entry["quantum"]:
                print(f"   {q['method']:28s} err {q['pose_error_deg_mean']:6.2f} deg | RMSD {q['ligand_rmsd_A_mean']:.3f} A | "
                      f"{q['circuit_evaluations_mean']:5.1f} circuits x 100 shots | "
                      f"{q['simulator_wall_clock_sec_mean']*1e3:8.2f} ms sim | "
                      f"{q['recovered_2A_rate']*100:.0f}% within 2 A ({q['n_trials']} trials)")
    return rows


# =====================================================================
# 6. Cross-method agreement over ligand pairs
# =====================================================================

def _single_qubit_overlap(p: float, l: float) -> float:
    """|<pocket qubit | U_tube | ligand qubit>|^2 for one site: the SWAP test
    on product registers factorises into these."""
    def prep(theta):
        return np.array([np.cos(np.pi / 4) * np.exp(-0.5j * theta), np.sin(np.pi / 4) * np.exp(0.5j * theta)])
    _, wy, wz = OMEGA
    c, s = np.cos(wy * TAU / 2), np.sin(wy * TAU / 2)
    ry = np.array([[c, -s], [s, c]])
    rz = np.diag([np.exp(-0.5j * wz * TAU), np.exp(0.5j * wz * TAU)])
    return float(abs(np.vdot(prep(p), rz @ ry @ prep(l))) ** 2)


def product_state_p0(pocket_phases: Sequence[float], ligand_phases: Sequence[float]) -> float:
    """Closed-form P(0) for the product-state SWAP test, equal to
    `simulate_swap_test_statevector` (checked in tests and in the benchmark
    itself). Used at 8 sites, where the dense 17-qubit statevector is slow."""
    f = 1.0
    for p, l in zip(pocket_phases, ligand_phases):
        f *= _single_qubit_overlap(float(p), float(l))
    return 0.5 * (1.0 + f)


def quantum_pair_score(ref_coords, ref_elems, probe_coords, probe_elems, n_sites: int,
                       step_deg: float = 2.0, use_statevector: bool = True) -> dict:
    """Best SWAP-test P(0) over rotations of the probe about z: the score the
    RUS search is trying to maximise."""
    target = pocket_ligand_to_qubit_phases(MolecularGeometry("t", ref_elems, ref_coords), n_qubits=n_sites)
    best, best_angle, at_zero = -1.0, 0.0, None
    for angle in np.arange(-180.0, 180.0, step_deg):
        phases = pocket_ligand_to_qubit_phases(
            MolecularGeometry("p", probe_elems, _rotate_z(probe_coords, angle)), n_qubits=n_sites)
        p0 = (simulate_swap_test_statevector(target, phases, TAU, OMEGA) if use_statevector
              else product_state_p0(target, phases))
        if angle == 0.0:
            at_zero = p0
        if p0 > best:
            best, best_angle = p0, angle
    return {"p0_best": best, "best_angle_deg": float(best_angle), "p0_at_deposited_frame": at_zero}


def run_cross_method_agreement(verbose: bool = True) -> dict:
    """For every ordered pair of the six ligands: quantum P(0) at the best
    z-alignment (4 and 8 sites), USR similarity, Gaussian Tanimoto at the best
    z-alignment and at the best unconstrained Euler alignment. Spearman rank
    correlation of each quantum score against each classical one."""
    ids = [s["id"] for s in REAL_MOLECULE_SYSTEMS]
    # Different ligands sit at different places in their crystal frames, so
    # every molecule is centred on its centroid first: the Gaussian overlap
    # is then optimised over rotation only, as ROCS does after its own
    # centroid alignment. USR and the quantum encoder are translation
    # invariant already.
    ligands = {}
    for i in ids:
        coords, elements = _ligand(i)
        ligands[i] = (coords - coords.mean(axis=0), elements)
    shapes = {i: GaussianShape(*ligands[i]) for i in ids}
    pairs, closed_form_gap = [], 0.0
    for a in ids:
        for b in ids:
            ca, ea = ligands[a]
            cb, eb = ligands[b]
            alpha_b = _alphas(eb, len(cb))
            q4 = quantum_pair_score(ca, ea, cb, eb, 4, use_statevector=True)
            q8 = quantum_pair_score(ca, ea, cb, eb, 8, use_statevector=False)
            # Keep the closed form honest against the dense statevector at
            # the 4-site best angle.
            t4 = pocket_ligand_to_qubit_phases(MolecularGeometry("t", ea, ca), n_qubits=4)
            p4 = pocket_ligand_to_qubit_phases(
                MolecularGeometry("p", eb, _rotate_z(cb, q4["best_angle_deg"])), n_qubits=4)
            closed_form_gap = max(closed_form_gap,
                                  abs(product_state_p0(t4, p4) - simulate_swap_test_statevector(t4, p4, TAU, OMEGA)))
            gz = search_z_grid(shapes[a], cb, alpha_b, refine=True)
            ge = search_principal_axes(shapes[a], cb, alpha_b)
            pairs.append({
                "reference": a, "probe": b, "self_pair": a == b,
                "quantum_p0_4_sites": round(q4["p0_best"], 4),
                "quantum_p0_8_sites": round(q8["p0_best"], 4),
                "quantum_p0_4_sites_deposited_frame": round(q4["p0_at_deposited_frame"], 4),
                "usr_similarity": round(usr_similarity(ca, cb), 4),
                "gaussian_tanimoto_z": round(gz.score, 4),
                "gaussian_tanimoto_3d": round(ge.score, 4),
            })
            if verbose:
                p = pairs[-1]
                print(f"  {a:10s} vs {b:10s}  P0(4)={p['quantum_p0_4_sites']:.3f} P0(8)={p['quantum_p0_8_sites']:.3f} "
                      f"USR={p['usr_similarity']:.3f} GaussZ={p['gaussian_tanimoto_z']:.3f} Gauss3D={p['gaussian_tanimoto_3d']:.3f}")

    def spearman(x_key, y_key, subset):
        x = [p[x_key] for p in subset]
        y = [p[y_key] for p in subset]
        rho, pval = spearmanr(x, y)
        return {"rho": round(float(rho), 4), "p_value": round(float(pval), 4), "n_pairs": len(subset)}

    off_diag = [p for p in pairs if not p["self_pair"]]
    correlations = {}
    for qk in ("quantum_p0_4_sites", "quantum_p0_8_sites", "quantum_p0_4_sites_deposited_frame"):
        for ck in ("usr_similarity", "gaussian_tanimoto_z", "gaussian_tanimoto_3d"):
            correlations[f"{qk}__vs__{ck}"] = {
                "all_36_ordered_pairs": spearman(qk, ck, pairs),
                "30_off_diagonal_pairs": spearman(qk, ck, off_diag),
            }
    correlations["classical_consistency__usr_vs_gaussian_3d"] = {
        "all_36_ordered_pairs": spearman("usr_similarity", "gaussian_tanimoto_3d", pairs),
        "30_off_diagonal_pairs": spearman("usr_similarity", "gaussian_tanimoto_3d", off_diag),
    }
    if verbose:
        print("\nSpearman rank correlation (30 off-diagonal ordered pairs, 15 unique):")
        for k, v in correlations.items():
            print(f"  {k:60s} rho={v['30_off_diagonal_pairs']['rho']:+.3f}")
    return {
        "pairs": pairs,
        "spearman": correlations,
        "closed_form_vs_statevector_max_abs_gap": closed_form_gap,
        "note": ("Scores are symmetric in (reference, probe), so the 36 ordered pairs carry 15 distinct "
                 "off-diagonal values plus 6 self pairs that every method scores at its maximum."),
    }


def run_classical_baseline(output_json_path: Optional[str] = "benchmarks/classical_baseline.json",
                           n_quantum_trials: int = 30) -> dict:
    print("=" * 80)
    print("CLASSICAL SHAPE BASELINES vs Q-ROTATE: POSE RECOVERY ON SIX LIGANDS")
    print("=" * 80)
    t0 = time.perf_counter()
    pose = run_pose_recovery_baseline(n_quantum_trials=n_quantum_trials)
    print("\n" + "=" * 80)
    print("CROSS-METHOD AGREEMENT OVER LIGAND PAIRS")
    print("=" * 80)
    agreement = run_cross_method_agreement()
    payload = {
        "pose_recovery": pose,
        "cross_method_agreement": agreement,
        "settings": {
            "z_grid_step_deg": Z_GRID_STEP_DEG,
            "quantum_effective_step_deg": round(QUANTUM_EFFECTIVE_STEP_DEG, 2),
            "rmsd_success_A": RMSD_SUCCESS_A,
            "rmsd_strict_A": RMSD_STRICT_A,
            "gaussian_p": GAUSSIAN_P,
            "quantum_trials_per_system": n_quantum_trials,
            "quantum_shots_per_circuit": 100,
            "quantum_max_iterations": 15,
            "tau": TAU, "omega": list(OMEGA),
        },
        "machine": _machine_info(),
        "total_wall_clock_sec": round(time.perf_counter() - t0, 1),
        "generated_by": "src/qrotate/classical_baseline.py::run_classical_baseline",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\n[Saved classical baseline to {output_json_path}]")
    return payload


def _machine_info() -> dict:
    import platform
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "cpu_count": os.cpu_count(),
    }


if __name__ == "__main__":
    run_classical_baseline()
