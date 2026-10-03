# Project Spec: VoiceDesk

**Status:** Live canonical spec.
**Created:** 14 May 2026.

For session-to-session current state, see the most recent 
`HANDOVER_*.md` in this folder.

---

## Vision

A free, offline, local push-to-talk dictation tool for Windows 11. 
Built as a personal alternative to commercial solutions like Wispr 
Flow. Runs entirely on-device — no cloud, no telemetry, no account.

## Core principle

Local-first. Latency over polish. The model stays in memory so 
transcription starts the moment the hotkey is released.

## Stack

- **Transcription:** faster-whisper, `small.en` model, CPU, int8 
  quantisation, kept in memory
- **Audio capture:** sounddevice
- **Global hotkey:** keyboard (Ctrl+Win push-to-talk)
- **Tray icon:** pystray
- **Clipboard paste:** pyperclip
- **UI (overlay, menu, palette):** PyQt6

## Code location

`C:\Users\<user>\Documents\voicedesk`

## Repo

`https://github.com/88Ekul/voicedesk` (private, branch `master`)

## Launch discipline

Always launched with:

```
python .\main.py --worker
```

The `--worker` flag is mandatory. Without it, the watchdog triggers 
and spawns a second instance. Antigravity IDE must be run as 
Administrator. Kill stale instances with 
`taskkill /F /IM python.exe /T` before relaunching.

## Auto-start

Task Scheduler launches VoiceDesk on login with a 30–35 second delay, 
using `pythonw.exe`. The Startup folder shortcut path is deprecated — 
running both simultaneously causes duplication.

## Module map

- `main.py` — orchestrator, lifecycle, `_terminate_recording` 
  convergence point, `_process()` pipeline
- `audio.py` — sounddevice capture, WAV writing
- `transcribe.py` — faster-whisper wrapper, hallucination blocklist, 
  VAD config
- `paste.py` — clipboard + window-targeted paste
- `hotkey.py` — global hotkey listener, push-to-talk state machine, 
  self-heal logic
- `tray.py` — pystray system tray icon
- `config_loader.py` — YAML/JSON config loading
- `text_processing.py` — corrections, snippets, fillers pipeline
- `overlay.py` — recording pill overlay with Stop/Cancel buttons
- `menu.py` — Ctrl+Win short-press palette (Dictionary, Snippets, 
  Recent, Settings)

## Design tokens

- Rose Gold: `#B76E79`
- Dark Slate: `#2F4F4F`
- Off-White: `#F5F5F5`

## Config files

- `config/config.yaml` — runtime config (rms_threshold, output_style, 
  whisper_prompt when added)
- `config/corrections.json` — case-insensitive word/phrase 
  replacements
- `config/snippets.json` — partial-phrase triggers (personal data; 
  gitignored)
- `config/fillers.json` — filler words to strip

All four hot-reload via mtime check — no restart needed for config 
changes.

## Rules

1. Always run Antigravity IDE as Administrator.
2. Always launch with `--worker`.
3. Kill stale instances by exact PID (`Stop-Process -Id <pid> -Force`), 
   identified via `Get-CimInstance Win32_Process` filtered for 
   `main.py --worker`. Never use a blind `taskkill /IM` image 
   sweep — it misses the pythonw.exe auto-start instance and 
   endangers unrelated Python processes. (Amended per R1, 
   replacing the original taskkill rule.)
4. Use `Select-String` in PowerShell, not `grep`.
5. Verify bug shape in logs before writing any fix.
6. Read the full relevant method before writing any fix.
7. Deliver a written plan first. No code until the plan is confirmed.
8. Confirm each fix with a live test before moving on.

## Architecture decisions — append-only log

### ADR-001 — faster-whisper small.en, CPU, int8 (initial build)
Chosen for compatibility across machines without GPU dependencies. 
Model kept in memory to eliminate cold-start latency. Trade-off: 
short monosyllables and proper nouns occasionally misrecognised. 
Upgrade path to medium.en via Vulkan/whisper.cpp noted for later.

### ADR-002 — `--worker` flag + watchdog pattern
Watchdog process monitors the worker and restarts on crash. The 
`--worker` flag distinguishes the worker from the launcher. Launching 
without the flag triggers a second spawn.

### ADR-003 — PyQt6 over Tkinter for overlay and menu
Required for window translucency, custom painting (rounded pills, 
glow effects), and frameless windows. Tkinter cannot do these cleanly 
on Windows 11.

### ADR-004 — Custom `paintEvent` glow, not `QGraphicsDropShadowEffect`
`QGraphicsDropShadowEffect` does not render on translucent windows. 
Glow is painted manually inside `paintEvent` using offset semi-
transparent strokes.

### ADR-005 — `_Dispatcher(QObject)` with `pyqtSignal()` for cross-thread marshalling
`QTimer.singleShot(0, fn)` cannot be posted from the keyboard hook 
thread — there is no Qt event loop on that thread. A `QObject` 
subclass with a `pyqtSignal` connected to a slot on the main thread 
is used instead.

### ADR-006 — `WH_MOUSE_LL` low-level Windows hook for palette dismiss
Qt-based outside-click dismiss approaches (`WindowDeactivate`, 
`ApplicationDeactivated`, `eventFilter`) all failed on subsequent 
opens because Windows refuses foreground activation after the first 
open (foreground-stealing prevention since Win2000). The low-level 
mouse hook watches `WM_LBUTTONDOWN` globally and dismisses the 
palette when the click falls outside its geometry. DPI scaling 
handled by converting Qt device-independent pixels to physical pixels 
via `devicePixelRatioF()`.

### ADR-007 — Single `_terminate_recording` convergence point
Hotkey release, Stop button, and Cancel button all funnel through one 
method. Prevents divergent code paths and inconsistent state between 
input sources. `_on_stop_button` captures `_target_hwnd` before 
spawning the worker thread so paste still hits the original window 
after focus loss.

### ADR-008 — Text-processing pipeline order: corrections → snippets → fillers
Corrections normalise proper nouns and known misrecognitions first. 
Snippets then expand triggers in normalised text. Fillers strip last 
so that snippet expansions are not affected.

### ADR-009 — RMS pre-transcription fast-fail with fail-open fallback
Normalised int16 RMS is computed from the saved WAV before 
transcription. Below threshold (currently `0.003`), transcription is 
skipped and a low beep plays. If the WAV read fails, the code falls 
through to transcription normally (fail-open). The earlier `0.01` 
threshold rejected real speech and was lowered. 
**Amendment (17 Jul 2026):** threshold lowered again to `0.001` after live
calibration against the actual microphone noise floor; `0.003` was still
rejecting quiet speech. The fail-open behaviour is unchanged.

### ADR-010 — Task Scheduler chosen over Startup folder shortcut
Both methods running simultaneously caused VoiceDesk to launch twice 
on login. Task Scheduler retained for its 30–35 second delay 
capability; Startup folder shortcut removed.

### ADR-011 — Query-JSON contract is append-only, widened by need not speculation
The query-JSON contract between VoiceDesk and Second-Brain-OS
(`{ query_text, captured_at, source }`, written to
`second-brain-query\inbox`) is live, not frozen. The 8 June convergence note
treated the three-field schema as fixed; that was premature. The contract will
widen once Second-Brain's answer-synthesis step is built, because synthesis may
require richer input than `query_text` alone (likely candidates: a query-type
field and/or conversation-threading for spoken follow-ups). Those fields are
deliberately not designed yet — they cannot be specified until synthesis is built
far enough to reveal what it actually needs; designing them now would be guessing.
Governing principle: the contract is APPEND-ONLY. Consumers ignore fields they do
not recognise. Second-Brain reads `query_text` and tolerates any additional
fields; VoiceDesk may add fields later without breaking the far side. This keeps
the two projects cleanly decoupled — the seam widens once, driven by a concrete
need surfaced in building, not by speculation up front. Build sequence:
(1) VoiceDesk reliability cluster [deaf-hook / watchdog-blindness / kill-ritual],
(2) VoiceDesk Alba gating under the current three-field contract,
(3) Second-Brain answer synthesis, (4) VoiceDesk second act — emit the richer
fields synthesis has revealed a need for. See `docs/CONTRACT_STATUS_05_JUL.md`
for the full cross-project note.

### ADR-012 — Alt+Win uses explicit Alba-prefix gating
Ctrl+Win remains ordinary dictation. Alt+Win is dual-purpose: an ordinary
capture writes a note only, while an Alba-prefixed capture writes the cleaned
note and then emits a query containing the same cleaned text. Matching is
deterministic, prefix-only, and case-insensitive, with explicit separator
boundaries; it uses neither fuzzy aliases nor an intent model. A recognised
trigger with no remaining alphanumeric request is retained as the original
note and does not emit an empty query. The query schema remains
`{ query_text, captured_at, source }`, and VoiceDesk remains decoupled from
Second Brain. Accepted trade-off: because `Alba` is a reserved opening prefix,
a note beginning `Alba is...` is treated as a command.
