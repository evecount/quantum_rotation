# Project Q-Rotate: Quantum-HPC Hybrid Biomolecular Simulation
**Quantinuum Singapore Grand Challenge 2026 — Chemistry Track**  
**Team: Eve Count (`1ightray`)**  
**Repository:** [github.com/evecount/quantum_rotation](https://github.com/evecount/quantum_rotation)  
**Aqora Workspace:** [aqora.io/1ightray/sg-grand-challenge-evecount](https://aqora.io/1ightray/sg-grand-challenge-evecount)

![Project Q-Rotate](assets/qrotate_banner.jpg)

---

## 1. Executive Summary

Standard computational docking and biomolecular simulations face severe scaling bottlenecks when modeling complex molecular geometries and photochemical active sites. Conventional classical methods (such as grid-based DFT or brute-force spatial sampling) scale poorly with system size, while multi-configurational methods (CASSCF, DMRG) hit an exponential wall when exploring the multi-reference excited states responsible for photoisomerization and catalytic activation.

**Project Q-Rotate** reformulates lock-and-key structural matching as an **information-theoretic quantum state overlap puzzle**:
1. **Classical HPC Embedding**: Macromolecular environment coordinates (>10,000 atoms) are partitioned via an ONIOM / quantum embedding framework (referencing *Yamamoto et al., arXiv:2601.15677* and *Merz et al., arXiv:2605.01138*).
2. **Dimensional Rotation Unitary ($\hat{U}_{\text{tube}}(\tau)$)**: Maps 3D spatial rotations and electronic phase discrepancies into an $SU(2)^{\otimes n}$ Lie algebra:
   $$\hat{U}_{\text{tube}}(\tau) = \exp\left(-i \tau (\hat{H}_{\text{rot}} + \hat{H}_{\text{phase}})\right)$$
   $$\hat{H}_{\text{rot}} = \vec{\omega} \cdot \sum_{k=1}^N \hat{\vec{\sigma}}_k, \quad \hat{H}_{\text{phase}} = \sum_{m=1}^N \Delta \Phi_m \hat{Z}_m$$
3. **Blind Parity Test (SWAP Test)**: An ancilla-mediated parity test verifies structural alignment without exposing the underlying proprietary coordinates.
4. **Repeat-Until-Success (RUS) Dynamic Loop in Guppy**: Leverages Quantinuum's trapped-ion native mid-circuit measurement and reset to dynamically apply adaptive phase corrections until the system locks into the zero-parity ground state.

---

## 📖 Plain-English Documentation Hub (`docs/`)

We believe anyone—engineers, judges, investors, or curious innovators without a PhD in molecular biology or quantum physics—should easily understand how Project Q-Rotate works:

* **[Chapter 1: The Big Picture (Explain Like I'm 5)](docs/01_the_big_picture.md)** — Lock-and-key matching without checking every millimeter.
* **[Chapter 2: The Math Demystified](docs/02_the_math_demystified.md)** — How $\hat{U}_{\text{tube}}(\tau)$ and phase cascading represent physical fit.
* **[Chapter 3: The Blind Parity Test](docs/03_the_blind_parity_test.md)** — Zero-knowledge matching via the SWAP test.
* **[Chapter 4: Repeat-Until-Success in Guppy](docs/04_the_rus_loop_in_guppy.md)** — Why Quantinuum trapped ions are uniquely built for dynamic loops.
* **[Chapter 5: The Hybrid Architecture](docs/05_quantum_hpc_hybrid.md)** — Dividing and conquering between supercomputers (Fugaku) and quantum QPUs (H2/Helios).
* **[Chapter 6: Roadmap & Submission Tracker](docs/06_roadmap_and_submission.md)** — Step-by-step milestone checklist toward October 15 and the Singapore Grand Finale.

---

## 2. Repository Layout

```text
D:\Quantinuum_GrandChallenge\
├── src\
│   └── qrotate\
│       ├── __init__.py        # Module entrypoint & exports
│       ├── operators.py       # U_tube definition & SU(2) Euler angle decomposition
│       ├── hpc_bridge.py      # Classical parser mapping 3D molecular coords to qubit phases
│       ├── circuits.py        # Guppy & Pytket circuit builders (RUS loop & SWAP test)
│       └── metrics.py         # Overlap fidelity & Quantinuum HQC costing model
├── notebooks\
│   └── project_q_rotate.py   # Interactive Marimo submission dashboard
├── tests\
│   └── test_qrotate.py        # Comprehensive test suite
├── utils.py                   # Official Quantinuum H-series op counter & cost estimator
├── pyproject.toml             # Pinned project dependencies
└── Competition.md             # Challenge guidelines and judging matrix
```

---

## 3. Getting Started

### Environment Setup
Activate the local virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

### Running the Test Suite
Verify all components (HPC bridge, unitary evolution, Pytket rebased circuits, Guppy HUGR/QIR compilation):
```powershell
python tests\test_qrotate.py
```

### Launching the Interactive Marimo Dashboard
Run the interactive application:
```powershell
marimo edit notebooks\project_q_rotate.py
```

---

## 4. Hardware Utilization Highlights (Quantinuum H2 / Helios)

* **Native Gate Optimization**: Compiles directly into Quantinuum trapped-ion physical primitives: `PhasedX`, `ZZPhase`, and virtual `Rz` rotations.
* **All-to-All Connectivity**: CSWAP and ancilla parity tests execute with zero SWAP network routing overhead.
* **Mid-Circuit Dynamic Control**: The Repeat-Until-Success (RUS) loop uses mid-circuit measurement and qubit reset directly on the ion trap, keeping circuit depth shallow while driving phase error to zero.
