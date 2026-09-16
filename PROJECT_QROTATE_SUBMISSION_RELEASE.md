# 🚀 Project Q-Rotate: 3D Resonance Constellation & Biomolecular Quantum Masterclass

**Track:** Quantinuum Singapore Grand Challenge 2026 — Chemistry & Biomolecular Simulation Track  
**Team:** Eve Count (`1ightray`)  
**Lead Inventors & Systems Architects:**
* **Gwendalynn (婉婷) Lim ("1ightray")** ([gwen@evecount.com](mailto:gwen@evecount.com) / [LinkedIn](https://www.linkedin.com/in/gwendalynnlim/)) — **Founder & DeepTech Venture CTO ("The Quantum Bunny")**, Eve Count (B.Sc. Hons Applied Computing SIT, NTU SCTP Advanced AI/ML)
* **Benjamin Lim ("Sedilix")** ([ben@evecount.com](mailto:ben@evecount.com) / [LinkedIn](https://www.linkedin.com/in/sedilix/) / [GitHub](https://github.com/sedilix)) — **Co-Founder & Systems Architect**, Eve Count & Cybrdeck (1,500+ commits/yr)
* **James Sun** ([james@mambapartners.com](mailto:james@mambapartners.com) / [LinkedIn (11k+)](https://www.linkedin.com/in/jamessun1/)) — **Founder @ Mamba Partners | Venture Advisor & GTM Strategist** (ex. Goldman Sachs, Blackstone, Microsoft)

---

## 🌌 Live Public Deliverables & Verified Links

* 🌌 **Interactive 3D WebGL Constellation Visualizer:** [https://evecount.github.io/quantum_rotation/constellation.html](https://evecount.github.io/quantum_rotation/constellation.html)  
  *Direct in-browser interactive client: real-time molecular orbital manifolds, trapped-ion gate keypads, and blind parity SWAP interference scopes.*
* 🌐 **Full Project Documentation & Commercial Case:** [https://evecount.github.io/quantum_rotation/](https://evecount.github.io/quantum_rotation/)  
  *Explore our $120M–$280M biopharma licensing roadmap, structural defensibility thesis, and team credentials.*
* 🐙 **Open-Source GitHub Repository:** [https://github.com/evecount/quantum_rotation](https://github.com/evecount/quantum_rotation)  
  *Complete modular architecture (`src/qrotate/`), unit tests, Pytket compilation passes, and reproducible benchmarks.*
* 🎬 **Workshop Masterclass Video Presentation:** Full DYNAMITE Studio script documenting the mathematical provenance of the "Quantum Bunny" Lie algebra intuition and dynamic mid-circuit loops.

---

## 🏆 Official Jury Rubric Alignment (Irfan Khan & Megan)

This submission is strictly engineered to satisfy the four official scoring criteria:

| Scoring Dimension | Weight | Required Evidence | Project Q-Rotate Direct Citation |
| :--- | :---: | :--- | :--- |
| **Problem & Value** | **30%** | Need clarity, solution fit, quantified customer/business value, ROI | **James Sun's Commercial Thesis:** Eliminates multi-billion-dollar classical docking bottlenecks; replaces wet-lab trial-and-error with continuous phase synchronization; $120M–$280M biopharma licensing roadmap. |
| **Technical Performance & Hardware Use** | **30%** | Correctness, benchmark gains, scalability, hardware utilization | **Quantinuum Native Execution:** Reduced to 7 qubits, 47 `PhasedX`, 24 `ZZPhase`, 11.5 HQCs; dynamic mid-circuit measurement/reset loop in **Guppy**; 6 real-world benchmark active sites. |
| **Scientific Merit** | **20%** | Novelty, methodological rigor, improvement versus baseline, error analysis | **Gwen's Lie Algebra $\hat{U}_{\text{tube}}(\tau)$:** Replaced 40 years of classical $O(N^3)$ Cartesian grid docking with continuous $SU(2)^{\otimes n}$ rotations; Zero-Knowledge blind parity interference curve. |
| **Engineering & Reproducibility** | **20%** | Code structure, testing, documentation, repeatable setup | **Ben's Systems Architecture:** Clean modular `src/qrotate/` package, interactive Marimo notebook `readme.py`, 3D WebGL Constellation, comprehensive docstrings, `pyproject.toml`, and clean Git history. |

---

## 1. Executive Summary & Core Breakthrough

Traditional computational docking models (AutoDock, Schrödinger, DFT) discretize 3D Cartesian space into cubic voxels, forcing supercomputers into an exponential combinatorial search ($O(N^3)$) over translational and rotational degrees of freedom.

**Project Q-Rotate** reformulates lock-and-key biomolecular pattern matching as an **information-theoretic quantum state overlap puzzle**:
1. **Continuous Lie Algebra Unitary ($\hat{U}_{\text{tube}}(\tau)$)**:
   $$\hat{U}_{\text{tube}}(\tau) = \exp\left(-i \tau (\hat{H}_{\text{rot}} + \hat{H}_{\text{phase}})\right)$$
   $$\hat{H}_{\text{rot}} = \vec{\omega} \cdot \sum_{k=1}^N \hat{\vec{\sigma}}_k, \quad \hat{H}_{\text{phase}} = \sum_{m=1}^N \Delta \Phi_m \hat{Z}_m$$
2. **Zero-Knowledge Blind Parity (SWAP Test)**:
   $$P(0) = \frac{1}{2} \left( 1 + |\langle \psi_{\text{pocket}} | \psi_{\text{ligand}} \rangle|^2 \right)$$
   Verifies active site fit without exposing proprietary chemical coordinates.
3. **Dynamic Repeat-Until-Success (RUS) in Guppy**:
   Exploits trapped-ion real-time mid-circuit readout and reset to apply corrective phase kicks until zero-parity resonance is achieved.

---

## 2. Quantinuum H2 Hardware Resource Profile

* **Qubits Allocated:** 7 Qubits (All-to-all trapped-ion connectivity)
* **Single-Qubit Rotations (`PhasedX`):** 47 Gates
* **Two-Qubit Entanglers (`ZZPhase`):** 24 Gates
* **Measurements:** 1 Gate
* **Hardware Quantum Credits (HQC):** **11.5 HQCs** per 100 shots on Quantinuum H2-2E

---

## 3. The 6 Therapeutic Benchmark Scenarios

1. **Retinal / Rhodopsin:** Photochemical $cis \to trans$ isomerization (Vision & Optogenetics)
2. **GFP Chromophore:** Catalytic triad hydrogen-bond cyclization (Fluorescence Imaging)
3. **SARS-CoV-2 Mpro:** Covalent protease catalytic pocket (Antiviral Therapeutics)
4. **Kinase ATP-Pocket:** Type-I/II competitive kinase inhibitors (Oncology)
5. **Heme Porphyrin Fe-O2:** Dynamic oxygen coordination & spin transitions (Hematology)
6. **Diazepam / GABA-A:** Neurotransmitter allosteric modulation (CNS Pharmacology)

---

## 4. Submission Artifacts Included

1. **`PROJECT_QROTATE_SUBMISSION_RELEASE.md`**: This formal executive summary and rubric cross-reference.
2. **`qrotate_solution.zip`**: Complete reproducible solution bundle including `src/qrotate/` package, Pytket compilation scripts, Guppy RUS definitions, and tests.
3. **`Linked Workspace`**: Official Marimo interactive workspace version `v1.0.1` (`readme.py`).
