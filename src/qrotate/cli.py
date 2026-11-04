"""``qrotate`` command line: fingerprint, compile, screen, serve.

    qrotate fingerprint ligand.pdb --resname RET --sites 4 -o ligand.json
    qrotate compile target.json ligand.json --shots 200
    qrotate screen target.json ligand_a.json ligand_b.json --local --shots 200
    qrotate screen target.json ligand.json --node http://node:8000
    qrotate serve --port 8000
    qrotate openapi -o docs/openapi.json

Output is JSON unless ``--table`` is given. Structures are read only by
``fingerprint``; ``compile`` and ``screen`` take fingerprint JSON files, so a
node URL never sees a coordinate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import typer

from . import __version__

app = typer.Typer(
    name="qrotate",
    help="Q-Rotate: coordinate-free molecular overlap screening on Quantinuum hardware.",
    add_completion=False,
    no_args_is_help=True,
)


def _emit(data: Any, table: bool, render=None) -> None:
    if table and render is not None:
        typer.echo(render(data))
    else:
        typer.echo(json.dumps(data, indent=2))


def _fail(message: str, code: int = 1) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code)


def _load_fp(path: Path):
    from .client import Fingerprint
    try:
        return Fingerprint.load(path)
    except (OSError, ValueError, KeyError) as exc:
        _fail(f"{path}: {exc}")


def _rows(headers: list[str], rows: list[list[Any]]) -> str:
    cells = [[str(h) for h in headers]] + [[str(c) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(headers))]
    line = "  ".join(h.ljust(w) for h, w in zip(cells[0], widths))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(c.ljust(w) for c, w in zip(r, widths)) for r in cells[1:]]
    return "\n".join(out)


# ---------------------------------------------------------------------------

@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", help="Print the version and exit", is_eager=True),
) -> None:
    if version:
        typer.echo(f"qrotate {__version__}")
        raise typer.Exit()


@app.command()
def fingerprint(
    file: Path = typer.Argument(..., exists=True, readable=True, help="PDB or SDF structure"),
    sites: int = typer.Option(4, "--sites", "-n", help="Shells per register: 4 or 8"),
    resname: Optional[str] = typer.Option(None, help="PDB only: residue name to encode (e.g. the ligand)"),
    chain: Optional[str] = typer.Option(None, help="PDB only: chain of that residue"),
    resseq: Optional[int] = typer.Option(None, help="PDB only: residue number"),
    label: Optional[str] = typer.Option(None, help="Name carried in the fingerprint"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write the fingerprint JSON here"),
    table: bool = typer.Option(False, "--table", help="Human-readable output"),
) -> None:
    """Encode a structure into a phase fingerprint, locally. Coordinates stay in the file."""
    from .client import fingerprint as _fingerprint
    try:
        fp = _fingerprint(file, sites=sites, resname=resname, chain=chain, resseq=resseq, label=label)
    except ValueError as exc:
        _fail(str(exc))
    if output is not None:
        fp.save(output)
    if table:
        rows = [[i, f"{p:+.6f}", o] for i, (p, o) in enumerate(zip(fp.phases, fp.moment_orders))]
        typer.echo(f"{fp.label}  sites={fp.sites}  atoms={fp.n_atoms}  "
                   f"elements={fp.element_summary}\nsha256={fp.sha256}")
        typer.echo(_rows(["shell", "phase (rad)", "moment order"], rows))
        if output is not None:
            typer.echo(f"saved {output}")
    elif output is None:
        typer.echo(fp.to_json(indent=2))
    else:
        typer.echo(json.dumps({"saved": str(output), "sha256": fp.sha256, "sites": fp.sites}))


@app.command()
def compile(
    target: Path = typer.Argument(..., exists=True, help="Target fingerprint JSON"),
    ligand: Path = typer.Argument(..., exists=True, help="Ligand fingerprint JSON"),
    shots: int = typer.Option(200, help="Shots the HQC estimate assumes"),
    tau: float = typer.Option(0.0, help="U_tube evolution time on the ligand register"),
    qasm: Optional[Path] = typer.Option(None, help="Also write the rebased circuit as OpenQASM (hqslib1)"),
    table: bool = typer.Option(False, "--table"),
) -> None:
    """Compile the SWAP-test circuit for one pair and report gate counts and HQC. Nothing runs."""
    from .metrics import compute_circuit_hqc_cost
    from .node import compile_pair
    t, l = _load_fp(target), _load_fp(ligand)
    if t.sites != l.sites:
        _fail(f"target has {t.sites} sites, ligand has {l.sites}")
    circ = compile_pair(t.phases, l.phases, tau=tau)
    cost = compute_circuit_hqc_cost(circ, shots=shots)
    data = {"target": t.label, "ligand": l.label, "sites": t.sites, **cost}
    if qasm is not None:
        from pytket.qasm import circuit_to_qasm_str
        qasm.write_text(circuit_to_qasm_str(circ, header="hqslib1"), encoding="utf-8")
        data["qasm"] = str(qasm)
    _emit(data, table, lambda d: _rows(["field", "value"], [[k, v] for k, v in d.items()]))


@app.command()
def screen(
    target: Path = typer.Argument(..., exists=True, help="Target fingerprint JSON"),
    ligands: list[Path] = typer.Argument(..., help="One or more ligand fingerprint JSON files"),
    node: Optional[str] = typer.Option(None, "--node", help="Node URL, e.g. http://127.0.0.1:8000"),
    local: bool = typer.Option(False, "--local", help="Run the statevector backend in this process"),
    backend: str = typer.Option("statevector", help="Execution backend name on the node"),
    shots: int = typer.Option(200, help="Shots per ligand (0 = ideal probability)"),
    seed: Optional[int] = typer.Option(None, help="Sampling seed"),
    tau: float = typer.Option(0.0, help="U_tube evolution time on the ligand register"),
    timeout: float = typer.Option(300.0, help="Seconds to wait for a remote job"),
    table: bool = typer.Option(False, "--table"),
) -> None:
    """Screen ligand fingerprints against a target. Only fingerprints reach the node."""
    if bool(node) == local:
        _fail("choose exactly one of --node URL or --local")
    t = _load_fp(target)
    ls = [_load_fp(p) for p in ligands]
    for p in ls:
        if p.sites != t.sites:
            _fail(f"{p.label}: {p.sites} sites, target has {t.sites}")

    if local:
        from .node import default_backends, execute_screen
        be = default_backends().get(backend)
        if be is None or not be.ready:
            _fail(f"backend {backend!r} is not available locally")
        results = execute_screen(t, ls, be, shots=shots, tau=tau, seed=seed)
        data = {"status": "done", "backend": backend, "shots": shots, "sites": t.sites,
                "target_label": t.label, "target_sha256": t.sha256, "results": results}
    else:
        from .client import Client, NodeError
        client = Client(node, timeout=timeout)
        try:
            data = client.screen(t, ls, backend=backend, shots=shots, tau=tau, seed=seed, timeout=timeout)
        except (NodeError, TimeoutError) as exc:
            _fail(str(exc))
        except Exception as exc:  # connection refused and friends
            _fail(f"could not reach node {node}: {exc}")

    def render(d: dict[str, Any]) -> str:
        head = (f"target {d['target_label']}  backend={d['backend']}  shots={d['shots']}  "
                f"sites={d['sites']}  job={d.get('job_id', 'local')}")
        rows = [[r["label"], f"{r['p0']:.4f}", f"[{r['ci95_low']:.3f}, {r['ci95_high']:.3f}]",
                 "" if r["ideal_p0"] is None else f"{r['ideal_p0']:.4f}",
                 r["hqc"].get("hqc_cost", ""), r["hqc"].get("two_qubit_count", "")]
                for r in d["results"]]
        return head + "\n" + _rows(["ligand", "P(0)", "Wilson 95%", "ideal", "HQC", "2q gates"], rows)

    _emit(data, table, render)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address"),
    port: int = typer.Option(8000, "--port", "-p"),
    log_level: str = typer.Option("info"),
) -> None:
    """Run a Q-Rotate node (FastAPI + uvicorn) in the foreground."""
    from .node import serve as _serve
    _serve(host=host, port=port, log_level=log_level)


@app.command()
def openapi(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write here instead of stdout"),
) -> None:
    """Export the node's OpenAPI schema as JSON."""
    from .node import app as node_app
    text = json.dumps(node_app.openapi(), indent=2)
    if output is None:
        typer.echo(text)
    else:
        output.write_text(text + "\n", encoding="utf-8")
        typer.echo(json.dumps({"saved": str(output)}))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
