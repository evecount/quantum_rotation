# Chapter 10: The Client/Node Protocol

## What crosses the wire, what the node learns, and what it does not

The Decentralized Quantum Testing Facility idea is a split: a lab keeps its
structure and computes a compact *phase fingerprint* locally; a node holds
the hardware access, runs the blind parity (SWAP) test, and returns an overlap
score. This chapter documents that split as it exists in software:

| Piece | Module | Runs where |
|---|---|---|
| `fingerprint()`, `Fingerprint`, `Client` | `src/qrotate/client.py` | the lab |
| `POST /v1/screen`, `GET /v1/jobs/{id}`, `GET /v1/cost`, `GET /v1/health` | `src/qrotate/node.py` | the node |
| `qrotate fingerprint / compile / screen / serve` | `src/qrotate/cli.py` | either |

The machine-readable contract is `docs/openapi.json` (regenerate with
`qrotate openapi -o docs/openapi.json`).

---

### 1. The honest one-paragraph version

The node never receives atomic coordinates. It receives, per molecule, a
register of `sites` phase angles plus an element census and a hash. That
register is **derived from** the structure by a deterministic encoder, so it
is information about the structure: a node that stores fingerprints learns
each molecule's radial-shell angular moments, how many atoms of each element
it has, and (across repeated queries) how its overlap with the target changes.
What the node cannot do from a fingerprint is reconstruct the geometry: the
encoder maps *N* atoms × 3 coordinates to `sites` angles, discarding radii,
the z-profile and every per-atom detail. This is a **coordinate-free,
reduced-exposure** protocol. It is **not zero-knowledge**, and no label in the
code, the docs or the OpenAPI schema should say otherwise. See
[Chapter 3, section 3](03_the_blind_parity_test.md) for the same caveat on the
circuit side.

---

### 2. Client side: the fingerprint

```bash
qrotate fingerprint 1U19.pdb --resname RET --sites 4 -o retinal.json
qrotate fingerprint pocket.pdb --sites 4 -o pocket.json     # every heavy atom in the file
```

or in Python:

```python
from qrotate.client import fingerprint
fp = fingerprint("1U19.pdb", sites=4, resname="RET")
fp.save("retinal.json")
```

`fingerprint()` accepts a PDB or SDF path, a `MolecularGeometry`, or a
mapping with `elements` and `coords` (the shape of each half of a
`benchmarks/active_sites.json` entry). It is the only function on the client
that touches coordinates. The result:

```json
{
  "phases": [0.176514690275, -3.039143616109, 0.257549034289, -1.897446165827],
  "sites": 4,
  "element_summary": {"C": 66, "N": 10, "O": 17, "S": 1},
  "sha256": "71561550f0834f91511f63cdbff5a92e6b7fbfef049fdb047a3fad761e372439",
  "qrotate_version": "0.1.0",
  "encoder": "molecular_shell_phases/v1",
  "label": "rhodopsin pocket",
  "moment_orders": [1, 1, 1, 1]
}
```

| Field | What it is | What it reveals |
|---|---|---|
| `phases` | one angle per radial shell, `arg(M_k)/k` of the weighted angular moment (`hpc_bridge.molecular_shell_phases`) | the orientation signature of each shell about the z axis, modulo 360/k degrees |
| `sites` | 4 (9-qubit H2 register) or 8 (17-qubit) | register size |
| `element_summary` | heavy-atom census | composition and atom count, not arrangement |
| `sha256` | hash of the rounded phases | identity: the same molecule in the same pose hashes identically regardless of atom order |
| `qrotate_version`, `encoder` | provenance | which encoder produced it, so stale fingerprints are not compared with new ones |
| `label` | free text chosen by the client | whatever the client puts there; use a code name if the target is confidential |
| `moment_orders` | which angular moment each shell used (0 = empty shell) | whether a shell is symmetric; a shell at order 2 is defined only modulo 180° |

`Fingerprint` is a frozen dataclass with a fixed field list. `from_dict`
rejects any extra key, so a structure dict cannot be passed off as a
fingerprint, and `__post_init__` recomputes the hash, so a tampered register
is rejected on either side.

The phases are rounded to 12 decimals before hashing. Two processes that
encode the same atoms get the same hash, and a JSON round trip does not
change it.

---

### 3. The wire

`Client.submit_screen(target, ligands, backend, shots)` sends exactly this
body (`client.build_screen_request` is a pure function of fingerprints, and
`tests/test_client_node.py` walks the body asserting no key is a coordinate
name and no list anywhere is a list of 3-vectors):

```json
{
  "target":  { ...fingerprint... },
  "ligands": [ { ...fingerprint... }, ... ],
  "backend": "statevector",
  "shots": 200,
  "tau": 0.0,
  "omega": [0.0, 0.0, 0.0],
  "seed": 7
}
```

| Endpoint | Request | Response |
|---|---|---|
| `POST /v1/screen` | fingerprints + backend + shots (+ `tau`, `omega`, `seed`) | `202 {job_id, status, n_ligands, backend}` |
| `GET /v1/jobs/{id}` | | status; per ligand: `p0`, Wilson 95 % `ci95_low/high`, `counts_0/1`, `ideal_p0` (simulators only), `hqc` gate counts and estimate, `backend_job_id` |
| `GET /v1/cost?sites=4&shots=200&n_ligands=1` | | compiled gate counts, depth, HQC per circuit and total; nothing executes |
| `GET /v1/health` | | version, pytket availability, backends and whether each is ready |

Errors: `422` for a malformed fingerprint (extra fields such as `coords`,
hash mismatch, unsupported `sites`, mixed register sizes), `400` unknown
backend, `501` backend known but not available on this node, `404` unknown
job.

`tau` and `omega` are the `U_tube` evolution applied to the ligand register
before the SWAP test (Chapter 2). The default `tau = 0` makes a screen the
plain overlap of the two registers as submitted; a pose search is a sequence
of screens with the ligand re-fingerprinted at each trial pose, driven from
the client, which is the Chapter 4 RUS loop in distributed form.

---

### 4. What the node computes

For every ligand in a job the node:

1. builds the SWAP-test circuit for `(target.phases, ligand.phases)` with
   `circuits.build_pytket_swap_test_circuit` and rebases it to the H-series
   gate set;
2. hands a `CircuitJob` to the chosen `ExecutionBackend`;
3. reports `p0 = counts_0 / shots`, the Wilson 95 % interval
   (`metrics._wilson_interval`), and the HQC estimate from the compiled
   circuit's real gate counts (`metrics.compute_circuit_hqc_cost`).

Backends implement one method, `run(CircuitJob) -> ExecutionResult`, and a
`ready` flag:

| Backend | Status | What it does |
|---|---|---|
| `statevector` | ready | exact simulation of the compiled gate sequence (`circuits.simulate_swap_test_statevector`) followed by binomial shot sampling of the ancilla (`circuits.simulate_shot_sampling`); `shots = 0` returns the ideal probability |
| `nexus` | stub, answers `501` | Quantinuum Nexus / Selene / H2 via `qrotate.runner`, on a parallel branch; `NexusBackend.run` raises `NotImplementedError("use qrotate.runner when merged")` until then |

Jobs run in a FastAPI background task and live in a `JobStore`. The shipped
`InMemoryJobStore` is a dict behind a lock; the interface (`create`, `get`,
`update`, `list_ids`) is what a Redis or SQLite store implements.

---

### 5. What the node learns, and what it does not

**The node learns:**

- the fingerprint itself: `sites` angles per molecule, the element census,
  and the label the client chose;
- the overlap P(0) between every ligand and the target it submitted them
  against, with its confidence interval;
- across many jobs from one client, how the target's overlap with a series of
  candidates varies, which is an aggregate signal about the target's register.

**The node does not learn:**

- any atomic coordinate, radius, bond or residue identity; none is in the
  body and the client has no code path that serialises one;
- the geometry behind a fingerprint: the encoder is many-to-one (every
  rotation of the molecule about z shifts all phases equally, and every
  arrangement with the same shell moments encodes identically), so the
  fingerprint does not determine the structure;
- which shots belong to which atoms: the measured bit is the ancilla's parity,
  one aggregate bit per shot.

**What the protocol does not promise:**

- It is not zero-knowledge. The fingerprint is a lossy but deterministic
  function of the structure, and a node that has seen enough fingerprints of
  related molecules can compare them. Treat it as a reduction in exposure, in
  the same way that sending a hash of a document is less than sending the
  document but is not nothing.
- It does not authenticate either party or encrypt the transport. Run the
  node behind TLS and whatever access control the deployment needs; this
  chapter describes only the application payload.
- Results from the `statevector` backend are a simulation. Nothing in this
  repository has run on physical H-series hardware; the `nexus` backend is the
  place that will change.

---

### 6. Running it

```bash
pip install -e ".[product]"            # fastapi, uvicorn, httpx, typer
qrotate serve --port 8000              # the node
qrotate fingerprint ligand.sdf -o ligand.json
qrotate fingerprint pocket.pdb -o pocket.json
qrotate screen pocket.json ligand.json --node http://127.0.0.1:8000 --shots 200 --table
qrotate screen pocket.json ligand.json --local        # same thing, in-process, no node
qrotate compile pocket.json ligand.json --shots 200   # gate counts and HQC, nothing runs
python examples/demo_client_node.py                   # six benchmark systems, 6 x 6 P(0) matrix
```

`qrotate screen --local` and the node share `node.execute_screen`, so a local
run and a remote run of the same fingerprints with the same seed give the same
counts.
