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

> **Scope note:** Section 1's ONIOM framework and Section 2's references describe the *target architecture* this project is designed toward and the literature it takes inspiration from. The `hpc_bridge.py` module shipped today does the lighter-weight piece of that pipeline — geometric and partial-charge feature extraction — not full ONIOM-layered DFT/ground-state optimization or a real quantum-embedding partition of the active site. The steps below describe what's implemented now; closing the gap to the full ONIOM picture is future work, not a current claim.

In Project Q-Rotate today:
1. **Classical geometry input**: `MolecularGeometry` takes already-computed atomic coordinates and partial charges (e.g. from a PDB/SDF file or an upstream classical pipeline) — this project does not itself run the DFT/force-field step that produces them.
2. **HPC Bridge (`src/qrotate/hpc_bridge.py`)**: Extracts two mathematical arguments from that geometry:
   - **The Target Manifold ($\vec{\omega}$)**: The pocket geometry is processed to extract the collective angular momentum required to orient the active site: $\vec{\omega} = (\omega_x, \omega_y, \omega_z)$.
   - **The Error Field (`initial_delta_phi`)**: The ligand geometry is compared against the pocket's complementary manifold to calculate the initial discrete phase discrepancy at each orbital contact site.
3. **Parameter Injection into Guppy**: Classical `float` and `list[float]` variables calculated by the HPC bridge are passed directly as compile-time/runtime parameters into `@guppy` functions.
4. **HUGR Dataflow Graph Compilation**: Guppy lowers both quantum gates and classical control flow (`while`, `if/else`, adaptive dampening) into a unified **HUGR (Hierarchical Unified Graph Representation)** and LLVM QIR bitcode.
5. **Quantinuum H2 / Helios Execution**: The trapped-ion hardware executes the Repeat-Until-Success protocol in real time right at the cryostat, leveraging mid-circuit measurement and ion reset without a datacenter network round-trip back to a classical host (latency internal to the control system is still nonzero — "no round-trip," not "zero latency").
6. **Classical Post-Processing (`src/qrotate/metrics.py`)**: Takes the measured output distributions and reports the resonance/parity curve. (Note: this reports overlap/resonance, not a computed binding free energy — see Chapter 2 for what the phase encoding does and doesn't capture.)

---

### 4. The End-to-End Dataflow Diagram

```
       CLASSICAL HPC LAYER (Slurm / Fugaku)
  ┌───────────────────────────────────────────────────────────┐
  │ 10,000+ Atoms (Solvent + Protein Scaffold + Ligand)       │
  │ Classical Force Field / DFT / Electrostatic Potential     │
  └─────────────────────────────┬─────────────────────────────┘
                                │ PDB / SDF Coordinates & Charges
                                ▼
       HPC BRIDGE (src/qrotate/hpc_bridge.py)
  ┌───────────────────────────────────────────────────────────┐
  │ - Radial & polar spherical decomposition: (r, θ, φ)       │
  │ - Target Manifold extraction: ω = (ω_x, ω_y, ω_z)         │
  │ - Error Field calculation: initial_delta_phi              │
  │ - Half-turn normalization: θ_halfturns = Φ / π ∈ [-1, 1]  │
  └─────────────────────────────┬─────────────────────────────┘
                                │ Classical Floats (tau, omega, initial_delta_phi)
                                ▼
       GUPPY COMPILER & HUGR LOWERING (src/qrotate/circuits.py)
  ┌───────────────────────────────────────────────────────────┐
  │ - Static compilation of @guppy(module) functions          │
  │ - Unification of quantum gates and classical while-loops  │
  │ - Generation of LLVM QIR bitcode payload                  │
  └─────────────────────────────┬─────────────────────────────┘
                                │ QIR Bitcode (3.6 KB)
                                ▼
       QUANTINUUM H2 / HELIOS TRAPPED-ION QPU
  ┌───────────────────────────────────────────────────────────┐
  │ - State Preparation: Rz(θ_halfturns)                      │
  │ - Dimensional Rotation: Û_tube(τ)                         │
  │ - Blind Parity Test (CSWAP)                               │
  │ - Real-Time Mid-Circuit Measure & Optical Reset Loop      │
  │ - Ancilla Readout: 0 = Match, 1 = Mismatch                │
  └───────────────────────────────────────────────────────────┘
```

---

### 5. Why the HUGR Dataflow Graph Matters

In conventional hybrid algorithms (like standard VQE):
* The quantum computer measures qubits.
* The numbers travel across the internet / datacenter network to a classical CPU.
* The CPU runs an optimizer like COBYLA or BFGS.
* The CPU sends a new parameter list back to the QPU.

This roundtrip latency kills performance and allows environmental decoherence to destroy quantum states.

**With Guppy and HUGR:**
The classical feedback logic (e.g. `current_phi[idx] = current_phi[idx] * 0.5`) is compiled **directly into the QPU's real-time controller**. The Quantinuum ion trap executes the loop autonomously in microseconds while ion coherence times last tens of seconds. That is the true power of trapped-ion hybrid computing.

