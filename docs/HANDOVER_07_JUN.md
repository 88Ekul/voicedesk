# VoiceDesk — Handover, 7 June 2026

Continuing from `HANDOVER_06_JUN.md`. Step 11 (Second-Brain-OS Alt+Win
handoff) is now complete. Next session begins with Ctrl+Win menu submenus,
which is now the immediate priority.

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
- Repo: `https://github.com/88Ekul/voicedesk` (private), branch `master`

---

## Done this session

### Step 11 — Alt+Win writes query JSON, drops paste

**Behaviour change:** Alt+Win hold previously transcribed, saved a `.md`
to the vault inbox, and pasted at cursor. It now transcribes, saves `.md`
to vault inbox, and writes a JSON query file to the Second-Brain-OS query
inbox. No paste.

Rationale: Alba speaks the answer back via the query service. Pasting the
transcript at cursor was redundant and actively confusing alongside spoken
output.

**Changes to `main.py`:**

1. `_on_hold_inbox()` — `_recording_mode` repointed from `"inbox_and_paste"`
   to `"inbox"`. Docstring updated to reflect no-paste behaviour. The
   `"inbox_and_paste"` mode string survives as the dictate focus-loss
   fallback path only; that branch in `_process()` is untouched.

2. `_write_query_json(text)` — new private helper inserted immediately
   before `_process()`. Reads `query_inbox_path` from config; logs a
   warning and returns early if the key is absent. Creates the directory
   if needed. Writes `query_YYYYMMDD_HHMMSS.json` with schema:
   ```json
   {
     "query_text": "...",
     "captured_at": "<ISO8601 UTC>",
     "source": "voicedesk"
   }

```

Logs the written path at INFO. Entire body wrapped in try/except — logs error, never raises.

1. `_process()` `elif mode == "inbox":` branch — `_write_query_json(text)` called after `paste.save_to_inbox()`, before the two beeps. No other branch is touched.
Changes to `config/config.yaml`:
Added:

```
query_inbox_path: C:\path\to\your\query\inbox

```

Placed immediately below the existing `inbox_path` line.
Test results (7 June 2026):

* Test 1 (10:56 UTC): `.md` saved to vault inbox ✓, JSON written to query inbox ✓, no paste ✓, Alba spoke ✓
* Test 2 (11:05 UTC): `.md` saved to vault inbox ✓, JSON written to query inbox ✓, no paste ✓, Alba silent ✗
Test 2 Alba silence is a Second-Brain-OS side issue — VoiceDesk dropped the file correctly both times. Under investigation in the Second-Brain-OS project chat.
Commit to make:

```
git add main.py config/config.yaml
git commit -m "feat: Step 11 — Alt+Win writes query JSON to Second-Brain-OS inbox, drops paste"

```

Pending work — next session

1. Ctrl+Win menu submenus ← immediate Four buttons — Dictionary, Snippets, Recent, Settings — currently go nowhere. Target behaviour:
   * Dictionary: open `config/corrections.json` in default editor
   * Snippets: open `config/snippets.json` in default editor
   * Recent: show last 5 transcriptions — rolling JSON log in `config/recent.json`, max 5 entries
   * Settings: expose `rms_threshold`, `output_style`, filler list inline, editable without touching YAML
2. Whisper `initial_prompt` / custom vocabulary (carried) Add `whisper_prompt` field to `config/config.yaml`, pass as `initial_prompt` to faster-whisper in `transcribe.py`. Hot-reloadable.
3. Transcription quality upgrade (carried) Upgrade to whisper.cpp + medium.en via Vulkan. Vulkan path currently failing silently. First step: test `whisper-cli.exe` directly with medium.en.
4. Repo hygiene — untrack auto-generated files (carried)

```
git rm -r --cached __pycache__/
git rm --cached logs/voicedesk.log
git commit -m "chore: untrack auto-generated files"
git push

```

5. Logging housekeeping (carried) Revert log level to INFO once RMS threshold settled. Add `if root.handlers: return` guard to `_setup_logging`.
6. Instance lock robustness (carried) Patch using `msvcrt` for reliable single-instance guarantee.
7. Quiet-speech tuning — next lever if needed (carried) If quiet-speech proves unreliable, tune `min_silence_duration_ms` in `transcribe.py` (currently 500ms).
Known issues

* Alba silence on second test — Second-Brain-OS watchdog did not process `query_20260607_100547.json`. Under investigation. VoiceDesk side confirmed clean.
* Mode naming asymmetry — `"inbox"` is the Alt+Win mode (now includes JSON write); `"inbox_and_paste"` survives only as the focus-loss fallback label. Naming no longer maps cleanly to intent. Flagged as technical debt; not worth renaming until a natural refactor opportunity arises.
* Halo corner artefacts on menu palette — cosmetic, low priority, parked.
* Orphaned punctuation after filler removal — accepted limitation.
* Transcription delay between successive recordings — no interrupt mechanism in faster-whisper, accepted for now.
* RMS threshold may need further adjustment — check `Pre-transcription RMS:` lines in log to calibrate.
Repo state

* Branch: `master`
* Commit pending this session: `feat: Step 11 — Alt+Win writes query JSON to Second-Brain-OS inbox, drops paste`
* Previous commits from 15 May session (verify pushed before next session):
   1. `fix: lower RMS threshold and VAD min_speech_duration for quiet-speech dictation`
   2. `fix: widen hotkey freshness window and shorten post-dictation cooldown`
* `.gitignore` covers: `*.bin`, `*.dll`, `*.exe`, `*.ggml`, `models/`, `temp/`, `logs/`, `__pycache__/`, `config/snippets.json`
How to start the next session

1. Read `docs/PROJECT_SPEC.md`
2. Read `docs/HANDOVER_07_JUN.md` (this file)
3. Read `docs/LEARNINGS.md`
4. Read `main.py` and `menu.py` in full before touching anything
5. Immediate task: Ctrl+Win menu submenus — deliver written plan first, no code until confirmed
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
* British English spelling throughout