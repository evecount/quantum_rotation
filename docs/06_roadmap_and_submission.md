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

- [ ] **Milestone 4: Cloud Emulator Benchmarks (Upcoming)**
  - [ ] Log in with `aqora login` to link local CLI with `1ightray` account
  - [ ] Execute `project_q_rotate.py` against Quantinuum `nexus:H2-2E` emulator
  - [ ] Capture run logs, job IDs, and HQC consumption records

- [ ] **Milestone 5: Benchmark against Classical Baselines (Upcoming)**
  - [ ] Run comparison against classical brute-force grid search
  - [ ] Quantify speedup and scaling advantage as number of contact sites increases
  - [ ] Compare fidelity curves against theoretical resonance bounds

- [ ] **Milestone 6: Submission 1 Packaging (Target: October 15, 2026)**
  - [ ] Publish version `1.1.0` to team workspace on Aqora
  - [ ] Attach benchmark logs, Marimo dashboard, and documentation
  - [ ] Click "Submit to Track" on the Quantinuum Grand Challenge portal
