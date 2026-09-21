# Chapter 6: Competition Roadmap & Milestone Tracker
## Quantinuum Singapore Grand Challenge 2026

**Team: Eve Count (`1ightray`)**  
**Track: Chemistry & Biomolecular Simulation**

---

### 1. Key Deadlines

| Date | Milestone | Target Deliverable |
| :--- | :--- | :--- |
| **Active Now** | Platform Prototyping & Emulation | Build Q-Rotate in Guppy & Pytket; benchmark on H2-2E emulator |
| **Oct 15, 2026** | 🎯 **Submission 1 (Qualifier Deadline)** | Complete code, benchmark logs, and documentation for judge shortlisting |
| **Oct 20, 2026** | **Shortlist Announcement** | Finalist teams announced |
| **Oct 21 – Nov 14** | **Grand Finale Hardware Window** | Live execution on Quantinuum trapped-ion hardware (H2 / Helios) |
| **Nov 14, 2026** | 🏁 **Submission 2 (Final Package)** | Final experimental hardware logs, paper, and demo video |
| **Nov 19, 2026** | 🏆 **Grand Finals & Presentation** | In-person presentations in Singapore & winner announcement |

---

### 2. Milestone Checklist

Every step has a verified status and placeholder tracking:

- [x] **Milestone 1: Project & Workspace Setup**
  - [x] Cloned official template into team workspace `1ightray/sg-grand-challenge-evecount`
  - [x] Initialized Python 3.11 virtual environment (`.venv`)
  - [x] Installed `aqora`, `guppylang`, `pytket`, `hugr-qir`, `marimo`, `openfermion`
  - [x] Verified local compilation pipeline (Guppy $\to$ HUGR $\to$ QIR bitcode)

- [x] **Milestone 2: Project Q-Rotate Core Architecture**
  - [x] Mathematical specification of $\hat{U}_{\text{tube}}(\tau) = \exp(-i \tau (\hat{H}_{\text{rot}} + \hat{H}_{\text{phase}}))$
  - [x] HPC Embedding Bridge (`src/qrotate/hpc_bridge.py`) for 3D coordinate-to-phase mapping
  - [x] Blind Parity Test (SWAP test) in Pytket and Guppy
  - [x] Native Quantinuum H2 gateset rebase (`PhasedX`, `ZZPhase`, virtual `Rz`)
  - [x] Repeat-Until-Success (RUS) dynamic control flow engine in Guppy
  - [x] Automated test suite passing (`tests/test_qrotate.py`)

- [x] **Milestone 3: Interactive Dashboard & Documentation**
  - [x] Interactive Marimo submission dashboard (`notebooks/project_q_rotate.py`)
  - [x] Created `docs/` knowledge base with 6 comprehensive chapters
  - [x] Plain-English explanations demystifying lock-and-key matching without a PhD

- [x] **Milestone 4a: Honest Local Benchmark Engine (done)**
  - [x] Replaced the fixed-iteration RUS mock with a real dense-statevector simulation of the actual SWAP-test circuit (`src/qrotate/circuits.py::simulate_swap_test_statevector`), verified against the closed-form single-qubit SWAP-test formula in `tests/test_qrotate.py`
  - [x] Replaced the target-phases-leaking feedback loop with a blind, target-never-read SPSA-style search (`src/qrotate/metrics.py::run_blind_rus_protocol`) — iteration counts and lock/no-lock outcomes now genuinely vary by molecule (regenerated `benchmarks/*.json`)
  - [ ] Log in with `aqora login` to link local CLI with `1ightray` account
  - [ ] Execute `project_q_rotate.py` against Quantinuum `nexus:H2-2E` emulator for real hardware/emulator job logs and job IDs (this step needs the team's own Aqora credentials — not something that can be done from a local dev pass)

- [x] **Milestone 5: Benchmark against Classical Baselines (done, locally)**
  - [x] Ran comparison against classical brute-force grid search (`run_performance_showdown`, `run_molecular_showdown`)
  - [x] Quantified the combinatorial step-count reduction as contact-site count scales (documented as a step-count comparison, not a proven wall-clock quantum-advantage claim)
  - [x] RUS iteration counts now emerge from real per-molecule phase mismatch instead of a fixed cap — see the honest-vs-mocked comparison note in `PROJECT_QROTATE_SUBMISSION_RELEASE.md`

- [ ] **Milestone 6: Submission 1 Packaging (Target: October 15, 2026)**
  - [ ] Publish version `1.1.0` to team workspace on Aqora
  - [ ] Attach benchmark logs, Marimo dashboard, and documentation
  - [ ] Click "Submit to Track" on the Quantinuum Grand Challenge portal
