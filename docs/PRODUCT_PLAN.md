# Q-Rotate: From Hackathon Submission to Product

**Date:** 22 October 2026 (day 2 of the Grand Finale hardware window, Oct 21 – Nov 14)
**Author:** Claude (multi-agent planning session), for Ben, Gwen and James
**Status:** Working plan. Workstreams are dispatched to agent sessions listed at the end.

---

## 1. Where the project actually stands

### What is real and good
- A clean, tested Python package (`src/qrotate/`, 19 passing tests) with an honest encoder (permutation-invariant, chirality-aware, rotation-equivariant radial-shell phases).
- A real dense-statevector simulator of the exact SWAP-test circuit, verified against the closed-form formula.
- A genuinely blind RUS search (SPSA-style, target phases never read) with Wilson confidence intervals across 180 trials.
- H2-native compilation via Pytket (62 PhasedX, 32 ZZPhase, 0 SWAPs, depth 68) and an HQC cost model from the published formula.
- Six real structures (RCSB 1U19, 1EMA, 7VH8, 3LN1; PubChem 2272; exact H2) extracted by `structures.py`.
- A documentation set that, after the October overclaim corrections, is unusually honest for a hackathon.
- A WebGL demo, a pitch page and a one-page PDF.

### What is missing or overstated (ranked by damage)

| # | Gap | Why it matters | Evidence |
| :-- | :-- | :-- | :-- |
| 1 | **Zero emulator or hardware execution.** No job IDs, no logs, no counts from H2-1E, H2-2E, H2-Emulator or Selene. | The Oct 10 submission checklist says a submission missing "evidence of emulator execution, such as job IDs, logs, outputs" **will not proceed to scoring**, and lists "evidence of hardware utilization" as a minimum deliverable. Hardware access opened Oct 21. | `UPDATE 14102026_...pdf` p.6–8; `notebooks/project_q_rotate.py:239` is the only submission hook and needs `aqora login`. |
| 2 | **The Guppy "RUS loop" is a 3-qubit single-shot demo.** The real n-site circuit exists only in Pytket; the repeat-until-success loop runs in classical Python around the simulator. | README and treatise describe mid-circuit Guppy feedback on trapped ions as the core mechanism. It is not implemented. | `src/qrotate/circuits.py:392–430`; `POC_INVESTOR_EVALUATION_GUIDE.md` §3 admits this. |
| 3 | **Search is one-dimensional.** The pose search rotates only about z. Real docking is SO(3) × translation (6 DoF) plus torsions. | A 1-DoF search on a 4–8 phase fingerprint is not docking; a reviewer from A*STAR BII will say so in one sentence. | `metrics.py:_rotate_z`, `run_blind_rus_pose_recovery`. |
| 4 | **No fair classical baseline.** The "1,920×–3,360×" numbers compare RUS step counts to a 30° brute-force grid. Classical shape-similarity methods (USR, ROCS-style Gaussian overlap, spherical-harmonic fingerprints) solve the same shape-overlap problem in microseconds with no grid. | Scientific Merit (20%) asks for "improvement versus a baseline". The current baseline is a straw man; judges and chemists know it. | `metrics.py:benchmark_classical_docking`. |
| 5 | **No noise study.** All 180 trials are ideal statevector + shot noise. | Technical Performance (30%) wants hardware realism. The lock rate under the H2 noise model is unknown; it may collapse on CCX (Toffoli) depth. | `PROJECT_QROTATE_SUBMISSION_RELEASE.md` disclosure. |
| 6 | **Reproducibility holes.** `pyproject.toml` omits numpy, scipy, marimo, altair; package is named `sg-grand-challenge`; no LICENSE file despite the Apache badge; no CI (workflow was deleted in PR #5); tests take ~57 s. | Engineering (20%): "repeatable setup, CI, pinned environment" is listed as the thing that would raise the score. | `pyproject.toml`; `git log` 98ecf8e. |
| 7 | **The product does not exist as software.** No CLI, no API, no client/node split. The "coordinate-free" claim is a property of the circuit, not of any deployable system: today the fingerprint and the circuit are computed in the same process. | The commercial thesis (Quantum CRO node) requires a client SDK that fingerprints locally and a node that only ever sees fingerprints. | `commercial/DECENTRALIZED_QUANTUM_TESTING_FACILITY.md` §3. |
| 8 | **Pricing is underwater.** The team's own doc shows a $50–$250 screen costs $140–$850 of QPU time at list HQC rates. | Problem & Value (30%) wants ROI. The unit economics as written disprove the margin claim. | `DECENTRALIZED_QUANTUM_TESTING_FACILITY.md` §4. |
| 9 | **Repo sprawl.** `workbook.html` exists in four places; `index.html`, `constellation.html`, `simulation.html` are duplicated in root and `docs/`; an 830 KB HTML one-pager and 10 MB of PDFs are committed. | Confuses judges and makes the "clean repository" claim hard to defend. | `ls`. |

### What the Phase 0 studies found (22 Oct 2026)
The fair-baseline and noise workstreams (`docs/08_classical_baseline.md`, `docs/09_noise_study.md`) settled gaps 4 and 5 with results that must shape the product:
- **Classical wins every axis.** A ROCS-style Gaussian-overlap search recovers every deposited pose exactly in 8–32 evaluations and milliseconds; USR identifies the shape in under a millisecond with no search. The quantum blind RUS lands 10–50° off on average and needs 430–560 shots across 4–6 circuits. The step-count "speedups" must not be quoted again.
- **The fingerprint does not rank like a chemist.** Across 30 ligand pairs the quantum P(0) has no rank correlation with USR or Gaussian Tanimoto (|ρ| ≤ 0.14), while the two classical scores agree with each other (ρ = +0.77). The 4- or 8-angle encoder is too lossy to carry chemistry.
- **Noise ceiling.** At the H2 two-qubit spec (p2 = 1e-3 to 2e-3) the 9-qubit search keeps a 91.7% lock rate; it drops below 80% near p2 = 4e-3. The 17-qubit register loses a third of its locks at 2e-3 and should not be presented as hardware-ready.

### The honest framing to adopt
Q-Rotate is **an end-to-end, costed, privacy-preserving quantum execution workflow on trapped ions, demonstrated on a shape-matching toy problem.** It is not a docking engine, not a quantum advantage, and, per Chapter 8, not yet a competitive similarity method. Its defensible value today is:
1. A hardware-realistic, fully costed, end-to-end workflow on Quantinuum systems (exactly what the track exists to build), now with a noise model that predicts what the finale hardware run should show.
2. A blind-evaluation protocol where the node never receives coordinates, implemented as a client/node split with a CLI.
3. A reproducible benchmark harness (six real structures, fair classical comparators, noise sweep) that any richer encoder can be dropped into.

Every doc, pitch and UI label should say this. The pitch must stop leading with docking speedups; it should lead with the workflow, the protocol, and the open scaling question (an encoding rich enough to carry chemistry, compared on hardware against a classical score of the same richness). Everything else is roadmap.

---

## 2. Product definition

**Product:** `qrotate`, a Python package + CLI + node service that lets a lab screen candidate molecules against a target by quantum shape overlap, with the molecule's coordinates never leaving the lab.

**Users:**
- *Now:* Grand Challenge jury; computational chemists evaluating a pilot (A*STAR BII, Engine Bio, Hummingbird).
- *Next:* biotech teams with 10–10,000 candidates per target who want a cheap pre-filter they can run without exporting structures.

**Architecture (three layers):**

```
 ┌──────────────── CLIENT (runs inside the lab) ────────────────┐
 │  qrotate.client                                              │
 │  PDB/SDF ──> radial-shell phase fingerprint (4–8 floats)     │
 │  never sends coordinates; signs + sends fingerprint only     │
 └──────────────────────────┬───────────────────────────────────┘
                            │ fingerprint + job spec (JSON)
 ┌──────────────────────────▼───────────────────────────────────┐
 │  qrotate.node   (FastAPI service, runs at the QPU operator)  │
 │  builds SWAP-test circuit  ──> qrotate.runner                │
 │  runner backends: statevector | Selene | H2-Emulator | H2-2E | H2 hw
 │  returns P(0), Wilson CI, HQC cost, job IDs, logs            │
 └──────────────────────────┬───────────────────────────────────┘
                            │ results JSON
 ┌──────────────────────────▼───────────────────────────────────┐
 │  qrotate CLI / WebGL front-end / Marimo workbook             │
 └──────────────────────────────────────────────────────────────┘
```

**CLI surface (v0.1):**
```
qrotate fingerprint  <structure.pdb|sdf> [--sites 4|8]        -> fingerprint.json
qrotate compile      <target.json> <ligand.json>               -> gate counts, depth, HQC
qrotate screen       <target.json> <ligands/*.json> --backend  -> P(0), CI, cost, job IDs
qrotate evidence     --backend H2-2E --systems all             -> evidence/<date>/ (job IDs, logs, counts)
qrotate serve                                                  -> node API on :8000
```

---

## 3. Roadmap

### Phase 0 — Finale evidence (Oct 22 – Nov 7). *Blocks everything else.*
1. **Runner abstraction** with backends: `statevector` (existing), `selene` (free local noisy emulator), `nexus:H2-Emulator`, `nexus:H2-2E`, `nexus:H2-1` (hardware). Every run writes `evidence/<timestamp>/{manifest.json, circuit.json, counts.json, job.log}` with job IDs.
2. **Run the six systems on Selene and H2-2E**, then on hardware in the allocation window. Report ideal vs noisy-emulator vs hardware P(0) side by side, with the lock rate under noise.
3. **Native Guppy RUS kernel** for n sites with mid-circuit measurement and reset, compiled to QIR, executed on Selene/H2-2E. This converts the central claim from aspiration to evidence.
4. **Reproducibility pass:** complete `pyproject.toml`, LICENSE, GitHub Actions CI, `uv.lock` regenerated, fast test tier.
5. **Written report** (no page limit) restructured around the checklist: problem, approach, implementation, assumptions, validation, results, execution evidence.

### Phase 1 — Scientific credibility (Nov – Dec)
6. **SO(3) search**: three Euler angles (and optionally translation via centroid alignment) instead of z-only; report pose error as RMSD in Å, not degrees. Chapter 8 already scores RMSD; extend the quantum side to match.
7. ~~Fair classical baseline~~ **Done** (`docs/08_classical_baseline.md`). Next: rewrite README, pitch and one-pager so the baseline result is the quoted comparison and the step-count speedups are removed.
8. ~~Noise study~~ **Done** (`docs/09_noise_study.md`). Next: compare its prediction with the real H2-2E and hardware runs from Phase 0 and report the gap.
8b. **Richer encoder** (the real scientific question): design an encoding with enough angular moments or amplitude structure to correlate with Gaussian Tanimoto (target ρ > 0.6 on the 30-pair test), then re-run Chapter 8 and Chapter 9. If no encoder reaches that bar within the HQC budget, say so and position the product purely as workflow and protocol.
9. **Preprint** (arXiv) with Kentaro Yamamoto / CQT as potential co-reviewers, including the negative result.

### Phase 2 — Product (Dec – Feb)
10. `qrotate.client` + `qrotate.node` + CLI, pip-installable, versioned, with an OpenAPI spec.
11. Front-end: `constellation.html` becomes the node's UI (drop a structure → fingerprint in the browser → submit → results). Consolidate root/docs duplication into one static site build.
12. Pilot with one Singapore lab (A*STAR BII or Engine Bio): 100-candidate screen against one target, compared with their own docking ranking.

### Phase 3 — Commercial (Feb onward)
13. Fix the unit economics: either (a) shots per circuit down and HQC negotiated, or (b) price per screen ≥ $300 at 9 qubits, or (c) sell the client SDK + node software as a license and let operators own QPU cost.
14. LOI or pilot term sheet before any raise. Replace the $120M–$280M scenario with a bottom-up TAM/SAM/SOM.

---

## 4. Competition deliverables map (Submission 2, Nov 14)

| Checklist item | Status | Owner / workstream |
| :-- | :-- | :-- |
| Working source + README + dependencies | Partial (deps incomplete) | Packaging |
| Evidence of emulator execution (job IDs, logs) | **Missing** | Hardware evidence |
| Evidence of hardware utilization | **Missing** | Hardware evidence |
| Representative results | Simulation only | Hardware evidence + noise study |
| One-page summary | Done (v3) | Regenerate after hardware data |
| Written report | README + release doc, needs restructure | Report (after evidence) |
| Publish + Submit to Track | Needs team Aqora credentials | Gwen |

---

## 5. Workstreams dispatched to agent sessions

| Session | Scope | Branch |
| :-- | :-- | :-- |
| Hardware evidence runner | Runner abstraction, `evidence/` writer, Selene run, H2-2E/hardware scripts ready for `aqora login` | own worktree |
| Guppy native RUS kernel | n-site Guppy kernel with mid-circuit measure/reset, QIR, Selene execution, tests | own worktree |
| Classical baseline + noise study | USR + Gaussian-overlap baseline on six systems; noise-model lock-rate study | own worktree |
| Client/node product split | `qrotate.client`, `qrotate.node`, CLI, OpenAPI, end-to-end demo on statevector | own worktree |
| Packaging and CI (existing "Main branch monitoring" session) | `pyproject.toml`, LICENSE, GitHub Actions, fast test tier, repo de-duplication plan | this checkout |

**Things only the team can do:** `aqora login` with the `1ightray` credentials, Publish + Submit to Track, hardware allocation confirmation with Irfan Khan, and the pilot conversation with A*STAR BII.
