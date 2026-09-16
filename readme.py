# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "aqora==0.29.0",
#     "pytket==2.18.1",
# ]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full", auto_download=["html", "markdown", "ipynb"])


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Quantinuum Singapore Grand Challenge — starter template

    **This is a template, not a submission.** It is here to get you running on a
    Quantinuum emulator in a few minutes. Clone it, make it yours, and build your
    solution on top.

    ## How this works

    1. **Clone** — on the track's **Templates** tab, press **Clone**. Join the track
       first; your clone belongs to your team for the track.
    2. **Build** — edit this notebook. Add cells, pull in datasets, install the
       packages you need. It is your workspace.
    3. **Publish** — press **Publish version** when a version is worth showing.
       Publishing freezes it: it becomes visible to everyone and can no longer be
       edited, so keep working by creating a new version.
    4. **Submit to Track** — a *published* version that was cloned from the track
       gets a **Submit to Track** button. It opens the track's submission page with
       that version attached for you to review and confirm.

    You do not need to be a quantum expert. The worked examples below cover the one
    thing every team needs: **running a circuit on a Quantinuum emulator.**
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Backend Support

    This project demonstrates quantum program development using two distinct frameworks:

    - **Guppy** - A Pythonic quantum-classical programming language with high-level abstractions.
    - **Pytket** - A quantum circuit builder and optimizing compiler toolkit.
    - **Qiskit** - 3rd part quantum circuit builder package.

    Job submissions target Quantinuum's H2 emulators through Aqora's interface. Guppy is backwards compatible on H2 emulators by lowering source programs to QIR via HUGR-QIR.

    The table below shows support for Guppy, Pytket & Qiskit across all the emulator and syntax checker targets available to users during the Grand Challenge.

    | Framework / Target | H2-1E | H2-2E | H2-Emulator | H2-1SC | H2-2SC |
    | ------------------ | :---: | :---: | :---------: | :----: | :----: |
    | Guppy (hugr-qir)   |   ✅  |  ✅   |             |   ✅   |   ✅   |
    | Pytket             |   ✅  |  ✅   |      ✅     |   ✅   |   ✅   |
    | Qiskit (qsharp)    |   ✅  |  ✅   |             |   ✅   |   ✅   |


    - `H2-Emulator`: A Nexus-tier emulation resource with state-vector and stabilizer simulation support. An average error model across all H2 hardware instances is used to model noise mechanisms. This is costed in seconds.
    - `H2-1E`: A hardware-tier emulator instance with state-vector and stabilizer simulation support. The noise model and physical properties of the emulator corresponds to H2-1 hardware. This is costed in hardware quantum credits (HQCs).
    - `H2-2E`: A hardware-tier emulator instance with state-vector and stabilizer simulation support. The noise model and physical properties of the emulator corresponds to H2-2 hardware. This is costed in hardware quantum credits (HQCs).
    - `H2-1SC`, `H2-2SC`: A debug tool, also known as a syntax checker, to verify user programs and to estimate the job cost of running a program on hardware or hardware-tier emulators.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Worked examples

    Two notebooks in this workspace each run one circuit end to end on the H2-2E
    emulator, with the pipeline explained step by step:

    - `guppy_example.py` — a GHZ state written in **Guppy**, compiled to HUGR and
      lowered to QIR before submission.
    - `pytket_example.py` — a Bell state built with **pytket** and rebased into the
      H2 gateset before submission.

    Both import shared helpers from `utils.py`: cost estimation, program summary
    tiles, circuit rendering and a counts histogram.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Where to take this

    Replace the example circuits with your own problem. The themes are:

    - **Quantum Primitives** — Hamiltonian simulation for strongly correlated ground states
    - **Chemistry** — electronic structure for battery and drug development
    - **AI for Quantum** — generative methods for hardware utilisation and resource requirements
    - **QEC** — error correction, the firmware for fault tolerance
    - **Optimization** — portfolio allocation, routing, scheduling

    ### Other frameworks

    `aqora.QPU` is framework-agnostic. `run()` accepts pytket `Circuit`s, qiskit
    `QuantumCircuit`s, `@guppy`-decorated functions, hugr `Package`s, raw HUGR or
    QIR bytes, and QASM source — it reads the formats your platform advertises and
    encodes into the best match, so switching framework does not change the
    submission code in the examples:

    ```python
    qpu = QPU(platform='nexus:Selene')
    job = qpu.run(my_guppy_program, shots=1000)
    job.counts(timeout=600)
    ```

    ### Picking a job back up

    Jobs outlive this notebook session, so a long queue does not tie you to the
    tab. Keep the id and reconnect later:

    ```python
    from aqora import QPUJob

    QPUJob.from_id("<job id>").counts()
    ```

    ### Resources

    - [Quantinuum docs](https://docs.quantinuum.com) — Guppy, pytket and systems guides
    - [Aqora (QPU) docs](https://docs.aqora.io/qpu/) - How to use Aqora to run your code
    - [Guppy](https://docs.quantinuum.com/guppy/) — quantum-first programming language embedded in Python
    - [pytket](https://docs.quantinuum.com/tket/api-docs/) — API reference for interacting with tket through Python
    - [Qiskit Interop](https://github.com/microsoft/qdk/wiki/Qiskit-Interop#qir-generation) - Convert qiskit to QIR for use with H2 Emulators
    - [Book a mentor session](https://outlook.office.com/book/QuantinuumSGGrandChallengeMentors@quantinuum.com/?ismsaljsauthenabled)

    When you have something worth showing: **Publish version**, then **Submit to Track**.
    """)
    return


if __name__ == "__main__":
    app.run()
