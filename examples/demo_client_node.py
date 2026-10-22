"""End-to-end demo of the Q-Rotate client/node split.

Starts a node in this process (uvicorn on a free localhost port), fingerprints
the six benchmark systems from benchmarks/active_sites.json on the client
side, and screens every ligand against every pocket over HTTP. Only the
fingerprints (phases, element census, hash) cross the socket; the coordinates
loaded here never leave this function's locals.

    python examples/demo_client_node.py [--sites 4|8] [--shots N] [--seed S]

Prints the 6 x 6 matrix of measured P(0): rows are ligands, columns the
pocket each was screened against. Azobenzene and H2 have no protein pocket, so
their "pocket" is their own reference pose and the diagonal there is 1.0 by
construction. For the four complexes the pocket and the ligand are different
molecules, so the diagonal is not a self-match; the point of the demo is the
product shape (what the node sees), not a docking claim.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from qrotate.client import Client, fingerprint  # noqa: E402
from qrotate.structures import load_active_sites  # noqa: E402

ORDER = ["rhodopsin", "gfp", "mpro", "cox2", "azobenzene", "h2bench"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_node(port: int):
    """Runs qrotate.node in a daemon thread; returns the uvicorn server."""
    import uvicorn
    from qrotate.node import create_app

    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True, name="qrotate-node")
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("node did not start")
        time.sleep(0.05)
    return server, thread


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sites", type=int, default=4, choices=(4, 8))
    ap.add_argument("--shots", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--json", action="store_true", help="Also print the raw job results")
    args = ap.parse_args(argv)

    sites = load_active_sites(str(_REPO_ROOT / "benchmarks" / "active_sites.json"))
    if not sites:
        print("benchmarks/active_sites.json missing; run `python -m src.qrotate.structures`")
        return 1

    port = _free_port()
    server, thread = start_node(port)
    client = Client(f"http://127.0.0.1:{port}")
    health = client.health()
    print(f"node up at http://127.0.0.1:{port}  version={health['version']}  "
          f"backends={[b['name'] + ('' if b['ready'] else ' (not ready)') for b in health['backends']]}")

    # Client side: coordinates are read here and only here.
    pockets, ligands = {}, {}
    for sid in ORDER:
        site = sites[sid]
        pockets[sid] = fingerprint(site["pocket"], sites=args.sites, label=f"{sid} pocket")
        ligands[sid] = fingerprint(site["ligand"], sites=args.sites, label=f"{sid} ligand")
        print(f"  fingerprinted {sid:11s} pocket {site['pocket']['n_atoms']:4d} atoms -> "
              f"{args.sites} phases {pockets[sid].sha256[:12]}   ligand {site['ligand']['n_atoms']:3d} atoms -> "
              f"{args.sites} phases {ligands[sid].sha256[:12]}")

    cost = client.cost(sites=args.sites, shots=args.shots, n_ligands=len(ORDER))
    print(f"cost per screen job (one pocket vs six ligands): {cost['n_qubits']} qubits, "
          f"{cost['two_qubit_count']} ZZPhase/circuit, {cost['hqc_total']} HQC at {args.shots} shots")

    # One job per pocket; every job carries all six ligand fingerprints.
    t0 = time.time()
    jobs = {sid: client.submit_screen(pockets[sid], [ligands[l] for l in ORDER],
                                      backend="statevector", shots=args.shots, seed=args.seed)
            for sid in ORDER}
    results = {sid: client.wait(job_id, timeout=300) for sid, job_id in jobs.items()}
    elapsed = time.time() - t0

    # Rows: ligands. Columns: the pocket each was screened against.
    matrix = {l: {p: results[p]["results"][i]["p0"] for p in ORDER} for i, l in enumerate(ORDER)}
    width = max(len(s) for s in ORDER)
    print(f"\nP(0) measured at {args.shots} shots, {args.sites} sites "
          f"({2 * args.sites + 1} qubits), statevector backend, {elapsed:.1f}s for 6 jobs")
    print("rows: ligand, columns: pocket (target)\n")
    print(" " * (width + 2) + "".join(f"{p:>{width + 2}s}" for p in ORDER))
    for l in ORDER:
        print(f"{l:<{width + 2}s}" + "".join(f"{matrix[l][p]:>{width + 2}.3f}" for p in ORDER))
    print()
    for sid in ORDER:
        r = results[sid]["results"][ORDER.index(sid)]
        print(f"  {sid:11s} own pocket: P(0)={r['p0']:.3f}  Wilson95=[{r['ci95_low']:.3f}, {r['ci95_high']:.3f}]"
              f"  ideal={r['ideal_p0']:.3f}  HQC/circuit={r['hqc']['hqc_cost']}")

    if args.json:
        print(json.dumps(results, indent=1))

    server.should_exit = True
    thread.join(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
