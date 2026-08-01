# VoiceDesk — Handover, 6 July 2026
Continuing from `HANDOVER_08_JUN.md`. This was a verification and planning session
(no application code written); the immediate next work is the Phase 1 design
sitting — in-process deaf-hook detection and self-heal, now that the supervision
topology is known.
## Stack and location
- Project: `C:\Users\luke_\Documents\voicedesk`
- Run via Antigravity IDE as Administrator
- Launch command: `python .\main.py --worker` — never without `--worker`
- Auto-start: Task Scheduler on login, ~30–35s delay. VERIFIED THIS SESSION —
  the task invokes `pythonw.exe` with arguments `main.py --worker`
  (working directory `C:\Users\luke_\Documents\voicedesk`).
- Stack: faster-whisper (small.en, CPU int8), sounddevice, keyboard, PyQt6,
  pystray, pyperclip
- Repo: `https://github.com/88Ekul/voicedesk` (private), branch `master`
### Repo state (verified 6 July, after this session's cleanup)
- Branch `master` is **up to date with origin/master**. Last pushed commit:
  `e18fdd2` ("docs: add contract status, ADR-011, deaf-hook learning; update
  dictionary").
- Working tree is CLEAN. The `__pycache__/*.pyc` and `logs/voicedesk.log` files
  are now UNTRACKED (committed as `f53a2f0`) and will regenerate locally without
  showing in `git status`.
- Two commits landed and pushed this session:
  - `f53a2f0` — chore: untrack auto-generated pycache and log files (10 files,
    index deletions only).
  - `e18fdd2` — docs: add `CONTRACT_STATUS_05_JUL.md`, ADR-011 in PROJECT_SPEC,
    deaf-hook entry in LEARNINGS, Alba item in HANDOVER_08_JUN, plus manual
    `config/corrections.json` dictionary edits.
## Done this session
No application code changed. This was a verification, planning, and repo-hygiene
session.
### Phase 0 complete — repo baseline reached
Ran the git cleanup: untracked the auto-generated `__pycache__/*.pyc` and
`logs/voicedesk.log` (they were tracked and dirtying every `git status`), and
committed the outstanding documentation edits. Branch is now clean and pushed at
`e18fdd2`. This gives a legible baseline before any reliability diffs land.
### Adopted the 6 July Build Plan as the governing sequenced plan
The externally-authored Build Plan (6 July) is adopted as governing. It supersedes
the 8 June handover's priority ordering. Key correction: the reliability cluster
ranks ABOVE all feature work. The Settings tile, marked "immediate priority" in
HANDOVER_08_JUN, is demoted to Phase 3 — a UI feature was standing ahead of a
twice-observed silent failure in a daily driver. RECOMMENDATION: save the Build
Plan into `docs/` as the governing plan (it currently exists only in chat).
### R0 resolved — supervision topology (architectural finding)
Verified via `Get-ScheduledTask` that auto-start runs `pythonw.exe main.py
--worker`. Because `--worker` goes straight to `main()`, the daily-use instance
BYPASSES the watchdog entirely — it is UNSUPERVISED. "Watchdog blindness" is
therefore actually "watchdog absence" for daily use. Consequence for Phase 1: the
deaf-hook liveness detector and its recovery must run IN-PROCESS (self-heal inside
the worker), not report to a watchdog parent — there is no parent. This also
explains the 12 June deaf-hook incident: the login instance that went deaf was
unsupervised by construction, so nothing was ever going to restart it.
## Pending work
1. **Phase 1 design sitting — in-process deaf-hook self-heal (R2 + R3)** ← immediate
   No code; written design plan only. Now that R0 confirms the daily instance is
   unsupervised, design the in-process liveness detector: distinguish "hook dropped"
   from "user idle" without false positives (candidate signals to weigh at design
   time — event-absence heartbeat cross-checked against system-wide last-input time;
   scheduled periodic hook re-registration; active probe). Before designing:
   GitHub-first vetting — check the `keyboard` library issue tracker for known
   dropped-hook behaviour and mitigations. Recovery: re-arm the hook in place; a
   self-heal that gives up should fail LOUDLY (audible/visible), not silently. Note:
   the R3 "watchdog gives up after MAX_RESTARTS = 3" observation is likely moot for
   daily use given the topology, but relevant if a supervised launch path is kept.
2. **R1 — recovery ritual correction.** Amend PROJECT_SPEC Rule 3: the documented
   `taskkill /F /IM python.exe /T` cannot kill the `pythonw.exe` auto-start instance,
   and a blind image sweep endangers Antigravity's runtime and the
   second-brain-query venv. Replace with a PID-targeted procedure
   (`Stop-Process -Id <pid>`) covering both `python.exe` and `pythonw.exe`. Small,
   high immediate value; can precede or follow item 1.
3. **R4 — instance-lock robustness (carried "msvcrt" item) — SOFT-SCOPED.** The
   current lock is a Win32 named mutex, auto-released by the kernel on process death.
   No document records what failure the msvcrt rewrite addresses. OPEN QUESTION (Q2):
   state the failure mode first, or the item folds into R3's restart choreography
   (guarantee the old worker's mutex is gone before the replacement starts). Do not
   build on momentum.
4. **Phase 2 — Alba gating (cross-project step 2).**
   - A1: trigger-word empirical test — ~12 live utterances through the real
     pipeline; pick a reliably-heard word or accept a small spelling set,
     case-insensitive, tolerant of "Hey Alba" / trailing punctuation.
   - A2: split the Alt+Win dual-write — default silent capture (`.md` only);
     Alba-prefixed strips the trigger and writes BOTH the `.md` and the query JSON.
     Contract unchanged; Second Brain untouched. Re-read `_process()` before editing
     (line references in older docs predate the Phase 1 edits). Ends with the
     trigger-word-set handshake back to Second Brain.
5. **Phase 3 — features (order is a recommendation, not a dependency chain).**
   - F1: whisper `initial_prompt` custom vocabulary — small, hot-reloadable, serves
     proper-noun accuracy (ADR-001's known small.en weakness). Highest value first.
   - F2: Settings tile inline editor — last unwired palette tile; its own session.
   - F3: deterministic style pass (rule-based caps/punctuation, not LLM).
   - F4: whisper.cpp medium.en / Vulkan upgrade — first step: test `whisper-cli.exe`
     with medium.en directly; make the currently-silent Vulkan failure LOUD.
   - F5: Recent in-app panel — optional; data side already solved.
   - F6: Flow-style Dictionary/Snippets editors — deferred under rule-of-three until
     raw-JSON editing proves annoying in daily use.
6. **Phase 4 — second act (externally blocked).** Emit richer JSON fields once
   Second Brain's built synthesiser reveals what it needs. Not schedulable from
   inside VoiceDesk; ADR-011's append-only principle makes waiting safe.
7. **H2 — logging revert to INFO** once RMS is settled (check `Pre-transcription
   RMS:` lines). Opportunistic, any session.
### Struck from the roadmap (unchanged)
- Transforms (Wispr Flow's AI rewrite actions) — requires a cloud LLM; contradicts
  local-first / no-cloud. Not a VoiceDesk feature.
## Known issues
- **Deaf-hook, unsupervised daily instance** — the login `pythonw --worker` instance
  has no supervisor and no in-process liveness detection; when Windows drops the
  WH_KEYBOARD_LL hook it goes deaf silently (tray up, mutex held, no events, no
  error). Twice observed. Addressed by Pending item 1.
- **Kill ritual documents its own blind spot** — PROJECT_SPEC Rule 3 targets
  `python.exe`, missing the `pythonw.exe` auto-start instance. Addressed by R1.
- **msvcrt lock motivation unknown** — see Q2, Pending item 3.
- **whisper.cpp Vulkan path fails silently**, falls back to CPU — addressed by F4.
- **HANDOVER_08_JUN.md was edited** (Alba item appended via Cowork) — a brush against
  the append-only protocol. Harmless (a forward-looking roadmap line, not a rewrite
  of recorded facts) but noted so the discipline stays clean going forward.
- Mode-naming asymmetry (`"inbox"` vs `"inbox_and_paste"` fallback label) — parked.
- Halo corner artefacts on menu palette — cosmetic, parked.
- Orphaned punctuation after filler removal — accepted.
- Transcription delay between successive recordings — no interrupt in faster-whisper,
  accepted.
- RMS threshold may need adjustment — check `Pre-transcription RMS:` lines.
## Key operating principles
- Always run as Administrator in Antigravity IDE
- Always use `python .\main.py --worker` — never without `--worker`
- Kill stale instances by exact PID (`Stop-Process -Id <pid> -Force`), not a blind
  image sweep — protects Antigravity's runtime and the second-brain-query venv
- `grep` does not exist in PowerShell — use `Select-String`
- Verify bug shape in logs before writing any fix
- Read the full relevant method before writing any fix
- Deliver written plan first, no code until confirmed
- Confirm each fix with a live test before moving on
- Do not run any git commands — commit and push done manually
- One task per session — no scope creep
- Reliability work ranks above feature work (6 July Build Plan)
- British English spelling throughout
- Treat Claude Code's claims about file state with scepticism — verify diffs directly
