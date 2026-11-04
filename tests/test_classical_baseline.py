"""Tests for the classical shape baselines (USR, Gaussian overlap)."""

import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from qrotate.classical_baseline import (  # noqa: E402
    usr_descriptor, usr_similarity, gaussian_tanimoto, GaussianShape, _alphas,
    rotation_euler, rotation_z, rotate_about_centroid, rotation_error_deg, ligand_rmsd,
    search_z_grid, search_euler_unconstrained, search_principal_axes, product_state_p0,
)
from qrotate.circuits import simulate_swap_test_statevector  # noqa: E402


def _molecule(seed=3, n=18):
    rng = np.random.default_rng(seed)
    coords = rng.normal(size=(n, 3)) * 2.5 + np.array([10.0, -4.0, 2.0])
    elements = (["C", "N", "O", "C", "C", "S"] * 3)[:n]
    return coords, elements


def test_usr_is_invariant_to_rotation_and_translation():
    coords, _ = _molecule()
    base = usr_descriptor(coords)
    for rot in (rotation_z(37.0), rotation_euler(20.0, 75.0, -140.0), rotation_euler(180.0, 90.0, 10.0)):
        moved = rotate_about_centroid(coords, rot) + np.array([3.0, -7.5, 1.25])
        assert np.allclose(usr_descriptor(moved), base, atol=1e-9)
        assert abs(usr_similarity(coords, moved) - 1.0) < 1e-9
    # And it does separate different shapes.
    other, _ = _molecule(seed=11)
    assert usr_similarity(coords, other) < 0.9
    print("PASS: test_usr_is_invariant_to_rotation_and_translation")


def test_gaussian_self_overlap_tanimoto_is_one():
    coords, elements = _molecule()
    assert abs(gaussian_tanimoto(coords, elements, coords, elements) - 1.0) < 1e-12
    # A rotated copy scores 1 at the right alignment and strictly less away from it.
    rot = rotation_euler(30.0, 60.0, -20.0)
    moved = rotate_about_centroid(coords, rot)
    shape = GaussianShape(coords, elements)
    assert abs(GaussianShape(moved, elements).tanimoto(shape) - GaussianShape(coords, elements).tanimoto(shape)) < 1.0
    assert abs(gaussian_tanimoto(coords, elements, rotate_about_centroid(moved, rot.T), elements) - 1.0) < 1e-12
    assert gaussian_tanimoto(coords, elements, moved, elements) < 0.95
    print("PASS: test_gaussian_self_overlap_tanimoto_is_one")


def test_gaussian_searches_recover_a_z_rotation():
    coords, elements = _molecule()
    true_angle = -115.0
    probe = rotate_about_centroid(coords, rotation_z(-true_angle))
    ref = GaussianShape(coords, elements)
    alpha = _alphas(elements, len(probe))
    true_rot = rotation_z(true_angle)
    for search in (lambda: search_z_grid(ref, probe, alpha, refine=True),
                   lambda: search_principal_axes(ref, probe, alpha)):
        res = search()
        assert rotation_error_deg(res.rotation, true_rot) < 0.5, res.method
        assert ligand_rmsd(res.recovered_coords, coords) < 0.05, res.method
        assert res.evaluations < 100, (res.method, res.evaluations)
    coarse = search_z_grid(ref, probe, alpha, refine=False)
    assert coarse.evaluations == 24
    assert rotation_error_deg(coarse.rotation, true_rot) <= 7.5 + 1e-9
    # The unconstrained Euler minimiser from the identity converges to a
    # genuine optimum; whether it is the global one depends on the start.
    res = search_euler_unconstrained(ref, probe, alpha)
    assert res.score > 0.9
    print("PASS: test_gaussian_searches_recover_a_z_rotation")


def test_product_state_p0_matches_statevector():
    rng = np.random.default_rng(5)
    for n in (2, 4):
        for _ in range(5):
            p = list(rng.uniform(-np.pi, np.pi, n))
            l = list(rng.uniform(-np.pi, np.pi, n))
            sv = simulate_swap_test_statevector(p, l, 0.25, (1.0, 0.5, 0.25))
            assert abs(product_state_p0(p, l) - sv) < 1e-12, (n, sv, product_state_p0(p, l))
    print("PASS: test_product_state_p0_matches_statevector")


if __name__ == "__main__":
    test_usr_is_invariant_to_rotation_and_translation()
    test_gaussian_self_overlap_tanimoto_is_one()
    test_gaussian_searches_recover_a_z_rotation()
    test_product_state_p0_matches_statevector()
