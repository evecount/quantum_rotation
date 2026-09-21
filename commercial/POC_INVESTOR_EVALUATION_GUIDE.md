# 🧪 Project Q-Rotate: Investor & Partner POC Evaluation Guide

**Venture:** Eve Count (`1ightray`)  
**Product:** Project Q-Rotate: Coordinate-Free Molecular Pose Search  
**Target Hardware:** Quantinuum Trapped-Ion Processors (H-Series, Helios)  
**Lead Contact:** Gwen Lim (`gwen@evecount.com`) | James Sun (`james@mambapartners.com`)  

---

## 🎯 Executive Summary: What This Proof-of-Concept Proves

This Proof-of-Concept (POC) demonstrates that **biomolecular pattern matching and pose recovery can be executed natively on trapped-ion quantum processors without brute-forcing rigid 3D cubic grids ($O(N^3)$)**.

### Core Verified Capabilities:
1. **Coordinate-Free Blind Parity:** Matches candidate molecules against target active sites via quantum state overlap on an ancilla qubit. What crosses the wire is a compressed phase fingerprint, not raw 3D atomic coordinates.
2. **Native Trapped-Ion Compilation:** Compiles directly into Quantinuum's native gateset (`PhasedX`, `ZZPhase`) with zero SWAP overhead, averaging **~13.6 estimated HQCs per 100-shot run**.
3. **Dynamic Feedback (RUS Loops):** Real-time mid-circuit measurement and conditional phase resets written in Quantinuum `guppylang`, lowered through HUGR into 3.6KB of executable QIR bitcode.
4. **Tested on Real PDB Crystal Structures:** Validated on experimental structures (Retinal `1U19`, GFP `1EMA`, Paxlovid Mpro `7VH8`, COX-2 `3LN1`, Azobenzene, and $H_2$).

---

## 🚀 3 Ways to Experience the POC

### Option 1: 30-Second Interactive Browser Demonstration (Zero Install)
* **3D Resonance Constellation:** [evecount.github.io/quantum_rotation/constellation.html](https://evecount.github.io/quantum_rotation/constellation.html)
  * *What to observe:* Toggle between the **4Q** and **8Q** fidelity models. Drag the misalignment angle slider and watch real-time statevector simulation calculate the parity curve and quantum telemetry.
* **Pre-Rendered Interactive Workbook:** [evecount.github.io/quantum_rotation/workbook.html](https://evecount.github.io/quantum_rotation/workbook.html)
  * *What to observe:* Live sliders for binding contact points, thermal coordinate noise, and the compiled Quantinuum H2 native gate count.

---

### Option 2: 2-Minute Automated Test Suite Verification
To verify the complete mathematical, physical, and compiler pipeline from the command line:

```powershell
# 1. Clone the repository
git clone https://github.com/evecount/quantum_rotation.git
cd quantum_rotation

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Run the automated test suite
python tests\test_qrotate.py
```

#### Expected Test Outputs:
* `PASS: test_hpc_bridge` (Geometric parsing & feature mapping)
* `PASS: test_operators (U_tube is unitary)` (Lie group $SU(2)$ conservation)
* `PASS: test_pytket_circuit` (Rebased into native `PhasedX` & `ZZPhase`)
* `PASS: test_guppy_circuit_compilation` (Compiles into HUGR & 3,612-byte QIR bitcode)
* `PASS: test_phase_encoding_is_rotation_equivariant` (Geometric phase preservation)
* `PASS: test_active_sites_are_real_structures` (Validates 6 real PDB binding sites)
* `PASS: test_hqc_cost_counts_compiled_circuit` (~13.64 HQCs per test)
* `PASS: test_blind_rus_protocol_does_not_cheat` (Dynamic loop convergence)

---

### Option 3: Hardware Compiler Benchmark & Cost Showdown
To reproduce the exact gate counts, circuit depths, and HQC credit requirements:

```powershell
python -m src.qrotate.metrics
```
* Generates `benchmarks/showdown_results.json` containing exact hardware allocations for Trapped Ions vs. Superconducting architectures.

---

## 🛡️ Technical & Commercial Inquiries
For institutional data room access, pilot terms, or SAFE investment syndication:
* **Gwen Lim (Founder & Lead Architect):** [gwen@evecount.com](mailto:gwen@evecount.com)
* **James Sun (Commercial & Venture Lead):** [james@mambapartners.com](mailto:james@mambapartners.com)
