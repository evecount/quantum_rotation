# Chapter 4: Repeat-Until-Success (RUS) in Guppy
## Why Trapped Ions and Guppy Are Built for Dynamic Feedback

Most quantum computers operate in a **"fire-and-forget"** mode:
1. You load all gates in a rigid, predetermined sequence.
2. The circuit runs without interruption.
3. At the very end, all qubits are measured at once.

If anything goes wrong midway, or if you need to adjust based on an intermediate result, you can't. You have to start the entire experiment over from scratch.

**Project Q-Rotate breaks free of this limitation using Repeat-Until-Success (RUS).**

---

### 1. What is Repeat-Until-Success?

Imagine trying to thread a needle in the dark.
* **Fire-and-Forget**: You take 1,000 blind stabs, look at a photo afterwards, and hope one of them went through.
* **Repeat-Until-Success (RUS)**: You poke the thread. You gently feel with your finger tip (a non-destructive probe). If it missed, you nudge your hand slightly to the left and push again—looping until you feel the thread slide through the eye.

```
                  ┌────────────────────────────────────────┐
                  ▼                                        │
           [ Apply Û_tube ]                                │
                  │                                        │
           [ Blind Parity Test ]                           │
                  │                                        │
          [ Measure Ancilla ]                              │
                  │                                        │
                  ▼                                        │
         Did it match? (m == 0)                            │
               /      \                                    │
              /        \                                   │
         YES /          \ NO (Mismatch detected)           │
            ▼            ▼                                 │
     [ LOCKED FIT! ]    [ Calculate Δθ Correction ]        │
     (Exit Loop)        [ Apply Rz(Δθ) to Ligand ]         │
                        [ Reset Ancilla to |0⟩ ] ──────────┘
```

---

### 2. Why Can't Other Quantum Hardware Do This Easily?

To run an RUS loop, your quantum hardware must satisfy three brutal physical requirements:

| Physical Requirement | Superconducting Qubits | Quantinuum Trapped Ions (H2 / Helios) |
| :--- | :--- | :--- |
| **Coherence Lifetime** | $\approx 100 \text{ microseconds}$ (Decays before classical computer can compute feedback) | **Tens of seconds** (Qubits comfortably wait while the controller computes!) |
| **Mid-Circuit Measurement** | Laser/microwave crosstalk often blows away neighbor qubits | **Individual ion shuttling** separates the measured ion into a dedicated readout zone |
| **Clean Qubit Reset** | Incomplete ground-state optical pumping creates residual errors | **Optical pumping** resets individual ions to $|0\rangle$; trapped-ion state preparation and measurement is generally reported at high fidelity (>99%) in the published literature, though we haven't run our own hardware characterization to cite a project-specific number here |
| **Connectivity** | Nearest-neighbor 2D grid requires heavy SWAP networks | **All-to-all connectivity**: Any ion can interact with any other ion directly |

**Quantinuum's trapped-ion architecture is uniquely tailored for dynamic circuits.**

---

### 3. How Guppy Turns Python Loops into Trapped-Ion Firmware

Normally, programming a dynamic loop on a quantum processor requires low-level pulse sequencers or assembly-level quantum instructions.

Quantinuum built **Guppy**, a Python-embedded quantum programming language, to bridge this gap. Q-Rotate's kernel lives in `src/qrotate/guppy_kernel.py`; `build_rus_kernel(pocket_phases, ligand_phases_init, tau, omega, max_iters, lock_threshold_shots)` returns the compiled program for any number of sites. Stripped of bookkeeping, its loop is:

```python
@guppy
def qrotate_rus() -> None:
    anc = qubit()
    pocket, ligand = alloc_registers()       # 2n qubits, comptime-unrolled
    encode(pocket, ligand)                   # Ry(pi/2) Rz(phase) per site, constants baked in
    apply_u_tube(ligand)                     # Ry(omega_y tau) Rz(omega_z tau) per site
    locked = False
    for t in range(max_iters):               # bounded loop (see below)
        if not locked:
            if t > 0:                        # failed last time: reset and kick
                reset(anc)
                reset_registers(pocket, ligand)
                encode(pocket, ligand)
                for m in range(max_iters):   # kick row t = t constant steps
                    if m < t:
                        kick_step(ligand)        # Rz(step) on every site
                apply_u_tube(ligand)
            swap_test(anc, pocket, ligand)   # H, per site CX / CCX / CX, H
            bit = project_z(anc).read()      # mid-circuit measurement, read by the controller
            if not bit:
                locked = True
    output("iterations", ...); output("kick_index", ...); output("locked", locked); output("parity", bit)
```

When you call `.compile()`:
1. Guppy translates the loop and the `if` branches into a **HUGR (Hierarchical Unified Graph Representation)** control-flow graph; the comptime helpers are unrolled over the sites with every angle a constant.
2. `hugr-qir` lowers that graph to **LLVM QIR bitcode** for the `quantinuum-hardware` target.
3. The Quantinuum control system executes the classical branches in real time, next to the trap.

**What is implemented today (Oct 2026):**

* The kernel above compiles to HUGR and to hardware-target QIR for n = 1, 2, 4 and 8 sites (3 to 17 qubits), and runs on **Selene**, Quantinuum's emulator, through `kernel.emulate(shots)`. Results for the six benchmark systems are in `benchmarks/guppy_rus_selene.json`; `tests/test_guppy_kernel.py` covers compilation, QIR size, linear scaling of native op counts and the ligand == pocket case.
* After a failed test the default kernel resets **both** registers and re-prepares them with the kicked ligand phases, so every test is an independent trial with the same P(0) the rest of the project computes. The literal sketch above (reset only the ancilla, kick the live ligand) is available as `reprepare_on_failure=False`; after a failed SWAP test the registers are entangled, so its later tests are not product-state overlaps.
* The kick is blind: kick row $j$ is $j$ applications of a constant step (default $2\pi/\text{max\_iters}$ on every site, a rotation of the whole ligand about $z$, which is what rotating the molecule does to the shell encoding), or a $\pm$ step random walk whose signs come from the controller's RNG (`kick_mode="rng"`).

**The honest single-shot caveat.** One SWAP test returns one bit with $P(0) = (1 + |\langle\text{pocket}|\text{ligand}\rangle|^2)/2$, which is never below 1/2. A single ancilla $= 0$ is therefore *not* evidence of a match: two orthogonal registers pass half the time. The kernel's `locked` flag means "the per-shot stopping rule fired" (first pass, or `lock_threshold_shots` consecutive passes at the same kick, which drives the false accept rate of an orthogonal pair down to $2^{-t}$), not "the pose is right". The statistical lock the project uses, the lower confidence bound on $P(0)$ across hundreds of shots clearing 0.90, is a property of a *distribution* of shots, so it is computed on the host: `first_parity` across shots estimates $P(0)$ of the starting pose, and the `kick_index` histogram says which rows the shots stopped on. The SPSA-style pose search in `src/qrotate/metrics.py` (`run_blind_rus_protocol`) therefore stays classical; `guppy_kernel.estimate_first_test_p0` lets it read its $P(0)$ estimate from Selene shots instead of the numpy statevector.

**Toolchain limits we hit** (guppylang 1.1.1, hugr-qir 0.3.0, selene-sim 0.3.2):

* `hugr-qir` lowers only loops whose trip count is known at compile time and unrolls them, because the QIR adaptive profile has no backward branches. A `while not locked:` loop is rejected, so the kernel is a static `for` over `max_iters` slots with an `if not locked` guard: the bounded RUS the hardware runs anyway. Selene executes the HUGR with the loop intact.
* For the hardware target every rotation angle must fold to a constant (a runtime float into `Rz` is rejected as "may panic"), so a kick is a static-bound loop of constant-angle steps, and the RNG kick draws signs with `random_int_bounded` (`RandomFloat` is unsupported).
* Qubit *arrays* lower to `alloca` instructions that Quantinuum's `qircheck` rejects (and trip hugr-qir's unroller once the loop carries streak or RNG state), so the registers are tuples of qubits threaded through the comptime helpers. With that, every variant (deterministic or RNG kick, any `lock_threshold_shots`) lowers for n = 1 to 8 and validates with qircheck 0.9.0.
* `quantinuum_qircheck` has no CPython $\geq$ 3.13 release, so on a 3.14 machine QIR is emitted with validation skipped; the benchmark re-validates the same bitcode with qircheck 0.9.0 under a separate CPython 3.12.

Static native op counts after the QSystem rebase, single SWAP test (Guppy twin vs the Pytket circuit): see `op_counts` in `benchmarks/guppy_rus_selene.json`. The loop body of the RUS kernel adds one more state preparation and $2n+1$ resets to those numbers; executed gates per shot grow with the number of tests the shot ran.
