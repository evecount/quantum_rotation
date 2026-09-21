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
| **Problem & Value** | **30%** | Need clarity, solution fit, quantified customer/business value, ROI | **James Sun's Commercial Thesis:** Eliminates multi-billion-dollar classical docking bottlenecks; replaces wet-lab trial-and-error with continuous phase synchronization; $120M–$280M biopharma licensing roadmap. |
| **Technical Performance & Hardware Use** | **30%** | Correctness, benchmark gains, scalability, hardware utilization | **Quantinuum Native Compilation:** Each SWAP-test circuit rebases to 9 qubits, 62 `PhasedX`, 32 `ZZPhase`, 1 measurement (depth 68), ≈13.6 estimated HQCs per 100-shot run; dynamic mid-circuit measurement/reset loop in **Guppy**; 6 benchmark systems on experimental coordinates (PDB 1U19, 1EMA, 7VH8, 3LN1, PubChem 2272, exact H2), each locking onto its deposited pose in 1–5 RUS iterations at 9 qubits (0.4–20° from the exact angle), or 1–8 at 17 (0.4–15°). |
| **Scientific Merit** | **20%** | Novelty, methodological rigor, improvement versus baseline, error analysis | **Gwen's Lie Algebra $\hat{U}_{\text{tube}}(\tau)$:** Replaced 40 years of classical $O(N^3)$ Cartesian grid docking with continuous $SU(2)^{\otimes n}$ rotations; coordinate-free blind parity interference curve. Documented in full in [`provenance/INTELLECTUAL_GENESIS_AND_PROVENANCE.md`](provenance/INTELLECTUAL_GENESIS_AND_PROVENANCE.md). |
| **Engineering & Reproducibility** | **20%** | Code structure, testing, documentation, repeatable setup | **Ben's Systems Architecture:** Clean modular `src/qrotate/` package, interactive Marimo notebook `readme.py`, 3D WebGL Constellation, comprehensive docstrings, `pyproject.toml`, and clean Git history. |

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

## 3. The 6 Therapeutic Benchmark Scenarios

All six run on experimental coordinates (`benchmarks/active_sites.json`, extracted by `src/qrotate/structures.py`):

1. **Retinal / Rhodopsin (PDB 1U19):** the chromophore of vision, bound to Lys296 by a Schiff base (Vision & Optogenetics)
2. **GFP Chromophore (PDB 1EMA):** the fluorescent core of green fluorescent protein (Fluorescence Imaging)
3. **SARS-CoV-2 Mpro + Nirmatrelvir (PDB 7VH8):** the antiviral in Paxlovid, in the Cys145/His41 pocket it blocks (Antiviral Therapeutics)
4. **COX-2 + Celecoxib (PDB 3LN1):** the side pocket that Val523 opens, which COX-1 lacks (Anti-inflammatories)
5. **Azobenzene (PubChem 2272):** a trans photoswitch with no protein pocket (Photopharmacology)
6. **H2 (exact 0.7414 Å geometry):** the smallest possible input, a hardware stress test

---

## 4. Submission Artifacts Included

1. **`PROJECT_QROTATE_SUBMISSION_RELEASE.md`**: This formal executive summary and rubric cross-reference.
2. **`qrotate_solution.zip`**: Complete reproducible solution bundle including `src/qrotate/` package, Pytket compilation scripts, Guppy RUS definitions, and tests.
3. **`Linked Workspace`**: Official Marimo interactive workspace version `v1.0.1` (`readme.py`).
