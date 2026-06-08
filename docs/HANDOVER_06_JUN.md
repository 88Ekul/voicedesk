# VoiceDesk — Handover, 6 June 2026

Continuing from `HANDOVER_15_MAY.md`. Step 11 (Second-Brain-OS 
Alt+Win handoff) is now the immediate next task, promoted above 
the Ctrl+Win menu submenus. All fixes and pending items from 15 
May carry forward unchanged unless noted below.

---

## Stack & location (unchanged)

- Project: `C:\Users\<user>\Documents\voicedesk`
- Run via Antigravity IDE as Administrator
- Launch command: `python .\main.py --worker` — never without 
  `--worker`
- Auto-starts via Task Scheduler on login with 30–35 second delay
- Stack: faster-whisper (small.en, CPU int8), sounddevice, 
  keyboard, PyQt6, pystray, pyperclip
- Core modules: `main.py`, `audio.py`, `transcribe.py`, `paste.py`, 
  `hotkey.py`, `tray.py`, `config_loader.py`, `text_processing.py`, 
  `overlay.py`, `menu.py`
- Repo: `https://github.com/88Ekul/voicedesk` (private), branch 
  `master`

---

## Done this session

No code changes this session. Session used to review project state, 
update documentation to reflect Second-Brain-OS integration 
requirements, and update VoiceDesk project instructions in Claude.

---

## Second-Brain-OS interface — Step 11

Step 11 connects VoiceDesk to the Second-Brain-OS query service 
via the Alt+Win hotkey. This is now the immediate next build item.

### Current Alt+Win behaviour
Transcribes voice and saves a timestamped `.md` file to the 
Second-Brain-OS vault inbox (`00_INBOX`) for the Router to 
classify. This behaviour changes in Step 11.

### New Alt+Win behaviour (to build)
Transcribes voice and writes a JSON query file to the query 
service inbox, triggering a RAG query and spoken response via 
Piper TTS on the Second-Brain-OS side.

### Interface contract
- Drop file to: 
  `C:\path\to\your\query\inbox\`
- Filename: timestamp-based, e.g. `query_20260606_213000.json`
- Schema:
```json
{
  "query_text": "transcribed text here",
  "captured_at": "2026-06-06T21:30:00Z",
  "source": "voicedesk"
}

What VoiceDesk needs to build

* Detect Alt+Win usage vs Ctrl+Win
* For Alt+Win: write JSON to inbox path instead of saving .md to vault
* Confirm query service watchdog is live on Second-Brain-OS side before end-to-end testing
* Coordinate with Second-Brain-OS project chat before building
Second-Brain-OS side status
Steps 8–10 of the query service (watchdog, logging, Task Scheduler) reported complete as of early June 2026. Confirm live status in Second-Brain-OS chat before testing.
Pending work — next session
1. Step 11 — Second-Brain-OS Alt+Win handoff ← immediate
See Second-Brain-OS interface section above. Confirm query service is live first, then build the Alt+Win JSON write.
Start next session with:
Read `docs/PROJECT_SPEC.md` and `docs/HANDOVER_06_JUN.md` in full. Step 11 is the immediate task — Alt+Win should write a JSON query file to `C:\path\to\your\query\inbox\` instead of saving a .md file to the vault. Read `main.py` and `hotkey.py` in full without making changes. Deliver a written plan only — no code until confirmed.
2. Ctrl+Win menu submenus ← high priority (carried)
Deferred below Step 11. Four buttons — Dictionary, Snippets, Recent, Settings — currently go nowhere.

* Dictionary: open `config/corrections.json` in default editor
* Snippets: open `config/snippets.json` in default editor
* Recent: show last 5 transcriptions — rolling JSON log in `config/recent.json`, max 5 entries
* Settings: expose `rms_threshold`, `output_style`, filler list inline, editable without touching YAML
3. Whisper initial_prompt / custom vocabulary (carried)
Low effort, good accuracy gain. Add `whisper_prompt` field to `config/config.yaml`, pass as `initial_prompt` to faster-whisper in `transcribe.py`. Hot-reloadable.
4. Transcription quality upgrade (carried)
Planned upgrade to whisper.cpp + medium.en via Vulkan. Vulkan path currently failing silently. First step: test `whisper-cli.exe` directly with medium.en.
5. Repo hygiene — untrack auto-generated files (carried)

```
git rm -r --cached __pycache__/
git rm --cached logs/voicedesk.log
git commit -m "chore: untrack auto-generated files"
git push

```

6. Logging housekeeping (carried)
Revert log level to INFO once RMS threshold settled. Add `if root.handlers: return` guard to `_setup_logging`.
7. Instance lock robustness (carried)
Patch using `msvcrt` for reliable single-instance guarantee.
8. Quiet-speech tuning — next lever if needed (carried)
If quiet-speech proves unreliable, tune `min_silence_duration_ms` in `transcribe.py` (currently 500ms).
Known issues carried forward

* Halo corner artefacts on menu — faint, cosmetic, low priority
* Orphaned punctuation after filler removal — accepted limitation
* Transcription delay between successive recordings — no interrupt mechanism in faster-whisper, accepted for now
* RMS threshold may need further adjustment — check `Pre-transcription RMS:` lines in log to calibrate
Repo state

* Branch: `master`
* Two commits from 15 May session pending (may already be pushed — verify before next session):
   1. `fix: lower RMS threshold and VAD min_speech_duration for quiet-speech dictation`
   2. `fix: widen hotkey freshness window and shorten post- dictation cooldown`
* `.gitignore` covers: `*.bin`, `*.dll`, `*.exe`, `*.ggml`, `models/`, `temp/`, `logs/`, `__pycache__/`, `config/snippets.json`
How to start the next session

1. Read `docs/PROJECT_SPEC.md`
2. Read this file (`docs/HANDOVER_06_JUN.md`)
3. Read `docs/LEARNINGS.md`
4. Confirm Second-Brain-OS query service is live before building Step 11
5. Paste the Pending item 1 prompt to kick off work
Key operating principles (unchanged)

* Always run as Administrator in Antigravity IDE
* Always use `python .\main.py --worker` — never without `--worker`
* Kill stale instances with `taskkill /F /IM python.exe /T` before relaunching
* `grep` does not exist in PowerShell — use `Select-String`
* Verify bug shape in logs before writing any fix
* Read the full relevant method before writing any fix
* Deliver written plan first, no code until confirmed
* Confirm each fix with a live test before moving on
* Do not run any git commands — commit and push done manually
