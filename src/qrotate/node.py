"""Node side of the Q-Rotate client/node split: a FastAPI service.

A node receives phase fingerprints (never coordinates), prepares the SWAP-test
circuit for each target/ligand pair, runs it on an execution backend and
reports P(0) with a Wilson confidence interval and an HQC estimate.

    POST /v1/screen         submit fingerprints + backend + shots -> job id
    GET  /v1/jobs/{id}      status, per-ligand P(0), CI, HQC, backend job id
    GET  /v1/cost           gate counts + HQC for sites/shots, no execution
    GET  /v1/health         version and which backends are ready

Execution goes through :class:`ExecutionBackend`. :class:`StatevectorBackend`
wraps the project's exact simulator and shot sampler; :class:`NexusBackend`
is the hook for ``qrotate.runner`` (Selene / Nexus H2 targets, on a parallel
branch) and raises until that lands. Jobs live in a :class:`JobStore`; the
in-memory one here is what a Redis or SQLite store would replace.

Run it with ``qrotate serve`` or ``uvicorn qrotate.node:app``.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Protocol, Sequence, runtime_checkable

import numpy as np
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from . import __version__
from .circuits import (
    HAS_PYTKET,
    build_pytket_swap_test_circuit,
    rebase_to_h2_gateset,
    simulate_shot_sampling,
    simulate_swap_test_statevector,
)
from .client import SUPPORTED_SITES, Fingerprint
from .metrics import _wilson_interval, compute_circuit_hqc_cost

JobState = Literal["queued", "running", "done", "failed"]


# ---------------------------------------------------------------------------
# Execution backends
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CircuitJob:
    """One SWAP-test evaluation: both phase registers and the run settings."""
    pocket_phases: tuple[float, ...]
    ligand_phases: tuple[float, ...]
    tau: float = 0.0
    omega: tuple[float, float, float] = (0.0, 0.0, 0.0)
    shots: int = 200
    seed: Optional[int] = None

    @property
    def sites(self) -> int:
        return len(self.pocket_phases)


@dataclass
class ExecutionResult:
    """What a backend hands back. `p0` is the estimate the node reports."""
    p0: float
    shots: int
    counts_0: Optional[int] = None
    counts_1: Optional[int] = None
    ideal_p0: Optional[float] = None      # exact value when the backend knows it
    mode: str = "discrete_shots"
    backend_job_id: Optional[str] = None  # Nexus job handle, when there is one
    backend_name: str = ""


@runtime_checkable
class ExecutionBackend(Protocol):
    """Anything that can evaluate a `CircuitJob`.

    `ready` says whether `run` can be called at all; the node refuses a
    screen on a backend that is not ready instead of failing it later.
    """
    name: str
    ready: bool

    def run(self, job: CircuitJob) -> ExecutionResult: ...


class StatevectorBackend:
    """Exact simulation of the compiled gate sequence, then binomial shot
    sampling of the ancilla. ``shots=0`` returns the ideal probability."""
    name = "statevector"
    ready = True

    def run(self, job: CircuitJob) -> ExecutionResult:
        p0_true = simulate_swap_test_statevector(
            list(job.pocket_phases), list(job.ligand_phases), job.tau, tuple(job.omega))
        shots = int(job.shots)
        sample = simulate_shot_sampling(p0_true, n_shots=shots or None, seed=job.seed)
        return ExecutionResult(
            p0=float(sample["empirical_prob"]),
            shots=shots,
            counts_0=sample["counts_0"],
            counts_1=sample["counts_1"],
            ideal_p0=float(p0_true),
            mode=sample["mode"],
            backend_name=self.name,
        )


class NexusBackend:
    """Quantinuum Nexus / Selene / H2 execution. Lands with ``qrotate.runner``.

    Keeps the wire contract stable now: a client can name ``backend="nexus"``
    today and the node answers 501 until this is wired up.
    """
    name = "nexus"
    ready = False

    def __init__(self, target: str = "H2-1E"):
        self.target = target

    def run(self, job: CircuitJob) -> ExecutionResult:
        raise NotImplementedError("use qrotate.runner when merged")


def default_backends() -> dict[str, ExecutionBackend]:
    return {"statevector": StatevectorBackend(), "nexus": NexusBackend()}


# ---------------------------------------------------------------------------
# Job store
# ---------------------------------------------------------------------------

@dataclass
class Job:
    id: str
    status: JobState
    backend: str
    shots: int
    sites: int
    target_sha256: str
    target_label: str
    n_ligands: int
    created_at: float
    request: dict[str, Any] = field(default_factory=dict, repr=False)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    results: list[dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def public(self) -> dict[str, Any]:
        """The ``GET /v1/jobs/{id}`` view: everything but the raw request."""
        return {
            "job_id": self.id,
            "status": self.status,
            "backend": self.backend,
            "shots": self.shots,
            "sites": self.sites,
            "target_sha256": self.target_sha256,
            "target_label": self.target_label,
            "n_ligands": self.n_ligands,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "results": self.results,
            "error": self.error,
        }


class JobStore(Protocol):
    """Persistence interface. Implement these four for Redis/SQLite."""

    def create(self, job: Job) -> None: ...
    def get(self, job_id: str) -> Optional[Job]: ...
    def update(self, job_id: str, **fields: Any) -> Job: ...
    def list_ids(self) -> list[str]: ...


class InMemoryJobStore:
    """Dict behind a lock. Jobs vanish when the process does."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields: Any) -> Job:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in fields.items():
                setattr(job, key, value)
            return job

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._jobs)


# ---------------------------------------------------------------------------
# Wire models
# ---------------------------------------------------------------------------

class FingerprintModel(BaseModel):
    """A fingerprint as the node accepts it. Extra fields are rejected, so a
    body carrying ``coords`` or ``xyz`` is a 422, never silently accepted."""
    model_config = {"extra": "forbid"}

    phases: list[float] = Field(description="One phase per shell, radians in [-pi, pi]")
    sites: int = Field(description="Number of shells (qubits per register)")
    element_summary: dict[str, int] = Field(default_factory=dict, description="Heavy-atom census")
    sha256: str = Field(description="sha256 of the canonical rounded phases")
    qrotate_version: str = __version__
    encoder: str = "molecular_shell_phases/v1"
    label: str = ""
    moment_orders: list[int] = Field(default_factory=list)

    @field_validator("sites")
    @classmethod
    def _supported(cls, v: int) -> int:
        if v not in SUPPORTED_SITES:
            raise ValueError(f"sites must be one of {SUPPORTED_SITES}")
        return v

    def to_fingerprint(self) -> Fingerprint:
        try:
            return Fingerprint.from_dict(self.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"{self.label or 'fingerprint'}: {exc}")


class ScreenRequest(BaseModel):
    model_config = {"extra": "forbid"}

    target: FingerprintModel
    ligands: list[FingerprintModel] = Field(min_length=1)
    backend: str = "statevector"
    shots: int = Field(200, ge=0, le=100_000, description="0 = ideal probability, no sampling")
    tau: float = Field(0.0, description="U_tube evolution time applied to the ligand register")
    omega: tuple[float, float, float] = (0.0, 0.0, 0.0)
    seed: Optional[int] = Field(None, description="Sampling seed for reproducible shot noise")


class ScreenAccepted(BaseModel):
    job_id: str
    status: JobState
    n_ligands: int
    backend: str


class LigandResult(BaseModel):
    label: str
    sha256: str
    p0: float = Field(description="Estimated P(ancilla = 0) = (1 + |<pocket|ligand>|^2) / 2")
    ci95_low: float = Field(description="Wilson 95% interval, lower")
    ci95_high: float = Field(description="Wilson 95% interval, upper")
    shots: int
    counts_0: Optional[int] = None
    counts_1: Optional[int] = None
    ideal_p0: Optional[float] = Field(None, description="Exact value, when the backend is a simulator")
    mode: str
    hqc: dict[str, Any] = Field(default_factory=dict, description="Compiled gate counts and HQC estimate")
    backend_job_id: Optional[str] = None


class JobView(BaseModel):
    job_id: str
    status: JobState
    backend: str
    shots: int
    sites: int
    target_sha256: str
    target_label: str
    n_ligands: int
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    results: list[LigandResult] = Field(default_factory=list)
    error: Optional[str] = None


class BackendInfo(BaseModel):
    name: str
    ready: bool


class Health(BaseModel):
    status: str
    service: str
    version: str
    pytket: bool
    backends: list[BackendInfo]
    jobs: int


class CostEstimate(BaseModel):
    sites: int
    n_qubits: int
    shots: int
    n_ligands: int
    tau: float
    omega: list[float]
    single_qubit_count: int
    two_qubit_count: int
    measure_count: int
    reset_count: int
    depth: int
    hqc_per_circuit: float
    hqc_total: float
    formula: str = "HQC = 5 + (N_1q + 10 N_2q + 5 N_m) * shots / 5000"
    note: str = ("Estimate from Quantinuum's published formula on the rebased circuit; "
                 "the backend's own cost query is authoritative. Nothing was executed.")


# ---------------------------------------------------------------------------
# Compilation and execution (shared by the node and `qrotate screen --local`)
# ---------------------------------------------------------------------------

def compile_pair(pocket_phases: Sequence[float], ligand_phases: Sequence[float],
                 tau: float = 0.0, omega: Sequence[float] = (0.0, 0.0, 0.0)):
    """The rebased H-series circuit for one target/ligand pair."""
    circ = build_pytket_swap_test_circuit(list(pocket_phases), list(ligand_phases),
                                          tau=tau, omega=tuple(omega))
    return rebase_to_h2_gateset(circ)


def cost_estimate(
    sites: int,
    shots: int = 200,
    n_ligands: int = 1,
    tau: float = 0.0,
    omega: Sequence[float] = (0.0, 0.0, 0.0),
) -> dict[str, Any]:
    """Gate counts and HQC for a `sites`-site screen, without running anything.

    The phase values do not change the gate counts (Rz is virtual on
    H-series), so a reference circuit with generic non-zero phases is costed.
    `tau` and `omega` do matter: at ``tau = 0`` the U_tube rotations vanish and
    the rebase drops them, so the estimate is for the same settings a screen
    would run with.
    """
    if sites not in SUPPORTED_SITES:
        raise ValueError(f"sites must be one of {SUPPORTED_SITES}")
    if not HAS_PYTKET:
        raise RuntimeError("pytket is required to compile the cost reference circuit")
    pocket = [0.3 + 0.1 * i for i in range(sites)]
    ligand = [0.9 - 0.1 * i for i in range(sites)]
    circ = compile_pair(pocket, ligand, tau=tau, omega=omega)
    one = compute_circuit_hqc_cost(circ, shots=shots)
    return {
        "sites": sites,
        "n_qubits": one["n_qubits"],
        "shots": shots,
        "n_ligands": n_ligands,
        "tau": float(tau),
        "omega": [float(w) for w in omega],
        "single_qubit_count": one["single_qubit_count"],
        "two_qubit_count": one["two_qubit_count"],
        "measure_count": one["measure_count"],
        "reset_count": one["reset_count"],
        "depth": one["depth"],
        "hqc_per_circuit": one["hqc_cost"],
        "hqc_total": round(one["hqc_cost"] * n_ligands, 2),
    }


def execute_screen(
    target: Fingerprint,
    ligands: Sequence[Fingerprint],
    backend: ExecutionBackend,
    shots: int = 200,
    tau: float = 0.0,
    omega: Sequence[float] = (0.0, 0.0, 0.0),
    seed: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Runs every ligand against the target on `backend`. Returns one
    `LigandResult`-shaped dict per ligand, in input order."""
    rng = np.random.default_rng(seed)
    results = []
    for lig in ligands:
        if lig.sites != target.sites:
            raise ValueError(f"ligand {lig.label!r}: {lig.sites} sites vs target {target.sites}")
        job = CircuitJob(
            pocket_phases=tuple(target.phases),
            ligand_phases=tuple(lig.phases),
            tau=float(tau),
            omega=tuple(float(w) for w in omega),
            shots=int(shots),
            seed=int(rng.integers(1 << 31)) if seed is not None else None,
        )
        res = backend.run(job)
        if res.counts_0 is not None and res.shots > 0:
            lo, hi = _wilson_interval(int(res.counts_0), int(res.shots))
        else:
            lo = hi = float(res.p0)
        hqc: dict[str, Any] = {}
        if HAS_PYTKET:
            hqc = compute_circuit_hqc_cost(compile_pair(target.phases, lig.phases, tau, omega),
                                           shots=max(int(shots), 1))
        results.append({
            "label": lig.label,
            "sha256": lig.sha256,
            "p0": round(float(res.p0), 6),
            "ci95_low": round(float(lo), 6),
            "ci95_high": round(float(hi), 6),
            "shots": int(res.shots),
            "counts_0": res.counts_0,
            "counts_1": res.counts_1,
            "ideal_p0": None if res.ideal_p0 is None else round(float(res.ideal_p0), 6),
            "mode": res.mode,
            "hqc": hqc,
            "backend_job_id": res.backend_job_id,
        })
    return results


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def create_app(
    backends: Optional[dict[str, ExecutionBackend]] = None,
    store: Optional[JobStore] = None,
) -> FastAPI:
    backends = backends if backends is not None else default_backends()
    store = store if store is not None else InMemoryJobStore()

    app = FastAPI(
        title="Q-Rotate node",
        version=__version__,
        description=(
            "Runs the Q-Rotate blind parity (SWAP) test on phase fingerprints. "
            "Clients send fingerprints, never coordinates; the node returns P(0). "
            "The fingerprint is derived from the structure and is information about it: "
            "this is coordinate-free, reduced exposure, not zero-knowledge "
            "(see docs/10_client_node_protocol.md)."
        ),
    )
    app.state.backends = backends
    app.state.store = store

    def _run_job(job_id: str) -> None:
        job = store.get(job_id)
        if job is None:
            return
        store.update(job_id, status="running", started_at=time.time())
        try:
            req = job.request
            results = execute_screen(
                Fingerprint.from_dict(req["target"]),
                [Fingerprint.from_dict(l) for l in req["ligands"]],
                backends[job.backend],
                shots=req["shots"], tau=req["tau"], omega=req["omega"], seed=req.get("seed"),
            )
            store.update(job_id, status="done", results=results, finished_at=time.time())
        except Exception as exc:  # the job must record its own failure
            store.update(job_id, status="failed",
                         error=f"{type(exc).__name__}: {exc}", finished_at=time.time())
            traceback.print_exc()

    @app.get("/v1/health", response_model=Health, tags=["node"])
    def health() -> Health:
        return Health(
            status="ok", service="qrotate-node", version=__version__, pytket=HAS_PYTKET,
            backends=[BackendInfo(name=b.name, ready=b.ready) for b in backends.values()],
            jobs=len(store.list_ids()),
        )

    @app.get("/v1/cost", response_model=CostEstimate, tags=["node"])
    def cost(
        sites: int = Query(4, description="Shells per register: 4 (9 qubits) or 8 (17 qubits)"),
        shots: int = Query(200, ge=1, le=100_000),
        n_ligands: int = Query(1, ge=1, le=100_000),
        tau: float = Query(0.0, description="U_tube evolution time the screen would use"),
        omega: list[float] = Query([0.0, 0.0, 0.0], description="U_tube angular velocity (3 values)"),
    ) -> CostEstimate:
        if len(omega) != 3:
            raise HTTPException(status_code=422, detail="omega needs exactly three values")
        try:
            return CostEstimate(**cost_estimate(sites, shots=shots, n_ligands=n_ligands,
                                                tau=tau, omega=omega))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    @app.post("/v1/screen", response_model=ScreenAccepted, status_code=202, tags=["screen"])
    def screen(req: ScreenRequest, background: BackgroundTasks) -> ScreenAccepted:
        backend = backends.get(req.backend)
        if backend is None:
            raise HTTPException(status_code=400,
                                detail=f"unknown backend {req.backend!r}; have {sorted(backends)}")
        if not backend.ready:
            raise HTTPException(status_code=501,
                                detail=f"backend {req.backend!r} is not available on this node")
        target = req.target.to_fingerprint()
        ligands = [l.to_fingerprint() for l in req.ligands]
        for lig in ligands:
            if lig.sites != target.sites:
                raise HTTPException(status_code=422,
                                    detail=f"ligand {lig.label!r} has {lig.sites} sites, target has {target.sites}")
        job = Job(
            id=uuid.uuid4().hex[:12],
            status="queued",
            backend=req.backend,
            shots=req.shots,
            sites=target.sites,
            target_sha256=target.sha256,
            target_label=target.label,
            n_ligands=len(ligands),
            created_at=time.time(),
            request={
                "target": target.to_dict(),
                "ligands": [l.to_dict() for l in ligands],
                "shots": req.shots, "tau": req.tau, "omega": list(req.omega), "seed": req.seed,
            },
        )
        store.create(job)
        background.add_task(_run_job, job.id)
        return ScreenAccepted(job_id=job.id, status=job.status, n_ligands=job.n_ligands,
                              backend=job.backend)

    @app.get("/v1/jobs/{job_id}", response_model=JobView, tags=["screen"])
    def get_job(job_id: str) -> JobView:
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"no job {job_id!r}")
        return JobView(**job.public())

    return app


app = create_app()


def serve(host: str = "127.0.0.1", port: int = 8000, log_level: str = "info") -> None:
    """Blocking uvicorn server, used by ``qrotate serve``."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level=log_level)


__all__ = [
    "app", "create_app", "serve",
    "ExecutionBackend", "CircuitJob", "ExecutionResult",
    "StatevectorBackend", "NexusBackend", "default_backends",
    "Job", "JobStore", "InMemoryJobStore",
    "compile_pair", "cost_estimate", "execute_screen",
    "ScreenRequest", "FingerprintModel", "JobView", "LigandResult", "CostEstimate", "Health",
]
