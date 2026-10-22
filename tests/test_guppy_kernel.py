"""Tests for the native Guppy repeat-until-success kernel (src/qrotate/guppy_kernel.py).

Compiles the kernel for n = 1, 2, 4 sites, lowers it to QIR, checks that the
native op counts grow linearly in n and match the project's `utils`
counter, and runs the trivial ligand == pocket case on the local emulator
(Selene through guppylang) where the first-test ancilla=0 probability must
be exactly 1.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

gk = pytest.importorskip("qrotate.guppy_kernel")
if not gk.HAS_GUPPY:
    pytest.skip("guppylang not installed", allow_module_level=True)

from qrotate.circuits import (  # noqa: E402
    build_pytket_swap_test_circuit,
    rebase_to_h2_gateset,
    simulate_swap_test_statevector,
)

TAU = 0.25
OMEGA = (1.0, 0.5, 0.25)
SIZES = (1, 2, 4)


def _phases(n):
    pocket = [0.3 * (i + 1) for i in range(n)]
    ligand = [0.3 * (i + 1) + 0.9 for i in range(n)]
    return pocket, ligand


@pytest.fixture(scope="module")
def rus_kernels():
    return {n: gk.build_rus_kernel(*_phases(n), TAU, OMEGA, max_iters=4) for n in SIZES}


@pytest.fixture(scope="module")
def single_kernels():
    return {n: gk.build_single_test_kernel(*_phases(n), TAU, OMEGA) for n in SIZES}


def test_compiles_for_each_n(rus_kernels):
    from hugr.package import Package

    for n, kernel in rus_kernels.items():
        pkg = kernel.compile()
        assert isinstance(pkg, Package)
        assert kernel.n_qubits == 2 * n + 1


def test_qir_is_nonzero(rus_kernels):
    for kernel in rus_kernels.values():
        qir = kernel.to_qir("bitcode")
        assert isinstance(qir, (bytes, bytearray)) and len(qir) > 0
    assert gk.qir_validation_status() != "unknown"


def test_native_op_counts_scale_linearly(single_kernels, rus_kernels):
    for kernels in (single_kernels, rus_kernels):
        counts = {n: k.op_counts() for n, k in kernels.items()}
        for key in ("PhasedX", "ZZPhase", "Qubits", "Reset"):
            c1, c2, c4 = (counts[n][key] for n in SIZES)
            # c(n) = a + b*n  <=>  c(4) - c(2) == 2 * (c(2) - c(1))
            assert c4 - c2 == 2 * (c2 - c1), f"{key}: {c1}, {c2}, {c4}"
        for n in SIZES:
            assert counts[n]["Qubits"] == 2 * n + 1
            assert counts[n]["Measure"] >= 1
            assert counts[n]["ZZPhase"] > 0 and counts[n]["PhasedX"] > 0


def test_counts_match_utils_and_pytket(single_kernels):
    try:
        import utils  # repo-root marimo helpers
    except ImportError:
        utils = None
    for n, kernel in single_kernels.items():
        counts = kernel.op_counts()
        if utils is not None:
            assert counts == utils.hugr_op_counts(kernel.compile())
        circ = rebase_to_h2_gateset(build_pytket_swap_test_circuit(*_phases(n), TAU, OMEGA))
        pytket_counts = gk.pytket_native_op_counts(circ)
        assert pytket_counts["Qubits"] == counts["Qubits"]
        # Same circuit, different rebase: within a few gates per site.
        assert counts["ZZPhase"] <= pytket_counts["ZZPhase"]
        assert abs(counts["PhasedX"] - pytket_counts["PhasedX"]) <= 3 * n + 2


def test_trivial_overlap_first_test_p0_is_one():
    pocket = [0.3, 0.6]
    # tau = 0 so U_tube is the identity and the registers are identical.
    kernel = gk.build_rus_kernel(pocket, pocket, 0.0, OMEGA, max_iters=3)
    shots = kernel.emulate(shots=40, seed=1)
    summary = gk.summarize_shots(shots)
    assert summary.first_test_p0_hat == 1.0
    assert summary.lock_rate == 1.0
    assert set(summary.iterations_hist) == {1}
    assert simulate_swap_test_statevector(pocket, pocket, 0.0, OMEGA) == pytest.approx(1.0)


def test_rus_shots_report_kick_rows_and_p0_estimate(rus_kernels):
    kernel = rus_kernels[2]
    summary = gk.summarize_shots(kernel.emulate(shots=100, seed=3))
    exact = simulate_swap_test_statevector(*_phases(2), TAU, OMEGA)
    assert abs(summary.first_test_p0_hat - exact) <= 3 * summary.first_test_p0_stderr + 0.02
    assert all(0 <= k < kernel.max_iters for k in summary.kick_index_hist)
    assert all(1 <= it <= kernel.max_iters for it in summary.iterations_hist)
    assert kernel.ligand_phases_for_kick(1) == pytest.approx(
        [l + kernel.kick_schedule[1][i] for i, l in enumerate(kernel.ligand_phases_init)])


def test_variant_kernels_run_on_emulator_and_lower():
    pocket, ligand = _phases(2)
    streak = gk.build_rus_kernel(pocket, ligand, TAU, OMEGA, max_iters=3, lock_threshold_shots=2)
    s = gk.summarize_shots(streak.emulate(shots=20, seed=5))
    assert max(s.iterations_hist) <= 6
    assert len(streak.to_qir("bitcode")) > 0
    rng = gk.build_rus_kernel(pocket, ligand, TAU, OMEGA, max_iters=3, kick_mode="rng")
    s = gk.summarize_shots(rng.emulate(shots=20, seed=5))
    assert s.n_shots == 20
    assert len(rng.to_qir("bitcode")) > 0
    # Static counts keep the constant-false re-prepare branch, so only check it runs.
    live = gk.build_rus_kernel(pocket, ligand, TAU, OMEGA, max_iters=3, reprepare_on_failure=False)
    s = gk.summarize_shots(live.emulate(shots=20, seed=5))
    assert s.n_shots == 20


def test_external_qircheck_when_available():
    import os

    if not os.environ.get("QROTATE_QIRCHECK_PYTHON"):
        pytest.skip("set QROTATE_QIRCHECK_PYTHON to a CPython <= 3.12 with quantinuum-qircheck")
    kernel = gk.build_rus_kernel(*_phases(2), TAU, OMEGA, max_iters=3, lock_threshold_shots=2)
    verdict = gk.validate_qir_externally(kernel.to_qir("bitcode"))
    assert verdict["ok"], verdict
