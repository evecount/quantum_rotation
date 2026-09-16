# Project Q-Rotate: Documentation Hub
### Demystifying Quantum Biomolecular Pattern Matching for Everyone

**Core Team & Key Responsibilities:**
* **1ightray** — **Founder & Core Quantum Engine ("The Quantum Bunny")**, Eve Count  
  *In charge of:* Scientific innovation and core quantum engine, mathematical formulation of $\hat{U}_{\text{tube}}(\tau)$, Lie algebra generators, dynamic Guppy/Pytket quantum kernels, and trapped-ion physical execution.
* **Benjamin Lim** ([ben@evecount.com](mailto:ben@evecount.com)) — **Frontend Lead & Systems Architect**, Eve Count  
  *In charge of:* Client-facing web applications, 3D WebGL / Three.js data visualization systems (The Resonance Constellation), Marimo dashboard integration, and developer UX.
* **Gwen** ([gwen@evecount.com](mailto:gwen@evecount.com)) — **Operations & Challenge Execution Lead**, Eve Count  
  *In charge of:* Grand Challenge operational logistics, milestone roadmap governance, team execution cadence, partner communication, and submission compliance.
* **James Sun** ([james@mambapartners.com](mailto:james@mambapartners.com)) — **Venture Advisor & Go-To-Market (GTM) Strategist**, Mamba Partners  
  *In charge of:* Venture capital strategy, global Go-To-Market (GTM) execution, pharma industry commercial partnerships, strategic network syndication, and investor positioning.

> *"If you can't explain it simply, you don't understand it well enough."*

Welcome to the **Project Q-Rotate** knowledge base. This documentation is deliberately written so that anyone—software engineers, competition judges, investors, or curious innovators without a PhD in molecular biology or quantum physics—can understand **what problem we are solving, why classical computers struggle, and how quantum trapped ions unlock a brand-new approach.**

---

## Guide Index

| Chapter | Title | Who It's For | Core Question Answered |
| :--- | :--- | :--- | :--- |
| **[01](01_the_big_picture.md)** | **[The Big Picture: Lock-and-Key Matching](01_the_big_picture.md)** | Everyone / Non-experts | Why is drug docking so hard for classical computers, and how does Q-Rotate turn it into a pattern-matching puzzle? |
| **[02](02_the_math_demystified.md)** | **[The Math Demystified: $\hat{U}_{\text{tube}}(\tau)$](02_the_math_demystified.md)** | Developers / Innovators | What is this "dimensional rotation evolution operator" and how does phase cascading represent physical fit? |
| **[03](03_the_blind_parity_test.md)** | **[The Blind Parity Test: Zero-Knowledge Matching](03_the_blind_parity_test.md)** | Cryptography / Quantum Curious | How can a single ancilla qubit verify that a key fits a lock without revealing the key's shape? |
| **[04](04_the_rus_loop_in_guppy.md)** | **[Repeat-Until-Success (RUS) in Guppy](04_the_rus_loop_in_guppy.md)** | Engineers / Hardware Judges | Why are Quantinuum's trapped ions and Guppy uniquely able to run real-time dynamic loops? |
| **[05](05_quantum_hpc_hybrid.md)** | **[The Hybrid Architecture: Quantum + Classical HPC](05_quantum_hpc_hybrid.md)** | Systems Architects | How classical supercomputers (Fugaku) and quantum QPUs (H2/Helios) divide and conquer macromolecular systems. |
| **[06](06_roadmap_and_submission.md)** | **[Competition Roadmap & Milestone Tracker](06_roadmap_and_submission.md)** | Team Eve Count | Every step from today to **Submission 1 (Oct 15)** and the Singapore Grand Finale. |

---

## 💻 Interactive Workbook Sessions

You don't just have to read about Q-Rotate—you can experiment with the quantum models in real time:

* 📓 **[View Jupyter Notebook on GitHub](../notebooks/project_q_rotate.ipynb)**: Pre-rendered notebook on GitHub showing 3D coordinate parsing, phase spectra, resonance curves, and HQC costing.
* 🌐 **[Interactive Marimo App](../notebooks/project_q_rotate.py)**: Full dashboard with sliders for rotation angles, noise levels, and one-click submission to the Quantinuum H2-2E emulator.
* 📄 **[Standalone HTML Report](../notebooks/project_q_rotate.html)**: Open directly in your browser without installing Python or dependencies.

---

## How We Update This Hub

Every time we implement a new feature, run a benchmark, or optimize a circuit:
1. We add a corresponding section or update the progress status here.
2. We provide an intuitive mental model first, followed by the rigorous mathematics and runnable code.

