"""Test suite for Project Q-Rotate."""

import sys
import os
import numpy as np
from pathlib import Path

# Ensure repo root and src/ are on the python path, relative to this file,
# so the suite runs on any machine/CI rather than only the original author's.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from qrotate.operators import (
    HTubeHamiltonian,
    decompose_rotation_euler,
    compute_phase_mismatch,
)
from qrotate.hpc_bridge import (
    MolecularGeometry,
    pocket_ligand_to_qubit_phases,
    generate_synthetic_binding_pair,
)
from qrotate.metrics import (
    compute_overlap_fidelity,
    estimate_qrotate_hqc_cost,
    compute_circuit_hqc_cost,
)
from qrotate.circuits import (
    build_pytket_swap_test_circuit,
    build_pytket_rus_simulation,
    rebase_to_h2_gateset,
    guppy_qrotate_rus_demo,
    simulate_swap_test_statevector,
)
from qrotate.metrics import run_blind_rus_protocol
import utils

try:
    from hugr_qir.hugr_to_qir import hugr_to_qir
    from hugr_qir.output import OutputFormat
    HAS_HUGR_QIR = True
except ImportError:
    HAS_HUGR_QIR = False


def test_hpc_bridge():
    pocket_geo, ligand_geo, delta_phi = generate_synthetic_binding_pair(n_sites=3, rotation_angle_deg=10.0)
    assert pocket_geo.n_atoms == 3
    assert ligand_geo.n_atoms == 3
    assert len(delta_phi) == 3
    print("PASS: test_hpc_bridge")


def test_operators():
    h_tube = HTubeHamiltonian(
        n_qubits=2,
        omega=(0.1, 0.2, 0.3),
        delta_phi=[0.05, -0.05],
        coupling_j=0.01,
    )
    u_mat = h_tube.get_evolution_unitary(tau=1.0)
    assert u_mat.shape == (4, 4)
    # Check unitarity
    identity_diff = np.max(np.abs(u_mat.conj().T @ u_mat - np.eye(4)))
    assert identity_diff < 1e-10
    print("PASS: test_operators (U_tube is unitary)")


def test_pytket_circuit():
    pocket_phases = [0.1, 0.2]
    ligand_phases = [0.15, 0.25]
    circ = build_pytket_swap_test_circuit(
        pocket_phases, ligand_phases, tau=0.5, omega=(0.0, 0.1, 0.2)
    )
    assert circ.n_qubits == 5  # 1 ancilla + 2 pocket + 2 ligand
    rebased = rebase_to_h2_gateset(circ)
    stats = utils.pytket_op_counts(rebased)
    assert stats["Qubits"] == 5
    cost = utils.estimate_cost(stats, n_shots=100)
    print(f"PASS: test_pytket_circuit (Rebased Op counts: {stats}, Estimated HQC: {cost:.2f})")


def test_guppy_circuit_compilation():
    print("Compiling guppy_qrotate_rus_demo to HUGR...")
    hugr = guppy_qrotate_rus_demo.compile()
    stats = utils.hugr_op_counts(hugr)
    print(f"Guppy HUGR stats: {stats}")
    if not HAS_HUGR_QIR:
        print("SKIP: hugr_qir not installed in this environment (HUGR compilation still verified above)")
        return
    qir = hugr_to_qir(hugr, output_format=OutputFormat.BITCODE)
    assert len(qir) > 0
    print(f"PASS: test_guppy_circuit_compilation (Generated {len(qir)} bytes of QIR bitcode)")


def test_metrics_cost():
    cost_info = estimate_qrotate_hqc_cost(n_qubits=3, rus_attempts=3, shots=100)
    assert cost_info["n_qubits"] == 7
    assert cost_info["estimated_hqcs"] > 5.0
    print(f"PASS: test_metrics_cost (Estimate: {cost_info['estimated_hqcs']} HQCs)")


def test_phase_encoding_is_rotation_equivariant():
    """Rotating a molecule about z by theta must shift every chunk's phase by
    exactly theta. A plain mean of angles breaks this at the +/-pi branch cut
    (atoms at +179 and -179 average to 0), which turned the phase register into
    a step function and invented local maxima in the resonance landscape."""
    rng = np.random.default_rng(7)
    coords = rng.normal(size=(24, 3)) * 3.0
    geom = MolecularGeometry("m", ["C"] * len(coords), coords)
    base = np.array(pocket_ligand_to_qubit_phases(geom, n_qubits=4))

    for theta_deg in (5.0, 90.0, 179.0, -155.0):
        theta = np.radians(theta_deg)
        rot = np.array([
            [np.cos(theta), -np.sin(theta), 0.0],
            [np.sin(theta), np.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ])
        centroid = coords.mean(axis=0)
        turned = (coords - centroid) @ rot.T + centroid
        moved = np.array(pocket_ligand_to_qubit_phases(
            MolecularGeometry("m", ["C"] * len(turned), turned), n_qubits=4))

        # Compare on the circle: the difference must be theta for every chunk.
        delta = np.angle(np.exp(1j * (moved - base - theta)))
        assert np.max(np.abs(delta)) < 1e-9, (
            f"rotation by {theta_deg} deg shifted phases by {moved - base}, expected {theta}")

    print("PASS: test_phase_encoding_is_rotation_equivariant")


def test_second_order_moment_rescues_centrosymmetric_molecules():
    """A centrosymmetric shell cancels the first-order moment exactly, so the
    encoder falls back to the second order. H2 is the extreme case: it used to
    encode as all zeros at every orientation, which made any "match" against it
    two empty registers agreeing."""
    from qrotate.hpc_bridge import (
        shell_moment_orders, shell_anisotropy, is_encoding_degenerate,
        has_180_degree_ambiguity,
    )

    h2 = np.array([[-0.3707, 0.0, 0.0], [0.3707, 0.0, 0.0]])
    geom = MolecularGeometry("h2", ["H", "H"], h2)

    assert shell_moment_orders(geom, 4)[0] == 2, "first shell should fall back to second order"
    assert shell_anisotropy(geom, 4)[0] > 0.9, "two opposed atoms give a maximal second moment"
    assert not is_encoding_degenerate(geom, 4), "H2 is encodable via the second order"
    assert has_180_degree_ambiguity(geom, 4), "a second-order-only register is mod 180 degrees"

    # The register must still move with the molecule: a rotation by alpha
    # shifts arg(M2)/2 by exactly alpha.
    base = pocket_ligand_to_qubit_phases(geom, n_qubits=4)[0]
    for deg in (20.0, 45.0, 80.0):
        theta = np.radians(deg)
        rot = np.array([[np.cos(theta), -np.sin(theta), 0.0],
                        [np.sin(theta), np.cos(theta), 0.0],
                        [0.0, 0.0, 1.0]])
        turned = h2 @ rot.T
        moved = pocket_ligand_to_qubit_phases(
            MolecularGeometry("h2", ["H", "H"], turned), n_qubits=4)[0]
        # Modulo pi, because the second order cannot see a 180 degree flip.
        err = np.angle(np.exp(2j * (moved - base - theta))) / 2.0
        assert abs(err) < 1e-9, f"{deg} deg moved the phase by {moved - base}"

    # And that ambiguity is a statement about the molecule, not a defect:
    # H2 turned by 180 degrees is the same arrangement.
    flipped = MolecularGeometry("h2", ["H", "H"], -h2)
    assert abs(pocket_ligand_to_qubit_phases(flipped, n_qubits=4)[0] - base) < 1e-9

    print("PASS: test_second_order_moment_rescues_centrosymmetric_molecules")


def test_moment_ladder_handles_rotational_symmetry():
    """A k-fold symmetric ring cancels every angular moment below order k, so
    the encoder climbs the ladder until one survives. Benzene's six-fold ring
    is the case that matters: it is everywhere in drug-like molecules, and with
    only first and second moments it would encode as nothing."""
    from qrotate.hpc_bridge import (
        shell_moment_orders, rotational_ambiguity_deg, is_encoding_degenerate,
        MAX_MOMENT_ORDER,
    )

    def ring(n, radius=1.4):
        a = np.linspace(0, 2 * np.pi, n, endpoint=False)
        return np.column_stack([radius * np.cos(a), radius * np.sin(a), np.zeros(n)])

    for n in (2, 3, 4, 6):
        geom = MolecularGeometry(f"ring{n}", ["C"] * n, ring(n))
        assert shell_moment_orders(geom, 1)[0] == n, f"{n}-fold ring should use order {n}"
        assert not is_encoding_degenerate(geom, 1), f"{n}-fold ring should be encodable"
        # Its register necessarily repeats every 360/n degrees, which is a fact
        # about the molecule: those orientations are the same arrangement.
        assert abs(rotational_ambiguity_deg(geom, 1) - 360.0 / n) < 1e-9

        # Equivariance still holds: rotating by alpha moves the phase by alpha.
        base = pocket_ligand_to_qubit_phases(geom, n_qubits=1)[0]
        theta = np.radians(360.0 / n / 3.0)      # safely inside one period
        rot = np.array([[np.cos(theta), -np.sin(theta), 0.0],
                        [np.sin(theta), np.cos(theta), 0.0],
                        [0.0, 0.0, 1.0]])
        moved = pocket_ligand_to_qubit_phases(
            MolecularGeometry("r", ["C"] * n, ring(n) @ rot.T), n_qubits=1)[0]
        err = np.angle(np.exp(1j * n * (moved - base - theta))) / n
        assert abs(err) < 1e-9, f"{n}-fold ring: phase moved by {moved - base}, expected {theta}"

    # Beyond the ladder's top the encoder must report nothing rather than
    # silently encode noise.
    too_symmetric = MolecularGeometry("ring", ["C"] * (MAX_MOMENT_ORDER + 2),
                                      ring(MAX_MOMENT_ORDER + 2))
    assert is_encoding_degenerate(too_symmetric, 1)

    print(f"PASS: test_moment_ladder_handles_rotational_symmetry (orders 2-{MAX_MOMENT_ORDER})")


def test_phase_encoding_is_permutation_invariant():
    """The register must describe the molecule, not the order its atoms happen
    to appear in. The previous encoder chunked atoms by input order, so a
    reordered copy of the same ligand scored as low as 0.52 against itself."""
    rng = np.random.default_rng(11)
    coords = rng.normal(size=(21, 3)) * 2.5
    elements = ["C", "N", "O"] * 7
    base = np.array(pocket_ligand_to_qubit_phases(
        MolecularGeometry("m", elements, coords), n_qubits=4))

    for _ in range(5):
        p = rng.permutation(len(coords))
        shuffled = np.array(pocket_ligand_to_qubit_phases(
            MolecularGeometry("m", [elements[i] for i in p], coords[p]), n_qubits=4))
        delta = np.angle(np.exp(1j * (shuffled - base)))
        assert np.max(np.abs(delta)) < 1e-9, f"reordering changed the register by {delta}"

    # Atoms at identical radii are the hard case: they must not be split
    # across a shell boundary by input order (H2 is two atoms at one radius).
    h2 = np.array([[-0.3707, 0.0, 0.0], [0.3707, 0.0, 0.0]])
    a = pocket_ligand_to_qubit_phases(MolecularGeometry("h2", ["H", "H"], h2), n_qubits=4)
    b = pocket_ligand_to_qubit_phases(MolecularGeometry("h2", ["H", "H"], h2[::-1]), n_qubits=4)
    assert np.max(np.abs(np.angle(np.exp(1j * (np.array(a) - np.array(b)))))) < 1e-9

    print("PASS: test_phase_encoding_is_permutation_invariant")


def test_phase_encoding_sees_chirality():
    """A molecule and its mirror image are different structures and must not
    encode identically. The previous encoder used only the azimuth, so a
    z-reflection left the register untouched (overlap 0.99)."""
    rng = np.random.default_rng(5)
    coords = rng.normal(size=(16, 3)) * 2.0
    elements = ["C"] * 16
    mirrored = coords.copy()
    mirrored[:, 2] *= -1.0

    original = pocket_ligand_to_qubit_phases(MolecularGeometry("m", elements, coords), n_qubits=4)
    flipped = pocket_ligand_to_qubit_phases(MolecularGeometry("m", elements, mirrored), n_qubits=4)

    overlap = simulate_swap_test_statevector(original, flipped, tau=0.25, omega=(1.0, 0.5, 0.25))
    assert overlap < 0.9, f"mirror image is indistinguishable (P(0)={overlap:.3f})"
    print(f"PASS: test_phase_encoding_sees_chirality (mirror P(0)={overlap:.3f})")


def test_radial_shells_leave_no_qubit_empty():
    """Every shell must get atoms whenever the molecule has at least as many
    distinct radii as there are shells, and shell sizes may differ by no more
    than the largest group of tied atoms (which can never be split). The old
    split starved the last shell: at eight shells four of the five benchmark
    ligands encoded nothing on q7."""
    from qrotate.hpc_bridge import _radial_shells
    from qrotate.structures import load_active_sites

    def check(radii, n_shells, label):
        radii = np.asarray(radii, dtype=float)
        sizes = [len(s) for s in _radial_shells(radii, n_shells)]
        assert sum(sizes) == len(radii), (label, sizes)
        _, tie_counts = np.unique(np.round(radii, 6), return_counts=True)
        if len(tie_counts) >= n_shells:
            assert min(sizes) > 0, (label, n_shells, sizes)
            assert max(sizes) - min(sizes) <= tie_counts.max(), (label, n_shells, sizes)
        else:
            # Fewer distinct radii than shells: inner shells filled, outer empty.
            assert all(sizes[:len(tie_counts)]) and not any(sizes[len(tie_counts):]), (label, sizes)
        return sizes

    for sid, site in load_active_sites().items():
        c = np.asarray(site["ligand"]["coords"], dtype=float)
        for n_shells in (4, 8):
            check(np.linalg.norm(c - c.mean(axis=0), axis=1), n_shells, sid)

    rng = np.random.default_rng(20260921)
    for trial in range(2000):
        n_atoms = int(rng.integers(1, 60))
        n_shells = int(rng.choice([2, 3, 4, 6, 8]))
        # Coarse radii force plenty of ties, including very large tie-groups.
        radii = rng.integers(1, int(rng.integers(1, 40)) + 1, size=n_atoms) * 0.5
        check(radii, n_shells, f"random trial {trial}")

    assert check([0.3707, 0.3707], 8, "H2") == [2, 0, 0, 0, 0, 0, 0, 0]
    print("PASS: test_radial_shells_leave_no_qubit_empty (6 ligands x 2 sizes, 2000 tie-heavy random molecules)")


def test_soft_shells_make_the_register_continuous():
    """A hard shell boundary makes the register jump whenever coordinate error
    carries an atom across it, and a count-balanced split sometimes puts a
    boundary between two atoms at almost the same radius (trans-azobenzene's
    near-equal pairs). Atoms near a boundary are therefore shared between the
    two shells, so swapping such a pair barely moves the register."""
    from qrotate.hpc_bridge import radial_shell_membership, molecular_shell_phases
    from qrotate.structures import load_active_sites

    sites = load_active_sites()
    for sid, site in sites.items():
        c = np.asarray(site["ligand"]["coords"], dtype=float)
        r = np.linalg.norm(c - c.mean(axis=0), axis=1)
        for n_shells in (4, 8):
            m = radial_shell_membership(r, n_shells)
            assert np.allclose(m.sum(axis=0), 1.0), (sid, n_shells)
            assert (m >= -1e-12).all(), (sid, n_shells)
    # H2's two atoms share one radius: everything stays in the first shell.
    h2 = radial_shell_membership(np.array([0.3707, 0.3707]), 4)
    assert np.allclose(h2[0], 1.0) and np.allclose(h2[1:], 0.0)

    # Atoms 3 and 4 sit 0.004 A apart in radius, either side of the boundary
    # between shells 1 and 2. Nudging them so their order swaps must not swap
    # which shell each belongs to: a hard split moves each one's whole weight
    # (a change of 1.0), the soft edge barely changes it.
    def radii(delta):
        return np.array([1.0, 1.5, 2.0, 3.0 - delta, 3.0 + delta, 3.5, 4.0, 4.5])
    jump = np.abs(radial_shell_membership(radii(0.002), 4) - radial_shell_membership(radii(-0.002), 4)).max()
    assert jump < 0.05, jump

    # Regression guard on the property the soft edge exists for: a tenth of an
    # Angstrom of coordinate error, about experimental precision, costs little.
    rng = np.random.default_rng(7)
    scores = []
    for sid, site in sites.items():
        if sid == "h2bench":
            continue
        c = np.asarray(site["ligand"]["coords"], dtype=float)
        e = site["ligand"]["elements"]
        ref = molecular_shell_phases(MolecularGeometry("r", e, c), n_qubits=4)
        scores.append(np.mean([
            simulate_swap_test_statevector(
                ref, molecular_shell_phases(MolecularGeometry("n", e, c + rng.normal(0, 0.1, c.shape)), n_qubits=4),
                0.25, (1.0, 0.5, 0.25))
            for _ in range(40)
        ]))
    # A hard balanced split scores 0.55 on azobenzene and 0.86 on average here.
    assert min(scores) >= 0.75 and np.mean(scores) >= 0.90, scores
    print(f"PASS: test_soft_shells_make_the_register_continuous (pair swap moves membership {jump:.3f}; "
          f"0.1 A noise self-overlap {min(scores):.2f}-{max(scores):.2f})")


def test_constellation_profiles_carry_the_true_pose():
    """The Constellation draws its gold ghost and "exact answer" tick from
    pose_offset_deg, so it must be the offset the benchmark actually applied,
    and each landscape must peak close to it: U_tube(tau) shifts the peak a few
    degrees, but a peak far from the true pose would mean the page and the
    benchmark describe different rotations."""
    import json
    from qrotate.metrics import REAL_MOLECULE_SYSTEMS

    path = Path(__file__).resolve().parent.parent / "benchmarks" / "constellation_profiles.json"
    if not path.exists():
        print("SKIP: benchmarks/constellation_profiles.json missing")
        return
    profiles = {p["id"]: p for p in json.loads(path.read_text(encoding="utf-8"))["constellation_profiles"]}

    for sys_spec in REAL_MOLECULE_SYSTEMS:
        prof = profiles[sys_spec["id"]]
        assert prof["pose_offset_deg"] == sys_spec["optimal_angle_deg"], sys_spec["id"]
        for size, reg in prof["registers"].items():
            gap = abs((reg["best_angle_deg"] - prof["pose_offset_deg"] + 180) % 360 - 180)
            if reg["ambiguous_180_deg"]:
                gap = min(gap, 180 - gap)
            assert gap <= 6, (sys_spec["id"], size, reg["best_angle_deg"], prof["pose_offset_deg"])
    print(f"PASS: test_constellation_profiles_carry_the_true_pose ({len(REAL_MOLECULE_SYSTEMS)} systems, every peak within 6 deg)")


def test_active_sites_are_real_structures():
    """The six benchmark systems must come from experimental coordinates, and
    each pocket must contain the residues that site is actually known for. This
    is the guard against quietly sliding back to synthetic point clouds."""
    from qrotate.structures import load_active_sites

    sites = load_active_sites()
    if not sites:
        print("SKIP: benchmarks/active_sites.json missing "
              "(run `python -m src.qrotate.structures` to fetch the structures)")
        return

    expected_sources = {
        "rhodopsin": "1U19", "gfp": "1EMA", "mpro": "7VH8",
        "cox2": "3LN1", "azobenzene": "2272", "h2bench": "H2",
    }
    # Residues each active site is defined by in the literature.
    expected_residues = {
        "rhodopsin": ["LYS296", "GLU113"],
        "gfp": ["HIS148", "THR203", "GLU222"],
        "mpro": ["CYS145", "HIS41"],
        "cox2": ["VAL523", "ARG120", "TYR355"],
    }

    assert set(sites) == set(expected_sources), sorted(sites)
    for sid, source_id in expected_sources.items():
        assert sites[sid]["source"]["id"] == source_id, sid
        assert sites[sid]["ligand"]["n_atoms"] > 0, sid
        assert len(sites[sid]["ligand"]["coords"]) == sites[sid]["ligand"]["n_atoms"], sid

    for sid, residues in expected_residues.items():
        present = set(sites[sid]["pocket"]["residues"])
        missing = [r for r in residues if r not in present]
        assert not missing, f"{sid} pocket is missing {missing}"

    print(f"PASS: test_active_sites_are_real_structures "
          f"({len(sites)} sites, catalytic residues present)")


def test_hqc_cost_counts_compiled_circuit():
    """The HQC estimate must come from the rebased circuit's real gate counts,
    and a multi-run screen must cost exactly runs x one circuit."""
    circ = rebase_to_h2_gateset(build_pytket_swap_test_circuit(
        [0.3, 0.4, 0.5, 0.6], [0.6, 0.5, 0.4, 0.3], tau=0.25, omega=(1.0, 0.5, 0.25)))
    one = compute_circuit_hqc_cost(circ, shots=100)
    expected = 5.0 + (one["single_qubit_count"] + 10 * one["two_qubit_count"]
                      + 5 * (one["n_qubits"] + one["measure_count"] + one["reset_count"])) * 100 / 5000
    assert one["n_qubits"] == 9
    assert one["hqc_cost"] == round(expected, 2)
    screen = estimate_qrotate_hqc_cost(4, rus_attempts=3, shots=100, circuit=circ)
    assert screen["estimated_hqcs"] == round(3 * one["hqc_cost"], 2)
    # The closed-form counts used where pytket isn't available (and mirrored in
    # simulation.html) must match the compiled circuit.
    from qrotate.circuits import compile_h2_native_gates, calculate_exact_hqc_budget
    for n in (2, 4, 8):
        c = rebase_to_h2_gateset(build_pytket_swap_test_circuit(
            [0.3 + 0.1 * i for i in range(n)], [0.9 - 0.1 * i for i in range(n)],
            tau=0.25, omega=(1.0, 0.5, 0.25)))
        real = compute_circuit_hqc_cost(c, shots=100)
        model = compile_h2_native_gates(n)
        assert model["single_qubit_laser_gates"] == real["single_qubit_count"], n
        assert model["native_two_qubit_zzphase"] == real["two_qubit_count"], n
        assert calculate_exact_hqc_budget(n, 1, 100)["hqc"] == real["hqc_cost"], n
    print(f"PASS: test_hqc_cost_counts_compiled_circuit ({one['single_qubit_count']} PhasedX, "
          f"{one['two_qubit_count']} ZZPhase, {one['hqc_cost']} HQC per circuit)")


def test_swap_test_statevector_matches_closed_form():
    """The dense-statevector SWAP-test simulator must reproduce the textbook
    single-qubit SWAP-test formula P(0) = (1 + cos^2(delta_phi/2)) / 2 exactly
    (this is the ground truth the honest RUS benchmark measures against)."""
    for dphi in (0.0, 0.3, 1.2, 2.5):
        p0 = simulate_swap_test_statevector([0.4], [0.4 - dphi], tau=0.0, omega=(0.0, 0.0, 0.0))
        expected = 0.5 * (1.0 + np.cos(dphi / 2.0) ** 2)
        assert abs(p0 - expected) < 1e-9, f"dphi={dphi}: sim={p0} expected={expected}"
    # Identical states must swap-test to a certain P(0) = 1.0.
    p0_identical = simulate_swap_test_statevector([0.1, -0.2, 0.9], [0.1, -0.2, 0.9], tau=0.0, omega=(0.0, 0.0, 0.0))
    assert abs(p0_identical - 1.0) < 1e-9
    print("PASS: test_swap_test_statevector_matches_closed_form")


def test_pose_recovery_reports_where_it_stopped():
    """A lock only says the measured P(0) cleared the bar, and it clears across
    a band of angles, so the result has to say where the search actually
    stopped. The benchmark reports the pose error from this."""
    from qrotate.metrics import (
        REAL_MOLECULE_SYSTEMS,
        _system_coordinates,
        _rotate_z,
        pose_error_deg,
        run_blind_rus_pose_recovery,
    )
    from qrotate.structures import site_elements

    assert pose_error_deg(170.0, -170.0) == 20.0
    assert pose_error_deg(-160.0, 15.0) == 175.0
    assert pose_error_deg(-160.0, 15.0, ambiguous_180=True) == 5.0

    spec = next(s for s in REAL_MOLECULE_SYSTEMS if s["id"] == "rhodopsin")
    target, probe = _system_coordinates(spec["id"], spec["n_atoms_proxy"], spec["optimal_angle_deg"], 0)
    elements = site_elements(spec["id"]) or ["C"] * len(probe)
    target_phases = pocket_ligand_to_qubit_phases(MolecularGeometry("t", elements, target), n_qubits=4)

    res = run_blind_rus_pose_recovery(target_phases, probe, n_qubits=4, seed=7, elements=elements)
    assert res.final_angle_deg is not None and -180.0 <= res.final_angle_deg < 180.0
    # final_p0_true must be the circuit at the reported angle, not some other one.
    phases = pocket_ligand_to_qubit_phases(
        MolecularGeometry("p", elements, _rotate_z(probe, res.final_angle_deg)), n_qubits=4)
    assert abs(simulate_swap_test_statevector(target_phases, phases, 0.25, (1.0, 0.5, 0.25))
               - res.final_p0_true) < 1e-9
    assert res.locked
    error = pose_error_deg(res.final_angle_deg, spec["optimal_angle_deg"])
    assert error <= 30.0, error
    print(f"PASS: test_pose_recovery_reports_where_it_stopped (rhodopsin locked {error:.1f} deg from the true pose)")


def test_blind_rus_protocol_does_not_cheat():
    """The RUS search must never be handed the pocket's own phases as its
    update rule (that was the bug that made the old benchmark self-fulfilling)
    and outcomes must genuinely depend on the starting mismatch."""
    pocket_phases = [0.6, -0.7, 0.5, -0.4]

    # A search starting already close to the target should lock, and in no
    # more iterations than a search starting maximally uninformed (all zeros).
    near_result = run_blind_rus_protocol(
        pocket_phases, [p * 0.95 for p in pocket_phases],
        tau=0.25, omega=(1.0, 0.5, 0.25), max_retries=15, shots=100, seed=7,
    )
    far_result = run_blind_rus_protocol(
        pocket_phases, [0.0, 0.0, 0.0, 0.0],
        tau=0.25, omega=(1.0, 0.5, 0.25), max_retries=15, shots=100, seed=7,
    )
    assert near_result.locked
    assert near_result.iterations <= far_result.iterations
    print(
        f"PASS: test_blind_rus_protocol_does_not_cheat "
        f"(near-start locked in {near_result.iterations} iters, far-start in {far_result.iterations})"
    )


if __name__ == "__main__":
    test_hpc_bridge()
    test_operators()
    test_pytket_circuit()
    test_guppy_circuit_compilation()
    test_metrics_cost()
    test_phase_encoding_is_rotation_equivariant()
    test_second_order_moment_rescues_centrosymmetric_molecules()
    test_moment_ladder_handles_rotational_symmetry()
    test_phase_encoding_is_permutation_invariant()
    test_radial_shells_leave_no_qubit_empty()
    test_soft_shells_make_the_register_continuous()
    test_phase_encoding_sees_chirality()
    test_active_sites_are_real_structures()
    test_constellation_profiles_carry_the_true_pose()
    test_hqc_cost_counts_compiled_circuit()
    test_swap_test_statevector_matches_closed_form()
    test_blind_rus_protocol_does_not_cheat()
    test_pose_recovery_reports_where_it_stopped()
    print("\nALL PROJECT Q-ROTATE TESTS PASSED SUCCESSFULLY!")
