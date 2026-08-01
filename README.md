# VoiceDesk
A free, offline, local push-to-talk dictation tool for Windows 11. 
Built as a personal alternative to commercial solutions like Wispr 
Flow. Runs entirely on-device — no cloud, no telemetry, no account.
Hold `Ctrl+Win` to record. Release to transcribe and paste into the 
focused window.
---
## Licence

Source-available under the PolyForm Strict License 1.0.0 — you may view and evaluate this code, but not reuse, redistribute, or create derivative works without written permission. See [LICENSE.md](./LICENSE.md).
---
## Stack
- **Transcription:** faster-whisper, `small.en` model, CPU, int8 
  quantisation, kept in memory
- **Audio capture:** sounddevice (16 kHz mono WAV)
- **Global hotkey:** keyboard (Ctrl+Win push-to-talk)
- **UI:** PyQt6 (recording pill overlay, short-press palette)
- **Tray icon:** pystray
- **Clipboard paste:** pyperclip
A Vulkan/whisper.cpp + `medium.en` upgrade path is planned but not 
yet active. See `docs/HANDOVER_*.md` for status.
---
## Prerequisites
Python 3.x on Windows 11. The `keyboard` library requires elevated 
privileges for global hooks, so VoiceDesk must be run as 
Administrator.
---
## Installation
```bash
pip install -r requirements.txt
```
Copy `config/config.example.yaml` to `config/config.yaml` and set 
your own paths before first run.
The `small.en` faster-whisper model downloads automatically on first 
run.
---
## Launch
```
python .\main.py --worker
```
The `--worker` flag is **mandatory**. Without it, the watchdog 
triggers and spawns a second instance. Kill stale instances by exact PID, not a blind image sweep. 
Identify the VoiceDesk process with 
`Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'"` 
(look for `main.py --worker` in the CommandLine), then 
`Stop-Process -Id <pid> -Force`. A blind `taskkill /IM` sweep can 
kill unrelated Python processes.
Auto-start at login is handled by Task Scheduler with a 30–35 second 
delay using `pythonw.exe`.
---
## Usage
A rose-gold circle appears in the system tray.
- **Hold `Ctrl+Win`** — recording pill overlay appears, mic captures
- **Release** — transcription runs, text pastes into the focused 
  window
- **Click the red ✕ on the pill** — cancels (no paste, low beep)
- **Click the green ■ on the pill** — stops and pastes to the 
  originally focused window even if focus has since changed
- **Short-press `Ctrl+Win`** (under hold threshold) — opens a 2×2 
  palette with Dictionary, Snippets, Recent, and Settings (stub) entries
A second hotkey, `Alt+Win`, captures spoken notes to a 
configurable inbox path as Markdown/JSON — used as the voice 
front-end for a separate personal system. Set `inbox_path` and 
`query_inbox_path` in config.
If the recording RMS is below the silence threshold, transcription 
is skipped and a low beep plays — no empty pastes.
Logs are written to `logs/voicedesk.log`.
---
## Text processing pipeline
Every transcription passes through three stages in order, all hot-
reloadable via mtime check on their config files:
1. **Corrections** (`config/corrections.json`) — case-insensitive 
   word/phrase replacements for proper nouns and known 
   misrecognitions
2. **Snippets** (`config/snippets.json`) — partial-phrase triggers, 
   word-boundary matching (gitignored; contains personal data)
3. **Fillers** (`config/fillers.json`) — strips configured filler 
   words such as "um", "uh", "you know"
---
## Configuration
Edit `config/config.yaml` to adjust runtime settings:
| Key | Default | Description |
|-----|---------|-------------|
| `hotkey` | `ctrl+win` | Global push-to-talk hotkey |
| `model` | `small.en` | faster-whisper model name |
| `rms_threshold` | `0.001` | Silence fast-fail threshold (normalised int16 RMS) |
| `max_duration_seconds` | `120` | Maximum recording length |
| `audio_device` | `null` | Input device (null = system default) |
| `output_style` | varies | Reserved — persisted to config but not yet wired to transcription |
---
## Architecture
| Module | Responsibility |
|--------|---------------|
| `main.py` | Orchestrator, lifecycle, `_terminate_recording` convergence, `_process()` pipeline |
| `config_loader.py` | Loads and validates `config/config.yaml` |
| `audio.py` | Mic capture via sounddevice → 16 kHz mono WAV |
| `transcribe.py` | faster-whisper wrapper, hallucination blocklist, VAD config |
| `text_processing.py` | Corrections → snippets → fillers pipeline |
| `paste.py` | Clipboard save/restore + window-targeted Ctrl+V |
| `tray.py` | pystray system tray icon |
| `hotkey.py` | Global push-to-talk listener, state machine, stuck-state self-heal |
| `overlay.py` | Recording pill overlay with Stop/Cancel buttons |
| `menu.py` | Ctrl+Win short-press palette (Dictionary, Snippets, Recent, Settings (stub)) |
---
## Documentation
All canonical documentation lives in [`docs/`](./docs/):
- [`docs/README.md`](./docs/README.md) — how the docs folder works
- [`docs/PROJECT_SPEC.md`](./docs/PROJECT_SPEC.md) — vision, stack, 
  module map, ADR log
- [`docs/HANDOVER_*.md`](./docs/) — append-only session-by-session 
  deltas (most recent = current state)
- [`docs/LEARNINGS.md`](./docs/LEARNINGS.md) — append-only failure 
  modes and findings
For current build state and what's next, read the latest 
`HANDOVER_*.md` first.
---
## Troubleshooting
**Hotkey not working** — Run as Administrator. The `keyboard` 
library requires elevated privileges for global hooks on Windows.
**Two instances launching at login** — Check that only one of Task 
Scheduler or Startup folder shortcut is active. Running both causes 
duplication. Task Scheduler is the canonical method.
**No audio captured** — Check that your microphone is set as the 
default recording device in Windows Sound settings. Set 
`audio_device` in config to a specific device name or index if 
needed.
**Empty pastes / "you" hallucinations on silence** — Both are 
guarded against (RMS fast-fail and a hallucination blocklist in 
`transcribe.py`). If you see one, raise it via the handover 
workflow.
**Stuck hotkey state** — `hotkey.py` self-heals on the next fresh 
key-down if the prior press is stale. If you suspect a stuck state, 
press and release Ctrl+Win once to reset.
