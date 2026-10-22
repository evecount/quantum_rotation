"""Client/node split: fingerprints cross the wire, coordinates never do."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from qrotate.client import (  # noqa: E402
    Client, Fingerprint, NodeError, build_screen_request, fingerprint, phases_sha256,
)
from qrotate.cli import app as cli_app  # noqa: E402
from qrotate.node import ExecutionBackend, NexusBackend, StatevectorBackend, create_app, cost_estimate  # noqa: E402
from qrotate.structures import load_active_sites  # noqa: E402

SITES = load_active_sites(str(_REPO_ROOT / "benchmarks" / "active_sites.json"))
COORD_KEYS = {"coords", "coordinates", "xyz", "x", "y", "z", "atoms", "atom_names", "positions"}


@pytest.fixture(scope="module")
def node():
    return TestClient(create_app())


@pytest.fixture(scope="module")
def rhodopsin():
    site = SITES["rhodopsin"]
    target = fingerprint(site["pocket"], sites=4, label="rhodopsin pocket")
    ligand = fingerprint(site["ligand"], sites=4, label="RET")
    return target, ligand


def _write_pdb(path: Path, elements, coords, resname="RET"):
    lines = []
    for i, (el, (x, y, z)) in enumerate(zip(elements, coords), start=1):
        name = f"{el}{i}"[:4]
        lines.append(f"HETATM{i:5d} {name:<4s} {resname} A 296    "
                     f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {el:>2s}")
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _walk(obj, path=""):
    """Every (path, value) pair in a JSON tree."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def _looks_like_coordinates(value) -> bool:
    """A list of >= 2 triples of numbers is a coordinate array whatever it is called."""
    if not isinstance(value, list) or len(value) < 2:
        return False
    return all(isinstance(row, (list, tuple)) and len(row) == 3
               and all(isinstance(c, (int, float)) for c in row) for row in value)


# ---------------------------------------------------------------------------

def test_fingerprint_carries_no_coordinates_and_round_trips(rhodopsin):
    target, ligand = rhodopsin
    assert target.sites == 4 and len(target.phases) == 4
    assert ligand.element_summary == {"C": 20}
    assert ligand.n_atoms == SITES["rhodopsin"]["ligand"]["n_atoms"]
    data = json.loads(ligand.to_json())
    assert set(data) == set(Fingerprint.FIELDS)
    assert not (set(data) & COORD_KEYS)
    assert Fingerprint.from_json(ligand.to_json()) == ligand
    assert ligand.sha256 == phases_sha256(ligand.phases, 4)
    # Same molecule, reordered atoms: same fingerprint, same hash.
    site = SITES["rhodopsin"]["ligand"]
    perm = np.random.default_rng(0).permutation(site["n_atoms"])
    shuffled = {"elements": [site["elements"][i] for i in perm],
                "coords": [site["coords"][i] for i in perm]}
    assert fingerprint(shuffled, sites=4, label="RET").sha256 == ligand.sha256
    # Tampered phases are caught.
    data["phases"][0] += 0.1
    with pytest.raises(ValueError):
        Fingerprint.from_dict(data)
    # A structure cannot be smuggled through as a fingerprint.
    with pytest.raises(ValueError):
        Fingerprint.from_dict({**ligand.to_dict(), "coords": site["coords"]})


def test_screen_request_body_contains_no_coordinate_arrays(rhodopsin):
    target, ligand = rhodopsin
    body = build_screen_request(target, [ligand, target], backend="statevector", shots=100)
    text = json.dumps(body)
    assert "coords" not in text and "xyz" not in text
    for path, value in _walk(body):
        last = path.rsplit("/", 1)[-1].split("[")[0]
        assert last not in COORD_KEYS, path
    # No list anywhere in the body is a list of 3-vectors.
    def lists(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                yield from lists(v)
        elif isinstance(obj, list):
            yield obj
            for v in obj:
                yield from lists(v)
    assert not any(_looks_like_coordinates(l) for l in lists(body))
    # And the only float arrays are the phase registers, `sites` long.
    for path, value in _walk(body):
        if isinstance(value, float) and not any(k in path for k in ("phases", "omega", "tau")):
            raise AssertionError(f"unexpected float at {path}")
    assert len(body["target"]["phases"]) == 4
    assert body["target"]["element_summary"] == target.element_summary


def test_node_rejects_a_body_that_carries_coordinates(node, rhodopsin):
    target, ligand = rhodopsin
    body = build_screen_request(target, [ligand])
    body["ligands"][0]["coords"] = SITES["rhodopsin"]["ligand"]["coords"]
    r = node.post("/v1/screen", json=body)
    assert r.status_code == 422, r.text


def test_health(node):
    r = node.get("/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok" and data["service"] == "qrotate-node"
    backends = {b["name"]: b["ready"] for b in data["backends"]}
    assert backends == {"statevector": True, "nexus": False}


def test_cost_matches_the_compiled_circuit(node):
    from qrotate.circuits import compile_h2_native_gates
    from qrotate.metrics import compute_circuit_hqc_cost
    from qrotate.node import compile_pair
    for sites in (4, 8):
        # Default settings (tau = 0): the circuit a screen actually runs.
        r = node.get("/v1/cost", params={"sites": sites, "shots": 100, "n_ligands": 3})
        assert r.status_code == 200, r.text
        c = r.json()
        ref = compute_circuit_hqc_cost(compile_pair([0.3] * sites, [0.7] * sites), shots=100)
        assert c["n_qubits"] == 2 * sites + 1
        assert c["single_qubit_count"] == ref["single_qubit_count"]
        assert c["two_qubit_count"] == ref["two_qubit_count"]
        assert c["hqc_per_circuit"] == ref["hqc_cost"]
        assert c["hqc_total"] == round(3 * c["hqc_per_circuit"], 2)
        assert c["hqc_per_circuit"] == cost_estimate(sites, shots=100)["hqc_per_circuit"]
        # With the U_tube evolution switched on, the closed-form model applies.
        r = node.get("/v1/cost", params={"sites": sites, "shots": 100, "tau": 0.25,
                                         "omega": [1.0, 0.5, 0.25]})
        assert r.status_code == 200, r.text
        c = r.json()
        model = compile_h2_native_gates(sites)
        assert c["single_qubit_count"] == model["single_qubit_laser_gates"]
        assert c["two_qubit_count"] == model["native_two_qubit_zzphase"]
    assert node.get("/v1/cost", params={"sites": 5}).status_code == 422
    assert node.get("/v1/cost", params={"sites": 4, "omega": [1.0]}).status_code == 422


def test_screen_round_trip_on_statevector(node, rhodopsin):
    target, ligand = rhodopsin
    client = Client(http=node)
    job_id = client.submit_screen(target, [ligand, target], backend="statevector", shots=400, seed=7)
    job = client.wait(job_id, timeout=60)
    assert job["status"] == "done" and job["n_ligands"] == 2
    assert job["target_sha256"] == target.sha256
    self_match, other = job["results"][1], job["results"][0]
    assert self_match["label"] == "rhodopsin pocket"
    assert self_match["ideal_p0"] == pytest.approx(1.0)
    assert self_match["p0"] == 1.0 and self_match["counts_0"] == 400
    assert self_match["ci95_low"] > 0.98 and self_match["ci95_high"] == 1.0
    assert other["label"] == "RET" and 0.5 <= other["ideal_p0"] < 1.0
    assert other["ci95_low"] <= other["p0"] <= other["ci95_high"]
    assert other["counts_0"] + other["counts_1"] == 400
    assert other["hqc"]["n_qubits"] == 9 and other["hqc"]["hqc_cost"] > 5
    assert other["backend_job_id"] is None
    # Same seed, same shot noise.
    again = client.screen(target, [ligand, target], shots=400, seed=7)
    assert [r["counts_0"] for r in again["results"]] == [r["counts_0"] for r in job["results"]]
    # shots=0 is the ideal probability with a degenerate interval.
    ideal = client.screen(target, [ligand], shots=0)
    r0 = ideal["results"][0]
    assert r0["mode"] == "ideal" and r0["p0"] == r0["ideal_p0"] == r0["ci95_low"] == r0["ci95_high"]


def test_screen_errors(node, rhodopsin):
    target, ligand = rhodopsin
    client = Client(http=node)
    with pytest.raises(NodeError) as exc:
        client.submit_screen(target, [ligand], backend="nexus")
    assert exc.value.status_code == 501
    with pytest.raises(NodeError) as exc:
        client.submit_screen(target, [ligand], backend="abacus")
    assert exc.value.status_code == 400
    eight = fingerprint(SITES["rhodopsin"]["ligand"], sites=8)
    with pytest.raises(ValueError):
        build_screen_request(target, [eight])
    assert node.get("/v1/jobs/nope").status_code == 404
    with pytest.raises(NotImplementedError):
        NexusBackend().run(None)
    assert isinstance(StatevectorBackend(), ExecutionBackend)
    assert isinstance(NexusBackend(), ExecutionBackend)


def test_cli_fingerprint_on_a_pdb_produces_n_phases(tmp_path):
    site = SITES["rhodopsin"]["ligand"]
    pdb = tmp_path / "ret.pdb"
    _write_pdb(pdb, site["elements"], site["coords"])
    runner = CliRunner()
    for sites in (4, 8):
        res = runner.invoke(cli_app, ["fingerprint", str(pdb), "--sites", str(sites), "--resname", "RET"])
        assert res.exit_code == 0, res.output
        data = json.loads(res.output)
        assert len(data["phases"]) == sites and data["sites"] == sites
        assert data["element_summary"] == {"C": 20}
        assert not (set(data) & COORD_KEYS)
    # The PDB path and the JSON site give the same fingerprint.
    res = runner.invoke(cli_app, ["fingerprint", str(pdb), "-o", str(tmp_path / "ret.json")])
    assert res.exit_code == 0, res.output
    saved = Fingerprint.load(tmp_path / "ret.json")
    assert saved.sha256 == fingerprint(site, sites=4).sha256
    res = runner.invoke(cli_app, ["fingerprint", str(pdb), "--table"])
    assert res.exit_code == 0 and "shell" in res.output
    res = runner.invoke(cli_app, ["fingerprint", str(pdb), "--resname", "XYZ"])
    assert res.exit_code != 0


def test_cli_compile_and_local_screen(tmp_path, rhodopsin):
    target, ligand = rhodopsin
    t, l = tmp_path / "target.json", tmp_path / "ligand.json"
    target.save(t)
    ligand.save(l)
    runner = CliRunner()
    res = runner.invoke(cli_app, ["compile", str(t), str(l), "--shots", "100"])
    assert res.exit_code == 0, res.output
    comp = json.loads(res.output)
    assert comp["n_qubits"] == 9 and comp["two_qubit_count"] > 0
    res = runner.invoke(cli_app, ["screen", str(t), str(l), str(t), "--local", "--shots", "50", "--seed", "1"])
    assert res.exit_code == 0, res.output
    out = json.loads(res.output)
    assert out["status"] == "done" and len(out["results"]) == 2
    assert out["results"][1]["p0"] == 1.0
    res = runner.invoke(cli_app, ["screen", str(t), str(l), "--local", "--table"])
    assert res.exit_code == 0 and "Wilson" in res.output
    res = runner.invoke(cli_app, ["screen", str(t), str(l)])
    assert res.exit_code != 0
