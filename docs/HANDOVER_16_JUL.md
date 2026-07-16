# VoiceDesk — Handover, 16 July 2026
Continuing from `HANDOVER_06_JUL.md`. This session diagnosed and fixed the stuck-Win-key failure live from DEBUG traces, and in doing so most likely root-caused the deaf-hook (same mechanism, later stage). The immediate next work is field confirmation of the fixes through normal daily use, then Phase 2 — Alba gating (A1/A2), now backed by a documented pain point.
## Stack and location
- Project: `C:\Users\<user>\Documents\voicedesk`
- Run via Antigravity IDE as Administrator
- Launch command: `python .\main.py --worker` — never without `--worker`
- Auto-start: Task Scheduler on login, ~30–35s delay, `pythonw.exe main.py --worker`
- Stack: faster-whisper (small.en, CPU int8), sounddevice, keyboard, PyQt6, pystray, pyperclip
- Repo: `https://github.com/88Ekul/voicedesk` (private), branch `master`
- Repo state: last pushed commit `e18fdd2`. Working tree now carries UNCOMMITTED changes to `main.py` and `hotkey.py` (this session's fixes). Commit and push manually.
## Done this session
### Fix 1 — hook-thread stall removed (`main.py`, `_on_stop`)
`_on_stop` previously called `_terminate_recording` synchronously on the keyboard hook callback thread, blocking it (beep, audio stop, overlay, thread join up to 10s) past Windows' low-level hook timeout. Consequences: dropped Win key-up events (stuck Win key, captured in trace at 19:39:02) and, on repeat offences, silent hook removal by Windows (the deaf-hook). Fixed by dispatching `_terminate_recording` to a daemon worker thread (`name="hotkey-stop"`), matching the existing tap-stop and button paths. Verified live: release path now returns instantly; the 19:39 event-flush signature is gone.
### Fix 2 — suppressor lifecycle decision (`hotkey.py`, `_suppress_combo`)
Per-event suppression allowed a ctrl-first release to leak a trailing Win auto-repeat to the OS raw while suppressing the matching key-up — OS-level stuck Win. Side effect: VoiceDesk's own Ctrl+V paste then landed as Win+Ctrl+V, opening the Windows sound-output flyout. Fixed by making the suppress/pass decision once at the initial Win key-down and applying it to the whole press (new `_win_is_down` attribute; repeats and key-up inherit the decision). Verified live: the exact killer sequence (ctrl-up, straggler win-down, win-up at 23:44:13) now handled cleanly; dictation, tap-palette, and win-first releases all pass.
### Verified — both hotkeys covered by construction
`listener.start(... on_stop_cb=_on_stop ...)` at main.py line 557 (ctrl+win) and line 567 (alt+win): both listeners share `_on_stop` and converge on `_terminate_recording` (ADR-007), so both fixes cover both hotkeys. Alt+Win live-tested end-to-end (capture → JSON → Alba responded).
### Diagnostics performed
- Deaf-hook: no evidence of hook loss in either log this period ("deaf" hits were a WAV filename coincidence).
- 13 July: seven `Audio recording failed ... device ID out of range (MME error 2)` errors, two clusters — stale input device index, self-recovered. Parked; silent-failure hardening is a candidate future item.
- Temporary DEBUG logging used for capture (main.py line 54, hardcoded level).
## Pending work
1. **Verify main.py line 54 is reverted to `logging.INFO` and relaunch** ← immediate. DEBUG logs every keystroke in plaintext — must not run in daily use.
2. **Commit and push this session's fixes** (`main.py`, `hotkey.py`) manually from Antigravity.
3. **Field confirmation window** — several days of normal daily use. Watch for: any Win wedge, any sound-flyout-instead-of-paste, any deaf-hook recurrence. Reliability cluster status: likely root-caused, pending field confirmation. The in-process liveness detector (previous Pending item 1) is DOWNGRADED to belt-and-braces; do not build it unless the deaf-hook recurs post-fix.
4. **R1 — recovery ritual correction** (carried): amend PROJECT_SPEC Rule 3 to a PID-targeted procedure covering `pythonw.exe`. Small, high value.
5. **Phase 2 — Alba gating (A1/A2)** (carried, now pain-point-backed): current Alt+Win dual-writes on every capture, so Alba speaks after every inbox dictation — confirmed as a real daily irritation this session. A2 splits it: default silent capture (`.md` only); "Alba"-prefixed transcripts strip the trigger and write the query JSON. A1 trigger-word empirical test first.
6. **R4 — instance-lock robustness** (carried, soft-scoped): state the failure mode first or fold into restart choreography. Do not build on momentum.
7. **Phase 3 — features** (carried, order unchanged): F1 whisper `initial_prompt` vocabulary; F2 Settings tile; F3 deterministic style pass; F4 whisper.cpp/Vulkan (make silent failure loud); F5 Recent panel; F6 Flow-style editors (rule-of-three).
8. **Audio-device resilience** (new, unscheduled): recording fails silently when the configured input device index goes stale. Candidate: fall back to system default and surface the failure audibly/visibly.
9. **H2 — logging tidy** (carried): opportunistic.
### Struck from the roadmap (unchanged)
- Transforms — requires a cloud LLM; contradicts local-first. Not a VoiceDesk feature.
## Known issues
- **Fixes unconfirmed in the field** — mechanism-level evidence is strong, but sign-off requires days of clean daily use. Treat deaf-hook as open-but-likely-resolved until then.
- **Alba speaks on every Alt+Win capture** — by current design (dual-write); addressed by Phase 2 A2.
- **Audio input device staleness** — silent recording failure after device changes (13 July); parked, see Pending 8.
- **Benign staleness-guard log line** — post-release ignore window can leave a key in a listener's `_held` set; the "Combo parts present but stale" guard correctly refuses to fire. Cosmetic, by design.
- Mode-naming asymmetry (`"inbox"` vs `"inbox_and_paste"` fallback label) — parked.
- Halo corner artefacts on menu palette — cosmetic, parked.
- Orphaned punctuation after filler removal — accepted.
- Transcription delay between successive recordings — accepted.
- RMS threshold may need adjustment — check `Pre-transcription RMS:` lines.
## Key operating principles
- Always run as Administrator in Antigravity IDE
- Always use `python .\main.py --worker` — never without `--worker`
- Kill stale instances by exact PID (`Stop-Process -Id <pid> -Force`), not a blind image sweep — protects Antigravity's runtime and the second-brain-query venv
- `grep` does not exist in PowerShell — use `Select-String`
- Verify bug shape in logs before writing any fix
- Read the full relevant method before writing any fix
- Deliver written plan first, no code until confirmed
- Confirm each fix with a live test before moving on
- Do not run any git commands — commit and push done manually
- One task per session — no scope creep
- Reliability work ranks above feature work (6 July Build Plan)
- Nothing that blocks may run on the keyboard hook callback path (16 July)
- Key suppression decisions belong to the press lifecycle, not individual events (16 July)
- DEBUG logging captures keystrokes in plaintext — short deliberate windows only, revert to INFO immediately (16 July)
- British English spelling throughout
- Treat Claude Code's claims about file state with scepticism — verify diffs directly