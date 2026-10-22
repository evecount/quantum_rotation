"""Tests for the execution backends (`qrotate.runner`) and the evidence
writer (`qrotate.evidence`)."""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

from qrotate.circuits import simulate_swap_test_statevector, simulate_shot_sampling, HAS_PYTKET
from qrotate import runner
from qrotate.runner import (
    CredentialsRequired,
    NexusBackend,
    RunResult,
    StatevectorBackend,
    SwapTestProgram,
    check_credentials,
    get_backend,
    NEXUS_TARGETS,
)
from qrotate import evidence


TAU, OMEGA = 0.25, (1.0, 0.5, 0.25)


def _random_program(rng, n_sites=4):
    pocket = rng.uniform(-np.pi, np.pi, n_sites)
    ligand = pocket + rng.normal(0, 0.4, n_sites)
    return SwapTestProgram.build(pocket, ligand, TAU, OMEGA, label="t")


# ---------------------------------------------------------------------
# statevector backend == the simulator every benchmark used
# ---------------------------------------------------------------------

def test_statevector_backend_reproduces_reference_simulator():
    rng = np.random.default_rng(3)
    backend = StatevectorBackend()
    for _ in range(5):
        prog = _random_program(rng)
        shots, seed = 400, int(rng.integers(1 << 30))
        res = backend.run(prog, shots, seed=seed)

        ref_p0 = simulate_swap_test_statevector(prog.pocket_phases, prog.ligand_phases, TAU, OMEGA)
        assert res.prob_zero_exact == pytest.approx(ref_p0, abs=1e-12)

        # Same seed -> the very counts simulate_shot_sampling draws today.
        ref_sample = simulate_shot_sampling(ref_p0, n_shots=shots, seed=seed)
        assert res.counts == {"0": ref_sample["counts_0"], "1": ref_sample["counts_1"]}
        assert res.shots == shots and res.counts_zero + res.counts_one == shots

        # Empirical P(0) within shot noise of the exact value (5 sigma).
        sigma = np.sqrt(max(ref_p0 * (1 - ref_p0), 1e-4) / shots)
        assert abs(res.prob_zero - ref_p0) < 5 * sigma
        assert res.ci_low <= res.prob_zero <= res.ci_high
        assert 0.0 <= res.ci_low < res.ci_high <= 1.0
        assert res.backend == "statevector" and res.job_id is None and res.hqc is None
    print("PASS: test_statevector_backend_reproduces_reference_simulator")


@pytest.mark.skipif(not HAS_PYTKET, reason="pytket not installed")
def test_compiled_circuit_computes_the_same_prob_zero():
    """The H-series-rebased circuit that gets submitted must compute the same
    P(0) as the hand-written simulator: pytket's own statevector of the
    compiled circuit is the independent check."""
    rng = np.random.default_rng(11)
    prog = _random_program(rng, n_sites=3)
    p_raw = runner._pytket_prob_zero(prog.circuit)
    p_compiled = runner._pytket_prob_zero(prog.compiled)
    assert p_raw == pytest.approx(prog.exact_prob_zero(), abs=1e-9)
    assert p_compiled == pytest.approx(prog.exact_prob_zero(), abs=1e-9)

    # And the backend accepts the bare compiled circuit too.
    res = StatevectorBackend().run(prog.compiled, 100, seed=1)
    assert res.prob_zero_exact == pytest.approx(prog.exact_prob_zero(), abs=1e-9)
    print(f"PASS: test_compiled_circuit_computes_the_same_prob_zero (P0={p_compiled:.4f})")


def test_run_result_serialises():
    res = StatevectorBackend().run(_random_program(np.random.default_rng(1)), 20, seed=5)
    payload = json.loads(json.dumps(res.to_dict()))
    for key in ("backend", "shots", "counts", "prob_zero", "ci_low", "ci_high", "job_id", "wall_time_s", "hqc", "seed"):
        assert key in payload
    print("PASS: test_run_result_serialises")


# ---------------------------------------------------------------------
# evidence writer
# ---------------------------------------------------------------------

REQUIRED_MANIFEST_FIELDS = (
    "schema_version", "generated_at_utc", "backend", "git", "environment", "parameters", "runs", "status", "summary",
)


def test_evidence_writer_produces_manifest_with_required_fields(tmp_path):
    out_dir = evidence.write_evidence(
        StatevectorBackend(), systems=["h2bench", "rhodopsin"], n_sites=4, shots=30,
        out_root=tmp_path, echo=False,
    )
    assert out_dir.parent == tmp_path and "statevector" in out_dir.name
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    for field in REQUIRED_MANIFEST_FIELDS:
        assert field in manifest, field
    assert "commit" in manifest["git"] and "dirty" in manifest["git"]
    assert manifest["environment"]["packages"]["numpy"]
    assert manifest["backend"]["name"] == "statevector"
    assert manifest["parameters"] == {
        "n_sites": 4, "n_qubits": 9, "shots": 30, "base_seed": evidence.DEFAULT_BASE_SEED,
        "tau": 0.25, "omega": [1.0, 0.5, 0.25], "systems": ["h2bench", "rhodopsin"],
        "poses": ["deposited", "start"],
    }
    assert manifest["status"] == "complete"
    assert manifest["summary"]["runs_ok"] == 4
    assert (out_dir / "run.log").read_text(encoding="utf-8").count("[rhodopsin/start]") >= 1

    for run in manifest["runs"]:
        assert run["status"] == "ok"
        record = json.loads((out_dir / run["file"]).read_text(encoding="utf-8"))
        ex = record["execution"]
        assert ex["shots"] == 30 and sum(ex["counts"].values()) == 30
        assert ex["ci95_wilson"][0] <= ex["prob_zero"] <= ex["ci95_wilson"][1]
        assert ex["job_id"] is None
        assert record["circuit"]["hqc_estimate"]["hqc_cost"] > 5.0
        if HAS_PYTKET:
            assert record["circuit"]["pytket_json"]["commands"]
            assert record["circuit"]["gate_counts"]["ZZPhase"] == 32  # 8 per site, 4 sites

    # The `start` pose is the showdown's starting misalignment, so its exact
    # P(0) must match the committed benchmark where that file exists.
    showdown = _REPO_ROOT / "benchmarks" / "molecular_showdown.json"
    if showdown.exists():
        rows = {r["system_id"]: r for r in json.loads(showdown.read_text(encoding="utf-8"))["molecular_showdown_results"]}
        for run in manifest["runs"]:
            if run["pose"] == "start" and run["system_id"] in rows:
                assert run["prob_zero_exact"] == pytest.approx(rows[run["system_id"]]["start_p0"], abs=1e-3)
    print(f"PASS: test_evidence_writer_produces_manifest_with_required_fields ({out_dir.name})")


def test_evidence_cli_rejects_unknown_system(tmp_path):
    with pytest.raises(SystemExit):
        evidence.main(["--systems", "unobtainium", "--out", str(tmp_path)])
    print("PASS: test_evidence_cli_rejects_unknown_system")


# ---------------------------------------------------------------------
# nexus backend without credentials
# ---------------------------------------------------------------------

def test_nexus_backend_without_credentials_raises_clear_error(monkeypatch):
    """No login -> `CredentialsRequired` naming `aqora login` and the command
    to rerun, never a traceback from inside aqora."""
    aqora = pytest.importorskip("aqora")

    def no_login(client):
        raise aqora.ClientError("GraphQL had errors: Missing Authorization")

    monkeypatch.setattr(runner, "_viewer_username", no_login)

    with pytest.raises(CredentialsRequired) as excinfo:
        check_credentials()
    message = str(excinfo.value)
    assert "aqora login" in message
    assert "python -m src.qrotate.evidence" in message
    assert "Missing Authorization" in message

    backend = NexusBackend("H2-2SC")
    prog = _random_program(np.random.default_rng(2), n_sites=2)
    with pytest.raises(CredentialsRequired):
        backend.run(prog, 10)
    assert backend.is_syntax_checker and backend.cost_unit.startswith("free")
    print("PASS: test_nexus_backend_without_credentials_raises_clear_error")


def test_nexus_backend_names_and_costing():
    for target in NEXUS_TARGETS:
        be = get_backend(f"nexus:{target}")
        assert isinstance(be, NexusBackend) and be.name == f"nexus:{target}" and be.is_h_series
    assert get_backend("h2-2e").target == "H2-2E"
    with pytest.raises(ValueError):
        get_backend("nexus:H9-X")
    with pytest.raises(ValueError):
        get_backend("abacus")

    prog = _random_program(np.random.default_rng(4))
    cost = NexusBackend("H2-2E").cost(prog, shots=100)
    assert cost["two_qubit_count"] == 32 and cost["hqc_cost"] == pytest.approx(13.64, abs=0.01)
    assert StatevectorBackend().cost(prog, shots=100) is None
    print("PASS: test_nexus_backend_names_and_costing")


# ---------------------------------------------------------------------
# selene (opt-in: a build takes minutes on a cold machine)
# ---------------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("QROTATE_TEST_SELENE") != "1",
                    reason="set QROTATE_TEST_SELENE=1 to run the local Selene emulator")
def test_selene_backend_matches_statevector_within_shot_noise():
    ok, why = runner.selene_available()
    if not ok:
        pytest.skip(why)
    prog = _random_program(np.random.default_rng(8), n_sites=2)
    res = runner.SeleneBackend().run(prog, 200, seed=1)
    assert res.shots == 200
    assert res.ci_low - 0.02 <= prog.exact_prob_zero() <= res.ci_high + 0.02
    print(f"PASS: test_selene_backend_matches_statevector_within_shot_noise (P0={res.prob_zero:.3f})")
