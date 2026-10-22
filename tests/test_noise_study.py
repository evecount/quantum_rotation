"""Tests for the depolarizing noise model on the compiled H2 circuit."""

import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from qrotate.noise_study import (  # noqa: E402
    compile_noisy_circuit, noisy_p0_density_matrix, noisy_p0_trajectories, trajectory_p0,
    dense_trajectory_p0, noise_locations, sample_error_pattern, BranchState, make_noisy_sampler, _PAULI,
)
from qrotate.circuits import (  # noqa: E402
    simulate_swap_test_statevector, build_pytket_swap_test_circuit, rebase_to_h2_gateset,
)


def test_symbolic_template_matches_numeric_rebase():
    """The cached symbolic rebase, with numbers substituted, must give the
    same gate stream and unitaries as rebasing the numeric circuit."""
    from pytket.circuit import OpType
    for n in (2, 4):
        p, l = _phases(n, 40 + n)
        numeric = rebase_to_h2_gateset(build_pytket_swap_test_circuit(p, l, 0.25, (1.0, 0.5, 0.25)))
        reference = [c for c in numeric.get_commands() if c.op.type != OpType.Measure]
        compiled = compile_noisy_circuit(p, l)
        assert len(reference) == len(compiled.gates)
        for cmd, g in zip(reference, compiled.gates):
            assert cmd.op.type.name == g.kind
            assert tuple(q.index[0] for q in cmd.qubits) == g.qubits
            assert np.allclose(cmd.op.get_unitary(), g.unitary, atol=1e-12)
    print("PASS: test_symbolic_template_matches_numeric_rebase")


def _phases(n, seed):
    rng = np.random.default_rng(seed)
    return list(rng.uniform(-np.pi, np.pi, n)), list(rng.uniform(-np.pi, np.pi, n))


def test_compiled_stream_counts_native_gates():
    """Noise is attached to the rebased gates: 8 ZZPhase per site (2 from the
    CX pair, 6 from the Toffoli), 15n + 2 PhasedX. Rz carries no noise."""
    for n in (2, 4, 8):
        c = compile_noisy_circuit(*_phases(n, n))
        assert c.counts["ZZPhase"] == 8 * n, c.counts
        assert c.counts["PhasedX"] == 15 * n + 2, c.counts
        assert c.n_qubits == 2 * n + 1
        assert sum(1 for g in c.gates if g.noise == "none") == c.counts["Rz"]
    print("PASS: test_compiled_stream_counts_native_gates")


def test_noise_model_at_p_zero_reproduces_ideal_p0():
    for n in (2, 4):
        for seed in range(3):
            p, l = _phases(n, seed)
            c = compile_noisy_circuit(p, l)
            ideal = simulate_swap_test_statevector(p, l, 0.25, (1.0, 0.5, 0.25))
            assert abs(c.ideal_p0 - ideal) < 1e-12
            assert abs(noisy_p0_density_matrix(c, 0.0, 0.0) - ideal) < 1e-9, (n, seed)
            assert abs(trajectory_p0(c, {}) - ideal) < 1e-9, (n, seed)
    # The trajectory engine handles the 17-qubit register too.
    p, l = _phases(8, 8)
    c = compile_noisy_circuit(p, l)
    assert abs(trajectory_p0(c, {}) - simulate_swap_test_statevector(p, l, 0.25, (1.0, 0.5, 0.25))) < 1e-9
    print("PASS: test_noise_model_at_p_zero_reproduces_ideal_p0")


def test_heavy_depolarizing_drives_p0_to_one_half():
    """At p2 = 0.5 on every ZZPhase the register is close to maximally mixed
    and the ancilla says nothing: P(0) -> 0.5."""
    for n in (2, 4):
        p, l = _phases(n, 20 + n)
        aligned = compile_noisy_circuit(p, p)      # ideal P(0) is 1 at the aligned pose
        assert aligned.ideal_p0 > 0.99
        assert abs(noisy_p0_density_matrix(aligned, 0.05, 0.5) - 0.5) < 0.02, n
        c = compile_noisy_circuit(p, l)
        assert abs(noisy_p0_density_matrix(c, 0.05, 0.5) - 0.5) < 0.02, n
    # And trajectories agree on the way there.
    c = compile_noisy_circuit(*_phases(2, 2))
    assert abs(noisy_p0_trajectories(c, 0.05, 0.5, n_trajectories=400, seed=0) - 0.5) < 0.06
    print("PASS: test_heavy_depolarizing_drives_p0_to_one_half")


def test_branch_engine_matches_dense_statevector_per_pattern():
    """Trajectory by trajectory, the structured engine must equal a dense
    statevector run of the same gates with the same Pauli insertions. This is
    the exact check; the density-matrix comparison below is statistical."""
    rng = np.random.default_rng(9)
    for n in (2, 4):
        c = compile_noisy_circuit(*_phases(n, 50 + n))
        locs = noise_locations(c, 0.05, 0.05)
        for _ in range(8):
            errors = sample_error_pattern(locs, c, rng)
            assert abs(trajectory_p0(c, errors) - dense_trajectory_p0(c, errors)) < 1e-12, errors
    print("PASS: test_branch_engine_matches_dense_statevector_per_pattern")


def test_trajectories_agree_with_density_matrix():
    """The structured branch simulator must sample the same channel the dense
    density matrix evaluates exactly: norm preserved on every trajectory and
    the trajectory mean within statistical error of the exact noisy P(0)."""
    rng = np.random.default_rng(0)
    for n in (2, 3):
        p, l = _phases(n, 30 + n)
        c = compile_noisy_circuit(p, l)
        p1, p2 = 5e-3, 5e-2
        exact = noisy_p0_density_matrix(c, p1, p2)
        locs = noise_locations(c, p1, p2)
        samples, n_traj = [], 400
        for _ in range(n_traj):
            errors = sample_error_pattern(locs, c, rng)
            if not errors:
                samples.append(c.ideal_p0)
                continue
            st = BranchState(n)
            for i, g in enumerate(c.gates):
                if len(g.qubits) == 1:
                    st.apply_1q(g.unitary, g.qubits[0])
                else:
                    st.apply_2q(g.unitary, *g.qubits)
                code = errors.get(i)
                if code:
                    if len(g.qubits) == 1:
                        st.apply_1q(_PAULI[code], g.qubits[0])
                    else:
                        a, b = divmod(code, 4)
                        if a:
                            st.apply_1q(_PAULI[a], g.qubits[0])
                        if b:
                            st.apply_1q(_PAULI[b], g.qubits[1])
            assert abs(st.norm_squared() - 1.0) < 1e-9
            samples.append(st.prob_zero())
        mean = float(np.mean(samples))
        sem = float(np.std(samples) / np.sqrt(n_traj))
        assert abs(mean - exact) < 4 * sem + 0.01, (n, mean, exact, sem)
    print("PASS: test_trajectories_agree_with_density_matrix")


def test_noisy_sampler_feeds_the_rus_protocol():
    from qrotate.metrics import run_blind_rus_pose_recovery
    from qrotate.hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases
    from qrotate.metrics import _rotate_z

    rng = np.random.default_rng(4)
    coords = rng.normal(size=(16, 3)) * 2.5
    target = pocket_ligand_to_qubit_phases(MolecularGeometry("t", ["C"] * 16, coords), n_qubits=2)
    probe = _rotate_z(coords, -20.0)
    sampler = make_noisy_sampler(1e-4, 1e-3, 2e-3, method="density_matrix")
    r = run_blind_rus_pose_recovery(target, probe, n_qubits=2, max_retries=4, shots=50, seed=1, sampler=sampler)
    assert r.circuit_evaluations >= 1 and 0.0 <= r.final_p0_hat <= 1.0
    # Readout flips alone cap the measured P(0): with p_ro = 0.5 every
    # measurement is a coin toss, so no lock is possible.
    coin = make_noisy_sampler(0.0, 0.0, 0.5, method="density_matrix")
    r = run_blind_rus_pose_recovery(target, probe, n_qubits=2, max_retries=4, shots=50, seed=1, sampler=coin)
    assert not r.locked
    print("PASS: test_noisy_sampler_feeds_the_rus_protocol")


if __name__ == "__main__":
    test_symbolic_template_matches_numeric_rebase()
    test_compiled_stream_counts_native_gates()
    test_noise_model_at_p_zero_reproduces_ideal_p0()
    test_heavy_depolarizing_drives_p0_to_one_half()
    test_branch_engine_matches_dense_statevector_per_pattern()
    test_trajectories_agree_with_density_matrix()
    test_noisy_sampler_feeds_the_rus_protocol()
