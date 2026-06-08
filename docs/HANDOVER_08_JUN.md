# VoiceDesk — Handover, 8 June 2026
Continuing from `HANDOVER_07_JUN.md`. Phase 1 of the Ctrl+Win menu submenus is
complete — Dictionary, Snippets, and Recent tiles are wired up and live-tested.
Next session begins with the Settings tile (inline editor), which is now the
immediate priority.
---
## Stack and location
- Project: `C:\Users\<user>\Documents\voicedesk`
- Run via Antigravity IDE as Administrator
- Launch command: `python .\main.py --worker` — never without `--worker`
- Auto-starts via Task Scheduler on login with 30–35 second delay (`pythonw.exe`)
- Stack: faster-whisper (small.en, CPU int8), sounddevice, keyboard, PyQt6,
  pystray, pyperclip
- Core modules: `main.py`, `audio.py`, `transcribe.py`, `paste.py`, `hotkey.py`,
  `tray.py`, `config_loader.py`, `text_processing.py`, `overlay.py`, `menu.py`
- Repo: `https://github.com/88Ekul/voicedesk` (private), branch `master`
### Repo state (from `git status`, 8 June)
- Branch `master` is **ahead of origin by 1 commit** — the Step 11 commit
  (`feat: Step 11 — Alt+Win writes query JSON…`) is committed but **not yet
  pushed**. Push still pending.
- Today's Phase 1 changes are **uncommitted**: modified `main.py`, `menu.py`,
  `.gitignore`. Plus `config/corrections.json` shows modified (manual edits made
  during live testing).
- `config/recent.json` correctly does **not** appear in status — the new
  `.gitignore` line is working.
- Still tracked and showing as modified (repo-hygiene task not yet done):
  `__pycache__/*.pyc`, `logs/voicedesk.log`.
- Untracked: `docs/HANDOVER_06_JUN.md`, `docs/HANDOVER_07_JUN.md` (not yet added).
---
## Done this session — Phase 1: Ctrl+Win palette tiles wired up
Three of the four palette tiles now perform actions. The fourth (Settings)
remains a deliberate stub. Mechanism for all three live tiles: open the backing
config JSON in the system default editor, creating an empty stub only if the file
is absent.
### Change 1 — `menu.py`
1. Added `import json` and `import os` to the stdlib imports block.
2. Added module-level constant and helper (after the alpha-helper functions,
   before the glyph painters):
   - `_CONFIG_DIR = os.path.dirname(config_loader.CONFIG_PATH)` — single source of
     truth for the config directory, derived from `config_loader`, not re-derived
     from `__file__`.
   - `_open_json_in_editor(filename, default)` — joins `_CONFIG_DIR` + filename;
     if the file is absent, writes `default` as a JSON stub; then `os.startfile(path)`
     to shell-open in the default editor (non-blocking).
3. Replaced the `_on_tile` stub on the dialog with a dispatch:
   - `_TILE_FILES` class attribute maps `dictionary → corrections.json {}`,
     `snippets → snippets.json {}`, `recent → recent.json []`.
   - `_on_tile` looks up the tile id; if mapped, opens the file (try/except →
     logs a warning, never crashes); if unmapped (`settings`), logs
     "not yet implemented". All paths call `self._cancel()` to dismiss.
### Change 2 — `main.py`
1. Added `_append_recent(text, mode)` immediately before `_write_query_json`.
   Reads `config/recent.json` (path derived from `config_loader.CONFIG_PATH`),
   prepends a new entry `{text, at (ISO8601 UTC), mode}`, trims to the newest 5,
   writes back with `indent=2, ensure_ascii=False`. Entire body try/except —
   logs a warning, never raises into the pipeline.
2. In `_process()`, inserted a single call `_append_recent(text, mode)` after
   `text = text_processing.apply_fillers(text)` and before the
   `if mode in ("inbox_and_paste", "inbox_fallback"):` branch. This sits after the
   empty-text guard (empties never logged) and before the mode branch (one call
   site covers every mode — dictate, inbox, fallback).
### Change 3 — `.gitignore`
Appended `config/recent.json` (transcription content; same personal-data class as
the already-ignored `config/snippets.json`).
### Live test results (8 June, all passed)
1. Dictionary → `corrections.json` opened in VS Code showing existing entries ✓
2. Snippets → `snippets.json` opened showing `{}` (freshly-created stub) ✓
3. Dictate → Recent → `recent.json` showed the transcription, newest-first ✓
4. Alt+Win note → appeared in `recent.json` with `mode: "inbox"` ✓
5. Settings → palette dismissed cleanly, no error in log ✓
Verified directly (not via Claude Code's self-report): `_TILE_FILES` indentation
correct as a class attribute, `_CONFIG_DIR` sourced from `config_loader.CONFIG_PATH`,
call site correctly placed below the empty guard and before the mode branch.
---
## Pending work — next session
1. **Settings tile — inline editor** ← immediate
   The Settings tile is the last unwired tile. Build an in-palette editor exposing
   `rms_threshold`, `output_style`, and the filler list, editable without opening
   YAML. This is a form-building task (heterogeneous inputs: float, enum, list) —
   its own session by design. Largest of the four submenu tasks.
2. **Recent in-app panel (option 2)** — possible, sequenced before the full Flow
   editors but not committed. Replace the open-in-editor behaviour for Recent with
   a read-only list panel inside the palette (reusing Rose Gold / slate styling) to
   show the last 5 transcriptions natively. Data side already solved — `recent.json`
   logs correctly; only the display panel remains. No urgency.
3. **Full Flow-style in-app editors for Dictionary + Snippets (option 3)** — future,
   explicitly not soon. Add/edit/delete rows for corrections and snippets directly
   in the palette, mirroring Wispr Flow's Dictionary and Snippets panels. Big PyQt
   build, same class of effort as the Settings panel. Deferred under rule-of-three —
   build only once raw-JSON editing in VS Code proves annoying in daily use.
4. **Repo hygiene — untrack auto-generated files (carried)**
   `__pycache__/*.pyc` and `logs/voicedesk.log` are still tracked. Run
   `git rm -r --cached __pycache__/` and `git rm --cached logs/voicedesk.log`,
   then commit. (Manual git — not done in-session.)
5. **Whisper `initial_prompt` / custom vocabulary (carried)**
   Add `whisper_prompt` field to `config.yaml`, pass as `initial_prompt` to
   faster-whisper in `transcribe.py`. Hot-reloadable.
6. **Transcription quality upgrade (carried)**
   Upgrade to whisper.cpp + medium.en via Vulkan. Vulkan path currently failing
   silently. First step: test `whisper-cli.exe` directly with medium.en.
7. **Style processing pipeline (carried, re-scoped)**
   Wire `output_style` from config into transcription output. NOTE re-scope: Wispr
   Flow's Style is rule-based (Formal = caps + punctuation; Casual = caps + less
   punctuation; Very casual = no caps + less punctuation), NOT LLM-based. So this is
   a deterministic casing/punctuation pass in `text_processing.py`, not an AI
   feature — local-first compatible. Achievable without cloud.
8. **Logging housekeeping (carried)** — revert log level to INFO once RMS settled.
9. **Instance lock robustness (carried)** — patch using `msvcrt`.
10. **Quiet-speech tuning (carried)** — tune `min_silence_duration_ms` if needed.
### Explicitly struck from the roadmap
- **Transforms (Wispr Flow's AI rewrite actions — Polish, Prompt Engineer)** — NOT
  building. Requires a cloud LLM in the loop, which contradicts VoiceDesk's
  local-first / no-cloud / no-telemetry principle. If ever wanted, it is a separate
  project, not a VoiceDesk feature.
---
## Known issues
- Mode naming asymmetry — `"inbox"` is the Alt+Win mode; `"inbox_and_paste"`
  survives only as the focus-loss fallback label. Flagged as technical debt; not
  worth renaming until a natural refactor opportunity arises.
- Halo corner artefacts on menu palette — cosmetic, low priority, parked.
- Orphaned punctuation after filler removal — accepted limitation.
- Transcription delay between successive recordings — no interrupt mechanism in
  faster-whisper, accepted for now.
- RMS threshold may need further adjustment — check `Pre-transcription RMS:` lines
  in log to calibrate.
- Recent tile currently opens raw JSON in the default editor rather than a styled
  in-app view — functional but not polished. Addressed by Pending item 2 if/when
  picked up.
---
## Key operating principles (unchanged)
- Always run as Administrator in Antigravity IDE
- Always use `python .\main.py --worker` — never without `--worker`
- Kill stale instances with `taskkill /F /IM python.exe /T` before relaunching
- `grep` does not exist in PowerShell — use `Select-String`
- Verify bug shape in logs before writing any fix
- Read the full relevant method before writing any fix
- Deliver written plan first, no code until confirmed
- Confirm each fix with a live test before moving on
- Do not run any git commands — commit and push done manually
- One task per session — no scope creep
- British English spelling throughout
- Treat Claude Code's claims about file state with scepticism — verify diffs directly
