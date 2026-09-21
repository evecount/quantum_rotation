# 🧪 Project Q-Rotate: Investor & Partner POC Evaluation Guide

**Venture:** Eve Count (`1ightray`)  
**Product:** Project Q-Rotate: Coordinate-Free Molecular Pose Search  
**Target Hardware:** Quantinuum Trapped-Ion Processors (H-Series, Helios)  
**Lead Contact:** Gwen Lim (`gwen@evecount.com`) | James Sun (`james@mambapartners.com`)  

---

## 🎯 Executive Summary: What This Proof-of-Concept Proves

This Proof-of-Concept (POC) demonstrates, **in simulation of circuits compiled for Quantinuum's trapped-ion processors**, that biomolecular pose recovery can be done by a blind quantum search instead of brute-forcing rigid 3D cubic grids ($O(N^3)$). Nothing has run on quantum hardware yet; that is the next milestone.

### What Has Been Verified (in simulation):
1. **Coordinate-Free Blind Parity:** Matches candidate molecules against target active sites via quantum state overlap on an ancilla qubit. What crosses the wire is a compressed phase fingerprint, not raw 3D atomic coordinates.
2. **Native Trapped-Ion Compilation:** Compiles directly into Quantinuum's native gateset (`PhasedX`, `ZZPhase`) with zero SWAP overhead: **13.64 estimated HQCs per 100-shot circuit** at 9 qubits. A full blind search runs 1–5 circuits, so a screen costs 13.64–68.20 HQC (22.04–176.32 at 17 qubits). These are estimates from Quantinuum's published HQC formula, not billed jobs.
3. **Guppy Compilation:** The SWAP-test circuit is also written in Quantinuum `guppylang` and lowers through HUGR into about 3.6 KB of QIR bitcode. It is currently a single-shot kernel: the repeat-until-success search loop runs classically around the simulated circuit, and moving it into the Guppy kernel with mid-circuit measurement and reset is the next engineering step.
4. **Tested on Real Crystal Structures:** Six experimental structures (Retinal `1U19`, GFP `1EMA`, Paxlovid Mpro `7VH8`, COX-2 `3LN1`, Azobenzene PubChem `2272`, and $H_2$). The blind search locks onto every deposited pose, in 1–5 iterations at 9 qubits, landing 0.4–20° from the exact angle. A lock means the measured signal cleared a 95%-confidence bar, not that the angle is exact.

---

## 🚀 3 Ways to Experience the POC

### Option 1: 30-Second Interactive Browser Demonstration (Zero Install)
* **3D Resonance Constellation:** [evecount.github.io/quantum_rotation/constellation.html](https://evecount.github.io/quantum_rotation/constellation.html)
  * *What to observe:* Pick a molecule. The gold ghost is its true pose from the crystal structure; turn your copy back into it with the slider and watch the "How alike?" meter, which reads out the simulated SWAP test. Then press **"Let the quantum computer find it blind"** to watch the search recover the pose from measurements alone. "Under the hood" switches between the 9- and 17-qubit registers. The curves come from statevector simulation of the compiled circuit, computed ahead of time.
* **Pre-Rendered Interactive Workbook:** [evecount.github.io/quantum_rotation/workbook.html](https://evecount.github.io/quantum_rotation/workbook.html)
  * *What to observe:* Live sliders for binding contact points, thermal coordinate noise, and the compiled Quantinuum H2 native gate count.

---

### Option 2: 2-Minute Automated Test Suite Verification
To verify the complete mathematical, physical, and compiler pipeline from the command line:

```powershell
# 1. Clone the repository
git clone https://github.com/evecount/quantum_rotation.git
cd quantum_rotation

# 2. Create and activate the environment (needs uv: https://docs.astral.sh/uv/)
uv sync
.\.venv\Scripts\Activate.ps1

# 3. Run the automated test suite
python tests\test_qrotate.py
```

#### Expected Test Outputs:
18 tests, ending with `ALL PROJECT Q-ROTATE TESTS PASSED SUCCESSFULLY!`. Among them:
* `PASS: test_hpc_bridge` (Geometric parsing & feature mapping)
* `PASS: test_operators (U_tube is unitary)` (Lie group $SU(2)$ conservation)
* `PASS: test_pytket_circuit` (Rebased into native `PhasedX` & `ZZPhase`)
* `PASS: test_guppy_circuit_compilation` (Compiles into HUGR and about 3.6 KB of QIR bitcode, when `hugr-qir` is installed)
* `PASS: test_phase_encoding_is_rotation_equivariant` (Turning the molecule turns every phase by the same angle)
* `PASS: test_active_sites_are_real_structures` (Validates the 6 real structures and their catalytic residues)
* `PASS: test_hqc_cost_counts_compiled_circuit` (13.64 HQC per 100-shot circuit)
* `PASS: test_blind_rus_protocol_does_not_cheat` (The search never reads the answer)
* `PASS: test_pose_recovery_reports_where_it_stopped` (How far from the true pose a lock lands)

---

### Option 3: Hardware Compiler Benchmark & Cost Showdown
To reproduce the exact gate counts, circuit depths, and HQC credit requirements:

```powershell
python -m src.qrotate.metrics
```
* Regenerates the benchmark files (about 20 minutes): `benchmarks/molecular_showdown.json` (the six structures at 9 and 17 qubits: iterations, pose error, HQC), `benchmarks/showdown_results.json` (a scaling study on synthetic point clouds against a classical grid search) and `benchmarks/constellation_profiles.json` (the landscapes the Constellation plots).

---

## 🛡️ Technical & Commercial Inquiries
For institutional data room access, pilot terms, or SAFE investment syndication:
* **Gwen Lim (Founder & Lead Architect):** [gwen@evecount.com](mailto:gwen@evecount.com)
* **James Sun (Commercial & Venture Lead):** [james@mambapartners.com](mailto:james@mambapartners.com)
