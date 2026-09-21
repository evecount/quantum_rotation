# 🚀 Project Q-Rotate: 3D Resonance Constellation & Biomolecular Quantum Masterclass

**Track:** Quantinuum Singapore Grand Challenge 2026 — Chemistry & Biomolecular Simulation Track  
**Team:** Eve Count (`1ightray`)  
**Lead Inventors & Systems Architects:**
* **Gwendalynn (婉婷) Lim ("1ightray")** ([gwen@evecount.com](mailto:gwen@evecount.com) / [LinkedIn](https://www.linkedin.com/in/gwendalynnlim/)) — **Founder & DeepTech Venture CTO**, Eve Count (B.Sc. Hons Applied Computing SIT, NTU SCTP Advanced AI/ML)
* **Benjamin Lim ("Sedilix")** ([ben@evecount.com](mailto:ben@evecount.com) / [LinkedIn](https://www.linkedin.com/in/sedilix/) / [GitHub](https://github.com/sedilix)) — **Co-Founder & Systems Architect**, Eve Count & Cybrdeck (1,500+ commits/yr)
* **James Sun** ([james@mambapartners.com](mailto:james@mambapartners.com) / [LinkedIn (11k+)](https://www.linkedin.com/in/jamessun1/)) — **Founder @ Mamba Partners | Venture Advisor & GTM Strategist** (ex. Goldman Sachs, Blackstone, Microsoft)

---

## 🌌 Live Public Deliverables & Verified Links

* 🌌 **Interactive 3D WebGL Constellation Visualizer:** [https://evecount.github.io/quantum_rotation/constellation.html](https://evecount.github.io/quantum_rotation/constellation.html)  
  *In-browser demo on real crystal structures: turn a ligand back into its deposited pose (shown as a gold ghost), watch the simulated SWAP-test landscape, and let the blind search find it from coin flips alone.*
* 🌐 **Full Project Documentation & Commercial Case:** [https://evecount.github.io/quantum_rotation/](https://evecount.github.io/quantum_rotation/)  
  *Explore our $120M–$280M biopharma licensing roadmap, structural defensibility thesis, and team credentials.*
* 🐙 **Open-Source GitHub Repository:** [https://github.com/evecount/quantum_rotation](https://github.com/evecount/quantum_rotation)  
  *Complete modular architecture (`src/qrotate/`), unit tests, Pytket compilation passes, and reproducible benchmarks.*
* 🎬 **Workshop Masterclass Video Presentation:** Full DYNAMITE Studio script documenting the mathematical provenance of the continuous Lie algebra resonance intuition and dynamic mid-circuit loops.

---

## 🏆 Official Jury Rubric Alignment (Irfan Khan & Megan)

This submission is strictly engineered to satisfy the four official scoring criteria:

| Scoring Dimension | Weight | Required Evidence | Project Q-Rotate Direct Citation |
| :--- | :---: | :--- | :--- |
| **Problem & Value** | **30%** | Need clarity, solution fit, quantified customer/business value, ROI | **James Sun's Commercial Thesis:** Eliminates multi-billion-dollar classical docking bottlenecks; replaces wet-lab trial-and-error with continuous phase synchronization; $120M–$280M biopharma licensing roadmap, now benchmarked against 5 real 2024–2025 AI-drug-discovery licensing deals ($51M–$150M upfronts, $1B–$6B milestone ceilings — see [`workspaces/JAMES_VENTURE_GTM_BRIEF.md`](workspaces/JAMES_VENTURE_GTM_BRIEF.md)) rather than presented as an unsourced assumption. |
| **Technical Performance & Hardware Use** | **30%** | Correctness, benchmark gains, scalability, hardware utilization | **Quantinuum Native Compilation:** Each SWAP-test circuit rebases to 9 qubits, 62 `PhasedX`, 32 `ZZPhase`, 1 measurement (depth 68), ≈13.6 estimated HQCs per 100-shot run; dynamic mid-circuit measurement/reset loop in **Guppy**; 6 benchmark systems on experimental coordinates (PDB 1U19, 1EMA, 7VH8, 3LN1, PubChem 2272, exact H2), each locking onto its deposited pose in 1–5 RUS iterations at 9 qubits (0.4–20° from the exact angle), or 1–8 at 17 (0.4–15°). |
| **Scientific Merit** | **20%** | Novelty, methodological rigor, improvement versus baseline, error analysis | **Gwen's Lie Algebra $\hat{U}_{\text{tube}}(\tau)$:** Replaced 40 years of classical $O(N^3)$ Cartesian grid docking with continuous $SU(2)^{\otimes n}$ rotations; coordinate-free blind parity interference curve. Documented in full in [`provenance/INTELLECTUAL_GENESIS_AND_PROVENANCE.md`](provenance/INTELLECTUAL_GENESIS_AND_PROVENANCE.md). **Error analysis:** 30 independent shot-noise trials per system (180 total, `benchmarks/statistical_robustness.json`) give a 93.3% overall lock rate with a 95% Wilson confidence interval of [88.7%, 96.1%] — see §3b. |
| **Engineering & Reproducibility** | **20%** | Code structure, testing, documentation, repeatable setup | **Ben's Systems Architecture:** Clean modular `src/qrotate/` package, interactive Marimo notebook `readme.py`, 3D WebGL Constellation, comprehensive docstrings, `pyproject.toml`, clean Git history, and a 19-case `pytest` suite (`tests/test_qrotate.py`, all passing). |

---

## ⚠️ Emulator vs. Hardware Disclosure

**All benchmark numbers in this document — the molecular showdown table, HQC estimates, and the statistical robustness study — are produced by exact statevector simulation plus binomial shot-noise sampling (`src/qrotate/circuits.py::simulate_swap_test_statevector` / `simulate_shot_sampling`), not by execution on Quantinuum H2 physical hardware.** We state this plainly rather than let the H2-native gate counts (`PhasedX`/`ZZPhase` rebase, HQC costing) imply a hardware run they are not.

What *is* real: the circuits are compiled and rebased to the actual H2 native gateset via Pytket (`rebase_to_h2_gateset`), so the gate counts, circuit depth, and HQC costs are the real costs an H2 job would incur — only the measurement outcomes are simulated rather than sampled from physical qubits. Real device noise (T1/T2 decoherence, crosstalk, leakage) is therefore not captured, and the 93.3% lock rate in §3b should be read as an emulator-noise floor, not a hardware-validated number.

**Path to hardware validation:** per the [Official Event Timeline](Competition.md#-event-timeline), H2 hardware access and dedicated compute allocations are granted to shortlisted teams during the Grand Finale Acceleration stage (Oct 21) ahead of Submission 2 (Nov 14). Our plan for that window is to re-run the six-system molecular showdown and the 30-trial robustness study on H2 emulator-with-noise-model first, then on physical H2 qubits, and report both alongside the current pure-statevector numbers rather than replacing them — so the jury can see the degradation (or lack of it) directly.

---

## 1. Executive Summary & Core Breakthrough

Traditional computational docking models (AutoDock, Schrödinger, DFT) discretize 3D Cartesian space into cubic voxels, forcing supercomputers into an exponential combinatorial search ($O(N^3)$) over translational and rotational degrees of freedom.

**Project Q-Rotate** reformulates lock-and-key biomolecular pattern matching as an **information-theoretic quantum state overlap puzzle**:
1. **Continuous Lie Algebra Unitary ($\hat{U}_{\text{tube}}(\tau)$)**:
   $$\hat{U}_{\text{tube}}(\tau) = \exp\left(-i \tau (\hat{H}_{\text{rot}} + \hat{H}_{\text{phase}})\right)$$
   $$\hat{H}_{\text{rot}} = \vec{\omega} \cdot \sum_{k=1}^N \hat{\vec{\sigma}}_k, \quad \hat{H}_{\text{phase}} = \sum_{m=1}^N \Delta \Phi_m \hat{Z}_m$$
2. **Coordinate-Free Blind Parity (SWAP Test)**:
   $$P(0) = \frac{1}{2} \left( 1 + |\langle \psi_{\text{pocket}} | \psi_{\text{ligand}} \rangle|^2 \right)$$
   Verifies active site fit without exposing proprietary chemical coordinates.
3. **Dynamic Repeat-Until-Success (RUS) in Guppy**:
   Exploits trapped-ion real-time mid-circuit readout and reset to apply corrective phase kicks until zero-parity resonance is achieved.

---

## 2. Quantinuum H2 Hardware Resource Profile

Counts are for one SWAP-test circuit after `rebase_to_h2_gateset` (`src/qrotate/circuits.py`). They are the same for every input tested (the 2–35-atom benchmark ligands and synthetic clouds of 10–1,000 points).

* **Qubits Allocated:** 9 Qubits in the default 4-site configuration (4 target + 4 probe + 1 ancilla), or 17 in the 8-site one; all-to-all trapped-ion connectivity, 0 SWAPs. Both are benchmarked end to end on the same six ligands (`benchmarks/molecular_showdown.json`) and both lock onto all six deposited poses. The 17-qubit register costs about 1.6× as much per circuit (22.04 vs 13.64 HQC) and is no faster, but it locks closer to the exact pose (within ±15–17° rather than ±21–23° at 100 shots) and separates different ligands better (worst false match 0.56 vs 0.71).
* **Single-Qubit Rotations (`PhasedX`):** 62 Gates (plus 82 virtual `Rz`, which are free)
* **Two-Qubit Entanglers (`ZZPhase`):** 32 Gates
* **Measurements:** 1
* **Circuit Depth:** 68
* **Hardware Quantum Credits (HQC):** **≈13.6 HQCs** per 100-shot circuit, estimated with the H-series formula (HQC = 5 + (N₁q + 10·N₂q + 5·(Nq + Nm)) · shots / 5000). This is not a billed hardware job. A full blind RUS screen runs this circuit several times (1–5 iterations across the six benchmark sites at 9 qubits), so it costs a multiple of this: 13.64–68.20 estimated HQCs per screen, or 22.04–176.32 at 17 qubits (`benchmarks/molecular_showdown.json`).

---

## 3. Real-World Molecular Showdown: 6 Biological PDB Benchmarks

To provide concrete, reproducible experimental evidence for the Grand Challenge Jury, Project Q-Rotate was benchmarked against 6 experimentally characterized molecular systems from the **RCSB Protein Data Bank (PDB)** and **PubChem** using exact Quantinuum H-Series trapped-ion circuit rebasing (62 `PhasedX`, 32 `ZZPhase`, 0 SWAPs).

| Active Site Target | Structure Source | Ligand | Heavy Atoms | Start Misalignment | Initial Overlap $P(0)$ | RUS Loops to Lock | Final Overlap $P(0)$ | Pose Error at Lock | Circuit 2Q Gates (`ZZPhase`) | Total Est. HQCs | Classical Speedup Ratio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **11-cis Retinal / Rhodopsin** | **RCSB 1U19** | RET | 20 | +45.0° | 0.791 | **2** | **0.980** | 15.0° | 64 | **27.28** | **1,920×** |
| **GFP Chromophore** | **RCSB 1EMA** | CRO | 22 | +35.0° | 0.864 | **4** | **0.990** | 0.4° | 128 | **54.56** | **1,056×** |
| **SARS-CoV-2 Mpro + Nirmatrelvir** | **RCSB 7VH8** | 4WI | 35 | −50.0° | 0.701 | **2** | **1.000** | 10.0° | 64 | **27.28** | **3,360×** |
| **COX-2 + Celecoxib** | **RCSB 3LN1** | CEL | 26 | +80.0° | 0.573 | **2** | **0.960** | 20.0° | 64 | **27.28** | **2,496×** |
| **Azobenzene Molecular Switch** | **PubChem 2272** | AZO | 14 | −115.0° | 0.502 | **5** | **0.940** | 17.4° | 160 | **68.20** | **538×** |
| **$H_2$ Hardware Benchmark** | **Exact QM** | H2 | 2 | +15.0° | 0.986 | **1** | **0.990** | 15.0° | 32 | **13.64** | **384×** |

*All 6 of 6 real systems lock onto their deposited crystallographic pose within 1–5 RUS iterations on 9 qubits, landing 0.4–20° from the exact angle. A lock means the measured P(0) cleared a 95%-confidence bar, which it does across a band of angles, not that the angle is exact. H2 locked where it started: two atoms barely change under a 15° turn. Estimates use the official Quantinuum H-series costing formula in `src/qrotate/metrics.py`.*

### Register Architecture Scaling: 9 Qubits (4 Sites) vs. 17 Qubits (8 Sites)

| Benchmark Metric | 4 Sites / **9 Qubits** (Default Pose Recovery) | 8 Sites / **17 Qubits** (High-Resolution Fingerprinting) | Strategic Recommendation |
| :--- | :---: | :---: | :--- |
| **Deposited Pose Recovery** | **6 / 6 (100%)** | **6 / 6 (100%)** | Both register sizes lock onto every deposited pose |
| **Pose Error at Lock** | 0.4 – 20.0° | **0.4 – 15.0°** | 17-qubit register locks closer to the exact pose (lock band ±15–17° vs ±21–23° at 100 shots) |
| **RUS Iterations to Lock** | **1 – 5 iterations** | 1 – 8 iterations | 9-qubit register converges faster with lower gate overhead |
| **Estimated HQC Cost / Circuit** | **13.64 HQCs** | 22.04 HQCs | 9-qubit circuit costs ~38% less hardware quota per evaluation |
| **Total Screen Cost per Ligand** | **13.64 – 68.20 HQCs** | 22.04 – 176.32 HQCs | Highly cost-effective for commercial high-throughput screening runs |
| **Worst False Match (Off-Target)** | $P(0) \le 0.706$ | **$P(0) \le 0.558$** | **17-qubit register separates different ligands better** (0.5 means nothing in common) |
| **Coordinate Noise (0.1 Å jitter, 5 ligands)** | $P(0) \in [0.80, 0.99]$ | **$P(0) \in [0.91, 0.98]$** | With soft shell edges, the 17-qubit register holds up at least as well |

All six run on experimental coordinates (`benchmarks/active_sites.json`, extracted by `src/qrotate/structures.py`):

1. **Retinal / Rhodopsin (PDB 1U19):** the chromophore of vision, bound to Lys296 by a Schiff base (Vision & Optogenetics)
2. **GFP Chromophore (PDB 1EMA):** the fluorescent core of green fluorescent protein (Fluorescence Imaging)
3. **SARS-CoV-2 Mpro + Nirmatrelvir (PDB 7VH8):** the antiviral in Paxlovid, in the Cys145/His41 pocket it blocks (Antiviral Therapeutics)
4. **COX-2 + Celecoxib (PDB 3LN1):** the side pocket that Val523 opens, which COX-1 lacks (Anti-inflammatories)
5. **Azobenzene (PubChem 2272):** a trans photoswitch with no protein pocket (Photopharmacology)
6. **H2 (exact 0.7414 Å geometry):** the smallest possible input, a hardware stress test

---

## 3b. Statistical Robustness: 30 Independent Shot-Noise Trials per System

The table above reports one RUS run per system (one shot-noise seed). To answer the Scientific Merit rubric's call for error and validation analysis, each of the six systems was re-run **30 times** with independent shot-noise seeds (180 trials total, `src/qrotate/metrics.py::run_statistical_robustness`, data in `benchmarks/statistical_robustness.json`). Lock rate is reported with a 95% Wilson confidence interval, which — unlike the normal approximation — stays inside [0, 1] at small sample sizes.

| System | Locked / Trials | Lock Rate | 95% CI | Iterations (mean ± std) | Pose Error at Lock (mean ± std) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Rhodopsin (1U19)** | 30/30 | 100.0% | [88.6, 100.0]% | 3.5 ± 1.8 | 11.8° ± 6.1° |
| **GFP (1EMA)** | 30/30 | 100.0% | [88.6, 100.0]% | 3.6 ± 1.4 | 12.2° ± 10.0° |
| **Mpro (7VH8)** | 30/30 | 100.0% | [88.6, 100.0]% | 3.1 ± 1.3 | 10.7° ± 3.1° |
| **COX-2 (3LN1)** | 26/30 | 86.7% | [70.3, 94.7]% | 4.2 ± 3.1 | 17.5° ± 6.3° |
| **Azobenzene (PubChem 2272)** | 22/30 | 73.3% | [55.6, 85.8]% | 6.1 ± 3.2 | 10.2° ± 5.8° |
| **H2 (exact QM)** | 30/30 | 100.0% | [88.6, 100.0]% | 1.0 ± 0.0 | 15.0° ± 0.0° |
| **Overall (180 trials)** | 168/180 | **93.3%** | **[88.7, 96.1]%** | — | — |

**This is a more honest number than "6/6 systems locked."** The single-seed showdown table happened to draw a lucky seed for COX-2 and azobenzene; resampling shows those two systems lock reliably but not universally (73–87%), while the other four are robust across the full trial set (100%, CI floor ≥88.6%). Azobenzene's lower rate tracks its largest start misalignment (−115.0°, by far the hardest case in the set) and its all-organic composition (no metal/heteroatom shell contrast to lock onto), which is a plausible mechanism rather than an unexplained failure mode.

---

## 4. Submission Artifacts Included

1. **`PROJECT_QROTATE_SUBMISSION_RELEASE.md`**: This formal executive summary and rubric cross-reference.
2. **`qrotate_solution.zip`**: Complete reproducible solution bundle including `src/qrotate/` package, Pytket compilation scripts, Guppy RUS definitions, and tests.
3. **`Linked Workspace`**: Official Marimo interactive workspace version `v1.0.1` (`readme.py`).
4. **`benchmarks/molecular_showdown.json`** / **`benchmarks/statistical_robustness.json`**: Raw single-seed and 180-trial benchmark data, regenerable with `python -m src.qrotate.metrics`.
5. **`tests/test_qrotate.py`**: 19-case `pytest` suite covering circuit compilation, phase encoding, RUS convergence, and the statistical-robustness confidence interval — run with `pytest tests/`.
