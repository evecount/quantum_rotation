# Chapter 7: Execution Evidence
## How Q-Rotate's circuits were run, and how to read the proof

**Team: Eve Count (`1ightray`)**  
**Track: Chemistry & Biomolecular Simulation**

---

### 1. Why this chapter exists

The updated submission checklist (Oct 10, 2026) says a submission without
emulator execution evidence (job IDs, logs, outputs) will not be scored. Every
number in Chapters 1 to 6 came from the in-repo statevector simulator
(`src/qrotate/circuits.py::simulate_swap_test_statevector`) with binomial shot
sampling. This chapter describes the pipeline that runs the *same compiled
circuits* on real backends and writes a self-describing evidence directory a
judge can open without reading our code.

The pipeline has two parts:

| Module | Role |
| :--- | :--- |
| `src/qrotate/runner.py` | One interface, `Backend.run(program, shots, seed) -> RunResult`, with three implementations: `statevector` (the simulator every benchmark used), `selene` (Quantinuum's local emulator via guppylang / `selene-sim`), and `nexus:<target>` (Quantinuum Nexus through `aqora.QPU`: `H2-Emulator`, `H2-1E`, `H2-2E`, `H2-1SC`, `H2-2SC`, `H2-1`). |
| `src/qrotate/evidence.py` | Builds the compiled SWAP-test circuit for each benchmark system at two poses, runs it on the chosen backend, and writes `evidence/<timestamp>_<backend>/`. Also the command-line entry point. |

---

### 2. What gets run

For each of the six benchmark systems (`rhodopsin`, `gfp`, `mpro`, `cox2`,
`azobenzene`, `h2bench`, from `benchmarks/active_sites.json`) the writer derives
the inputs exactly as `metrics.run_molecular_showdown` does: the ligand's
experimental coordinates, the same radial-shell phase encoding, the same
`tau = 0.25` and `omega = (1.0, 0.5, 0.25)`, the same per-system seed. It then
builds two circuits per system:

| Pose | Registers compared | Meaning | Cross-check |
| :--- | :--- | :--- | :--- |
| `deposited` | ligand vs its own deposited pose | the state the RUS loop locks onto; P(0) should be close to 1 | the showdown's final locked P(0) |
| `start` | ligand vs the benchmark's starting misalignment (+45°, +35°, −50°, +80°, −115°, +15°) | where the blind search begins | `start_p0` in `benchmarks/molecular_showdown.json` |

Each circuit is `build_pytket_swap_test_circuit` followed by
`rebase_to_h2_gateset` (PhasedX, Rz, ZZPhase; 9 qubits for 4 sites, 17 for 8).
That rebased circuit is what every backend receives; the run file stores it as
pytket JSON so it can be reloaded with `pytket.circuit.Circuit.from_dict` and
re-submitted anywhere.

---

### 3. Directory layout

```
evidence/
└── 20261022T031500Z_statevector/        <UTC timestamp>_<backend>
    ├── manifest.json                    what, where, with which versions, index of runs
    ├── run.log                          the run as it happened, one line per event
    ├── rhodopsin_deposited.json         one file per (system, pose)
    ├── rhodopsin_start.json
    ├── gfp_deposited.json
    ├── ...
    └── h2bench_start.json
```

**`manifest.json`**

| Field | Contents |
| :--- | :--- |
| `backend` | name, kind (`local_simulator`, `local_emulator`, `quantinuum_nexus`), whether it is H-series, and for Nexus the target and its cost unit (HQC, seconds, or free for a syntax checker) |
| `git` | commit, branch, dirty flag: the exact code that produced the directory |
| `environment` | Python version, platform, and versions of numpy, pytket, guppylang, hugr, tket, aqora, selene-sim, hugr-qir |
| `parameters` | sites, qubits, shots, base seed, tau, omega, the systems and poses run |
| `runs` | one entry per circuit: file name, system, pose, exact statevector P(0), HQC estimate, counts, empirical P(0) with its 95 % Wilson interval, job id, wall time, status |
| `summary` | runs ok / errored, every job id, total estimated HQC, the largest deviation of measured P(0) from the exact value, and how many exact values fell inside their Wilson interval |
| `status` | `complete`, `partial` (some runs errored, recorded in `runs`) or `aborted` |

**`<system>_<pose>.json`**

| Section | Contents |
| :--- | :--- |
| `system` | system id and name, structure source (e.g. `RCSB 1U19`), ligand residue name, atom count, start offset, the showdown seed |
| `encoding` | sites, qubits, tau, omega, and the pocket and ligand phase registers that were encoded |
| `circuit` | gate counts (PhasedX, Rz, ZZPhase, Measure, depth), the HQC estimate from Quantinuum's published formula, the compiled circuit as pytket JSON, and the unrebased circuit for comparison |
| `execution` | backend, shots, seed (local backends only), counts, empirical P(0), 95 % Wilson interval, the exact statevector P(0) as a reference line, the Nexus job id, wall time, HQC estimate, and backend-specific extras (job status and raw result payloads for Nexus, simulator name and build time for Selene) |
| `coordinates` | the ligand's elements and the target and probe coordinates, so the encoding can be recomputed |

**`run.log`** is plain text: the backend and parameters, the git commit, the
package versions, then one line per circuit with its exact P(0) and one with
its counts, interval and job id.

---

### 4. How a judge reads it

1. Open `manifest.json`. `backend.name` says where the counts came from.
   `statevector` means our own simulator; `selene` means Quantinuum's local
   emulator; `nexus:H2-2E` (or another target) means a Quantinuum Nexus job,
   and every `runs[].job_id` can be looked up in the Nexus / Aqora job history.
2. Check `git.commit` against this repository and `environment.packages`
   against `pyproject.toml`.
3. For each run, compare `prob_zero` (measured) with `prob_zero_exact` (the
   dense statevector). `summary.exact_inside_wilson_ci` says how many of the
   exact values fall inside the measured 95 % intervals; with shot noise alone
   about 95 % should.
4. Compare the `start` pose of each system with `start_p0` in
   `benchmarks/molecular_showdown.json`: they are the same circuit, so the
   exact values match to the reported precision, and the measured value
   should agree within its interval.
5. To re-run any circuit elsewhere, load `circuit.pytket_json` with
   `Circuit.from_dict` and submit it; nothing in the run depends on our code.

A syntax-check directory (`--syntax-check`, backend `nexus:H2-2SC`) contains
the same files but `execution.shots` is 0 and `counts` empty: the syntax
checker validates and costs a program without executing it, so there is a job
id and a cost but no measurement, by design.

---

### 5. Commands

Reference evidence from the simulator (seconds, no credentials):

```bash
python -m src.qrotate.evidence --backend statevector --systems all --sites 4 --shots 100
```

Local Quantinuum emulator (Selene; `pip install selene-sim`; the first build
links a native runner and can take several minutes, later circuits take a few
seconds each):

```bash
python -m src.qrotate.evidence --backend selene --systems all --sites 4 --shots 100
```

Validate and cost every circuit on the H2-2 syntax checker, spending no HQC
(needs a login):

```bash
python -m src.qrotate.evidence --syntax-check --systems all --sites 4 --shots 100
```

Hardware-tier emulator, the evidence the checklist asks for (needs a login,
costs HQC; about 13.6 HQC per 9-qubit circuit at 100 shots, 12 circuits):

```bash
python -m src.qrotate.evidence --backend nexus:H2-2E --systems all --sites 4 --shots 100
```

Without a login the Nexus commands stop before writing anything and print the
steps: run `aqora login` once on the machine (it opens the browser; sign in
with the team account that holds the Grand Challenge quota), then re-run the
command above. `--sites 8` runs the 17-qubit register; `--systems` takes a
comma list; `--as-entity <org>` attributes Nexus jobs to a team organisation.

---

### 6. Evidence status

| Backend | Status | Where |
| :--- | :--- | :--- |
| `statevector` | executed, all six systems, 4 and 8 sites | `evidence/*_statevector/` |
| `selene` | executed locally where recorded | `evidence/*_selene/` |
| `nexus:H2-2SC` (syntax check) | pending team login | run the syntax-check command above |
| `nexus:H2-2E` | pending team login and hardware window (Oct 21 to Nov 14) | run the H2-2E command above |

The committed `statevector` directories are the reference line: anything a
Quantinuum backend produces should agree with their `prob_zero_exact` values
within shot noise plus the backend's own noise model.
