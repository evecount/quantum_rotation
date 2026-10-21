"""Execution-evidence writer for Project Q-Rotate.

Builds the compiled blind-parity SWAP-test circuit for each benchmark system
at two poses, runs it on a chosen backend, and writes a self-describing
evidence directory::

    evidence/<UTC timestamp>_<backend>/
        manifest.json        git commit, package versions, backend, parameters, run index
        run.log              what happened, in order
        <system>_<pose>.json circuit (pytket JSON), counts, P(0), CI, job id, cost

The two poses per system are the ones `metrics.run_molecular_showdown`
reports: ``deposited`` (the ligand against its own deposited pose, the state
the RUS loop locks onto) and ``start`` (the ligand against the benchmark's
starting misalignment, the showdown's ``start_p0``). Same coordinates, same
phase encoding, same tau and omega, so every number here can be checked
against ``benchmarks/molecular_showdown.json``.

Command line::

    python -m src.qrotate.evidence --backend statevector --systems all --sites 4 --shots 100
    python -m src.qrotate.evidence --backend selene --systems rhodopsin,gfp --sites 4 --shots 100
    python -m src.qrotate.evidence --backend nexus:H2-2E --systems all --sites 4 --shots 100
    python -m src.qrotate.evidence --syntax-check --systems all --sites 4 --shots 100
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from .hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases
from .metrics import REAL_MOLECULE_SYSTEMS, _system_coordinates, _rotate_z
from .structures import load_active_sites, site_elements
from .runner import (
    Backend,
    BackendUnavailable,
    CredentialsRequired,
    NexusBackend,
    RunResult,
    SwapTestProgram,
    check_credentials,
    get_backend,
    _package_version,
)

SCHEMA_VERSION = 1

#: The benchmark's evolution parameters (same as `metrics.run_molecular_showdown`).
TAU = 0.25
OMEGA = (1.0, 0.5, 0.25)
POSES = ("deposited", "start")
DEFAULT_BASE_SEED = 20261022

#: Packages whose versions a judge needs to reproduce a run.
TRACKED_PACKAGES = (
    "numpy", "pytket", "guppylang", "hugr", "tket", "aqora", "selene-sim", "selene-core", "hugr-qir",
)

SYSTEM_IDS: tuple[str, ...] = tuple(s["id"] for s in REAL_MOLECULE_SYSTEMS)


# =====================================================================
# Inputs: exactly what the showdown feeds the circuit
# =====================================================================

def showdown_inputs(system_id: str, n_sites: int) -> dict:
    """Coordinates, phases and provenance for one system, derived the way
    `metrics.run_molecular_showdown` derives them."""
    spec = next((s for s in REAL_MOLECULE_SYSTEMS if s["id"] == system_id), None)
    if spec is None:
        raise ValueError(f"unknown system {system_id!r}; choose from {', '.join(SYSTEM_IDS)}")
    seed = zlib.crc32(system_id.encode()) % (2 ** 31)
    target_coords, probe_coords = _system_coordinates(
        system_id, spec["n_atoms_proxy"], spec["optimal_angle_deg"], seed)
    n_atoms = len(probe_coords)
    elements = site_elements(system_id) or ["C"] * n_atoms
    target_geom = MolecularGeometry(f"{system_id}_target", elements, target_coords)
    probe_geom = MolecularGeometry(f"{system_id}_probe", elements, probe_coords)
    pocket_phases = [float(p) for p in pocket_ligand_to_qubit_phases(target_geom, n_qubits=n_sites)]
    start_phases = [float(p) for p in pocket_ligand_to_qubit_phases(probe_geom, n_qubits=n_sites)]
    site = load_active_sites().get(system_id)
    return {
        "system_id": system_id,
        "system_name": spec["name"],
        "structure_source": (
            f"{site['source']['db']} {site['source']['id']}" if site else "synthetic fallback"),
        "ligand_resname": site["ligand"]["resname"] if site else None,
        "n_ligand_atoms": n_atoms,
        "start_offset_deg": float(spec["optimal_angle_deg"]),
        "showdown_seed": seed,
        "n_sites": n_sites,
        "pocket_phases": pocket_phases,
        "start_phases": start_phases,
        "target_coords": np.asarray(target_coords, dtype=float).round(4).tolist(),
        "probe_coords": np.asarray(probe_coords, dtype=float).round(4).tolist(),
        "elements": list(elements),
    }


def build_programs(system_id: str, n_sites: int) -> dict[str, SwapTestProgram]:
    """`deposited`: ligand vs its deposited pose (the lock target);
    `start`: ligand vs the benchmark's start misalignment."""
    inputs = showdown_inputs(system_id, n_sites)
    pocket = inputs["pocket_phases"]
    return {
        "deposited": SwapTestProgram.build(pocket, pocket, TAU, OMEGA, label=f"{system_id}:deposited"),
        "start": SwapTestProgram.build(pocket, inputs["start_phases"], TAU, OMEGA, label=f"{system_id}:start"),
    }


def run_seed(base_seed: int, system_id: str, pose: str) -> int:
    """A per-run seed that is stable across machines (crc32, not hash())."""
    return (int(base_seed) ^ zlib.crc32(f"{system_id}:{pose}".encode())) % (2 ** 31)


# =====================================================================
# Manifest helpers
# =====================================================================

def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=20,
                             cwd=str(Path(__file__).resolve().parents[2]))
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_state() -> dict:
    status = _git("status", "--porcelain")
    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status) if status is not None else None,
        "describe": _git("describe", "--always", "--dirty"),
    }


def environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {name: _package_version(name) for name in TRACKED_PACKAGES},
    }


def utc_stamp(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ")


def backend_slug(backend_name: str) -> str:
    return backend_name.replace(":", "-").replace("/", "-")


# =====================================================================
# Writer
# =====================================================================

class _Log:
    def __init__(self, path: Path, echo: bool = True):
        self.path = path
        self.echo = echo
        self._fh = open(path, "a", encoding="utf-8")

    def __call__(self, msg: str) -> None:
        line = f"{datetime.now(timezone.utc).strftime('%H:%M:%S')}Z {msg}"
        self._fh.write(line + "\n")
        self._fh.flush()
        if self.echo:
            print(line, flush=True)

    def close(self) -> None:
        self._fh.close()


def write_evidence(
    backend: Backend,
    systems: Sequence[str] = SYSTEM_IDS,
    n_sites: int = 4,
    shots: int = 100,
    base_seed: int = DEFAULT_BASE_SEED,
    out_root: str | os.PathLike = "evidence",
    poses: Sequence[str] = POSES,
    syntax_check: bool = False,
    echo: bool = True,
    stop_on_error: bool = False,
) -> Path:
    """Runs every (system, pose) circuit on `backend` and writes the evidence
    directory. Returns its path. A run that raises is recorded in the manifest
    with its error and the loop continues (unless `stop_on_error`)."""
    for s in systems:
        if s not in SYSTEM_IDS:
            raise ValueError(f"unknown system {s!r}; choose from {', '.join(SYSTEM_IDS)}")

    started = datetime.now(timezone.utc)
    out_dir = Path(out_root) / f"{utc_stamp(started)}_{backend_slug(backend.name)}"
    out_dir.mkdir(parents=True, exist_ok=False)
    log = _Log(out_dir / "run.log", echo=echo)

    manifest: dict = {
        "schema_version": SCHEMA_VERSION,
        "project": "Q-Rotate (Team Eve Count, Quantinuum Singapore Grand Challenge 2026)",
        "generated_at_utc": started.isoformat(),
        "backend": backend.describe(),
        "syntax_check": bool(syntax_check),
        "git": git_state(),
        "environment": environment(),
        "parameters": {
            "n_sites": int(n_sites),
            "n_qubits": 2 * int(n_sites) + 1,
            "shots": int(shots),
            "base_seed": int(base_seed),
            "tau": TAU,
            "omega": list(OMEGA),
            "systems": list(systems),
            "poses": list(poses),
        },
        "what_the_poses_mean": {
            "deposited": "ligand register vs its own deposited-pose register: the state the RUS loop locks onto",
            "start": "ligand register vs the benchmark's start misalignment: metrics.run_molecular_showdown start_p0",
        },
        "runs": [],
        "status": "running",
    }
    _write_json(out_dir / "manifest.json", manifest)

    log(f"backend {backend.name} ({backend.kind}); {len(systems)} systems x {len(poses)} poses; "
        f"{n_sites} sites = {2 * n_sites + 1} qubits; {shots} shots"
        + ("; SYNTAX CHECK ONLY" if syntax_check else ""))
    log(f"git {manifest['git']['commit']} ({manifest['git']['branch']}"
        f"{', dirty' if manifest['git']['dirty'] else ''})")
    log("packages " + ", ".join(f"{k}={v}" for k, v in manifest["environment"]["packages"].items() if v))

    n_ok = 0
    for system_id in systems:
        inputs = showdown_inputs(system_id, n_sites)
        programs = build_programs(system_id, n_sites)
        for pose in poses:
            program = programs[pose]
            seed = run_seed(base_seed, system_id, pose)
            exact = program.exact_prob_zero()
            log(f"[{system_id}/{pose}] {inputs['structure_source']} | {program.n_qubits} qubits | "
                f"exact statevector P(0)={exact:.4f} | seed {seed}")
            entry = {
                "file": f"{system_id}_{pose}.json",
                "system_id": system_id,
                "pose": pose,
                "n_qubits": program.n_qubits,
                "prob_zero_exact": round(exact, 6),
                "hqc_estimate": program.hqc_estimate(shots),
            }
            t0 = time.perf_counter()
            try:
                result = backend.run(program, shots, seed=seed)
            except CredentialsRequired:
                raise
            except Exception as exc:  # record, keep going
                entry.update({"status": "error", "error": f"{type(exc).__name__}: {exc}",
                              "wall_time_s": round(time.perf_counter() - t0, 3)})
                manifest["runs"].append(entry)
                _write_json(out_dir / "manifest.json", manifest)
                log(f"[{system_id}/{pose}] ERROR {entry['error']}")
                if stop_on_error:
                    manifest["status"] = "aborted"
                    _write_json(out_dir / "manifest.json", manifest)
                    log.close()
                    raise
                continue

            record = _run_record(inputs, pose, program, result, shots, seed)
            _write_json(out_dir / entry["file"], record)
            entry.update({
                "status": "ok",
                "shots": result.shots,
                "counts": result.counts,
                "prob_zero": _nan_to_none(result.prob_zero),
                "ci95_wilson": [_nan_to_none(result.ci_low), _nan_to_none(result.ci_high)],
                "job_id": result.job_id,
                "wall_time_s": round(result.wall_time_s, 3),
                "hqc": result.hqc,
            })
            manifest["runs"].append(entry)
            _write_json(out_dir / "manifest.json", manifest)
            n_ok += 1
            if result.shots:
                log(f"[{system_id}/{pose}] counts {result.counts} -> P(0)={result.prob_zero:.3f} "
                    f"[{result.ci_low:.3f}, {result.ci_high:.3f}] 95% Wilson"
                    + (f" | job {result.job_id}" if result.job_id else "")
                    + f" | {result.wall_time_s:.2f}s")
            else:
                log(f"[{system_id}/{pose}] validated, no execution (syntax check)"
                    + (f" | job {result.job_id}" if result.job_id else "")
                    + (f" | est. {result.hqc['hqc_cost']} HQC at {shots} shots" if result.hqc else "")
                    + f" | {result.wall_time_s:.2f}s")

    manifest["status"] = "complete" if n_ok == len(systems) * len(poses) else "partial"
    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["summary"] = _summary(manifest["runs"])
    _write_json(out_dir / "manifest.json", manifest)
    log(f"{n_ok}/{len(systems) * len(poses)} runs ok -> {out_dir}")
    log.close()
    return out_dir


def _run_record(inputs: dict, pose: str, program: SwapTestProgram, result: RunResult,
                shots: int, seed: int) -> dict:
    from .circuits import HAS_PYTKET

    compiled = program.compiled
    gate_counts = None
    if HAS_PYTKET and compiled is not None:
        from pytket.circuit import OpType
        gate_counts = {
            "PhasedX": compiled.n_gates_of_type(OpType.PhasedX),
            "Rz": compiled.n_gates_of_type(OpType.Rz),
            "ZZPhase": compiled.n_gates_of_type(OpType.ZZPhase),
            "ZZMax": compiled.n_gates_of_type(OpType.ZZMax),
            "Measure": compiled.n_gates_of_type(OpType.Measure),
            "total": compiled.n_gates,
            "depth": compiled.depth(),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "system": {k: inputs[k] for k in (
            "system_id", "system_name", "structure_source", "ligand_resname",
            "n_ligand_atoms", "start_offset_deg", "showdown_seed")},
        "pose": pose,
        "pose_meaning": (
            "ligand vs its own deposited pose (lock target)" if pose == "deposited"
            else f"ligand vs start misalignment of {inputs['start_offset_deg']:+.1f} deg"),
        "encoding": {
            "n_sites": program.n_sites,
            "n_qubits": program.n_qubits,
            "tau": program.tau,
            "omega": list(program.omega),
            "pocket_phases": program.pocket_phases,
            "ligand_phases": program.ligand_phases,
        },
        "circuit": {
            "gateset": "Quantinuum H-series native (PhasedX, Rz, ZZPhase) via pytket AutoRebase",
            "gate_counts": gate_counts,
            "hqc_estimate": program.hqc_estimate(shots),
            "pytket_json": program.circuit_json(),
            "pytket_json_unrebased": (program.circuit.to_dict() if HAS_PYTKET and program.circuit is not None else None),
        },
        "execution": {
            "backend": result.backend,
            "shots_requested": int(shots),
            "shots": result.shots,
            "seed": seed if result.seed is not None else None,
            "counts": result.counts,
            "prob_zero": _nan_to_none(result.prob_zero),
            "ci95_wilson": [_nan_to_none(result.ci_low), _nan_to_none(result.ci_high)],
            "prob_zero_exact_statevector": result.prob_zero_exact,
            "job_id": result.job_id,
            "wall_time_s": round(result.wall_time_s, 3),
            "hqc": result.hqc,
            "extra": result.extra,
        },
        "coordinates": {
            "elements": inputs["elements"],
            "target": inputs["target_coords"],
            "probe": inputs["probe_coords"],
        },
    }


def _summary(runs: list[dict]) -> dict:
    ok = [r for r in runs if r.get("status") == "ok"]
    executed = [r for r in ok if r.get("shots")]
    out = {
        "runs_total": len(runs),
        "runs_ok": len(ok),
        "runs_errored": len(runs) - len(ok),
        "job_ids": [r["job_id"] for r in ok if r.get("job_id")],
        "hqc_estimate_total": round(sum((r.get("hqc_estimate") or {}).get("hqc_cost", 0.0) for r in ok), 2),
    }
    if executed:
        dev = [abs(r["prob_zero"] - r["prob_zero_exact"]) for r in executed if r.get("prob_zero") is not None]
        inside = [r for r in executed
                  if r["ci95_wilson"][0] is not None
                  and r["ci95_wilson"][0] <= r["prob_zero_exact"] <= r["ci95_wilson"][1]]
        out.update({
            "runs_executed": len(executed),
            "max_abs_deviation_from_exact": round(max(dev), 4) if dev else None,
            "exact_inside_wilson_ci": f"{len(inside)}/{len(executed)}",
        })
    return out


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=_json_default)
    os.replace(tmp, path)


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def _nan_to_none(value: float):
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else float(value)


# =====================================================================
# CLI
# =====================================================================

def parse_systems(spec: str) -> list[str]:
    if spec.strip().lower() == "all":
        return list(SYSTEM_IDS)
    chosen = [s.strip() for s in spec.split(",") if s.strip()]
    unknown = [s for s in chosen if s not in SYSTEM_IDS]
    if unknown:
        raise SystemExit(f"unknown system(s) {', '.join(unknown)}; choose from all, {', '.join(SYSTEM_IDS)}")
    return chosen


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.qrotate.evidence",
        description="Run the Q-Rotate SWAP-test circuits on a backend and write an evidence directory.",
    )
    p.add_argument("--backend", default="statevector",
                   help="statevector | selene | nexus:H2-Emulator | nexus:H2-1E | nexus:H2-2E | "
                        "nexus:H2-1SC | nexus:H2-2SC | nexus:H2-1 (default: statevector)")
    p.add_argument("--systems", default="all", help="all or a comma list: " + ",".join(SYSTEM_IDS))
    p.add_argument("--sites", type=int, default=4, choices=(4, 8), help="sites per register (4 -> 9 qubits, 8 -> 17 qubits)")
    p.add_argument("--shots", type=int, default=100)
    p.add_argument("--seed", type=int, default=DEFAULT_BASE_SEED, help="base seed for local sampling")
    p.add_argument("--out", default="evidence", help="root directory for evidence (default: evidence/)")
    p.add_argument("--syntax-check", action="store_true",
                   help="validate and cost every circuit on the H2-2SC syntax checker; spends no HQC")
    p.add_argument("--syntax-checker", default="H2-2SC", choices=("H2-1SC", "H2-2SC"),
                   help="which syntax checker --syntax-check uses (default H2-2SC)")
    p.add_argument("--timeout", type=float, default=600.0, help="seconds to wait for a Nexus job")
    p.add_argument("--as-entity", default=None, help="aqora organisation to attribute Nexus jobs to")
    p.add_argument("--selene-simulator", default="statevector", choices=("statevector", "stabilizer", "coinflip"))
    p.add_argument("--stop-on-error", action="store_true")
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    systems = parse_systems(args.systems)

    backend_name = f"nexus:{args.syntax_checker}" if args.syntax_check else args.backend
    try:
        if backend_name.lower() == "selene":
            backend = get_backend("selene", simulator=args.selene_simulator)
        elif backend_name.lower().startswith("nexus:") or backend_name.upper() in {t.upper() for t in ("H2-Emulator", "H2-1E", "H2-2E", "H2-1SC", "H2-2SC", "H2-1")}:
            backend = get_backend(backend_name, timeout=args.timeout, as_entity=args.as_entity)
        else:
            backend = get_backend(backend_name)
    except BackendUnavailable as exc:
        print(f"backend {backend_name!r} is unavailable: {exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # Check the login before creating a directory, so a machine without
    # credentials leaves no half-written evidence behind.
    if isinstance(backend, NexusBackend):
        try:
            user = check_credentials()
        except CredentialsRequired as exc:
            print(str(exc), file=sys.stderr)
            return 4
        if not args.quiet:
            print(f"aqora login found: {user}; target {backend.target} ({backend.cost_unit})")

    try:
        out_dir = write_evidence(
            backend, systems=systems, n_sites=args.sites, shots=args.shots, base_seed=args.seed,
            out_root=args.out, syntax_check=args.syntax_check, echo=not args.quiet,
            stop_on_error=args.stop_on_error,
        )
    except CredentialsRequired as exc:
        print(str(exc), file=sys.stderr)
        return 4
    print(f"\nevidence written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
