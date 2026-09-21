# 🏢 Business Case: The Decentralized Quantum Testing Facility Model

**Author:** Eve Count (`1ightray`) | Commercial Architecture: James Sun (Mamba Partners)  
**Status:** Confidential Investor & Commercial Partner Brief  
**Core Model:** Decentralized Quantum Contract Research Organization (Quantum CRO)  

---

## 1. Executive Summary

Project Q-Rotate introduces a novel commercial paradigm: **The Decentralized Quantum Testing Facility**.

Instead of requiring every pharmaceutical sponsor to own quantum computers or risk sending raw trade-secret 3D atomic coordinates to third-party cloud APIs, regional computing centers, academic research institutes, and commercial contract labs can now become **authorized Quantum Screening Nodes**.

Client pharmaceutical labs and biotech startups submit candidate molecules to these nodes using our **Coordinate-Free Protocol**. The node runs the trapped-ion matching circuit and returns a scalar match score: the SWAP-test P(0), which measures how closely two molecular shapes and orientations agree. **The client's raw 3D coordinates never leave the client.** What does leave is a compressed phase fingerprint derived from them, so this reduces exposure rather than guaranteeing secrecy; it is not a cryptographic zero-knowledge scheme (see `docs/03_the_blind_parity_test.md`).

---

## 2. The Multi-Billion-Dollar Market Pain

### The Drug Discovery Bottleneck
* Bringing a new drug to market currently costs **$2.6 Billion** and takes **10–14 years**.
* **Roughly 90% of drug candidates that enter clinical trials fail**, most often for lack of efficacy or for unmanageable toxicity.
* Wet-lab chemical synthesis and in-vitro binding assays cost **$15,000 to $50,000+ per molecule** and take weeks to synthesize.

### The Cloud Quantum Adoption Deadlock
* Pharmaceutical companies spend hundreds of millions of dollars synthesizing and patenting novel molecular scaffolds.
* They are notoriously reluctant to send raw 3D atomic coordinates over public cloud APIs to external quantum computing centers due to the risk of corporate espionage or inadvertent trade-secret exposure.
* **Result:** Quantum hardware remains severely underutilized by the very biopharma enterprises that need it most.

---

## 3. The Solution: Quantum Testing Node Architecture

```
┌────────────────────────────────────────────────────────┐
│               Client Biopharma / Biotech               │
│  - Holds proprietary 3D atomic scaffolds & trade secrets│
│  - Runs Q-Rotate Local Client SDK                      │
└──────────────────────────┬─────────────────────────────┘
                           │ 🛡️ Transmits ONLY compressed
                           │    phase fingerprint (NOT 3D coordinates)
                           ▼
┌────────────────────────────────────────────────────────┐
│        Authorized Quantum Testing Node (CRO Lab)        │
│  - Operates Trapped-Ion Hardware (Quantinuum H2/Helios)│
│  - Compiles continuous Lie group U_tube operators      │
│  - Executes blind parity test & RUS search loop        │
└──────────────────────────┬─────────────────────────────┘
                           │ 📊 Returns Scalar Resonance Metric:
                           │    P(0) Match Probability
                           ▼
┌────────────────────────────────────────────────────────┐
│                     Client Outcome                     │
│  - Shape & pose match score, not binding affinity      │
│  - Raw coordinates never leave the client              │
│  - Goal: fewer dead-end candidates reach the lab       │
└────────────────────────────────────────────────────────┘
```

### Why Labs Want to Become Testing Nodes
1. **Monetize Idle QPU Capacity:** Quantum centers with access to Quantinuum hardware can turn high fixed machine costs into recurring commercial revenue.
2. **Screening Revenue:** Testing nodes charge per-screen fees. QPU time, billed in HQCs, is the main cost of goods, so pricing has to clear it (see the pricing check below).
3. **No Biological Liability:** The node acts purely as an information-theoretic verification service—no wet-lab chemical handling or wet waste disposal.

---

## 4. Unit Economics & Margin Structure

| Parameter | Classical Wet-Lab Assay | Project Q-Rotate Quantum Node | Value & Caveats |
| :--- | :--- | :--- | :--- |
| **Cost per Candidate Tested** | $15,000 – $50,000 | **13.64 – 68.20 HQC per screen** at 9 qubits (1–5 circuit runs of 13.64 HQC each), ≈ **$140 – $850** at list H2 subscription rates | Far cheaper than an assay, but it measures shape and pose match, not binding affinity: a pre-filter, not a replacement |
| **Turnaround Time** | 2 – 6 Weeks | 1–5 circuit runs of 100 shots per screen | Not yet measured on hardware; queue time on shared machines will dominate |
| **IP Exposure Risk** | High (Physical sample transfer) | **Reduced:** raw coordinates stay with the client; a derived phase fingerprint is shared | Not a cryptographic guarantee |
| **Node Pricing to Client** | N/A | **$50 – $250** per candidate screen (proposed) | **Below QPU cost at list HQC rates** (see below) |

> **Pricing check.** Azure Quantum lists Quantinuum H2 access at $125,000/month for 10,000 HQC (Standard) or $175,000/month for 17,000 HQC (Premium), which is $10.29–$12.50 per HQC ([Azure Quantum pricing](https://learn.microsoft.com/en-us/azure/quantum/pricing), updated April 2026; pay-as-you-go is by quote). At those rates one 100-shot circuit (13.64 HQC) costs about $140–$170, and a full 9-qubit screen about $140–$850; the 17-qubit register costs 22.04–176.32 HQC per screen, about $227–$2,200. A $50–$250 price is below that unless HQC rates are negotiated well under list or shots per circuit come down, so the 85%+ gross margin is not supported at list rates. The figures come from `benchmarks/molecular_showdown.json`.

### Tiered Commercial Monetization
1. **Pilot Screening Enclaves ($2M – $5M):** Annual enterprise software license granting biopharma sponsors dedicated queue priority on node clusters.
2. **Per-Candidate High-Throughput Screening (priced above QPU cost; see the pricing check):** Transactional volume for screening chemical libraries of 10,000+ compounds. At list rates, a 10,000-compound library is 136,400–682,000 HQC, or about $1.4M–$8.5M of QPU time at 9 qubits.
3. **Downstream Milestone Options ($10M – $50M):** Optional equity or milestone participation if a pre-screened candidate advances to clinical trials.

---

## 5. Early Investor Traction & Syndicate Interest

We have validated this business case with early investors and deep-tech venture syndicates:
* **Two investment syndicates** have already expressed active interest in leading our Pre-Seed financing.
* **Target Vehicle:** Y Combinator Post-Money SAFE (Simple Agreement for Future Equity).
* **Target Raise:** $750k – $1.5M at a $5M – $8M valuation cap.
* **Use of Proceeds:**
  1. Funding dedicated Quantinuum H2/Helios QPU execution hours.
  2. Partnering with 1–2 Singapore biomedical labs (e.g., A*STAR BII / Biopolis) to validate quantum pose recovery against crystallographic poses and established docking benchmarks.
  3. Packaging the Q-Rotate Client SDK into an enterprise container for biopharma enclaves.
