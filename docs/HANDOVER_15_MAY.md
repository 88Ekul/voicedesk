# VoiceDesk — Handover, 15 May 2026 (end of session)

---

## Session focus

Two responsiveness fixes — quiet-speech dictation drop-outs (RMS 
threshold and VAD calibration) and Ctrl+Win hotkey timing (sequential-
press staleness and post-dictation cooldown). No new features; both 
fixes addressed long-standing friction points carried forward from 
prior sessions.

---

## Stack & location (unchanged)

- Project: `C:\Users\<user>\Documents\voicedesk`
- Run via Antigravity IDE as Administrator
- Launch command: `python .\main.py --worker` — never without `--worker`
- Auto-starts via Task Scheduler on login with 30–35 second delay
- Stack: faster-whisper (small.en, CPU int8), sounddevice, keyboard, 
  PyQt6, pystray, pyperclip
- Core modules: `main.py`, `audio.py`, `transcribe.py`, `paste.py`, 
  `hotkey.py`, `tray.py`, `config_loader.py`, `text_processing.py`, 
  `overlay.py`, `menu.py`
- Repo: `https://github.com/88Ekul/voicedesk` (private), branch 
  `master`, commits pending (see Repo state)

---

## Done this session

### 1. Quiet-speech dictation fix (five-file change)
The smoking gun was a single log line: `Skipping transcription — RMS 
0.00297 below threshold 0.00300`. A real recording was rejected by 
30 millionths because the configured threshold sat almost exactly at 
the user's normal speaking floor. Five changes applied:

- `config/config.yaml`: `rms_threshold: 0.003 → 0.001`
- `transcribe.py`: VAD `min_speech_duration_ms: 300 → 150`
- `config_loader.py`: fallback default `0.01 → 0.001` (aligned with 
  new config value)
- `main.py`: inline fallback `0.01 → 0.001` (aligned with new config 
  value)
- `main.py`: `Pre-transcription RMS:` log line promoted from DEBUG to 
  INFO for continuous calibration signal on every recording

Verified with three live tests. Normal speech registered 0.0053–0.0068 
(5–7× above new threshold). Quiet speech registered 0.0014–0.0026 — 
values that would have been rejected at the old threshold but now pass 
and transcribe correctly. Silence test (RMS 0.00001) correctly 
rejected.

### 2. Hotkey responsiveness fix (two-line change in `hotkey.py`)
Two issues addressed in one pass:

- **Sequential-press staleness**: the combo freshness window was 
  hardcoded at 500ms, meaning Ctrl pressed more than half a second 
  before Win was rejected as a "stale combo (stuck key?)". Widened to 
  2.0 seconds — generous enough for natural sequential presses, still 
  short enough that a genuinely stuck modifier from minutes ago won't 
  fire.
- **Post-dictation cooldown**: after a hold-release, hotkey events 
  were ignored for 5 seconds (`self._ignore_until = now + 5.0`). This 
  blocked rapid re-dictation when the user remembered something they'd 
  missed. Shortened to 0.5 seconds — long enough to absorb trailing 
  key events, short enough to allow immediate re-dictate.

Verified with three live tests: sequential press (Ctrl, pause, Win) 
now works, rapid re-dictate immediately after release now works, 
simultaneous press (regression check) still works as before.

Note: both changes apply automatically to both hotkeys (`ctrl+win` and 
`alt+win`) because they share the same `HotkeyListener` class and code 
path. If per-hotkey tuning ever becomes desirable, the hardcoded values 
would need to be moved into `start()` parameters and exposed per-
listener.

---

## Pending work — next session

### 1. Ctrl+Win menu submenus ← highest priority (carried from 9 May)
The short-press Ctrl+Win menu has four buttons — Dictionary, 
Snippets, Recent, and Settings — that currently go nowhere. Each 
needs a functional backend:
- **Dictionary**: open `config/corrections.json` in the system 
  default editor
- **Snippets**: open `config/snippets.json` in the system default 
  editor
- **Recent**: show the last 5 transcriptions in a small read-only 
  panel — requires storing transcription history (suggest a rolling 
  JSON log in `config/recent.json`, max 5 entries, written by 
  `_process()` after each successful paste)
- **Settings**: expose key config values inline — at minimum 
  `rms_threshold`, `output_style`, and the filler word list — 
  editable and saveable without touching YAML directly

Start next session by pasting this into the agent panel:
> Read `menu.py` and `main.py` in full without making any changes. 
> The Ctrl+Win menu has four buttons (Dictionary, Snippets, Recent, 
> Settings) that are currently non-functional. Plan how to wire 
> each one up, covering: what each button does, what UI it opens 
> or triggers, and what changes are needed in `menu.py` and 
> `main.py`. Deliver a written plan only — no code until confirmed.

### 2. Whisper initial_prompt / custom vocabulary ← low effort, good accuracy gain (carried)
- Add a `whisper_prompt` field to `config/config.yaml` containing 
  proper nouns, project names, and dialect words
- Pass it to faster-whisper as `initial_prompt` on every 
  transcription call in `transcribe.py`
- Biases the model toward recognising those words without any 
  model changes
- Example: `whisper_prompt: "VoiceDesk, OnCall-Desk, St. Vincent, 
  laggy, lagginess"`
- Hot-reloadable via existing config pattern

### 3. Transcription quality upgrade ← medium priority (carried)
- Current model: small.en (CPU int8) — misrecognises short 
  monosyllables and proper nouns
- Planned upgrade: whisper.cpp + medium.en via Vulkan (GPU) path
- Vulkan path currently failing silently and falling back to CPU — 
  needs investigation
- First step: test `whisper-cli.exe` directly with medium.en to 
  confirm improvement justifies architecture change

### 4. Repo hygiene — untrack auto-generated files ← low priority (carried)
`git status` currently shows tracked files that shouldn't be in 
the repo:
- **`__pycache__/*.pyc`** — auto-generated bytecode, shows as 
  "modified" on every run. Listed in `.gitignore` but committed 
  before the rule was added, so Git still tracks them.
- **`logs/voicedesk.log`** — log file, grows every run. Same 
  history as `__pycache__` — `logs/` is in `.gitignore` but the 
  file was tracked before.

Fix in one commit:

```
git rm -r --cached __pycache__/
git rm --cached logs/voicedesk.log
git commit -m "chore: untrack auto-generated files now covered by .gitignore"
git push
```

Effect: files stay on disk locally but Git stops tracking them. 
`git status` will be clean except for genuine changes.

### 5. Logging housekeeping ← low priority (carried)
- Log level currently DEBUG (enabled for RMS calibration). Revert 
  to INFO once RMS threshold is settled
- Add `if root.handlers: return` guard to `_setup_logging` to 
  prevent duplicate log entries

### 6. Instance lock robustness ← low priority (carried)
- Patch instance lock using `msvcrt` for a more reliable single-
  instance guarantee on Windows

### 7. Quiet-speech tuning — next lever if needed ← new, low priority
If quiet-speech transcription ever proves unreliable in practice, the 
next lever to tune is `min_silence_duration_ms` in `transcribe.py` 
(currently 500ms) — slow or deliberate speech with long pauses may be 
getting chopped into separate segments. The `Pre-transcription RMS:` 
line is now at INFO so calibration data will be available without 
manual log-level changes.

---

## Known issues carried forward

- Halo corner artefacts on menu — faint, cosmetic, low priority
- Orphaned punctuation after filler removal — accepted limitation 
  ("Um, hello" → ", hello")
- Transcription delay between successive recordings — faster-
  whisper has no interrupt mechanism; in-progress transcription 
  cannot be cancelled if a new recording starts. Accepted for now.
- RMS threshold may need adjustment depending on environment — 
  check DEBUG log lines (`Pre-transcription RMS:`) to calibrate

---

## Repo state

- Branch: `master`, commits pending for this session
- Two commits suggested for clean history:
  1. `fix: lower RMS threshold and VAD min_speech_duration for quiet-speech dictation`
  2. `fix: widen hotkey freshness window and shorten post-dictation cooldown`
- `.gitignore` covers: `*.bin`, `*.dll`, `*.exe`, `*.ggml`, 
  `models/`, `temp/`, `logs/`, `__pycache__/`, 
  `config/snippets.json`

---

## How to start the next session

Direct the assistant to read:
1. `docs/PROJECT_SPEC.md` — canonical durable state
2. This file (`docs/HANDOVER_15_MAY.md`) — most recent session 
   detail
3. `docs/LEARNINGS.md` — accumulated lessons

Then paste the Pending item 1 prompt (Ctrl+Win menu submenus) to 
kick off work.

---

## Key operating principles (unchanged)

- Always run as Administrator in Antigravity IDE
- Always use `python .\main.py --worker` — never without `--worker`
- Kill stale instances with `taskkill /F /IM python.exe /T` before 
  relaunching
- `grep` does not exist in PowerShell — use `Select-String` instead
- Verify bug shape in logs before writing any fix
- Read the full relevant method before writing any fix
- Deliver written plan first, no code until confirmed
- Confirm each fix with a live test before moving on
