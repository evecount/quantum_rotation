# Chapter 9: Hardware-Noise Study

**What this chapter answers:** how far the blind RUS pose search survives gate and readout errors at the levels Quantinuum publishes for H2, and where its lock rate falls below 80%.

**Code:** `src/qrotate/noise_study.py` (run with `python -m src.qrotate.noise_study`).
**Data:** `benchmarks/noise_study.json`. **Tests:** `tests/test_noise_study.py`.

---

## 1. Noise model

Every number published before this chapter (`benchmarks/statistical_robustness.json`, the 93.3% lock rate) came from an ideal statevector plus binomial shot noise. This study puts a depolarizing model on the *compiled* circuit:

* The Pytket SWAP-test circuit is rebased to the H-series gate set (PhasedX, virtual Rz, ZZPhase). The abstract CX/CCX gates are not what the hardware runs: one controlled-SWAP per site compiles to 8 ZZPhase (2 from the CX pair, 6 from the Toffoli), so a 4-site circuit carries 32 two-qubit gates and 62 PhasedX, an 8-site circuit 64 and 122.
* After every ZZPhase a two-qubit depolarizing error fires with probability p2; after every PhasedX a one-qubit error with p1 = p2 / 10; the ancilla readout flips with p_ro = 2e-3. Rz is a frame change on H-series and carries no error. "Probability p of a uniformly random non-identity Pauli" is the convention, which for a two-qubit gate is exactly its average gate infidelity (for one qubit the infidelity is 2p/3).
* **Spec.** The Quantinuum System Model H2 Product Data Sheet (v2.00, October 2024, docs.quantinuum.com) lists two-qubit gate infidelity 1.3e-3 (min) / 1.5e-3 (typical) / 3e-3 (max), one-qubit infidelity about 3e-5, SPAM error 1.5e-3 typical; the per-device performance-validation pages report 0.8e-3 to 1.1e-3 for two-qubit gates on H2-1/H2-2 in 2025. The sweep p2 in {0, 1e-3, 2e-3, 5e-3, 1e-2} brackets that: 1e-3 to 2e-3 is the H2 spec, 5e-3 and 1e-2 are pessimistic.
* **Simulation.** At 9 qubits the noisy circuit is evaluated exactly as a 512 x 512 density matrix; that gives the noisy P(0) ceiling at the true pose in the table and validates the trajectory engine. The exact density matrix costs 3-7 s per circuit on the benchmark machine and a sweep needs about 20,000 circuits, and it is impossible at 17 qubits, so the RUS runs at both sizes draw each of their 100 shots as one Pauli trajectory: the error pattern is sampled gate by gate, the trajectory is simulated exactly, the ancilla bit is drawn from its P(0) and flipped with p_ro. That is a sample from the same channel the density matrix evaluates, with no approximation beyond the finite shots the protocol takes anyway. The trajectory engine exploits the circuit's structure (the ancilla is the only qubit shared between site pairs, so a trajectory is a two-branch sum of product states) and is checked against a dense statevector on identical error patterns to 1e-15 and against the density matrix in the mean. The 17-qubit ceilings are 1000-trajectory means.
* The search itself is `run_blind_rus_pose_recovery` unchanged: 15 iterations, 100 shots per circuit, lock when the one-sided 95% lower bound on measured P(0) clears 0.90. 30 trials per system at 4 sites, 10 at 8 sites.

## 2. Results

9 qubits (4 sites), 30 trials per system, 180 per row. Cells are locks / trials, with the exact noisy P(0) at the true pose in brackets:

| p2 | p1 | overall lock rate | 95% Wilson CI | mean iterations to lock | mean circuits per trial | rhodopsin | GFP | Mpro | COX-2 | azobenzene | H2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 168/180 = 93.3% | 88.7-96.2% | 3.5 | 4.3 | 30/30 (0.992) | 30/30 (0.990) | 30/30 (0.992) | 26/30 (0.992) | 22/30 (0.988) | 30/30 (0.988) |
| 1e-3 | 1e-4 | 165/180 = 91.7% | 86.7-94.9% | 3.8 | 4.8 | 30/30 (0.978) | 30/30 (0.975) | 30/30 (0.978) | 25/30 (0.978) | 20/30 (0.974) | 30/30 (0.974) |
| 2e-3 | 2e-4 | 165/180 = 91.7% | 86.7-94.9% | 4.3 | 5.3 | 30/30 (0.964) | 30/30 (0.962) | 30/30 (0.964) | 27/30 (0.964) | 18/30 (0.961) | 30/30 (0.961) |
| 5e-3 | 5e-4 | 137/180 = 76.1% | 69.4-81.8% | 8.6 | 10.4 | 26/30 (0.925) | 22/30 (0.923) | 21/30 (0.925) | 20/30 (0.925) | 18/30 (0.922) | 30/30 (0.922) |
| 1e-2 | 1e-3 | 11/180 = 6.1% | 3.5-10.6% | 9.6 | 15.6 | 0/30 (0.866) | 1/30 (0.865) | 1/30 (0.866) | 2/30 (0.866) | 1/30 (0.864) | 6/30 (0.864) |

17 qubits (8 sites), 10 trials per system, 60 per row:

| p2 | p1 | overall lock rate | 95% Wilson CI | mean iterations to lock | mean circuits per trial | rhodopsin | GFP | Mpro | COX-2 | azobenzene | H2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 53/60 = 88.3% | 77.8-94.2% | 4.3 | 5.7 | 10/10 (0.987) | 10/10 (0.982) | 10/10 (0.987) | 7/10 (0.989) | 6/10 (0.979) | 10/10 (0.979) |
| 1e-3 | 1e-4 | 52/60 = 86.7% | 75.8-93.1% | 6.0 | 7.4 | 10/10 (0.964) | 10/10 (0.952) | 10/10 (0.959) | 6/10 (0.963) | 6/10 (0.953) | 10/10 (0.956) |
| 2e-3 | 2e-4 | 37/60 = 61.7% | 49.0-72.9% | 8.4 | 11.4 | 7/10 (0.941) | 7/10 (0.921) | 8/10 (0.933) | 3/10 (0.938) | 2/10 (0.914) | 10/10 (0.932) |
| 5e-3 | 5e-4 | 1/60 = 1.7% | 0.3-8.9% | 15.0 | 16.0 | 0/10 (0.871) | 0/10 (0.866) | 1/10 (0.866) | 0/10 (0.861) | 0/10 (0.855) | 0/10 (0.864) |
| 1e-2 | 1e-3 | 0/60 = 0.0% | 0.0-6.0% | - | 16.0 | 0/10 (0.786) | 0/10 (0.770) | 0/10 (0.770) | 0/10 (0.758) | 0/10 (0.748) | 0/10 (0.773) |

Pose error of the locked trials stays at 7-15 degrees at every noise level (it is set by the step schedule, not the noise); what the noise removes is the lock itself. Full per-cell numbers, including pose errors and wall-clock, are in the JSON.

## 3. Where the lock rate falls below 80%

| register | last p2 at or above 80% | first p2 below 80% | linear crossing |
|---|---|---|---|
| 9 qubits (4 sites) | 2e-3 (91.7%) | 5e-3 (76.1%) | p2 = 4.2e-3 |
| 17 qubits (8 sites) | 1e-3 (86.7%) | 2e-3 (61.7%) | p2 = 1.3e-3 |

The mechanism is visible in the ceiling column. A lock needs the one-sided 95% lower bound of a 100-shot estimate to clear 0.90, which needs a true P(0) of about 0.945. With 32 two-qubit gates the ceiling at a perfect pose is 0.964 at p2 = 2e-3 and 0.923 at 5e-3; with 64 it is 0.930 at 2e-3 and 0.864 at 5e-3. Once the ceiling drops below about 0.945 the lock becomes a shot-noise lottery (hence the rising iteration counts), and below about 0.92 it is unreachable. Each doubling of the register halves the tolerable p2.

## 4. Conclusion, plainly

* At the H2 spec (p2 = 1e-3 to 2e-3) the 9-qubit search keeps its lock rate: 91.7% at both points, against 93.3% ideal, with the 95% intervals overlapping. The 17-qubit search holds at 1e-3 (86.7% vs 88.3% ideal) and loses a third of its locks at 2e-3 (61.7%), which is inside the data sheet's typical-to-max range. The 17-qubit configuration should not be presented as hardware-ready at the current lock rule.
* At 5e-3 the 9-qubit lock rate is 76%, at 1e-2 it is 6%; at 17 qubits both are effectively zero. These are pessimistic rates for H2 but realistic for a device a generation older, and they bound the claim.
* The lock rule, not the pose search, is what fails first: the ceiling P(0) is the whole story. A lock threshold calibrated to the device's measured ceiling (or more shots per circuit) would recover locks at 5e-3 at the cost of HQCs; this study did not change the rule, so that the numbers stay comparable with the published ideal ones.
* This is still a model, not a hardware run: uniform depolarizing with p1 = p2/10, no crosstalk, leakage, memory error or transport error, which on a QCCD device are not negligible over a depth-68 to depth-120 circuit. The physical H2 run in the finale window is the only thing that settles it; this chapter says what to expect from it and why.
