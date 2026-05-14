# VoiceDesk — Handover, 14 May 2026 (end of session)

---

## Session focus

Documentation system overhaul. No code changes to the application 
itself. Created a four-layer documentation pattern mirroring the 
Second-Brain-OS approach, rewrote the stale root README, and pushed 
everything to GitHub.

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
  `master`, clean working tree

---

## Done this session

### 1. Four-layer documentation system created
New `docs/` folder at the repo root, mirroring the Second-Brain-OS 
pattern. Four files:

- **`docs/README.md`** — explains how the docs folder works and the 
  four-layer pattern
- **`docs/PROJECT_SPEC.md`** — canonical durable spec: vision, 
  stack, module map, rules, append-only ADR log seeded with ten 
  architecture decisions already made (ADR-001 through ADR-010)
- **`docs/HANDOVER_09_MAY.md`** — previous handover committed 
  verbatim
- **`docs/LEARNINGS.md`** — append-only failure modes and findings, 
  seeded with nine durable lessons (verify bug shape in logs, 
  Gemini limits for causation, `QTimer.singleShot` cross-thread 
  failure, `QGraphicsDropShadowEffect` on translucent windows, 
  Windows foreground-stealing prevention, Task Scheduler + Startup 
  folder duplication, RMS threshold calibration, DPI scaling 
  pixel-coordinate mismatch, `print(..., flush=True)` as isolation 
  tool)

**Discipline:** handovers, ADRs, and learnings are append-only. 
Old ones do not get edited. New session = new handover file.

### 2. Root README.md rewritten
Previous README (dated 5 April) described a Vulkan/whisper.cpp 
build with toggle-hotkey behaviour that no longer matched reality. 
Rewritten from scratch to cover:
- Push-to-talk behaviour (hold Ctrl+Win, release to transcribe)
- Current CPU faster-whisper stack (Vulkan/medium.en noted as 
  planned, not active)
- Mandatory `--worker` launch flag
- Full module table including `overlay.py`, `menu.py`, 
  `text_processing.py`
- Text-processing pipeline section (corrections → snippets → 
  fillers)
- Stop/Cancel buttons on overlay
- RMS silence fast-fail
- Pointer to `docs/` for canonical documentation

### 3. Vault pointer created
`C:\path\to\your\vault\02_Areas\
VoiceDesk\README.md` — thin pointer file only. Names the repo's 
`docs/` folder as the canonical location and explains why no 
duplicate content lives in the vault (drift avoidance). Maintains 
PARA structure symmetry with Second-Brain-OS without splitting the 
source of truth.

### 4. All work committed and pushed
Commit: `47909fc` on `master`. Five files added, root README 
modified. Pushed to GitHub successfully.

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

### 4. Repo hygiene — untrack auto-generated files ← new, low priority
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

- Branch: `master`, fully pushed, clean working tree (apart from 
  the auto-generated file noise flagged in Pending item 4)
- Last commit: `47909fc` — "docs: add four-layer documentation 
  system, rewrite root README"
- `.gitignore` covers: `*.bin`, `*.dll`, `*.exe`, `*.ggml`, 
  `models/`, `temp/`, `logs/`, `__pycache__/`, 
  `config/snippets.json`

---

## How to start the next session

Direct the assistant to read:
1. `docs/PROJECT_SPEC.md` — canonical durable state
2. This file (`docs/HANDOVER_14_MAY.md`) — most recent session 
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
