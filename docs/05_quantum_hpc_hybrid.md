# Chapter 5: The Hybrid Architecture (Quantum + Classical HPC)
## How Supercomputers and Quantum Processors Divide and Conquer

No quantum computer in the world today has 100,000 logical qubits to simulate an entire protein in full atomic detail.
Likewise, no classical supercomputer in the world has the mathematical capacity to model multi-reference excited states without hitting an exponential wall.

The solution is a **Quantum-HPC Hybrid Workflow**.

---

### 1. The Division of Labor (The ONIOM Framework)

In 1995, Nobel laureate Keiji Morokuma developed the **ONIOM** (Our own N-layered Integrated molecular Orbital and molecular Mechanics) methodology. It works like an onion:

```
        ┌────────────────────────────────────────────────────────┐
        │  LAYER 3: The Outer Solvent (Water, Ions)              │
        │  Treated by Classical Molecular Mechanics (MM)         │
        │                                                        │
        │      ┌──────────────────────────────────────────┐      │
        │      │  LAYER 2: The Protein Scaffold           │      │
        │      │  Treated by Classical DFT / Semi-Empirical│     │
        │      │                                          │      │
        │      │      ┌────────────────────────────┐      │      │
        │      │      │  LAYER 1: The Active Core  │      │      │
        │      │      │  Photochemical Chromophore │      │      │
        │      │      │  Strongly Correlated State │      │      │
        │      │      │                            │      │      │
        │      │      │  ===> QUANTINUUM H2 / HELIOS│     │      │
        │      │      └────────────────────────────┘      │      │
        │      └──────────────────────────────────────────┘      │
        └────────────────────────────────────────────────────────┘
```

1. **Outer Layers (99% of the atoms)**: Handled by classical supercomputers (like Fugaku or GPU clusters). Classical physics is extraordinarily good at computing bulk electrostatic screening, hydrogen bond networks, and solvent drag.
2. **Inner Core (1% of the atoms, the active site)**: This is where chemical bonds break, electrons become entangled, or light triggers photochemical isomerization. This small active space ($\approx 4 \text{ to } 30$ orbitals) is handed over to the **Quantinuum QPU**.

---

### 2. The Reference Literature

Our workflow directly builds on the two landmark preprints defining this competition track:

#### Reference 1: Yamamoto et al. ([arXiv:2601.15677](https://arxiv.org/abs/2601.15677))
* **The Milestone**: Demonstrated the first end-to-end coupling between the **Fugaku supercomputer** and the **Quantinuum Reimei trapped-ion quantum computer** for biomolecular excited-state energies.
* **The Algorithm**: Introduced `e-QEB-ADAPT-VQE` and Quantum-Selected Configuration Interaction (QSCI) to construct compact ansätze with dramatically reduced 2-qubit gate counts.
* *Note: Lead author **Kentaro Yamamoto** is the Principal R&D Scientist at Quantinuum and mentor for this challenge track.*

#### Reference 2: Merz, Shajan et al. ([arXiv:2605.01138](https://arxiv.org/abs/2605.01138))
* **The Milestone**: Crossed the **12,000-atom barrier** using heterogeneous quantum-classical supercomputing for protein-ligand complexes (2026 ACM Gordon Bell Prize finalist).
* **The Algorithm**: Demonstrated that molecular fragmentation and projection-based embedding can scale quantum chemistry to real-world drug-target complexes.

---

### 3. How Q-Rotate Fits In

In Project Q-Rotate:
1. **Classical HPC** performs the ground-state geometry optimization, computes the electrostatic potential in the binding pocket, and extracts the 1-electron/2-electron integrals.
2. **HPC Bridge (`hpc_bridge.py`)** compresses these electrostatic and spatial features into compact phase registers.
3. **Quantinuum H2 (`circuits.py`)** runs the Q-Rotate blind parity check and dynamic RUS loop to solve the non-perturbative alignment and phase lock.
4. **Classical Post-Processing (`metrics.py`)** takes the measured output distributions and reconstructs the binding affinity and resonance curve.
