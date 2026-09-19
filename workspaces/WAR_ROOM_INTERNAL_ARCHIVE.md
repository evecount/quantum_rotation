# War Room / Mission Control — Internal Archive

**This content was removed from the public `index.html` on 2026-09-19 and is kept here for the team's own reference only. Do not re-publish this file or link it from any public page.**

## Why it was removed

The "War Room" section in `index.html` was gated only by a client-side JavaScript passcode check
(`initWarRoom()` — a hardcoded list of passcodes compared in the browser). That is not real access
control: anyone who opens the page's dev tools, or reads the HTML/JS source, can see the passcodes
and the full content regardless of the gate. Since this is a public hackathon submission that judges,
competitors, and anyone with the GitHub Pages URL can open, the section exposed:

- Internal team task checklists and completion state
- James's competitive-positioning notes and an "Unfair Advantage Matrix" against other teams
- A live GitHub API pull of private branch (`ben/frontend-systems`) commit activity
- Draft pitch / ROI / partner-outreach text fields (with a "Send to Gwen" mailto action)

None of that needs to be reachable from the public demo. The legitimate public-facing piece that lived
inside this section — the "Read Challenge Document" modal viewer for `Competition.md` — was **not**
removed; it was redundant with the already-public `competition.html` page (linked from the same section
and elsewhere), so no functionality was lost from the live site.

## Archived HTML (from `index.html`, lines 1356–2069 prior to removal)

```html
    <section id="war-room" class="war-room-container">
      <!-- Locked Passcode Gate -->
      <div id="war-room-gate" class="war-room-gate">
        <div style="font-size: 2.2rem; margin-bottom: 12px;"></div>
        <h2 style="font-size: 1.8rem; font-weight: 800; color: #fff; margin-bottom: 8px;">Private Team Mission Control</h2>
        <p style="color: var(--text-muted); font-size: 0.95rem; line-height: 1.5;">
          Restricted access for <strong>Gwen ("1ightray")</strong>, <strong>Benjamin Lim</strong>, and <strong>James Sun</strong>.<br />
          Enter your team passcode to access private deliverables, role-specific checklists, and roadmap action items.
        </p>
        <div class="passcode-input-wrap">
          <input type="password" id="warroom-passcode-input" class="passcode-input" placeholder="Enter team passcode..." />
          <button id="btn-unlock-warroom" class="btn-primary" style="padding: 12px 22px; cursor: pointer; border: none;">
            <span>Unlock Dashboard →</span>
          </button>
        </div>
        <p style="font-size: 0.75rem; color: #64748b; margin-top: 12px;">
           Authorized Eve Count team members only • Session persists on your device.
        </p>
      </div>

      <!-- Unlocked Dashboard -->
      <div id="war-room-dashboard" class="war-room-dashboard">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; margin-bottom: 24px; padding-bottom: 18px; border-bottom: 1px solid rgba(245, 158, 11, 0.25);">
          <div>
            <div style="display: inline-flex; align-items: center; gap: 8px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: #10b981; font-size: 0.75rem; font-weight: 800; padding: 4px 12px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;">
              <span>● Logged in as Team Eve Count</span>
            </div>
            <h2 style="font-size: 1.85rem; font-weight: 800; color: #fff;"> Project Q-Rotate Mission Control</h2>
          </div>
          <button id="btn-lock-warroom" class="btn-secondary" style="font-size: 0.85rem; padding: 8px 16px; border-color: rgba(239, 68, 68, 0.4); color: #ef4444; cursor: pointer;">
            <span> Lock Dashboard</span>
          </button>
        </div>

        <!-- Role Switcher Dropdown -->
        <div style="background: rgba(10, 15, 30, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px 24px; margin-bottom: 28px;">
          <label for="warroom-member-select" style="display: block; font-size: 0.85rem; font-weight: 700; color: var(--accent-cyan); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px;">
            Select Team Member View:
          </label>
          <select id="warroom-member-select" class="member-select">
            <option value="all"> All Team Members (Master Executive View)</option>
            <option value="gwen"> Gwen ("1ightray") — Founder & Core Quantum Engine</option>
            <option value="ben"> Benjamin Lim — Frontend Lead & Systems Architect</option>
            <option value="james"> James Sun — Venture Advisor & GTM Strategist</option>
          </select>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin: 0;">
            Check off action items as you finish them. Your checklist progress automatically persists across sessions on your device.
          </p>
        </div>

        <!-- PANEL: ALL TEAM (Master View) -->
        <div id="panel-all" class="role-panel active">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 28px;">
            <!-- Gwen -->
            <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(0, 245, 212, 0.25); border-radius: 14px; padding: 22px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h4 style="color: #fff; font-size: 1.1rem; margin: 0;"> Gwen ("1ightray")</h4>
                <span style="font-size: 0.72rem; font-weight: 700; color: var(--accent-cyan); background: rgba(0, 245, 212, 0.12); border: 1px solid rgba(0, 245, 212, 0.3); padding: 3px 8px; border-radius: 12px; text-transform: uppercase;">Prototype v1.0 Built</span>
              </div>
              <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 12px;">Founder & Core Quantum Engine Lead</p>
              <div style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5;">
                <strong>Current Status:</strong> Built foundational architecture, Lie algebra math specs, and Guppy RUS dynamic loop. Next: connect CLI via <code>aqora login</code> and run initial H2-2E emulator benchmarks.
              </div>
            </div>

            <!-- Ben -->
            <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 14px; padding: 22px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h4 style="color: #fff; font-size: 1.1rem; margin: 0;"> Benjamin Lim</h4>
                <span style="font-size: 0.72rem; font-weight: 700; color: #f59e0b; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.3); padding: 3px 8px; border-radius: 12px; text-transform: uppercase;">Branch: ben/frontend-systems</span>
              </div>
              <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 12px;">Frontend Lead & Systems Architect</p>
              <div style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5;">
                <strong>Current Status:</strong> Assigned to lead the client-facing web application and Three.js 3D Constellation enhancements. Work will be pushed to dedicated branch <code>ben/frontend-systems</code>.
              </div>
            </div>

            <!-- James -->
            <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 14px; padding: 22px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h4 style="color: #fff; font-size: 1.1rem; margin: 0;"> James Sun</h4>
                <span style="font-size: 0.72rem; font-weight: 700; color: #c084fc; background: rgba(168, 85, 247, 0.12); border: 1px solid rgba(168, 85, 247, 0.3); padding: 3px 8px; border-radius: 12px; text-transform: uppercase;">Scope of Work Assigned</span>
              </div>
              <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 12px;">Venture Advisor & GTM Strategist</p>
              <div style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5;">
                <strong>Current Status:</strong> Assigned to steer commercialization, biopharma enterprise syndicate outreach, and investor positioning for the Nov 19 Grand Finals in Singapore.
              </div>
            </div>
          </div>

          <!-- Overall Competition Timeline -->
          <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 22px;">
            <h4 style="color: var(--accent-cyan); font-size: 1rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 14px;"> Critical Competition Deadlines</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;">
              <div style="border-left: 2px solid var(--accent-cyan); padding-left: 12px;">
                <div style="font-size: 0.8rem; color: var(--accent-cyan); font-weight: 700;">OCTOBER 15, 2026</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #fff;">Submission 1 Deadline</div>
                <div style="font-size: 0.8rem; color: var(--text-muted);">Qualifier package: code, emulator logs, and Marimo workbook.</div>
              </div>
              <div style="border-left: 2px solid #f59e0b; padding-left: 12px;">
                <div style="font-size: 0.8rem; color: #f59e0b; font-weight: 700;">OCTOBER 20, 2026</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #fff;">Shortlist Announcement</div>
                <div style="font-size: 0.8rem; color: var(--text-muted);">Top finalist teams advance to physical trapped-ion QPU hardware.</div>
              </div>
              <div style="border-left: 2px solid var(--accent-purple); padding-left: 12px;">
                <div style="font-size: 0.8rem; color: var(--accent-purple); font-weight: 700;">OCT 21 – NOV 14</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #fff;">Hardware Run Window</div>
                <div style="font-size: 0.8rem; color: var(--text-muted);">Live execution on Quantinuum trapped ions (H2 / Helios).</div>
              </div>
              <div style="border-left: 2px solid #10b981; padding-left: 12px;">
                <div style="font-size: 0.8rem; color: #10b981; font-weight: 700;">NOVEMBER 19, 2026</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #fff;">Grand Finals in Singapore</div>
                <div style="font-size: 0.8rem; color: var(--text-muted);">In-person demonstration, investor syndication, and winner awards.</div>
              </div>
            </div>
          </div>
        </div>

        <!-- PANEL: GWEN -->
        <div id="panel-gwen" class="role-panel">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
            <div>
              <h3 style="font-size: 1.4rem; font-weight: 800; color: #fff; margin-bottom: 4px;"> Gwen ("1ightray") — Quantum Architecture Lead</h3>
              <p style="color: var(--text-muted); font-size: 0.9rem;">Founder & Core Quantum Engine ("The Quantum Bunny") • <a href="mailto:gwen@evecount.com" style="color: var(--accent-cyan);">gwen@evecount.com</a></p>
            </div>
            <span style="font-size: 0.78rem; font-weight: 700; color: var(--accent-cyan); background: rgba(0, 245, 212, 0.12); border: 1px solid rgba(0, 245, 212, 0.3); padding: 4px 12px; border-radius: 16px; text-transform: uppercase;">
              Prototype v1.0 Foundation Built
            </span>
          </div>

          
          <!-- Official Aqora Workspace Submission Pipeline Card -->
          <div style="background: rgba(12, 18, 34, 0.9); border: 1px solid rgba(0, 245, 212, 0.22); border-radius: 14px; padding: 22px; margin-bottom: 24px; box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.5rem;"></span>
                <div>
                  <h4 style="color: #fff; font-size: 1.15rem; margin: 0; font-weight: 800;">Official Aqora Workspace Submission Pipeline</h4>
                  <div style="font-size: 0.8rem; color: var(--accent-cyan); font-family: var(--font-mono); margin-top: 2px;">
                    Target: 1ightray / sg-grand-challenge-evecount-q-rotate-efficient-molecular-pattern-matching
                  </div>
                </div>
              </div>
              <a href="https://aqora.io/1ightray/sg-grand-challenge-evecount-q-rotate-efficient-molecular-pattern-matching" target="_blank" class="btn-primary" style="font-size: 0.85rem; padding: 8px 18px; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; background: #00f5d4; color: #01040c; font-weight: 700;">
                <span>Open Aqora Workspace ↗</span>
              </a>
            </div>

            <p style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.6; margin-bottom: 16px;">
              Quantinuum and Aqora have configured this Grand Challenge track around <strong>Interactive Marimo Workspaces</strong> running on their cloud Kubernetes cluster (<code>kubimo</code>). To submit Project Q-Rotate, follow the official 3-step publishing lifecycle:
            </p>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin-bottom: 18px;">
              <!-- Step 1 -->
              <div style="background: rgba(10, 15, 29, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
                <div style="font-size: 0.8rem; font-weight: 800; color: #f59e0b; text-transform: uppercase; margin-bottom: 6px;">
                  Step 1 • Initialize Draft
                </div>
                <div style="font-size: 0.86rem; color: #e2e8f0; line-height: 1.5;">
                  The remote workspace currently has <code>versions: []</code> (empty). Click <strong>"Create draft version"</strong> on the Aqora web page to initialize the cloud kernel environment.
                </div>
              </div>

              <!-- Step 2 -->
              <div style="background: rgba(10, 15, 29, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
                <div style="font-size: 0.8rem; font-weight: 800; color: var(--accent-cyan); text-transform: uppercase; margin-bottom: 6px;">
                  Step 2 • Sync / Edit Code
                </div>
                <div style="font-size: 0.86rem; color: #e2e8f0; line-height: 1.5;">
                  <strong>Option A:</strong> In-browser via Aqora Marimo editor / Files tab.<br/>
                  <strong>Option B:</strong> From local terminal using <code>aqora pair</code> to sync local files directly with the cloud kernel.
                </div>
              </div>

              <!-- Step 3 -->
              <div style="background: rgba(10, 15, 29, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
                <div style="font-size: 0.8rem; font-weight: 800; color: #10b981; text-transform: uppercase; margin-bottom: 6px;">
                  Step 3 • Publish & Submit
                </div>
                <div style="font-size: 0.86rem; color: #e2e8f0; line-height: 1.5;">
                  Click <strong>"Publish version"</strong> (freezes code as <code>v0.1.0</code>). Then click <strong>"Submit to Track"</strong> to officially submit to the Quantinuum judging committee.
                </div>
              </div>
            </div>

            <!-- Terminal Commands Box -->
            <div style="background: rgba(0, 0, 0, 0.6); border: 1px solid rgba(0, 245, 212, 0.2); border-radius: 8px; padding: 14px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 0.8rem; font-family: var(--font-mono); color: var(--accent-cyan); font-weight: 700;">
                   Local CLI Pairing Commands (Run in D:\Quantinuum_GrandChallenge)
                </span>
                <span style="font-size: 0.72rem; color: var(--text-muted);">PowerShell / Bash</span>
              </div>
              <pre style="margin: 0; font-family: var(--font-mono); font-size: 0.82rem; color: #38bdf8; background: transparent; padding: 0; overflow-x: auto; line-height: 1.6;"><code># 1. Authenticate local CLI with Gwen's 1ightray account
.venv\Scripts\aqora.exe login

# 2. Pair local repo directly to the active cloud workspace
.venv\Scripts\aqora.exe pair 1ightray/sg-grand-challenge-evecount-q-rotate-efficient-molecular-pattern-matching</code></pre>
            </div>
          </div>

          <!-- Foundation Built by Gwen -->
          <div style="background: rgba(0, 245, 212, 0.08); border: 1px solid rgba(0, 245, 212, 0.25); border-radius: 12px; padding: 18px 20px; margin-bottom: 20px;">
            <div style="font-size: 0.8rem; font-weight: 800; color: var(--accent-cyan); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px;">️ Prototype Foundation Built by Gwen</div>
            <ul style="margin: 0; padding-left: 20px; font-size: 0.9rem; color: #e2e8f0; line-height: 1.7;">
              <li><strong>Mathematical Formulation</strong> of $\hat{U}_{\text{tube}}(\tau) = \exp(-i \tau (\hat{H}_{\text{rot}} + \hat{H}_{\text{phase}}))$ and Lie algebra generators.</li>
              <li><strong>Classical-to-Quantum HPC Bridge</strong> (<code>src/qrotate/hpc_bridge.py</code>) for spherical coordinate-to-phase mapping.</li>
              <li><strong>Blind Parity SWAP Test</strong> in Pytket with native Quantinuum H2 gates (<code>PhasedX</code>, <code>ZZPhase</code>, virtual <code>Rz</code>).</li>
              <li><strong>Repeat-Until-Success (RUS) Dynamic Loop</strong> compiled to HUGR dataflow graph and LLVM QIR bitcode (3.6 KB).</li>
            </ul>
          </div>

          <!-- Interactive Action Items -->
          <h4 style="color: var(--accent-cyan); font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px;"> Gwen's Next Action Items</h4>
          <div class="task-checklist">
            <label class="task-item" data-task-id="gwen_aqora_login">
              <input type="checkbox" />
              <div>
                <strong>Connect local CLI to Aqora platform</strong> (<code>aqora login</code>) to link with team workspace <code>1ightray/sg-grand-challenge-evecount</code>.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Sept 18, 2026 • Prerequisite for cloud submissions</div>
              </div>
            </label>
            <label class="task-item" data-task-id="gwen_h2_emulator">
              <input type="checkbox" />
              <div>
                <strong>Execute test benchmarks against Quantinuum <code>nexus:H2-2E</code> emulator</strong> using the 6 curated molecular test cases.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Sept 22, 2026 • Capture run logs and verify zero SWAP overhead</div>
              </div>
            </label>
            <label class="task-item" data-task-id="gwen_hqc_records">
              <input type="checkbox" />
              <div>
                <strong>Record HQC credit usage and latency telemetry</strong> to quantify runtime advantage over classical brute-force docking.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Sept 26, 2026 • Needed for Submission 1 documentation</div>
              </div>
            </label>
            <label class="task-item" data-task-id="gwen_preprint_draft">
              <input type="checkbox" />
              <div>
                <strong>Draft preprint section comparing RUS convergence against standard VQE</strong> for excited-state biomolecules.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Oct 5, 2026 • Formulates the scientific paper companion</div>
              </div>
            </label>
          </div>
        </div>

        <!-- PANEL: BEN -->
        <div id="panel-ben" class="role-panel">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
            <div>
              <h3 style="font-size: 1.4rem; font-weight: 800; color: #fff; margin-bottom: 4px;"> Benjamin Lim — Frontend & Systems Architect</h3>
              <p style="color: var(--text-muted); font-size: 0.9rem;">Frontend Systems Lead • <a href="mailto:ben@evecount.com" style="color: var(--accent-cyan);">ben@evecount.com</a></p>
            </div>
            <span style="font-size: 0.78rem; font-weight: 700; color: #f59e0b; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.3); padding: 4px 12px; border-radius: 16px; text-transform: uppercase;">
              Active Branch: ben/frontend-systems
            </span>
          </div>

          <!-- Official Competition Document Viewer Callout (for Ben) -->
          <div style="background: rgba(12, 18, 34, 0.9); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 18px 22px; margin-bottom: 22px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.5);">
            <div>
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span style="font-size: 1.2rem;"></span>
                <strong style="color: #fff; font-size: 1.05rem;">Official Challenge Brief: <code>Competition.md</code></strong>
              </div>
              <p style="color: #cbd5e1; font-size: 0.86rem; margin: 0; line-height: 1.5;">
                Check the engineering & reproducibility criteria (20%), technical performance rubric (30%), and hardware access windows directly in the portal.
              </p>
            </div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
              <button class="btn-open-comp-modal-trigger btn-primary" style="font-size: 0.85rem; padding: 9px 18px; cursor: pointer; border: none; background: #00f5d4; color: #01040c; font-weight: 700;">
                <span> Read Challenge Document</span>
              </button>
              <a href="competition.html" target="_blank" class="btn-secondary" style="font-size: 0.85rem; padding: 9px 14px;">
                <span>Open in New Tab ↗</span>
              </a>
            </div>
          </div>

          
          <!-- Architecture Guide for Ben: Why Gwen's Idea is Visually & Architecturally Unique -->
          <div style="background: rgba(12, 18, 34, 0.9); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 22px; margin-bottom: 22px; box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; border-bottom: 1px solid rgba(245, 158, 11, 0.2); padding-bottom: 10px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.3rem;"></span>
                <div>
                  <h4 style="color: #fff; font-size: 1.1rem; margin: 0; font-weight: 800;">Ben's Guide: How Gwen's Algorithm Dictates the 3D Frontend</h4>
                  <div style="font-size: 0.78rem; color: #f59e0b; font-weight: 600;">The scientific uniqueness behind Q-Rotate and how to visually showcase it in Three.js</div>
                </div>
              </div>
              <span style="font-size: 0.72rem; font-family: var(--font-mono); color: var(--accent-cyan); background: rgba(0, 245, 212, 0.1); border: 1px solid rgba(0, 245, 212, 0.25); padding: 3px 10px; border-radius: 12px;">
                Continuous SO(3) vs Discrete Grid
              </span>
            </div>

            <p style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.6; margin-bottom: 16px;">
              Ben, traditional docking software (AutoDock, PyMOL) tests molecular fit by <em>stepping</em> a molecule in clumsy discrete 3D slices ($x, y, z, 	heta$). 
              <strong>Gwen’s genius is replacing discrete trial-and-error with a continuous Quantum Hamiltonian Tube ($\hat{H}_{	ext{tube}} = \hat{H}_{	ext{rot}} + \hat{H}_{	ext{phase}}$).</strong> 
              Instead of checking one angle at a time, the quantum computer evaluates <em>all spatial orientations simultaneously in a single wave superposition</em>. Here is how that translates into your frontend designs:
            </p>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-bottom: 16px;">
              <div style="background: rgba(10, 15, 29, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
                <div style="font-size: 0.76rem; font-weight: 800; color: #f59e0b; text-transform: uppercase; margin-bottom: 4px;">1. Don't Draw Clunky Dots, Draw Wave Shells</div>
                <div style="font-size: 0.84rem; color: #94a3b8; line-height: 1.5;">
                  In Three.js, render the binding target not just as static rigid atoms, but with an iridescent, translucent <strong>probability tube</strong>. This visually communicates continuous Lie algebra coverage rather than a static crystal lattice.
                </div>
              </div>

              <div style="background: rgba(10, 15, 29, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
                <div style="font-size: 0.76rem; font-weight: 800; color: var(--accent-cyan); text-transform: uppercase; margin-bottom: 4px;">2. WASD Tunes Lie Algebra Generators</div>
                <div style="font-size: 0.84rem; color: #94a3b8; line-height: 1.5;">
                  The interactive trapped-ion continuous rotation controls are not just a video game gimmick—they represent interactive tuning of the $L_x, L_y, L_z$ angular momentum generators in real-time, letting judges feel the quantum phase synchronization.
                </div>
              </div>

              <div style="background: rgba(10, 15, 29, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 14px;">
                <div style="font-size: 0.76rem; font-weight: 800; color: #10b981; text-transform: uppercase; margin-bottom: 4px;">3. The Single Spectator Qubit Readout</div>
                <div style="font-size: 0.84rem; color: #94a3b8; line-height: 1.5;">
                  When testing overlap, animate a single interference beam: constructive interference (Green laser pulse = 100% lock match) or destructive (Red dispersion). This visualizes the <strong>O(1) Blind Parity Test</strong> that protects chemical IP.
                </div>
              </div>
            </div>
          </div>

          <!-- Status & Handover Note -->
          <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 12px; padding: 18px 20px; margin-bottom: 20px;">
            <div style="font-size: 0.8rem; font-weight: 800; color: #f59e0b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;"> Project Status & Handover Note for Ben</div>
            <p style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.6; margin: 0 0 10px;">
              Gwen built the foundational v1.0 prototype—including the initial Three.js 3D Constellation, the interactive Lie-algebra gate alignment controls, and KaTeX math rendering—to provide a working demonstration. 
              <strong>Ben is now assigned to take ownership of the frontend codebase on his dedicated branch to refine, optimize, and build out production systems.</strong>
            </p>
            <div style="font-size: 0.82rem; color: #94a3b8;">
              Branch created on GitHub: <a href="https://github.com/evecount/quantum_rotation/tree/ben/frontend-systems" target="_blank" style="color: var(--accent-cyan); font-family: var(--font-mono);">ben/frontend-systems</a>
            </div>
          </div>

          <!-- Live Git Branch Tracker -->
          <div style="background: rgba(10, 15, 30, 0.85); border: 1px solid rgba(0, 245, 212, 0.3); border-radius: 14px; padding: 20px 22px; margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.1rem;"></span>
                <span style="font-size: 0.95rem; font-weight: 700; color: #fff;">Live Branch Activity: <code style="color: var(--accent-cyan);">ben/frontend-systems</code></span>
              </div>
              <button id="btn-refresh-ben-branch" class="btn-secondary" style="font-size: 0.75rem; padding: 5px 12px; cursor: pointer;">
                <span> Check Branch Pushes</span>
              </button>
            </div>
            
            <div id="ben-branch-activity" style="background: rgba(6, 10, 20, 0.9); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 10px; padding: 12px 16px; margin-bottom: 14px; font-size: 0.88rem;">
              <span style="color: var(--text-muted);">Fetching latest commit on <code>ben/frontend-systems</code>...</span>
            </div>

            <!-- Quick Git instructions for Ben -->
            <div style="background: rgba(15, 23, 42, 0.7); border-radius: 10px; padding: 12px 16px; font-family: var(--font-mono); font-size: 0.8rem; color: #94a3b8; line-height: 1.7;">
              <div style="color: var(--accent-cyan); font-weight: 700; margin-bottom: 4px;"># Ben's Quick Git Setup:</div>
              <div>git fetch origin</div>
              <div>git checkout ben/frontend-systems</div>
              <div style="color: #64748b;"># work on frontend, then push:</div>
              <div>git add .</div>
              <div>git commit -m "feat(ui): your update description"</div>
              <div>git push origin ben/frontend-systems</div>
            </div>

            <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-top: 14px;">
              <a href="https://github.com/evecount/quantum_rotation/tree/ben/frontend-systems" target="_blank" class="btn-secondary" style="font-size: 0.8rem; padding: 6px 14px;">
                <span> View Branch on GitHub →</span>
              </a>
              <a href="https://github.com/evecount/quantum_rotation/compare/main...ben/frontend-systems?expand=1" target="_blank" class="btn-secondary" style="font-size: 0.8rem; padding: 6px 14px; border-color: rgba(0, 245, 212, 0.4); color: var(--accent-cyan);">
                <span> Open Pull Request to Main →</span>
              </a>
            </div>
          </div>

          <!-- Assigned Scope of Work Checklist -->
          <h4 style="color: var(--accent-cyan); font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px;"> Ben's Assigned Scope of Work & Action Items</h4>
          <div class="task-checklist">
            <label class="task-item" data-task-id="ben_clone_branch">
              <input type="checkbox" />
              <div>
                <strong>Check out and verify branch <code>ben/frontend-systems</code> locally</strong> (<code>git checkout ben/frontend-systems</code>).
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Sept 18, 2026 • Confirm local environment and build setup</div>
              </div>
            </label>
            <label class="task-item" data-task-id="ben_mobile_safari">
              <input type="checkbox" />
              <div>
                <strong>Optimize WebGL 3D Constellation & audio performance across Safari & mobile touch devices</strong> to ensure silky smooth 60fps.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Sept 22, 2026 • Mobile responsive polish & touch controls</div>
              </div>
            </label>
            <label class="task-item" data-task-id="ben_marimo_embed">
              <input type="checkbox" />
              <div>
                <strong>Embed live Marimo telemetry curves into the workbook portal</strong> so judges can observe real-time fidelity graphs.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Sept 26, 2026 • Interactive submission dashboard widgets</div>
              </div>
            </label>
            <label class="task-item" data-task-id="ben_video_export">
              <input type="checkbox" />
              <div>
                <strong>Add an instant screen capture & video recording button</strong> to the 3D Constellation for generating demo video clips.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Oct 2, 2026 • Demo video asset production for Submission 1</div>
              </div>
            </label>
            <label class="task-item" data-task-id="ben_pitch_displays">
              <input type="checkbox" />
              <div>
                <strong>Format high-resolution presentation layout</strong> optimized for 4K stage displays at the Singapore Grand Finals.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Oct 8, 2026 • Stage-ready visual assets</div>
              </div>
            </label>
          </div>
        </div>

        <!-- PANEL: JAMES -->
        <div id="panel-james" class="role-panel">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
            <div>
              <h3 style="font-size: 1.4rem; font-weight: 800; color: #fff; margin-bottom: 4px;"> James Sun — Venture Advisor & GTM Strategist</h3>
              <p style="color: var(--text-muted); font-size: 0.9rem;">Venture Advisor & GTM Strategist • <a href="mailto:james@mambapartners.com" style="color: var(--accent-cyan);">james@mambapartners.com</a></p>
            </div>
            <span data-james-badge style="font-size: 0.78rem; font-weight: 700; color: #c084fc; background: rgba(168, 85, 247, 0.12); border: 1px solid rgba(168, 85, 247, 0.3); padding: 4px 12px; border-radius: 16px; text-transform: uppercase;">
              Scope of Work (Under Review)
            </span>
          </div>

          <!-- Official Competition Document Viewer Callout -->
          <div style="background: rgba(12, 18, 34, 0.9); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 18px 22px; margin-bottom: 22px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.5);">
            <div>
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span style="font-size: 1.2rem;"></span>
                <strong style="color: #fff; font-size: 1.05rem;">Official Challenge Brief: <code>Competition.md</code></strong>
              </div>
              <p style="color: #cbd5e1; font-size: 0.86rem; margin: 0; line-height: 1.5;">
                Review the official problem statements, judging criteria (<strong>30% Problem & Value</strong>), mentor list, and event roadmap directly in the portal.
              </p>
            </div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
              <button id="btn-open-comp-modal" class="btn-primary" style="font-size: 0.85rem; padding: 9px 18px; cursor: pointer; border: none; background: #00f5d4; color: #01040c; font-weight: 700;">
                <span> Read Challenge Document</span>
              </button>
              <a href="competition.html" target="_blank" class="btn-secondary" style="font-size: 0.85rem; padding: 9px 14px;">
                <span>Open in New Tab ↗</span>
              </a>
            </div>
          </div>

          <!-- THE "WHY WE WIN" ELEVATOR PITCH FOR JAMES -->
          <div style="background: rgba(12, 18, 34, 0.92); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 18px; padding: 26px 28px; margin-bottom: 24px; box-shadow: 0 12px 30px -6px rgba(0, 0, 0, 0.65);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; border-bottom: 1px solid rgba(168, 85, 247, 0.25); padding-bottom: 12px;">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.5rem;"></span>
                <div>
                  <h3 style="color: #fff; font-size: 1.25rem; font-weight: 800; margin: 0;">James's "Why We Win" Elevator Pitch</h3>
                  <div style="font-size: 0.78rem; color: #c084fc; font-weight: 600;">What we are making, why it is genius, and why judges will score us #1</div>
                </div>
              </div>
              <button id="btn-copy-pitch" class="btn-secondary" style="font-size: 0.8rem; padding: 7px 16px; cursor: pointer; border-color: rgba(168, 85, 247, 0.4); color: #c084fc; background: rgba(168, 85, 247, 0.1);">
                <span> Copy 30-Sec Pitch</span>
              </button>
            </div>

            <!-- 30-Sec Spoken Pitch -->
            <div style="background: rgba(6, 10, 20, 0.88); border-left: 3px solid #c084fc; border-radius: 8px; padding: 14px 18px; margin-bottom: 18px;">
              <div style="font-size: 0.75rem; font-weight: 800; color: #c084fc; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">️ The 30-Second Spoken Pitch (Say this to judges & biopharma leads):</div>
              <p id="pitch-text" style="font-size: 0.93rem; color: #f1f5f9; line-height: 1.6; font-style: italic; margin: 0;">
                "Today, testing if a drug fits a disease protein requires supercomputers running for months on massive 3D grids—and if two pharma companies collaborate, someone risks leaking multi-million dollar chemical IP. 
                <strong>Project Q-Rotate replaces spatial geometry with quantum wave information.</strong> We map the lock and key into wave states, apply a single dimensional rotation step, and ask a single spectator qubit: <em>'Did it lock, yes or no?'</em> 
                It gives an <strong>instant O(1) readout without ever revealing the underlying 3D coordinates</strong>. That is the holy grail for confidential drug discovery, and it only runs natively on Quantinuum’s trapped ions."
              </p>
            </div>

            <!-- The 4 Core Winning Pillars -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px;">
              <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 10px; padding: 14px 16px;">
                <div style="font-size: 0.78rem; font-weight: 800; color: var(--accent-cyan); text-transform: uppercase; margin-bottom: 4px;">1. Technical Unfair Advantage</div>
                <p style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5; margin: 0;">
                  Other teams run static VQE circuits. We built a <strong>Repeat-Until-Success (RUS) dynamic loop</strong> in Guppy. It exploits Quantinuum's 10-second ion coherence times to do mid-circuit measurement and optical reset with zero network latency.
                </p>
              </div>

              <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 10px; padding: 14px 16px;">
                <div style="font-size: 0.78rem; font-weight: 800; color: #f59e0b; text-transform: uppercase; margin-bottom: 4px;">2. Commercial Unfair Advantage (30% Score)</div>
                <p style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5; margin: 0;">
                  30% of the score is <em>Problem & Business Value</em>. Our Blind Parity Test functions as a <strong>Zero-Knowledge Proof</strong> for pharmaceutical licensing—allowing biopharma giants to screen proprietary candidate drugs without IP exposure.
                </p>
              </div>

              <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 10px; padding: 14px 16px;">
                <div style="font-size: 0.78rem; font-weight: 800; color: #a855f7; text-transform: uppercase; margin-bottom: 4px;">3. Direct Judge & Mentor Alignment</div>
                <p style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5; margin: 0;">
                  Our architecture is built on the research of lead mentor <strong>Kentaro Yamamoto</strong> (Principal R&D Scientist at Quantinuum). We are directly demonstrating the hybrid Fugaku-Quantinuum supercomputing vision he pioneered.
                </p>
              </div>

              <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 10px; padding: 14px 16px;">
                <div style="font-size: 0.78rem; font-weight: 800; color: #10b981; text-transform: uppercase; margin-bottom: 4px;">4. Stage-Ready UI & 3D Gamification</div>
                <p style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5; margin: 0;">
                  While other teams present dry terminal outputs, we have an interactive 3D WebGL Constellation with 3,500 particles, live audio synthesizer, and WASD gate matching ready for 4K stage displays in Singapore.
                </p>
              </div>
            </div>
          </div>

          
          <!-- The Unfair Advantage Matrix for James -->
          <div style="background: rgba(12, 18, 34, 0.9); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 22px; margin-bottom: 22px; box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; border-bottom: 1px solid rgba(168, 85, 247, 0.2); padding-bottom: 10px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.3rem;"></span>
                <div>
                  <h4 style="color: #fff; font-size: 1.1rem; margin: 0; font-weight: 800;">James's Unfair Advantage Matrix: Why Gwen's Breakthrough Beats All Rivals</h4>
                  <div style="font-size: 0.78rem; color: #c084fc; font-weight: 600;">The defensive IP moats and competitive differentiation to cite in decks and judge interviews</div>
                </div>
              </div>
              <span style="font-size: 0.72rem; font-family: var(--font-mono); color: #c084fc; background: rgba(168, 85, 247, 0.15); border: 1px solid rgba(168, 85, 247, 0.3); padding: 3px 10px; border-radius: 12px;">
                Aligned to 30% Problem & Value
              </span>
            </div>

            <p style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.6; margin-bottom: 16px;">
              James, when judges or biopharma venture partners ask <em>"Why can't classical supercomputers or other quantum teams just do this?"</em>, here is the exact 3-way technological moat:
            </p>

            <div style="overflow-x: auto; margin-bottom: 16px;">
              <table style="width: 100%; border-collapse: collapse; font-size: 0.84rem; text-align: left;">
                <thead>
                  <tr style="background: rgba(15, 23, 42, 0.9); border-bottom: 2px solid rgba(168, 85, 247, 0.3);">
                    <th style="padding: 10px 12px; color: #94a3b8; font-weight: 700;">Challenge Dimension</th>
                    <th style="padding: 10px 12px; color: #ef4444; font-weight: 700;">1. Classical HPC (Schrödinger / AutoDock)</th>
                    <th style="padding: 10px 12px; color: #f59e0b; font-weight: 700;">2. Rival Quantum Teams (VQE / QUBO on IBM)</th>
                    <th style="padding: 10px 12px; color: var(--accent-cyan); font-weight: 800; background: rgba(0, 245, 212, 0.08);">3. Gwen's Q-Rotate Engine (Quantinuum H2)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.06);">
                    <td style="padding: 10px 12px; font-weight: 600; color: #fff;">Search Space Physics</td>
                    <td style="padding: 10px 12px; color: #94a3b8;">Clumsy discrete spatial grids; tests millions of angles one by one ($\mathcal{O}(N^3)$).</td>
                    <td style="padding: 10px 12px; color: #94a3b8;">Discretizes continuous rotations into binary decisions; causes combinatorial qubit explosion.</td>
                    <td style="padding: 10px 12px; color: #e2e8f0; background: rgba(0, 245, 212, 0.04);"><strong>Continuous Lie Algebra Superposition:</strong> Explores all rotational orientations simultaneously in wave space.</td>
                  </tr>
                  <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.06);">
                    <td style="padding: 10px 12px; font-weight: 600; color: #fff;">Convergence / Optimization</td>
                    <td style="padding: 10px 12px; color: #94a3b8;">Trapped in local energy minima; requires hours to days of Monte Carlo compute per molecule.</td>
                    <td style="padding: 10px 12px; color: #94a3b8;"><strong>Barren Plateaus:</strong> Variational gradients vanish exponentially in NISQ noise; optimizer gets lost.</td>
                    <td style="padding: 10px 12px; color: #e2e8f0; background: rgba(0, 245, 212, 0.04);"><strong>Repeat-Until-Success (RUS):</strong> Mid-circuit measurement snaps state directly into target eigenstate without gradient descent!</td>
                  </tr>
                  <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.06);">
                    <td style="padding: 10px 12px; font-weight: 600; color: #fff;">Hardware Gate Overhead</td>
                    <td style="padding: 10px 12px; color: #94a3b8;">High GPU/CPU cloud cluster power bills ($10M+/yr at major pharma).</td>
                    <td style="padding: 10px 12px; color: #94a3b8;"><strong>70–80% SWAP Overhead</strong> on 2D nearest-neighbor superconducting grids (IBM/Google) destroys advantage.</td>
                    <td style="padding: 10px 12px; color: #e2e8f0; background: rgba(0, 245, 212, 0.04);"><strong>Zero SWAP Overhead:</strong> Quantinuum's trapped-ion QCCD all-to-all connectivity directly maps 3D atomic interactions.</td>
                  </tr>
                  <tr>
                    <td style="padding: 10px 12px; font-weight: 600; color: #fff;">IP Privacy & Commercial Value</td>
                    <td style="padding: 10px 12px; color: #94a3b8;">Zero IP privacy: Both parties must disclose full 3D atomic coordinates to run simulation.</td>
                    <td style="padding: 10px 12px; color: #94a3b8;">Full coordinates encoded in public Hamiltonian; easily reverse-engineered.</td>
                    <td style="padding: 10px 12px; color: #e2e8f0; background: rgba(0, 245, 212, 0.04);"><strong>Zero-Knowledge Molecular Proof:</strong> Blind Parity readout confirms binding fit with a single qubit without disclosing chemical structures!</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Status & Scope Note -->
          <div style="background: rgba(168, 85, 247, 0.08); border: 1px solid rgba(168, 85, 247, 0.25); border-radius: 12px; padding: 18px 20px; margin-bottom: 20px;">
            <div style="font-size: 0.8rem; font-weight: 800; color: #c084fc; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;"> Venture & GTM Status Note for James</div>
            <p style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.6; margin: 0;">
              The foundational commercial thesis—framing the $O(1)$ Blind Parity Test as a Zero-Knowledge Proof for confidential pharmaceutical IP licensing—was drafted as part of the technical prototype. 
              <strong>James is now assigned to review and elevate the commercial narrative, engage his biopharma network for prospective pilot syndicates, and structure the venture pitch for the Grand Finals.</strong>
            </p>
          </div>

          <!-- Assigned Scope of Work Checklist -->
          <h4 style="color: var(--accent-cyan); font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px;"> James's Assigned Scope of Work & Action Items</h4>
          <div class="task-checklist">
            <label class="task-item" data-task-id="james_review_deck">
              <input type="checkbox" />
              <div>
                <strong>Review Project Q-Rotate executive summary and pitch narrative</strong> across the live portal and interactive workbook.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Sept 22, 2026 • Provide strategic feedback on positioning</div>
              </div>
            </label>
            <label class="task-item" data-task-id="james_biopharma_syndicate">
              <input type="checkbox" />
              <div>
                <strong>Engage global & Singapore-based biopharma innovation leads</strong> for exploratory pilot partnership letters of intent (LOIs).
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Oct 1, 2026 • Commercial validation to present at Grand Finals</div>
              </div>
            </label>
            <label class="task-item" data-task-id="james_finals_pitch">
              <input type="checkbox" />
              <div>
                <strong>Structure the venture pitch framework</strong> for the live judging panel and venture syndicates at the Nov 19 Grand Finals in Singapore.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Oct 10, 2026 • Compete for grand prize & follow-on capital</div>
              </div>
            </label>
            <label class="task-item" data-task-id="james_portal_gtm">
              <input type="checkbox" />
              <div>
                <strong>Provide GTM feedback on interactive gamified portal</strong> to maximize virality and engagement across the quantum and biotech community.
                <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">Target: Oct 14, 2026 • Final polish ahead of Submission 1</div>
              </div>
            </label>
          </div>

          <!-- James's Interactive No-Code Venture Workbook -->
          <div class="james-workbook">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; border-bottom: 1px solid rgba(168, 85, 247, 0.25); padding-bottom: 14px;">
              <div>
                <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(168, 85, 247, 0.15); border: 1px solid rgba(168, 85, 247, 0.3); color: #c084fc; font-size: 0.75rem; font-weight: 800; padding: 3px 10px; border-radius: 12px; text-transform: uppercase; margin-bottom: 6px;">
                  <span> Zero Git / Terminal Required</span>
                </div>
                <h3 style="color: #fff; font-size: 1.25rem; font-weight: 800; margin: 0;"> James's Venture & GTM Fill-In Workbook</h3>
              </div>
              <div id="james-save-status" style="font-size: 0.78rem; color: #10b981; font-weight: 600;">
                 All entries auto-saved
              </div>
            </div>

            <p style="font-size: 0.86rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 20px;">
              James, you don't need to touch GitHub or use a terminal. Fill in your strategy notes directly into the 5 prompts below (aligned with the competition's <strong>30% Problem & Value</strong> judging criteria). Everything you write auto-saves instantly to your browser. When you're ready, click <strong>Copy Brief</strong> or <strong>Email to Gwen</strong> with one click!
            </p>

            <!-- Box 1 -->
            <div class="james-input-group">
              <label class="james-label" for="james-box-pitch">1. Executive Positioning & 2-Sentence Investor Hook</label>
              <div class="james-sublabel">How should we pitch Project Q-Rotate in 30 seconds to sovereign wealth judges (SGInnovate/CQT) and biopharma venture scouts?</div>
              <textarea id="james-box-pitch" class="james-textarea" placeholder="e.g. Project Q-Rotate introduces the first zero-knowledge molecular pattern matching engine on trapped-ion quantum hardware, replacing months of supercomputer spatial docking with instant O(1) quantum parity readout without exposing proprietary chemical IP..."></textarea>
            </div>

            <!-- Box 2 -->
            <div class="james-input-group">
              <label class="james-label" for="james-box-customers">2. Target Customers & Ideal Customer Profile (ICP)</label>
              <div class="james-sublabel">Who are the high-value commercial customers who will pay for this technology?</div>
              <textarea id="james-box-customers" class="james-textarea" placeholder="e.g. Tier-1 global biopharma (Novartis, Pfizer, Roche), AI-driven drug discovery biotechs (Recursion, Relay Therapeutics), and contract research organizations (CROs)..."></textarea>
            </div>

            <!-- Box 3 -->
            <div class="james-input-group">
              <label class="james-label" for="james-box-roi">3. Commercial ROI & Quantified Business Value (30% of Judging Score!)</label>
              <div class="james-sublabel">What is the quantified savings in compute cost, screening time, or IP protection?</div>
              <textarea id="james-box-roi" class="james-textarea" placeholder="e.g. Cuts initial virtual hit-screening compute costs from $250k on classical GPU clusters down to minutes of QPU time; eliminates multi-million dollar chemical IP leakage risks through blind zero-knowledge verification..."></textarea>
            </div>

            <!-- Box 4 -->
            <div class="james-input-group">
              <label class="james-label" for="james-box-partners">4. Prospective Biopharma Partners & Pilot Syndicates</label>
              <div class="james-sublabel">Which enterprise contacts or venture syndicates in your network can we approach for an exploratory pilot or Letter of Intent (LOI)?</div>
              <textarea id="james-box-partners" class="james-textarea" placeholder="e.g. Reaching out to biopharma venture scouts in Singapore, SGInnovate deeptech EIRs, and healthtech venture funds to test appetite for exploratory zero-knowledge docking pilot..."></textarea>
            </div>

            <!-- Box 5 -->
            <div class="james-input-group">
              <label class="james-label" for="james-box-finals">5. Singapore Grand Finals Presentation Notes (November 19)</label>
              <div class="james-sublabel">What are the essential slide narrative beats or judge objection handlers we must nail on stage?</div>
              <textarea id="james-box-finals" class="james-textarea" placeholder="e.g. Slide 1: The $50B docking bottleneck. Slide 2: Trapped-ion rotation breakthrough. Slide 3: Live 3D resonance demo. Slide 4: Zero-knowledge pharma licensing business model. Slide 5: The team & commercial roadmap..."></textarea>
            </div>

            <!-- Action Toolbar -->
            <div style="margin-top: 24px; padding-top: 18px; border-top: 1px solid rgba(255, 255, 255, 0.08);">
              <div style="display: flex; gap: 14px; flex-wrap: wrap; align-items: center; justify-content: space-between;">
                <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                  <!-- Main Mailto & Mark Done Button -->
                  <button id="btn-james-send-done" class="btn-primary" style="font-size: 0.92rem; padding: 12px 22px; cursor: pointer; border: none; background: #00f5d4; color: #01040c; font-weight: 700; box-shadow: 0 4px 14px rgba(0, 245, 212, 0.25);">
                    <span>Send to Gwen (gwen@evecount.com) & Complete</span>
                  </button>
                  <button id="btn-james-copy" class="btn-secondary" style="font-size: 0.85rem; padding: 10px 16px; cursor: pointer; border-color: rgba(168, 85, 247, 0.4); color: #c084fc;">
                    <span> Copy Text</span>
                  </button>
                  <button id="btn-james-download" class="btn-secondary" style="font-size: 0.85rem; padding: 10px 16px; cursor: pointer;">
                    <span> Download .md</span>
                  </button>
                </div>
                <button id="btn-james-clear" style="background: transparent; border: none; color: #64748b; font-size: 0.78rem; cursor: pointer; text-decoration: underline;">
                  Clear Form
                </button>
              </div>

              <!-- Instant Confirmation Banner -->
              <div id="james-done-banner" style="display: none; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 12px; padding: 16px 20px; margin-top: 16px; animation: fadeIn 0.3s ease;">
                <div style="display: flex; align-items: center; gap: 8px; color: #10b981; font-weight: 800; font-size: 0.95rem; margin-bottom: 4px;">
                  <span> Awesome work, James!</span>
                </div>
                <p style="color: #cbd5e1; font-size: 0.86rem; margin: 0; line-height: 1.5;">
                  Your strategy brief has been compiled into an email draft for <strong>gwen@evecount.com</strong>, and all of your action items above have been automatically <strong>marked COMPLETE</strong> on your dashboard.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
        <!-- Competition Document Modal Reader -->
    <div id="comp-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(3, 6, 15, 0.88); backdrop-filter: blur(12px); z-index: 9999; padding: 30px 16px; overflow-y: auto;">
      <div style="max-width: 980px; margin: 0 auto; background: rgba(13, 19, 36, 0.98); border: 1px solid rgba(0, 245, 212, 0.35); border-radius: 20px; padding: 36px 40px; box-shadow: 0 0 60px rgba(0, 0, 0, 0.9); position: relative;">
        <!-- Modal Sticky Header -->
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.12); padding-bottom: 16px; margin-bottom: 24px; position: sticky; top: -10px; background: rgba(13, 19, 36, 0.98); padding-top: 10px; z-index: 10;">
          <div>
            <div style="font-size: 0.75rem; color: var(--accent-cyan); font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em;">Official Competition Document • Competition.md</div>
            <h2 style="font-size: 1.4rem; color: #fff; margin: 2px 0 0; font-weight: 800;">Quantinuum Singapore Grand Challenge 2026</h2>
          </div>
          <div style="display: flex; gap: 10px; align-items: center;">
            <a href="competition.html" target="_blank" class="btn-secondary" style="font-size: 0.8rem; padding: 6px 14px;">Open Full Page ↗</a>
            <button id="btn-close-comp-modal" style="background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); color: #ef4444; border-radius: 8px; padding: 6px 14px; font-weight: 700; cursor: pointer; transition: background 0.2s;">Close &times;</button>
          </div>
        </div>
        <!-- Modal Content Container -->
        <div id="comp-modal-content" style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.7;">
          Loading Competition.md...
        </div>
      </div>
    </div>
  </section>
```

## Archived JavaScript (`initWarRoom()`, from `index.html`, lines 2226–2545 prior to removal)

```javascript
    function initWarRoom() {
      const gateEl = document.getElementById('war-room-gate');
      const dashEl = document.getElementById('war-room-dashboard');
      const passInput = document.getElementById('warroom-passcode-input');
      const unlockBtn = document.getElementById('btn-unlock-warroom');
      const lockBtn = document.getElementById('btn-lock-warroom');
      const memberSelect = document.getElementById('warroom-member-select');

      function unlock() {
        if (gateEl && dashEl) {
          gateEl.style.display = 'none';
          dashEl.style.display = 'block';
          localStorage.setItem('evecount_warroom_auth', 'true');
        }
      }

      function lock() {
        if (gateEl && dashEl) {
          gateEl.style.display = 'block';
          dashEl.style.display = 'none';
          localStorage.removeItem('evecount_warroom_auth');
          if (passInput) passInput.value = '';
        }
      }

      // Check existing auth
      if (localStorage.getItem('evecount_warroom_auth') === 'true') {
        unlock();
      }

      function verifyPasscode() {
        const val = (passInput ? passInput.value : '').trim().toLowerCase();
        const validPasscodes = ['evecount2026', 'evecount', '1ightray', 'ben2026', 'james2026'];
        if (validPasscodes.includes(val)) {
          unlock();
        } else {
          alert('Incorrect team passcode. Access restricted to authorized team members.');
        }
      }

      if (unlockBtn) unlockBtn.addEventListener('click', verifyPasscode);
      if (passInput) {
        passInput.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') verifyPasscode();
        });
      }
      if (lockBtn) lockBtn.addEventListener('click', lock);

      // Member Switcher Dropdown
      if (memberSelect) {
        memberSelect.addEventListener('change', (e) => {
          const role = e.target.value;
          document.querySelectorAll('.role-panel').forEach(p => p.classList.remove('active'));
          const targetPanel = document.getElementById(`panel-${role}`);
          if (targetPanel) targetPanel.classList.add('active');
        });
      }

      // Interactive Checklist Persistence
      document.querySelectorAll('.task-item').forEach(item => {
        const taskId = item.dataset.taskId;
        const cb = item.querySelector('input[type="checkbox"]');
        if (!taskId || !cb) return;

        // Restore state
        const savedState = localStorage.getItem(`task_${taskId}`);
        if (savedState === 'done') {
          cb.checked = true;
          item.classList.add('completed');
        }

        // Toggle state
        cb.addEventListener('change', () => {
          if (cb.checked) {
            item.classList.add('completed');
            localStorage.setItem(`task_${taskId}`, 'done');
          } else {
            item.classList.remove('completed');
            localStorage.removeItem(`task_${taskId}`);
          }
        });
      });

      // Real-time GitHub Branch tracker for Ben's branch
      function escapeHtml(str) {
        return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      }

      async function fetchBenBranchActivity() {
        const container = document.getElementById('ben-branch-activity');
        if (!container) return;
        try {
          const res = await fetch('https://api.github.com/repos/evecount/quantum_rotation/commits?sha=ben/frontend-systems&per_page=1');
          if (!res.ok) throw new Error('API status ' + res.status);
          const commits = await res.json();
          if (commits && commits.length > 0) {
            const c = commits[0];
            const sha = c.sha.substring(0, 7);
            const rawMsg = c.commit.message.split('\n')[0];
            const author = c.commit.author ? c.commit.author.name : 'Unknown';
            const date = c.commit.author ? new Date(c.commit.author.date).toLocaleString() : '';
            const commitUrl = c.html_url || `https://github.com/evecount/quantum_rotation/commit/${c.sha}`;
            container.innerHTML = `
              <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                  <span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#10b981; margin-right:6px; box-shadow:0 0 8px #10b981;"></span>
                  <strong style="color:#fff;">Latest Push on <code>ben/frontend-systems</code>:</strong> 
                  <a href="${commitUrl}" target="_blank" style="color:var(--accent-cyan); font-family:var(--font-mono); text-decoration:none; font-weight:700;">${sha}</a> 
                  <span style="color:#cbd5e1;">- ${escapeHtml(rawMsg)}</span>
                </div>
                <div style="font-size:0.78rem; color:var(--text-muted);">
                  By <strong style="color:#e2e8f0;">${escapeHtml(author)}</strong> • ${date}
                </div>
              </div>
            `;
          } else {
            container.innerHTML = `<span style="color:var(--text-muted); font-size:0.82rem;">Branch active: <code style="color:var(--accent-cyan);">ben/frontend-systems</code> • Waiting for first commit</span>`;
          }
        } catch (err) {
          container.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <span> Branch active: <code style="color:var(--accent-cyan);">ben/frontend-systems</code></span>
            <a href="https://github.com/evecount/quantum_rotation/tree/ben/frontend-systems" target="_blank" style="color:var(--accent-cyan); font-size:0.8rem;">View commits on GitHub →</a>
          </div>`;
        }
      }

      fetchBenBranchActivity();
      const refreshBenBtn = document.getElementById('btn-refresh-ben-branch');
      if (refreshBenBtn) {
        refreshBenBtn.addEventListener('click', () => {
          const container = document.getElementById('ben-branch-activity');
          if (container) container.innerHTML = '<span style="color:var(--text-muted); font-size:0.82rem;">Checking GitHub for new branch pushes...</span>';
          fetchBenBranchActivity();
        });
      }

      // =======================================================================
      // James's Interactive Workbook Auto-Save & Export Logic
      // =======================================================================
      const jamesFields = [
        { id: 'james-box-pitch', title: '1. Executive Positioning & 2-Sentence Hook' },
        { id: 'james-box-customers', title: '2. Target Customers & Ideal Customer Profile (ICP)' },
        { id: 'james-box-roi', title: '3. Commercial ROI & Quantified Value (30% Score)' },
        { id: 'james-box-partners', title: '4. Prospective Partners & Pilot Syndicates' },
        { id: 'james-box-finals', title: '5. Singapore Grand Finals Presentation Notes' }
      ];

      const saveStatusEl = document.getElementById('james-save-status');

      function getJamesBriefMarkdown() {
        let md = '# Project Q-Rotate: Venture & GTM Strategy Brief\n\n';
        md += `**Author:** James Sun (Venture Advisor & GTM Strategist)\n`;
        md += `**Email:** james@mambapartners.com\n`;
        md += `**Timestamp:** ${new Date().toLocaleString()}\n\n---\n\n`;
        jamesFields.forEach(f => {
          const el = document.getElementById(f.id);
          const val = el ? el.value.trim() : '';
          md += `### ${f.title}\n\n${val || '_No input provided yet._'}\n\n`;
        });
        return md;
      }

      // Restore saved answers from localStorage
      jamesFields.forEach(f => {
        const el = document.getElementById(f.id);
        if (!el) return;
        const saved = localStorage.getItem(f.id);
        if (saved) el.value = saved;

        el.addEventListener('input', () => {
          localStorage.setItem(f.id, el.value);
          if (saveStatusEl) {
            saveStatusEl.textContent = ' Auto-saved to browser';
            saveStatusEl.style.color = '#10b981';
          }
        });
      });

      // Send Email to Gwen & Mark All James's Tasks Complete
      function markJamesTasksComplete() {
        const jamesItems = document.querySelectorAll('#panel-james .task-item');
        jamesItems.forEach(item => {
          const cb = item.querySelector('input[type="checkbox"]');
          const taskId = item.dataset.taskId;
          if (cb) cb.checked = true;
          item.classList.add('completed');
          if (taskId) localStorage.setItem(`task_${taskId}`, 'done');
        });

        // Update badge
        const badge = document.querySelector('#panel-james [data-james-badge]');
        if (badge) {
          badge.textContent = 'Strategy Brief Submitted to Gwen!';
          badge.style.background = 'rgba(16, 185, 129, 0.15)';
          badge.style.borderColor = 'rgba(16, 185, 129, 0.4)';
          badge.style.color = '#10b981';
        }

        // Show confirmation banner
        const banner = document.getElementById('james-done-banner');
        if (banner) banner.style.display = 'block';
      }

      const sendDoneBtn = document.getElementById('btn-james-send-done');
      if (sendDoneBtn) {
        sendDoneBtn.addEventListener('click', () => {
          const text = getJamesBriefMarkdown();
          const subject = encodeURIComponent('Project Q-Rotate: GTM Strategy Brief from James Sun');
          const body = encodeURIComponent(text);
          
          // 1. Mark tasks complete in dashboard & persist to localStorage
          markJamesTasksComplete();

          // 2. Open mailto to Gwen
          window.location.href = `mailto:gwen@evecount.com?subject=${subject}&body=${body}`;
        });
      }

      // Copy Brief
      const copyBtn = document.getElementById('btn-james-copy');
      if (copyBtn) {
        copyBtn.addEventListener('click', () => {
          const text = getJamesBriefMarkdown();
          navigator.clipboard.writeText(text).then(() => {
            alert('Full Venture & GTM Brief copied to your clipboard!');
          }).catch(() => {
            alert('Could not copy automatically. Use the "Send to Gwen" button.');
          });
        });
      }

      // Download Brief
      const downloadBtn = document.getElementById('btn-james-download');
      if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
          const text = getJamesBriefMarkdown();
          const blob = new Blob([text], { type: 'text/markdown' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'qrotate_gtm_brief_james.md';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        });
      }

      // Clear Form
      const clearBtn = document.getElementById('btn-james-clear');
      if (clearBtn) {
        clearBtn.addEventListener('click', () => {
          if (confirm('Are you sure you want to clear your workbook entries?')) {
            jamesFields.forEach(f => {
              const el = document.getElementById(f.id);
              if (el) el.value = '';
              localStorage.removeItem(f.id);
            });
            if (saveStatusEl) saveStatusEl.textContent = 'Form cleared';
          }
        });
      }
      // =======================================================================
      // Competition Document Modal Viewer Logic
      // =======================================================================
      const compMarkdown = "Quantinuum Singapore Grand Challenge\nWhy this challenge exists?\nThis track is designed to help participants explore how quantum computing can be applied to meaningful, real-world challenges while also building readiness for the arrival of Helios in Singapore. Over the course of the challenge, teams will move from problem exploration to solution development, using Quantinuum software, tools, resources, and mentor guidance to test ideas, build prototypes, and gain hands-on experience with practical quantum-enabled approaches.\nThe goal is not only to identify strong technical solutions, but also to help participants develop the software familiarity, workflow experience, and applied quantum skills needed to take advantage of next-generation quantum hardware as it becomes available in Singapore. This track is also intended to strengthen collaboration and contribute to a growing quantum innovation ecosystem in Singapore and beyond.\nWho is this track for?\nThis track is open to students, researchers, developers, startups, and innovators who are interested in applying quantum computing to real-world problems. Participants may come from backgrounds such as quantum information, computer science, engineering, chemistry, optimization, AI, finance, logistics, or other applied domains.\nYou do not need to be a quantum expert to participate. Teams with a mix of technical, domain, and product perspectives are encouraged, especially those who are eager to learn, experiment, and build practical solutions with support from mentors and available challenge resources.\nHow to get started?\nReview the challenge details, form a team, choose a problem to tackle, and begin developing your quantum-enabled solution. Participants are encouraged to use available learning resources, mentor sessions, and platform tools throughout the challenge. Final submission requirements and key dates will be shared in the challenge timeline.\nR&D Themes\nQuantum Primitives\nHamiltonian simulation methods to find strongly correlated ground states for physics-based models.\nChemistry\nElectronic structure simulation methods to predict chemical properties in battery development and drug development that frustrate classical computers.\nAI for Quantum\nGenerative AI methods to improve hardware utilization, resource requirements and time/quality to solution.\nQEC\nEnabler for reliable quantum computation by improving (correcting) defects (errors) in quantum compute. This is required firmware for fault-tolerance.\nOptimization\nEnables industries such as finance, logistics, and energy to more efficiently solve complex decision problems, for example portfolio allocation, routing, and scheduling.\nOpen Innovation\nBring your own use case: any industrially relevant challenge where quantum computing could make a difference.\nYour own industry problem\nNovel applications of Quantinuum systems\nCross-disciplinary ideas\nFull challenge briefs and supporting materials are available to registered participants.\nProblem Statements\nConcrete problems teams can tackle within the R&D themes above. Each statement gives the scientific context, the question to answer, and the reference literature to start from.\nX-ray Absorption Spectroscopy\nTheme: Chemistry\nAccurate simulation of X-ray absorption spectra (XAS), particularly transition-metal L\u2082,\u2083-edge spectra, requires modelling strong electron-correlation effects that are difficult for conventional methods such as Density Functional Theory (DFT) and multiple-scattering approaches. Existing classical methods struggle to scale while maintaining chemical accuracy for strongly correlated systems. The challenge is to develop and experimentally demonstrate a quantum-computing workflow capable of computing XAS spectra with manageable resource requirements and robustness to quantum hardware noise.\nChallenge: Can Quantum Phase Estimation (QPE), combined with qubit-efficient circuits and error-detection techniques, accurately reproduce XAS spectra on current trapped-ion quantum hardware?\nReferences:\narxiv.org/html/2505.08612v2\narxiv.org/html/2509.24664v1\nQuantum-HPC Hybrid Biomolecular Simulation\nTheme: Chemistry\nMany biologically important photochemical processes depend on excited electronic states that are difficult to model because the number of relevant electron configurations grows rapidly with system size.\nChallenge: Can quantum computers and classical supercomputers work together to efficiently capture these complex electronic effects and improve the accuracy of biomolecular simulations?\nReferences:\narxiv.org/pdf/2601.15677\narxiv.org/pdf/2605.01138v1\nError-Corrected Quantum Chemistry\nThemes: QEC, Chemistry\nQuantum Phase Estimation offers an asymptotically efficient route to molecular energy calculations, but its deep circuits are highly sensitive to noise and exceed the capabilities of unprotected quantum hardware. While quantum error correction (QEC) is widely recognized as essential for scalable quantum chemistry, end-to-end demonstrations of a quantum chemistry workflow using fully encoded logical qubits remain limited.\nChallenge: Demonstrate that QPE can be executed within a practical QEC framework and deliver chemically meaningful molecular energy estimates. Specifically, can logical qubits protected by quantum error correction improve computational fidelity sufficiently to enable accurate molecular energy calculations on current trapped-ion quantum processors?\nReferences:\narxiv.org/pdf/2505.09133\narxiv.org/pdf/2306.16608\nQuantum Search\nTheme: Quantum Primitives\nCan a quantum computer uncover a hidden pattern in a black-box function exponentially faster than any known classical algorithm (Simon's Algorithm)? Given a black-box function containing a hidden XOR relationship, how can we efficiently uncover the secret bit string that links pairs of inputs producing identical outputs?\nChallenge: Classical algorithms require exponentially many function evaluations, while Simon's quantum algorithm solves the problem in polynomial time.\nEvent Timeline\nRegistration | July 20th to August 15th | Announcement, challenge format, judges and mentor selection.\nEducation & Problem Formulation | July 20th to August 30th | Technical collateral for self-onboarding and platform education, mentor consultations, problem formulation.\nOnboarding Delivery | August 19th to August 28th | Deliver virtual onboarding webinars with recordings available post-webinar.\nPlatform Utilization | July 20th to October 15th | Emulator access, Guppy usage, Aqora datasets.\nSubmission 1 | October 15th | Submission for grand finale. Judges will shortlist teams for the grand finale.\nShortlist Teams | October 20th | Finalists announced for the grand finals.\nGrand Finale | October 21st | Hardware access and further solution refinement.\nSubmission 2 | November 14th | Submission for grand finale.\nFinals | November 19th | In-person presentations and winner announced.\nOnboarding Webinars\nEight virtual sessions covering the platforms, the tooling, and each R&D theme. Each session runs 1h 30m unless stated otherwise. Registration is open to all participants, and no prior quantum experience is assumed for the platform sessions.\nHere you will find the links to the PDF of the presentations for each session: Presentation slides (Google Drive)\nAugust 19th, 09:00 SGT | Platforms | Quantinuum Platform Overview | Irfan | Watch the recording\nAugust 20th, 15:30 SGT | Guppy + Pytket | Guppy, Selene, H2 Integration: Zero to Hero | Melf | Watch the recording\nAugust 21st, 15:30 SGT | AI for Quantum | Discovering Quantum Algorithms with AI | Freddy | Watch the recording\nPostponed due to unforeseen issues | QEC | QEC in Practice: Writing logical circuits with Guppy | Shival |\nAugust 25th, 09:00 SGT | Quantum Primitives | Quantum Magnetism / HTC Paper | Watch the recording\nAugust 26th, 15:30 SGT | Chemistry | Big Chemistry | Riku, Carlo | Watch the recording\nAugust 27th, 15:30 SGT | Optimization | Title to be announced | Alexandre Krajenbrink | Watch the recording\nAugust 28th, 16:00 SGT | Aqora Platform | What is Aqora's platform and how to use it? | Julian | Watch the recording\nMentors\nMentors are grouped by R&D theme. Some mentors support more than one theme and appear in each relevant section.\nBook a mentor session: Mentor booking page\nQuantum Primitives\nIrfan Khan, Lead Applications Engineer, Quantinuum\nEtienne Granet, Lead R&D Scientist, Quantinuum\nChemistry\nKentaro Yamamoto, Principal R&D Scientist, Quantinuum\nIrfan Khan, Lead Applications Engineer, Quantinuum\nAI\nJem Guhit, Advanced R&D Scientist, Quantinuum\nChen-Yu Liu, Advanced R&D Scientist, Quantinuum\nJacob Swain, Sr Advanced R&D Scientist, Quantinuum\nQEC\nNatalie Brown, Sr Advanced QEC Scientist, Quantinuum\nElijah Durso Sabina, QEC Scientist II, Quantinuum\nOptimization\nAlexandre Krajenbrink, Lead R&D Scientist, Quantinuum\nIfan Williams, Sr R&D Scientist, Quantinuum\nPlatform Support\nQuantinuum Platform\nIrfan Khan, Lead Applications Engineer, Quantinuum\nCallum MacPherson, Advanced Software Engineer III, Quantinuum\nAqora Platform\nJulian Popescu, Sr Full Stack Software Engineer, Aqora\nAntoine Chauvin, Sr Full Stack Software Engineer, Aqora\nJudges\nOur judging panel will include experts from Quantinuum and the broader quantum ecosystem. Additional details will be shared as the challenge progresses.\nJudging Framework\n4 criteria + one common 0\u20135 scale; every score traces to an artifact and rationale.\nProblem & Value \u2014 30%\nJudge on: need clarity; solution fit; quantified customer or business value\nEvidence to cite: problem/user validation; use-case evidence; business case or ROI\nTechnical Performance & Hardware Use \u2014 30%\nJudge on: correctness; benchmark gains; scalability; hardware utilization\nEvidence to cite: benchmark data; run logs; job metadata; demo results\nScientific Merit \u2014 20%\nJudge on: novelty; methodological rigor; improvement versus a baseline\nEvidence to cite: algorithm rationale; baseline comparison; error and validation analysis\nEngineering & Reproducibility \u2014 20%\nJudge on: code structure; testing; documentation; repeatable setup\nEvidence to cite: repository; README; test results; reproduction record\nCommon evidence scale (0\u20135)\nWeighted points = rating \u00f7 5 \u00d7 criterion weight\n0 \u2014 No evidence\n1 \u2014 Assertion only\n2 \u2014 Plausible; limited proof\n3 \u2014 Demonstrated with direct evidence\n4 \u2014 Measured and repeatable\n5 \u2014 Validated against a benchmark, user need, or external reference\nPrizes & Outcomes\nSelected teams will have the opportunity to advance through the challenge, receive mentor support, and showcase their work during the final stage of the program. Finalists may also receive access to quantum hardware and/or related resources to help develop and test their solutions ahead of final judging.\nPrizes and recognition will be awarded to top-performing teams based on the judging criteria, which includes solution relevance, hardware utilization, commercial impact, source code quality, and scientific impact. Additional prize details and finalist opportunities will be announced as the challenge progresses.\nTools & Platforms\nGuppy\nQuantinuum's next-generation quantum programming language, embedded in Python, designed to make quantum software development more intuitive, safe, and scalable. It enables developers to build complex quantum-classical applications using familiar Python-like syntax while supporting advanced capabilities such as real-time feedback, adaptive algorithms, and quantum error correction workflows.\ndocs.quantinuum.com/guppy\nNexus\nAn integrated quantum computing platform that provides a unified environment for developing, running, tracking, and managing quantum workloads. It offers seamless access to Quantinuum hardware, emulators, software tools, and third-party backends through a cloud-based workspace, enabling researchers and developers to accelerate quantum experimentation and application development.\ndocs.quantinuum.com/nexus\nH2\nQuantinuum's trapped-ion quantum computing system, designed to deliver high-fidelity, fully connected quantum processing for advanced research and commercial applications. Featuring industry-leading performance, error-correction capabilities, and scalable architecture, H2 enables users to explore complex quantum algorithms across domains such as chemistry, optimization, logistics, and finance.\ndocs.quantinuum.com/systems\nAqora\nAqora is a collaborative quantum computing platform that connects enterprises, researchers, developers, and students through real-world quantum challenges, datasets, competitions, and algorithm development tools. It helps organizations explore practical quantum use cases while enabling the quantum community to showcase expertise, solve industry problems, and accelerate adoption of quantum technologies.\naqora.io\nDocs\nFull Quantinuum documentation, including Guppy, Nexus, and systems guides: docs.quantinuum.com\nOnboarding webinar sign-up links and, after the sessions, the recordings will be published in this tab.\n";
      const compModal = document.getElementById('comp-modal');
      const compContent = document.getElementById('comp-modal-content');
      const openCompBtn = document.getElementById('btn-open-comp-modal');
      const closeCompBtn = document.getElementById('btn-close-comp-modal');

      function openCompetitionModal() {
        if (compModal && compContent) {
          compContent.innerHTML = marked.parse(compMarkdown);
          compModal.style.display = 'block';
          document.body.style.overflow = 'hidden';
          renderAllMath(compContent);
        }
      }

      function closeCompetitionModal() {
        if (compModal) {
          compModal.style.display = 'none';
          document.body.style.overflow = '';
        }
      }

            // Bind modal triggers across all tabs
      document.querySelectorAll('.btn-open-comp-modal-trigger, #btn-open-comp-modal').forEach(btn => {
        btn.addEventListener('click', openCompetitionModal);
      });

      // Copy Elevator Pitch Button
      const copyPitchBtn = document.getElementById('btn-copy-pitch');
      if (copyPitchBtn) {
        copyPitchBtn.addEventListener('click', () => {
          const pitchEl = document.getElementById('pitch-text');
          if (pitchEl) {
            navigator.clipboard.writeText(pitchEl.innerText.trim()).then(() => {
              alert('30-Second Elevator Pitch copied to clipboard!');
            }).catch(() => {
              alert('Could not copy automatically.');
            });
          }
        });
      }
      if (closeCompBtn) closeCompBtn.addEventListener('click', closeCompetitionModal);

      // Close modal on click outside or Escape key
      if (compModal) {
        compModal.addEventListener('click', (e) => {
          if (e.target === compModal) closeCompetitionModal();
        });
      }
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && compModal && compModal.style.display === 'block') {
          closeCompetitionModal();
        }
      });
    }
```

## If the team wants this back as a private tool

Rebuild it as a small standalone HTML file kept **outside** the published `docs/` mirror (e.g. a new
`workspaces/war_room.html` that nobody links to from the public site, or better, a real per-member doc
in a private tool like Notion/Linear). A client-side passcode is still not real security — if this needs
to stay actually private, put it behind a real auth layer or just don't publish it at all.
