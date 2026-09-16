import marimo

__generated_with = "0.24.0"
app = marimo.App()

with app.setup:
    import marimo as mo

    from guppylang import guppy
    try:
        from guppylang.std.builtins import output
    except ImportError:
        from guppylang.std.builtins import result as output
    from guppylang.std.quantum import qubit, measure, h, cx

    from hugr_qir.hugr_to_qir import hugr_to_qir
    from hugr_qir.output import OutputFormat

    from aqora import QPU


@app.cell
def _():
    from utils import counts_histogram, hugr_stats

    return counts_histogram, hugr_stats


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # GHZ state with Guppy

    This notebook prepares an $(N+1)$-qubit
    [GHZ state](https://en.wikipedia.org/wiki/Greenberger%E2%80%93Horne%E2%80%93Zeilinger_state)
    in **Guppy**, lowers it to QIR, and runs it on the **H2-2E** emulator through
    `aqora.QPU`:

    $$|\mathrm{GHZ}\rangle = \frac{|0\cdots0\rangle + |1\cdots1\rangle}{\sqrt{2}}$$

    Guppy source → HUGR (`main.compile()`) → QIR bitcode (`hugr_to_qir`) → `qpu.run(...)`.

    Every qubit is measured, so an ideal run returns only the all-zeros and all-ones
    bitstrings. Anything else is noise, which makes the GHZ state a good stress test
    for a backend's entangling gates and readout as $N$ grows.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## The circuit

    `N` is a plain Python value and `main` is decorated with `@guppy.comptime`, so its
    body runs **at compile time** as ordinary Python: the `for` loop is unrolled and
    `N` is baked into the program. Change `N` and everything below recompiles.

    The circuit is a Hadamard on one control qubit followed by a CNOT fan-out onto
    `N` targets. Each `output(label, bit)` call names a measurement result; those
    labels become the columns of the counts returned by the QPU, in alphabetical
    label order (`result_0`, `result_1`, …, then `result_top`).
    """)
    return


@app.cell
def _():
    N = 10
    return (N,)


@app.cell
def _(N):
    @guppy.comptime
    def main() -> None:
        qubit_top = qubit()
        h(qubit_top)
        qubits = [qubit() for _ in range(N)]
        for i in range(N):
            cx(qubit_top, qubits[i])
            m = measure(qubits[i])
            output(f"result_{i}", m)
        m_top = measure(qubit_top)
        output("result_top", m_top)

    return (main,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Compile: Guppy → HUGR → QIR

    `main.compile()` produces a **HUGR** package, Quantinuum's hierarchical program
    graph. The H2 emulators do not accept HUGR directly, so `hugr_to_qir` lowers it to
    **QIR** bitcode, the LLVM-based format the Nexus H2 targets run.
    """)
    return


@app.cell
def _(main):
    hugr = main.compile()
    return (hugr,)


@app.cell
def _(hugr):
    qir_program = hugr_to_qir(hugr, output_format=OutputFormat.BITCODE)
    return (qir_program,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Submit

    `QPU(platform="nexus:H2-2E")` targets the H2-2 hardware-tier emulator, which is
    costed in HQCs, so the job cell is gated behind the **Submit to QPU** button
    rather than re-running on every change. `hugr_stats` summarises the compiled
    program straight from its HUGR nodes and adds a rough HQC estimate for the
    current shot count, before anything is submitted.

    `job.counts()` blocks until the job finishes and returns one dict per submitted
    program. Each key is the measured value of every `output` label, joined by spaces
    in alphabetical label order; each value is how many shots produced that outcome.
    """)
    return


@app.cell
def _(hugr, hugr_stats, shots):
    hugr_stats(hugr, shots.value)
    return


@app.cell
def _():
    qpu = QPU(platform="nexus:H2-2E")
    return (qpu,)


@app.cell
def _():
    shots = mo.ui.number(start=1, stop=10000, step=1, value=100, label="Shots")
    submit = mo.ui.run_button(label="Submit to QPU", kind="success")

    mo.hstack([shots, submit], justify="start")
    return shots, submit


@app.cell
def _(qir_program, qpu, shots, submit):
    mo.stop(
        not submit.value,
        mo.callout(
            mo.md("Press **Submit to QPU** to run the Job"), kind="info"
        ),
    )

    job = qpu.run(qir_program, shots=shots.value)

    mo.callout(
        mo.md(f"Submitted Job **{job.job_id}** to the QPU!"), kind="success"
    )
    return (job,)


@app.cell
def _(job):
    # `counts()` waits on results and returns one mapping per submitted program
    counts = job.counts(timeout=600)[0]
    counts
    return (counts,)


@app.cell
def _(counts, counts_histogram):
    counts_histogram(counts)
    return


if __name__ == "__main__":
    app.run()
