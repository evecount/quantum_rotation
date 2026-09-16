import marimo

__generated_with = "0.24.0"
app = marimo.App()

with app.setup:
    import marimo as mo

    from pytket.circuit import Circuit
    from pytket.passes import AutoRebase

    from aqora import QPU
    from aqora.pytket.backend import GATESET


@app.cell
def _():
    from utils import counts_histogram, pytket_stats, render_circuit

    return counts_histogram, pytket_stats, render_circuit


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Bell state with pytket

    This notebook builds the two-qubit [Bell state](https://en.wikipedia.org/wiki/Bell_state)
    $|\Phi^+\rangle$ with **pytket**, rebases it into the H2 gateset, and runs it on the
    **H2-2E** emulator through `aqora.QPU`:

    $$|\Phi^+\rangle = \frac{|00\rangle + |11\rangle}{\sqrt{2}}$$

    pytket `Circuit` → `AutoRebase(GATESET)` → `qpu.run(...)` → counts.

    Only `00` and `11` should ever be measured. Any `01` or `10` beyond noise means the
    entangling gate or the readout is misbehaving, which is why the Bell state is the
    standard smoke test for a new backend.
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## The circuit

    `bell_circuit` allocates two qubits and two classical bits. A Hadamard puts qubit 0
    into an equal superposition, a CNOT copies that superposition onto qubit 1 so the
    pair is entangled, and `measure_all` reads both qubits into the classical bits.
    """)
    return


@app.function
def bell_circuit() -> Circuit:
    """Prepare (|00> + |11>)/sqrt(2) and measure both qubits."""
    circ = Circuit(2, 2)
    circ.H(0)
    circ.CX(0, 1)
    circ.measure_all()
    return circ


@app.cell
def _():
    bell = bell_circuit()
    return (bell,)


@app.cell
def _(bell, render_circuit):
    render_circuit(bell)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Rebase into the H2 gateset

    `aqora.QPU` submits circuits exactly as given, so rebasing into the platform's
    native gates (`Rz`, `PhasedX`, `ZZPhase`, `ZZMax`, `Measure`, `Reset`) is the
    caller's job. `AutoRebase(GATESET)` rewrites the H and CX gates in place, which is
    why it runs on a copy and the original `bell` above stays readable. The cost
    estimator only accepts circuits already in this gateset.
    """)
    return


@app.cell
def _(bell):
    compiled = bell.copy()
    AutoRebase(GATESET).apply(compiled)
    return (compiled,)


@app.cell
def _(compiled, render_circuit):
    render_circuit(compiled)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Submit

    `QPU(platform="nexus:H2-2E")` targets the H2-2 hardware-tier emulator, which is
    costed in HQCs, so the job cell is gated behind the **Submit to QPU** button
    rather than re-running on every change. `pytket_stats` summarises the rebased
    circuit and adds a rough HQC estimate for the current shot count, before anything
    is submitted.

    `job.counts()` blocks until the job finishes and returns one dict per submitted
    program. Each key is the readout of the classical register as a bitstring, for
    example `00` or `11`; each value is how many shots produced that outcome.
    """)
    return


@app.cell
def _(compiled, pytket_stats, shots):
    pytket_stats(compiled, shots.value)
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
def _(compiled, qpu, shots, submit):
    mo.stop(
        not submit.value,
        mo.callout(
            mo.md("Press **Submit to QPU** to run the Job"), kind="info"
        ),
    )

    job = qpu.run(compiled, shots=shots.value)

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
