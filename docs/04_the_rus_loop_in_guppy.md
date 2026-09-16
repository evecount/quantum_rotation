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
| **Clean Qubit Reset** | Incomplete ground-state optical pumping creates residual errors | **Optical optical pumping** resets individual ions to $|0\rangle$ with $>99.9\%$ fidelity |
| **Connectivity** | Nearest-neighbor 2D grid requires heavy SWAP networks | **All-to-all connectivity**: Any ion can interact with any other ion directly |

**Quantinuum's trapped-ion architecture is uniquely tailored for dynamic circuits.**

---

### 3. How Guppy Turns Python Loops into Trapped-Ion Firmware

Normally, programming a dynamic loop on a quantum processor requires low-level pulse sequencers or assembly-level quantum instructions.

Quantinuum built **Guppy**—a Python-embedded quantum programming language—specifically to bridge this gap:
```python
@guppy(module)
def qrotate_rus_engine(pocket: list[qubit], ligand: list[qubit], ancilla: qubit) -> bool:
    locked: bool = False
    while not locked:
        # Quantum operations
        apply_u_tube(ligand)
        parity_fail: bool = swap_test_parity(ancilla, pocket[0], ligand[0])
        
        # Real-time classical control flow!
        if not parity_fail:
            locked = True
        else:
            apply_correction(ligand)
            reset(ancilla)  # Mid-circuit ion reset!
            
    return locked
```

When you call `.compile()` on a Guppy function:
1. Guppy translates the Python `while` and `if/else` branches into a **HUGR (Hierarchical Unified Graph Representation)** control-flow graph.
2. `hugr-qir` compiles this graph into an **LLVM QIR bitcode** payload.
3. The Quantinuum control system executes the classical conditional branches in real time right next to the cryostat!
