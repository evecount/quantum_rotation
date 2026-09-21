# 🤝 Internal Sync Memo: Notes for Ben & Claude

**Date:** September 21, 2026  
**From:** Gwen Lim (Founder & Venture CTO, Eve Count)  
**To:** Benjamin Lim (Co-Founder & Systems Architect) & Claude (AI Engineering Partner)  
**CC Strategy:** Ben is CC'd directly on all external emails with Irfan Khan (Quantinuum) and Pierre (Aqora) so our core technical team is 100% unified without friction.  
**Subject:** High-Leverage Outreach Campaign (~10 Contacts Today) & POC Showcase Strategy  

---

## 🎯 Executive Context: Why We Are Reaching Out Today

1. **Major Milestone Achieved (v2.0.0):**  
   We have officially published `v2.0.0` on the Quantinuum Grand Challenge track on Aqora. The codebase now runs against **6 real crystallographic PDB structures (PDB 1U19, 1EMA, 7VH8, 3LN1, PubChem 2272, exact H2)**, compiling to native Quantinuum H2 gates (`PhasedX`, `ZZPhase`, 0 SWAPs). All 18 tests in `tests/test_qrotate.py` pass. Everything so far is simulated; no hardware runs yet.

2. **Incoming Commercial Pull (2 Investor Syndicates):**  
   Following initial pitch conversations, **two investor syndicates have specifically requested a POC evaluation**. They were sold on our commercial thesis: **"The Decentralized Quantum Testing Facility / Quantum CRO"**—enabling wet labs and biopharma teams to screen proprietary drug candidates on quantum hardware without sending their raw 3D molecular coordinates.

3. **Today's Goal:**  
   Send focused, high-clarity communications to ~10 high-value stakeholders across three buckets (Investors, Quantinuum/Aqora, and Singapore Ecosystem) so they see active velocity and clear commercial momentum.

---

## 👥 The 10 Outreach Targets

### Bucket 1: The 2 Interested Investor Syndicates (Immediate POC Delivery)
* **Target 1:** Investor Syndicate A (Lead Partner / DeepTech Principal)  
* **Target 2:** Investor Syndicate B (Life Sciences / Quantum Venture Lead)  
* **Pitch Angle:** Deliver the 30-second live 3D browser POC link + unit economics of the Quantum CRO model.

### Bucket 2: Challenge Mentors & Platform Partners (Ben CC'd)
* **Target 3:** **Irfan Khan** (Lead Applications Engineer, Quantinuum) — Update on v2.0.0, real PDB metrics, and hardware demand for Helios Singapore. *(Ben CC'd)*
* **Target 4:** **Pierre-Augustin Fehr** (Partnership & Operations Lead, Aqora) & **Julian Popescu** (Sr Full Stack Software Engineer, Aqora) — Confirmation of published workspace `v2.0.0`, real PDB benchmark integration, and Marimo kernel compatibility. *(Ben CC'd)*
* **Target 5:** **Megan** (Grand Challenge Lead / Quantinuum Jury) — Awareness of commercial pilot pipeline and hardware utilization alignment.

### Bucket 3: Singapore DeepTech & Biotech Ecosystem (Advisory & Pilot Discovery)
* **Target 6:** **NQSO (National Quantum Strategy Office)** — Briefing on sovereign drug discovery use cases for Singapore’s incoming Helios QPU.
* **Target 7:** **A*STAR Bioinformatics Institute (BII) / EDDC** — Exploratory connection on coordinate-free screening benchmarks for oncology & protease targets.
* **Target 8:** **SGInnovate (Deep Tech Investment / Talent)** — Update on home-grown quantum venture progress.
* **Target 9:** **James Sun (Mamba Partners)** — Briefed via his dedicated workspace on investor traction to unlock institutional syndication.
* **Target 10:** **Selected Biopharma Computational Chemist / Academic Advisor** — For independent validation of our PDB active site extraction.

---

## 🚀 The Core Asset We Share (What to Show)

We **never** send raw command lines or messy code to clients or investors. We send them:
1. 🌌 **Interactive 3D WebGL Constellation:** [https://evecount.github.io/quantum_rotation/constellation.html](https://evecount.github.io/quantum_rotation/constellation.html)  
   *(Runs in any mobile/desktop browser, zero install, interactive sliders for real PDB targets).*
2. 📄 **Investor POC Evaluation Guide:** [`commercial/POC_INVESTOR_EVALUATION_GUIDE.md`](https://github.com/evecount/quantum_rotation/blob/main/commercial/POC_INVESTOR_EVALUATION_GUIDE.md)  
   *(1-page executive summary covering verified capabilities and unit economics).*
3. 🏛️ **Testing Facility Architecture:** [`commercial/DECENTRALIZED_QUANTUM_TESTING_FACILITY.md`](https://github.com/evecount/quantum_rotation/blob/main/commercial/DECENTRALIZED_QUANTUM_TESTING_FACILITY.md)  
   *(The full commercial thesis: AWS/CRO model for blind molecular screening).*

---

## ✉️ Email Copy Templates

### Template A: To the 2 Interested Investors (POC Delivery)
```text
Subject: POC Demo & Technical Evaluation: Project Q-Rotate (Eve Count)

Hi [Name],

Following up on our conversation regarding Eve Count’s Decentralized Quantum Testing Facility model, we have published our end-to-end technical POC (v2.0.0).

You can test the interactive client directly in your browser with zero installation:
🔗 Interactive 3D Constellation POC: https://evecount.github.io/quantum_rotation/constellation.html

Key POC Highlights:
• Locks onto all 6 real structures: tested on experimental crystallographic data (Paxlovid's nirmatrelvir in SARS-CoV-2 Mpro, retinal in rhodopsin, celecoxib in COX-2, the GFP chromophore, azobenzene and H2). In simulation of the compiled circuit, a blind quantum search recovers each molecule's deposited pose to within 20°.
• Reduced IP exposure: the match is computed from quantum state overlap, so what leaves the client is a compressed phase fingerprint rather than raw 3D atomic coordinates. It is not a cryptographic guarantee, since the fingerprint is derived from the structure.
• Hardware-ready and costed: each circuit compiles to Quantinuum's native gates with zero SWAPs, at an estimated 13.6 HQC per 100-shot run. A full screen takes 1–5 runs (13.6–68.2 HQC) and 380–3,400× fewer evaluations than a 30° classical grid search (a step count, not wall-clock time). Running on hardware is our next milestone.

Attached are our Investor POC Evaluation Guide and commercial unit economics. I would be happy to host a brief 15-minute walkthrough this week to discuss pilot rollout terms.

Best regards,
Gwen Lim
Founder & Venture CTO, Eve Count
```

### Template B: To Irfan Khan & Quantinuum (Ben CC'd)
```text
Subject: Grand Challenge v2.0.0 Update & Commercial Inquiries — Team Eve Count (1ightray)
CC: ben@evecount.com

Hi Irfan,

Quick update from Team Eve Count: we have just published Version 2.0.0 of our workspace on Aqora with our complete empirical benchmarking suite:
🔗 Aqora Workspace: https://aqora.io/1ightray/sg-grand-challenge-evecount-q-rotate-efficient-molecular-pattern-matching

We re-ran our benchmarks across 6 real structures (PDB 1U19, 1EMA, 7VH8, 3LN1, PubChem 2272 and exact H2) on 9-qubit and 17-qubit registers. Each 9-qubit circuit compiles to 62 PhasedX and 32 ZZPhase gates with 0 SWAPs (13.64 estimated HQC per 100 shots), and in simulation the blind search locks onto all six deposited poses, within 20°. The circuit also compiles through Guppy to QIR; moving the repeat-until-success loop into the Guppy kernel, and running on H2, are our next steps.

In parallel, we have begun receiving initial pilot inquiries from two regional venture syndicates interested in our decentralized quantum testing facility model as Helios arrives in Singapore. We’d welcome a brief check-in during mentor office hours to align on hardware deployment timelines.

Best regards,
Gwen Lim & Benjamin Lim
Team Eve Count
```

### Template C: To Pierre-Augustin Fehr (Aqora) (Ben CC'd)
```text
Subject: Re: Quantinuum Grand Challenge — Team Eve Count Workspace v2.0.0 Published
CC: ben@evecount.com

Hi Pierre,

Following up on our registration and dashboard access, we wanted to let you know that Team Eve Count has just successfully published Version 2.0.0 of our project workspace on the platform!

🔗 Published Workspace: https://aqora.io/1ightray/sg-grand-challenge-evecount-q-rotate-efficient-molecular-pattern-matching

We've verified full compatibility with the Aqora interactive Marimo environment, embedding our complete 6-system PDB experimental benchmarks and Quantinuum H2 emulator execution flow.

Thank you and the Aqora team for organizing a fantastic platform and developer workflow for this Grand Challenge!

Best regards,
Gwen Lim & Benjamin Lim
Team Eve Count
```

---

## 🛡️ Action Items for the Team

* **Ben:** Check out the latest `origin/main`. The benchmark JSONs were regenerated on the corrected encoder in PR #2 (`8c7992f`), and the UI telemetry reads from them. When emails go out, keep an eye on incoming tech questions from Irfan/Pierre.
* **Claude / Antigravity:** Ensure documentation integrity, sync all workspaces, and assist with any incoming pilot integration questions.
* **James:** Briefed in `workspaces/JAMES_VENTURE_GTM_BRIEF.md` on investor inquiries to guide deal structuring.
