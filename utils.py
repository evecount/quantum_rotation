import marimo

__generated_with = "0.24.0"
app = marimo.App()

with app.setup:
    import html

    import altair as alt
    import marimo as mo

    import hugr
    from hugr import Hugr
    from hugr.package import Package

    from pytket.circuit import Circuit, OpType
    from pytket.circuit.display import get_circuit_renderer
    from pytket.predicates import GateSetPredicate

    try:
        from tket.passes import InlineFunctions, QSystemRebasePass
    except ImportError:
        from tket.passes import InlineFunctions, QSystemPass as QSystemRebasePass
    from tket.passes.inline_funcs import All

    from aqora.pytket.backend import GATESET

    PYTKET_PREDICATE = GateSetPredicate(GATESET)

    # Native H-series operations that drive the HQC cost, in display order.
    NATIVE_OPS = ("PhasedX", "ZZMax", "ZZPhase", "Measure", "Reset")


@app.function
def hugr_op_counts(hugr: Hugr | Package) -> dict[str, int]:
    """Count qubits and native gates in a HUGR program.

    Each module is rebased into the QSystem gate set on a copy, with function
    calls inlined, so the counts reflect what the hardware would run.
    """
    qsystem_ops = {
        "TryQAlloc": ("Qubits",),
        "PhasedX": ("PhasedX",),
        "ZZPhase": ("ZZPhase",),
        "LazyMeasure": ("Measure",),
        "LazyMeasureLeaked": ("Measure",),
        "LazyMeasureReset": ("Measure", "Reset"),
        "Reset": ("Reset",),
    }
    counts = dict.fromkeys(("Qubits", *NATIVE_OPS), 0)
    modules = hugr.modules if isinstance(hugr, Package) else [hugr]
    for module in modules:
        lowered = QSystemRebasePass().run(module, inplace=False).hugr
        InlineFunctions(All()).run(lowered)
        for node in lowered.descendants(lowered.entrypoint):
            name = lowered[node].op.name().rsplit(".", 1)[-1]
            for key in qsystem_ops.get(name, ()):
                counts[key] += 1
    return counts


@app.function
def pytket_op_counts(circuit: Circuit) -> dict[str, int]:
    """Count qubits and native gates in a pytket circuit rebased into GATESET."""
    if not PYTKET_PREDICATE.verify(circuit):
        raise ValueError("Circuit contains gates not in the allowed gate set.")
    counts = {"Qubits": circuit.n_qubits}
    for op in NATIVE_OPS:
        counts[op] = circuit.n_gates_of_type(getattr(OpType, op))
    return counts


@app.function
def estimate_cost(counts: dict[str, int], n_shots: int) -> float:
    """Rough HQC cost of running a program with these op counts for `n_shots`."""
    gating_cost = (
        counts["PhasedX"]
        + 10 * (counts["ZZMax"] + counts["ZZPhase"])
        + 5 * (counts["Qubits"] + counts["Measure"] + counts["Reset"])
    )
    return 5 + gating_cost * n_shots / 5000


@app.function
def cost_tiles(counts: dict[str, int], n_shots: int) -> mo.Html:
    """Show op counts as stat tiles, with the estimated HQC cost."""
    cost = estimate_cost(counts, n_shots)
    return mo.hstack(
        [
            mo.stat(value, label=label, bordered=True)
            for label, value in counts.items()
        ]
        + [mo.stat(f"{cost:.1f}", label="Estimated HQCs", bordered=True)],
        justify="start",
    )


@app.function
def hugr_stats(hugr: Hugr | Package, n_shots: int) -> mo.Html:
    """Summarise a HUGR program as stat tiles, with its estimated HQC cost."""
    return cost_tiles(hugr_op_counts(hugr), n_shots)


@app.function
def pytket_stats(circuit: Circuit, n_shots: int) -> mo.Html:
    """Summarise a rebased pytket circuit as stat tiles, with its estimated HQC cost."""
    return cost_tiles(pytket_op_counts(circuit), n_shots)


@app.function
def counts_histogram(counts: dict[str, int]) -> alt.Chart:
    """Bar chart of measurement outcomes, most frequent first."""
    return (
        alt.Chart(
            alt.Data(
                values=[{"outcome": k, "shots": v} for k, v in counts.items()]
            )
        )
        .mark_bar()
        .encode(
            x=alt.X("outcome:N", sort="-y", title="Measured bits"),
            y=alt.Y("shots:Q", title="Shots"),
            tooltip=["outcome:N", "shots:Q"],
        )
        .properties(width="container", height=300)
    )


@app.function
def render_circuit(circ: Circuit, height: str = "250px") -> mo.Html:
    """Render a pytket circuit with pytket's HTML circuit renderer."""
    renderer = get_circuit_renderer()
    renderer.config.min_width = "100%"
    renderer.config.min_height = height
    srcdoc = html.escape(renderer.render_circuit_as_html(circ), quote=True)
    return mo.Html(
        f'<iframe srcdoc="{srcdoc}" width="100%" height="{height}" '
        'style="border:none"></iframe>'
    )


if __name__ == "__main__":
    app.run()
