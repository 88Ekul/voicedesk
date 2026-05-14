# VoiceDesk — Handover, 9 May 2026 (end of session)

---

## Stack & location

- Project: `C:\Users\<user>\Documents\voicedesk`
- Run via Antigravity IDE as Administrator
- Launch command: `python .\main.py --worker` — never without `--worker`
- Auto-starts via Task Scheduler on login with 30-35 second delay
- Stack: faster-whisper (small.en, CPU int8), sounddevice, keyboard, 
  PyQt6, pystray, pyperclip
- Core modules: `main.py`, `audio.py`, `transcribe.py`, `paste.py`, 
  `hotkey.py`, `tray.py`, `config_loader.py`, `text_processing.py`
- Repo: `https://github.com/88Ekul/voicedesk` (private), branch 
  `master`, clean working tree

---

## Fixed this session

### 1. Stop/cancel buttons on recording overlay
- `overlay.py`: `PILL_W` widened 200→248px, 
  `WA_TransparentForMouseEvents` removed, `stop_clicked`/
  `cancel_clicked` signals added, two circular `QPushButton` children 
  (red ✕ cancel left, green ■ stop right)
- `main.py`: `_terminate_recording(cancel, pinned_hwnd)` is the 
  single convergence point for hotkey release, Stop button, and 
  Cancel button
- `_on_stop_button` captures `_target_hwnd` before spawning worker 
  thread and passes it through to `_process()` as `paste_hwnd`, 
  forcing paste to the original window regardless of focus loss 
  after button click
- Cancel: 220Hz beep, overlay dismisses, audio deleted, nothing pasted
- Stop: transcribes and pastes to pinned HWND

### 2. Custom dictionary (`config/corrections.json`)
- New `text_processing.py` module with `apply_corrections(text)`
- Case-insensitive, word-boundary regex, longest-key-first, single-pass
- mtime hot-reload — changes picked up without restart
- Current entries:
```json
{
  "voice desk": "VoiceDesk",
  "sent Vincent": "St. Vincent",
  "lagi": "laggy",
  "lagy": "laggy",
  "laginess": "lagginess",
  "laggyness": "lagginess"
}
```

### 3. Snippets (`config/snippets.json`)

- `apply_snippets(text)` in `text_processing.py`
- Partial-phrase, word-boundary matching — trigger can sit inside a sentence
- Same mtime hot-reload pattern as corrections
- Currently empty `{}` — user populates as needed
- ⚠️ `config/snippets.json` contains personal data — already in `.gitignore`

### 4. Filler word removal (`config/fillers.json`)

- `apply_fillers(text)` in `text_processing.py`
- Default list: `["um", "uh", "you know", "like", "basically", "literally"]`
- Word-boundary matching, trailing `\s*` swallows post-filler space, whitespace cleanup after substitution
- Same mtime hot-reload pattern
- ⚠️ Known limitation: orphaned punctuation not cleaned (e.g. "Um, hello" → ", hello"). Accepted for now.
- Pipeline order in `_process()`: corrections → snippets → fillers

### 5. RMS pre-transcription fast-fail

- Added to `_process()` in `main.py` before the `transcribe()` call
- Reads saved WAV, computes normalised int16 RMS, skips transcription if below threshold
- Threshold: `rms_threshold: 0.003` in `config/config.yaml` (lowered from 0.01 — 0.01 was rejecting real speech)
- On skip: plays 220Hz low beep, returns immediately, `finally` block cleans up temp file
- DEBUG log line `Pre-transcription RMS: X.XXXXX` on every recording for ongoing calibration
- Fail-open: if WAV read fails, falls through to transcription normally

### 6. Hotkey stuck state self-heal

- `hotkey.py`: self-heal added for stuck `_active=True` — detected on fresh KEY_DOWN if `_active=True` but press is stale (>2× hold threshold with no KEY_UP). Logs WARNING and resets cleanly
- `hotkey.py`: `_held` now cleared in the extra-modifier cancel path, returning listener to fully neutral state
- `hotkey.py`: broadcast-triggered cancel promoted to INFO log when `_active` was True, for future diagnostics
- `main.py`: `_terminating` reset tightened with `try/finally` in `_terminate_recording` and at end of max-duration path in `_record`
- Root cause: Ctrl+Win listener was getting stuck with `_active=True`; Alt+Win unstuck it as a side effect of the broadcast mechanism

### 7. Palette outside-click dismiss — WH_MOUSE_LL hook

- Previous Qt-based approaches (`WindowDeactivate`, `ApplicationDeactivated`, `eventFilter`) all failed on subsequent opens because Windows refuses foreground activation after the first open (foreground-stealing prevention since Win2000)
- Fix: low-level Windows mouse hook (`WH_MOUSE_LL`) installed via `ctypes.windll.user32.SetWindowsHookExW` for the lifetime of each `_PaletteDialog` instance
- Hook watches for `WM_LBUTTONDOWN` anywhere on screen, checks if click falls outside palette geometry, calls `_cancel()` if so
- DPI scaling handled: Qt geometry is device-independent pixels, hook POINT is physical pixels — converted via `devicePixelRatioF()`
- Hook installed in `_start_entry_animation`, uninstalled in `_cancel`
- Entry animation guard (`_entry_complete` flag) prevents dismiss during 200ms fade-in
- Existing Qt dismiss paths kept as defence-in-depth
- All 5 repeatability tests passed (desktop, browser, File Explorer, taskbar, foreign apps)

---

## Repo state

- Branch: `master`, fully pushed, clean working tree
- Last commit: `fix: WH_MOUSE_LL hook for reliable palette outside-click dismiss`
- `.gitignore` covers: `*.bin`, `*.dll`, `*.exe`, `*.ggml`, `models/`, `temp/`, `logs/`, `__pycache__/`, `config/snippets.json`

---

## Pending work — next session

### 1. Ctrl+Win menu submenus ← highest priority
The short-press Ctrl+Win menu has four buttons — Dictionary, Snippets, Recent, and Settings — that currently go nowhere. Each needs a functional backend:

- Dictionary: open `config/corrections.json` in the system default editor so the user can add/edit correction entries
- Snippets: open `config/snippets.json` in the system default editor
- Recent: show the last 5 transcriptions in a small read-only panel — requires storing transcription history (suggest a rolling JSON log in `config/recent.json`, max 5 entries, written by `_process()` after each successful paste)
- Settings: expose key config values inline — at minimum `rms_threshold`, `output_style`, and the filler word list — editable and saveable without touching YAML directly

Start next session by pasting this into the agent panel:
> Read `menu.py` and `main.py` in full without making any changes. The Ctrl+Win menu has four buttons (Dictionary, Snippets, Recent, Settings) that are currently non-functional. Plan how to wire each one up, covering: what each button does, what UI it opens or triggers, and what changes are needed in `menu.py` and `main.py`. Deliver a written plan only — no code until confirmed.

### 2. Whisper initial_prompt / custom vocabulary ← low effort, good accuracy gain

- Add a `whisper_prompt` field to `config/config.yaml` containing proper nouns, project names, and dialect words
- Pass it to faster-whisper as `initial_prompt` on every transcription call in `transcribe.py`
- Biases the model toward recognising those words without any model changes
- Example: `whisper_prompt: "VoiceDesk, OnCall-Desk, St. Vincent, laggy, lagginess"`
- Hot-reloadable via existing config pattern

### 3. Transcription quality upgrade ← medium priority

- Current model: small.en (CPU int8) — misrecognises short monosyllables and proper nouns
- Planned upgrade: whisper.cpp + medium.en via Vulkan (GPU) path
- Vulkan path currently failing silently and falling back to CPU — needs investigation
- First step: test `whisper-cli.exe` directly with medium.en to confirm improvement justifies architecture change

### 4. Logging housekeeping ← low priority

- Log level is currently DEBUG (enabled for RMS calibration). Revert to INFO once RMS threshold is settled
- Add `if root.handlers: return` guard to `_setup_logging` to prevent duplicate log entries

### 5. Instance lock robustness ← low priority

- Patch instance lock using `msvcrt` for a more reliable single-instance guarantee on Windows

---

## Known issues carried forward

- Halo corner artefacts on menu — faint, cosmetic, low priority
- Orphaned punctuation after filler removal — accepted limitation
- Transcription delay between successive recordings — faster-whisper has no interrupt mechanism; in-progress transcription cannot be cancelled if a new recording starts. Accepted for now.
- RMS threshold may need adjustment depending on environment — check DEBUG log lines (`Pre-transcription RMS:`) after dictation sessions to calibrate

---

## Key operating principles

- Always run as Administrator in Antigravity IDE
- Always use `python .\main.py --worker` — never without `--worker`
- Kill stale instances with `taskkill /F /IM python.exe /T` before relaunching
- `grep` does not exist in PowerShell — use `Select-String` instead
- Verify bug shape in logs before writing any fix
- Read the full relevant method before writing any fix
- Deliver written plan first, no code until confirmed
- Confirm each fix with a live test before moving on
