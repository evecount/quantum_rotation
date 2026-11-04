# Chapter 8: A Fair Classical Baseline

**What this chapter answers:** how Q-Rotate's blind pose recovery compares with the methods a computational chemist would actually use for the same shape-matching problem, and whether the 4- or 8-phase quantum fingerprint preserves the similarity ranking those methods give.

**Code:** `src/qrotate/classical_baseline.py` (run with `python -m src.qrotate.classical_baseline`).
**Data:** `benchmarks/classical_baseline.json`. **Tests:** `tests/test_classical_baseline.py`.

---

## 1. Why the published baseline was not fair

The "classical baseline" in `metrics.benchmark_classical_docking` is a brute-force Euler grid at 30-degree resolution (12^3 orientations times the atom count), and the "1,920x to 3,360x" reductions in the molecular showdown are step counts against that grid. Nobody solves shape alignment that way. Two standard tools exist:

* **USR** (Ultrafast Shape Recognition, Ballester and Richards, *J. Comput. Chem.* 2007): twelve moments of the distances from every atom to four reference points. It is exactly rotation and translation invariant, so it answers "is this the same shape?" with one descriptor comparison and no search at all. By the same token it returns no pose.
* **Gaussian volume overlap** (Grant, Gallardo and Pickup, *J. Comput. Chem.* 1996; the score behind OpenEye ROCS): every heavy atom is a Gaussian of its van der Waals volume, the overlap integral of two molecules has a closed form, and similarity is the Tanimoto of self and cross overlaps. It depends on orientation and is optimised, in microseconds per evaluation.

This chapter runs both on the six benchmark ligands (RCSB 1U19, 1EMA, 7VH8, 3LN1, PubChem 2272, exact H2) with the same start misalignments `run_molecular_showdown` applies, and scores every method the same way: pose error in degrees, heavy-atom RMSD to the deposited pose in Angstrom, number of score evaluations, and wall-clock time on the benchmark machine (Windows 11, Intel 10th-generation mobile CPU, 8 logical cores, Python 3.14, numpy 2.5; recorded in the JSON under `machine`).

Four Gaussian-overlap searches are reported:

| search | what it does | why it is here |
|---|---|---|
| 15-degree z-grid | 24 rotations about z | the same one-parameter search the quantum RUS runs, at the finest step the RUS schedule ever takes (60 / sqrt(15) = 15.5 degrees) |
| z-grid + 1-D refine | the grid, then a bounded scalar minimisation inside the best cell | what one would actually run |
| 3 Euler angles, unconstrained | `scipy.optimize.minimize` (Nelder-Mead) over z-y-z Euler angles from the identity, no grid, no prior | the honest "no search structure at all" case |
| principal axes + polish | align inertial frames, try the four proper sign choices, polish with a local Euler minimisation | what ROCS does |

The quantum rows are `run_blind_rus_pose_recovery` exactly as the showdown and the robustness study run it (15 iterations, 100 shots, lock when the one-sided 95% lower bound on P(0) clears 0.90), 30 shot-noise seeds per system, with the recovered pose scored by the same RMSD. "Recovered" uses the docking convention of RMSD within 2.0 A; the stricter 1.0 A count is given too. Pose errors for H2 allow the half-turn partner, as the quantum benchmark does.

## 2. Pose recovery on the six systems

Per-method totals over the six systems:

| method | recovered (RMSD <= 2 A) | worst pose error | worst RMSD | score evaluations | wall-clock per system |
|---|---|---|---|---|---|
| USR | no pose (score 1.000 at the start pose and at the truth, on every system) | n/a | n/a | 1 | 0.6-0.9 ms |
| Gaussian, 15-degree z-grid | 6 / 6 | 5.0 deg | 0.29 A | 24 | 2-10 ms |
| Gaussian, z-grid + refine | 6 / 6 | 0.00 deg | 0.000 A | 30-32 | 3-16 ms |
| Gaussian, 3 Euler angles from identity | 5 / 6 (azobenzene stops in a 180-degree local optimum, Tanimoto 0.92) | 180 deg | 6.23 A | 240-269 | 68-277 ms |
| Gaussian, principal axes + polish | 6 / 6 | 0.00 deg | 0.000 A | 8 | 2-3 ms |
| Quantum blind RUS, 4 sites (9 qubits), 180 trials | 170 / 180 = 94.4% (117 / 180 within 1 A); lock rate 93.3% | mean 20 deg | mean 0.91 A | 4.3 circuits x 100 shots = 430 shots | 33-55 ms of statevector emulation; on hardware 4.3 jobs |
| Quantum blind RUS, 8 sites (17 qubits), 180 trials | 159 / 180 = 88.3% (136 / 180 within 1 A); lock rate 87.8% | mean 25 deg | mean 1.10 A | 5.6 circuits x 100 shots | 30-46 ms of emulation; on hardware 5.6 jobs |

Per system (quantum rows are mean +/- standard deviation over 30 trials):

| system | atoms | start | Gaussian z-grid, 24 evals | Gaussian principal axes, 8 evals | Quantum, 4 sites | Quantum, 8 sites |
|---|---|---|---|---|---|---|
| rhodopsin (RET, 1U19) | 20 | +45 deg, 3.08 A | 0.0 deg, 0.00 A | 0.0 deg, 0.00 A | 11.7 +/- 6.0 deg, 0.82 +/- 0.42 A, 100% within 2 A | 9.6 +/- 6.5 deg, 0.67 A, 100% |
| GFP chromophore (CRO, 1EMA) | 22 | +35 deg, 1.99 A | 5.0 deg, 0.29 A | 0.0 deg, 0.00 A | 11.9 +/- 10.2 deg, 0.68 A, 100% | 7.1 +/- 5.1 deg, 0.41 A, 100% |
| Mpro + nirmatrelvir (4WI, 7VH8) | 35 | -50 deg, 2.76 A | 5.0 deg, 0.28 A | 0.0 deg, 0.00 A | 10.7 +/- 3.1 deg, 0.61 A, 100% | 17.6 +/- 27.0 deg, 0.92 A, 93% |
| COX-2 + celecoxib (CEL, 3LN1) | 26 | +80 deg, 4.28 A | 5.0 deg, 0.29 A | 0.0 deg, 0.00 A | 24.6 +/- 24.3 deg, 1.36 A, 90% | 45.1 +/- 56.0 deg, 2.12 A, 73% |
| azobenzene (PubChem 2272) | 14 | -115 deg, 5.25 A | 5.0 deg, 0.27 A | 0.0 deg, 0.00 A | 48.2 +/- 66.8 deg, 1.92 A, 77% | 54.6 +/- 61.7 deg, 2.35 A, 63% |
| H2 (exact) | 2 | +15 deg, 0.10 A | 0.0 deg, 0.00 A | 0.0 deg, 0.00 A | 15.0 deg, 0.10 A, 100% | 15.4 deg, 0.10 A, 100% |

The full per-method rows, including the refined grid and the Euler search, are in the JSON under `pose_recovery`.

**Reading the table.** The classical Gaussian search at the quantum method's own angular resolution (24 evaluations, a few milliseconds) lands within 5 degrees and 0.3 A on every system; adding a one-dimensional refinement makes it exact. The ROCS-style start needs 8 evaluations. The quantum search, on the same ligands and the same starts, needs 430 to 560 shots across 4 to 6 circuits and lands 10 to 50 degrees off on average, which is 0.6 to 2.4 A of RMSD, and misses the 2 A bar in 6 to 12% of trials. The only classical failure is the unconstrained Euler minimiser on azobenzene, which from an uninformed start settles in a 180-degree local optimum (Tanimoto 0.92); the standard inertial-frame starts remove it. There is no axis on which the quantum search beats the classical one: not accuracy, not evaluations, not wall-clock, and not robustness.

USR deserves its own sentence. Its score is 1.000 at the misaligned start and at the truth for every system because it is invariant to rotation: it tells you in under a millisecond that the probe *is* the reference ligand, without searching, and it cannot tell you the pose. The quantum fingerprint is the opposite kind of object: it is rotation *equivariant*, which is what makes a pose search possible and what makes a search necessary.

**What this does to the step-count claims.** The showdown's "classical steps" (for example 34,560 for rhodopsin) count a 3-axis 30-degree grid over every atom. The matching classical search for the problem Q-Rotate actually solves (rotation about z, same resolution) costs 24 evaluations of a closed-form score. Against that, 4.3 circuits times 100 shots is not a reduction. The step-count speedup figures should not be quoted as evidence of advantage.

## 3. Cross-method agreement over ligand pairs

For every ordered pair of the six ligands, each probe was scored against each reference by four methods. The quantum score is the SWAP-test P(0) at the probe's best rotation about z (2-degree sweep; dense statevector at 4 sites, the closed-form product-state formula at 8 sites, which agrees with the statevector to 8e-16). The Gaussian Tanimoto is maximised over z-rotation and, separately, over all three Euler angles from the ROCS-style starts; USR needs no alignment. All molecules are centred on their centroids first. Scores are symmetric in (reference, probe), so the 36 ordered pairs carry 15 distinct off-diagonal values:

| reference | probe | P(0), 4 sites | P(0), 8 sites | USR | Gaussian Tanimoto, z | Gaussian Tanimoto, 3D |
|---|---|---|---|---|---|---|
| rhodopsin | gfp | 0.651 | 0.509 | 0.614 | 0.531 | 0.571 |
| rhodopsin | mpro | 0.586 | 0.509 | 0.518 | 0.329 | 0.438 |
| rhodopsin | cox2 | 0.883 | 0.632 | 0.531 | 0.320 | 0.408 |
| rhodopsin | azobenzene | 0.556 | 0.576 | 0.428 | 0.428 | 0.534 |
| rhodopsin | h2 | 0.865 | 0.556 | 0.248 | 0.029 | 0.029 |
| gfp | mpro | 0.904 | 0.756 | 0.566 | 0.427 | 0.489 |
| gfp | cox2 | 0.668 | 0.516 | 0.621 | 0.523 | 0.678 |
| gfp | azobenzene | 0.662 | 0.517 | 0.482 | 0.430 | 0.608 |
| gfp | h2 | 0.500 | 0.500 | 0.281 | 0.044 | 0.044 |
| mpro | cox2 | 0.599 | 0.515 | 0.773 | 0.422 | 0.470 |
| mpro | azobenzene | 0.706 | 0.546 | 0.465 | 0.229 | 0.353 |
| mpro | h2 | 0.500 | 0.500 | 0.256 | 0.026 | 0.027 |
| cox2 | azobenzene | 0.695 | 0.519 | 0.474 | 0.389 | 0.477 |
| cox2 | h2 | 0.634 | 0.550 | 0.262 | 0.037 | 0.038 |
| azobenzene | h2 | 0.500 | 0.500 | 0.330 | 0.070 | 0.071 |

Self pairs score 0.99 (quantum) and 1.000 (classical) on every method and are excluded from the correlations below, since including them only rewards every method for recognising a molecule as itself.

Spearman rank correlation over the 30 off-diagonal ordered pairs:

| quantum score | vs USR | vs Gaussian Tanimoto (z) | vs Gaussian Tanimoto (3D) |
|---|---|---|---|
| P(0), 4 sites, best z-alignment | +0.03 (p = 0.86) | -0.10 (p = 0.61) | -0.07 (p = 0.71) |
| P(0), 8 sites, best z-alignment | -0.14 (p = 0.46) | -0.11 (p = 0.56) | -0.08 (p = 0.67) |
| P(0), 4 sites, deposited frames (no alignment) | +0.05 (p = 0.81) | -0.02 (p = 0.92) | -0.02 (p = 0.93) |
| *USR vs Gaussian Tanimoto (3D), for reference* | | | **+0.77 (p = 0.0007)** |

The two classical scores agree with each other (rho = +0.77). The quantum P(0), at either register size and with or without alignment, has no rank correlation with either of them. Concretely: the classical methods say H2 is the least similar probe to everything (Tanimoto 0.03-0.07, USR 0.25-0.33), while the 4-site P(0) rates rhodopsin-vs-H2 at 0.865, higher than rhodopsin-vs-GFP (0.651). The 4-phase register holds four angles from the first non-vanishing angular moment of four radial shells; two 20-atom ligands and a diatomic can share those angles by coincidence, and P(0) = (1 + prod cos^2(dphi_i / 2)) / 2 cannot fall below 0.5, so the "dissimilar" end of the scale is compressed into 0.50-0.65 where shot noise lives. Going to 8 sites sharpens self-recognition and pulls most off-diagonal pairs down to 0.50-0.55, but does not restore the chemists' ordering.

## 4. Conclusion

On the six benchmark systems the classical Gaussian-overlap search recovers every deposited pose exactly, in 8 to 32 score evaluations and a few milliseconds, and USR identifies the shape in under a millisecond without a search. The quantum blind RUS search recovers the pose to within 2 A in 94% (4 sites) and 88% (8 sites) of trials, 10 to 50 degrees off on average, using 430 to 560 shots across 4 to 6 circuits, and the similarity its fingerprint reports across different ligands does not correlate with either classical score. The classical methods win on every axis measured here. The step-count reductions quoted elsewhere in this repository compare against a grid nobody runs and should not be read as a quantum advantage.

What the quantum protocol still offers, stated without inflation:

* **A hardware workflow that exists and is costed.** The SWAP-test circuit compiles to the H2 native gate set with zero SWAP routing, the RUS loop is written in Guppy, and the budget per screen is known in HQCs. That is a working end-to-end quantum-classical feedback loop on a real-structure benchmark; it is not a faster or more accurate docking method.
* **Blind comparison of two fingerprints.** The classical controller only ever sees one parity bit per shot; the pocket's register is prepared on the device and never read out. What is protected is a lossy 4- or 8-angle summary, not the structure, and the same summary could be compared classically on a trusted machine, so this is a property of the protocol rather than an advantage over the classical baseline.
* **An honest scaling question for later.** Nothing in this chapter tests the regime where a quantum register might matter (an encoding rich enough to carry chemistry, compared on hardware against a classical score of the same richness). The present encoder is too lossy for that question to arise.

The classical baseline should be the comparison quoted in the finale report, and Chapter 9 adds the hardware-noise ceiling on the quantum rows.
