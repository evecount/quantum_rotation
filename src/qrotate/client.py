"""Client side of the Q-Rotate client/node split.

The lab keeps its structure. This module turns a molecule into a compact
phase *fingerprint* locally and talks to a node (``qrotate.node``) that runs
the SWAP-test circuit and returns an overlap score P(0).

What leaves the lab is a :class:`Fingerprint`: one phase per shell (``sites``
of them), an element census, a hash of the phases and the encoder version.
Atomic coordinates are never part of it, and :class:`Client` has no code path
that could serialise them. The privacy claim is strictly "coordinate-free,
reduced exposure": the fingerprint is derived from the structure and is itself
information about it (see ``docs/10_client_node_protocol.md``). It is not a
zero-knowledge protocol and nothing here should be labelled as one.

Usage::

    from qrotate.client import fingerprint, Client

    target = fingerprint("pocket.pdb", sites=4)
    ligand = fingerprint("ligand.sdf", sites=4)
    client = Client("http://localhost:8000")
    job_id = client.submit_screen(target, [ligand], backend="statevector", shots=200)
    print(client.wait(job_id)["results"][0]["p0"])
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional, Sequence, Union

import numpy as np

from . import __version__
from .hpc_bridge import MolecularGeometry, molecular_shell_phases, shell_moment_orders
from .structures import _parse_pdb, _parse_sdf

# Sites (shells, one qubit each per register) the product supports. 4 is the
# H2 single-shell register (9 qubits), 8 the dual-shell one (17 qubits).
SUPPORTED_SITES = (4, 8)

# The encoder the phases came from. Bump when `molecular_shell_phases` changes
# in a way that makes old fingerprints incomparable with new ones.
ENCODER = "molecular_shell_phases/v1"

# Phases are rounded before hashing so that the hash survives a JSON round
# trip (floats print with 17 significant digits; 12 is well inside that).
_PHASE_DECIMALS = 12

GeometryLike = Union[str, os.PathLike, MolecularGeometry, Mapping[str, Any]]


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------

def _round_phases(phases: Sequence[float]) -> list[float]:
    return [round(float(p), _PHASE_DECIMALS) + 0.0 for p in phases]


def phases_sha256(phases: Sequence[float], sites: int) -> str:
    """Hash of the canonical JSON of the rounded phases. Identical fingerprints
    hash identically regardless of which process produced them."""
    payload = json.dumps({"sites": int(sites), "phases": _round_phases(phases)},
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Fingerprint:
    """What crosses the wire. No field holds a coordinate.

    phases          one angle per shell in [-pi, pi], from the geometry alone
    sites           number of shells (= qubits per register)
    element_summary heavy-atom census, e.g. {"C": 20} for retinal
    sha256          hash of the rounded phases (see `phases_sha256`)
    qrotate_version package version that produced it
    encoder         encoder identifier, for comparability across versions
    label           free text the client chose (a name, never a structure)
    moment_orders   which angular moment encoded each shell (0 = empty shell);
                    a shell at order k is only defined modulo 360/k degrees
    """
    phases: list[float]
    sites: int
    element_summary: dict[str, int]
    sha256: str
    qrotate_version: str = __version__
    encoder: str = ENCODER
    label: str = ""
    moment_orders: list[int] = field(default_factory=list)

    # Field names a fingerprint may carry. Anything else (coords, xyz, ...)
    # is rejected by `from_dict`, so a mislabelled structure cannot sneak
    # through the client as a fingerprint.
    FIELDS = ("phases", "sites", "element_summary", "sha256", "qrotate_version",
              "encoder", "label", "moment_orders")

    def __post_init__(self):
        if self.sites != len(self.phases):
            raise ValueError(f"sites={self.sites} but {len(self.phases)} phases")
        if self.sha256 != phases_sha256(self.phases, self.sites):
            raise ValueError("sha256 does not match the phases")

    @property
    def n_atoms(self) -> int:
        return int(sum(self.element_summary.values()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Fingerprint":
        unknown = sorted(set(data) - set(cls.FIELDS))
        if unknown:
            raise ValueError(f"not a fingerprint: unexpected fields {unknown}")
        return cls(
            phases=_round_phases(data["phases"]),
            sites=int(data["sites"]),
            element_summary={str(k): int(v) for k, v in dict(data["element_summary"]).items()},
            sha256=str(data["sha256"]),
            qrotate_version=str(data.get("qrotate_version", __version__)),
            encoder=str(data.get("encoder", ENCODER)),
            label=str(data.get("label", "")),
            moment_orders=[int(o) for o in data.get("moment_orders", [])],
        )

    @classmethod
    def from_json(cls, text: str) -> "Fingerprint":
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: Union[str, os.PathLike]) -> "Fingerprint":
        with open(path, encoding="utf-8") as handle:
            return cls.from_json(handle.read())

    def save(self, path: Union[str, os.PathLike]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.to_json(indent=2))
            handle.write("\n")


# ---------------------------------------------------------------------------
# Geometry loading (stays on the client; nothing here is ever sent)
# ---------------------------------------------------------------------------

def _atoms_to_geometry(atoms: list[dict], name: str) -> MolecularGeometry:
    if not atoms:
        raise ValueError(f"{name}: no heavy atoms to encode")
    return MolecularGeometry(
        name=name,
        atom_names=[a["element"] for a in atoms],   # the encoder weights by element
        coordinates=np.array([a["xyz"] for a in atoms], dtype=float),
    )


def load_geometry(
    source: GeometryLike,
    *,
    resname: Optional[str] = None,
    chain: Optional[str] = None,
    resseq: Optional[int] = None,
    label: Optional[str] = None,
) -> MolecularGeometry:
    """Reads a structure into a `MolecularGeometry`.

    `source` may be a PDB/SDF path, a `MolecularGeometry`, or a mapping with
    ``elements`` and ``coords`` (the shape of each half of a
    ``benchmarks/active_sites.json`` entry). For a PDB file, `resname` (and
    optionally `chain`, `resseq`) selects one residue, typically the ligand;
    without it every heavy atom of the first model is used, which is what you
    want for a pocket extract.
    """
    if isinstance(source, MolecularGeometry):
        return source

    if isinstance(source, Mapping):
        if "phases" in source and "coords" not in source:
            raise ValueError("that is already a fingerprint, not a structure")
        coords = source["coords"]
        elements = list(source.get("elements") or ["C"] * len(coords))
        return MolecularGeometry(
            name=label or str(source.get("resname") or source.get("name") or "structure"),
            atom_names=[str(e).upper() for e in elements],
            coordinates=np.array(coords, dtype=float),
        )

    path = os.fspath(source)
    ext = os.path.splitext(path)[1].lower()
    name = label or os.path.splitext(os.path.basename(path))[0]
    if ext in (".sdf", ".mol"):
        return _atoms_to_geometry(_parse_sdf(path), name)
    if ext not in (".pdb", ".ent", ""):
        raise ValueError(f"unsupported structure format {ext!r} (use .pdb or .sdf)")

    atoms, _title = _parse_pdb(path)
    if resname is not None:
        want = resname.strip().upper()
        atoms = [a for a in atoms if a["resname"].upper() == want
                 and (chain is None or a["chain"] == chain)
                 and (resseq is None or a["resseq"] == resseq)]
        if not atoms:
            raise ValueError(f"{path}: no heavy atoms for residue {resname} "
                             f"{chain or ''}{resseq if resseq is not None else ''}")
        name = label or f"{name}:{want}"
    return _atoms_to_geometry(atoms, name)


def fingerprint(
    source: GeometryLike,
    sites: int = 4,
    *,
    resname: Optional[str] = None,
    chain: Optional[str] = None,
    resseq: Optional[int] = None,
    label: Optional[str] = None,
) -> Fingerprint:
    """Encodes a structure into a `Fingerprint` of `sites` phases, locally.

    This is the only place the client touches coordinates. The returned object
    carries the phases, an element census and a hash; the geometry it came
    from is not referenced by it.
    """
    if sites not in SUPPORTED_SITES:
        raise ValueError(f"sites must be one of {SUPPORTED_SITES}, got {sites}")
    geometry = load_geometry(source, resname=resname, chain=chain, resseq=resseq, label=label)
    phases = _round_phases(molecular_shell_phases(geometry, n_qubits=sites))
    elements = Counter(str(n).strip().upper() for n in geometry.atom_names)
    return Fingerprint(
        phases=phases,
        sites=sites,
        element_summary=dict(sorted(elements.items())),
        sha256=phases_sha256(phases, sites),
        label=label if label is not None else geometry.name,
        moment_orders=shell_moment_orders(geometry, n_qubits=sites),
    )


# ---------------------------------------------------------------------------
# Wire format
# ---------------------------------------------------------------------------

def build_screen_request(
    target: Fingerprint,
    ligands: Sequence[Fingerprint],
    backend: str = "statevector",
    shots: int = 200,
    tau: float = 0.0,
    omega: Sequence[float] = (0.0, 0.0, 0.0),
    seed: Optional[int] = None,
) -> dict[str, Any]:
    """The JSON body of ``POST /v1/screen``. A pure function of fingerprints,
    so a test can assert what it contains (and what it never contains)."""
    if not ligands:
        raise ValueError("at least one ligand fingerprint is required")
    for lig in ligands:
        if lig.sites != target.sites:
            raise ValueError(f"ligand {lig.label!r} has {lig.sites} sites, target has {target.sites}")
    body: dict[str, Any] = {
        "target": target.to_dict(),
        "ligands": [lig.to_dict() for lig in ligands],
        "backend": backend,
        "shots": int(shots),
        "tau": float(tau),
        "omega": [float(w) for w in omega],
    }
    if seed is not None:
        body["seed"] = int(seed)
    return body


class NodeError(RuntimeError):
    """The node answered with an error status."""

    def __init__(self, status_code: int, detail: Any):
        super().__init__(f"node returned {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class Client:
    """HTTP client for a Q-Rotate node.

    `http` may be any object with ``get``/``post`` returning httpx-style
    responses (an ``httpx.Client`` or FastAPI's ``TestClient``). Without one,
    an ``httpx.Client`` against `node_url` is created lazily.
    """

    def __init__(self, node_url: str = "http://127.0.0.1:8000", http=None, timeout: float = 30.0):
        self.node_url = node_url.rstrip("/")
        self._http = http
        self._timeout = timeout

    @property
    def http(self):
        if self._http is None:
            import httpx
            self._http = httpx.Client(base_url=self.node_url, timeout=self._timeout)
        return self._http

    def _url(self, path: str) -> str:
        # TestClient and a base_url'd httpx.Client both accept a bare path.
        return path

    @staticmethod
    def _check(response) -> Any:
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise NodeError(response.status_code, detail)
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._check(self.http.get(self._url("/v1/health")))

    def cost(self, sites: int = 4, shots: int = 200, n_ligands: int = 1,
             tau: float = 0.0, omega: Sequence[float] = (0.0, 0.0, 0.0)) -> dict[str, Any]:
        """Gate counts and HQC the node would spend; nothing is executed."""
        params = {"sites": sites, "shots": shots, "n_ligands": n_ligands,
                  "tau": tau, "omega": [float(w) for w in omega]}
        return self._check(self.http.get(self._url("/v1/cost"), params=params))

    def submit_screen(
        self,
        target: Fingerprint,
        ligands: Sequence[Fingerprint],
        backend: str = "statevector",
        shots: int = 200,
        **kwargs: Any,
    ) -> str:
        """Submits a screen and returns the job id. Only fingerprints are sent."""
        body = build_screen_request(target, ligands, backend=backend, shots=shots, **kwargs)
        data = self._check(self.http.post(self._url("/v1/screen"), json=body))
        return str(data["job_id"])

    def result(self, job_id: str) -> dict[str, Any]:
        """Current state of a job: status plus, once done, per-ligand results."""
        return self._check(self.http.get(self._url(f"/v1/jobs/{job_id}")))

    def wait(self, job_id: str, timeout: float = 120.0, poll: float = 0.2) -> dict[str, Any]:
        """Polls until the job is done or failed. Raises on failure or timeout."""
        deadline = time.monotonic() + timeout
        while True:
            job = self.result(job_id)
            if job["status"] == "done":
                return job
            if job["status"] == "failed":
                raise NodeError(500, job.get("error") or "job failed")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"job {job_id} still {job['status']} after {timeout}s")
            time.sleep(poll)

    def screen(
        self,
        target: Fingerprint,
        ligands: Sequence[Fingerprint],
        backend: str = "statevector",
        shots: int = 200,
        timeout: float = 120.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """submit_screen + wait."""
        return self.wait(self.submit_screen(target, ligands, backend=backend, shots=shots, **kwargs),
                         timeout=timeout)


__all__ = [
    "Fingerprint", "fingerprint", "load_geometry", "phases_sha256",
    "build_screen_request", "Client", "NodeError", "SUPPORTED_SITES", "ENCODER",
]
