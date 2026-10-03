# VoiceDesk — Handover, 24 September 2026

Superseded for current status by HANDOVER_03_OCT.md.

Continuing from `HANDOVER_16_JUL.md`. A2 Alba-prefix gating is now implemented, covered by isolated automated tests, and live-tested. VoiceDesk remains in active daily use.

## Project and runtime

- Project: `C:\Users\luke_\Documents\voicedesk`
- Branch: `master` (per the canonical project state; no Git command was run for this documentation step)
- Luke reports no recent recurrence of stuck keys. This does not prove that the earlier deaf-hook failure is mathematically eliminated; do not reopen reliability work unless fresh symptoms recur.
- Controlled restart on 24 September:
  - Old worker PID: `91864`
  - Executable: `C:\Users\luke_\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe`
  - Replacement worker PID: `44324`
  - Launched through Scheduled Task `VoiceDesk`; its action uses `main.py --worker`
- Current source logging is `INFO`. The running process's effective logging level was not independently introspected.

## A1 — trigger-word test

- A1 used real VoiceDesk output to select a practical first rule; it did not establish a measured recognition-success percentage.
- `Hey Alba` is the recommended spoken command. Bare `Alba` is also accepted.
- There are no fuzzy aliases such as `But`.
- Mid-sentence `Alba` and longer words do not trigger.
- Accepted reserved-prefix trade-off: a note beginning `Alba is...` is treated as a command.

## A2 — implementation

- `text_processing.py` provides `extract_alba_request(text)`.
- `main.py` calls it only inside the `mode == "inbox"` route.
- An ordinary Alt+Win capture saves the original processed text as a Markdown note only.
- A recognised `Hey Alba` or `Alba` command with a remaining request strips only the command and its separators, saves the cleaned text as Markdown, then writes one query JSON using that same cleaned text. Existing note-before-query ordering is retained.
- A trigger-only capture such as `Alba` saves the original non-empty processed text and emits no empty query.
- Ctrl+Win and every non-inbox route remain unchanged.
- The query schema remains `query_text`, `captured_at`, and `source`.
- No Second Brain code was changed.

### Matching rule

- Matching applies only at the beginning of the final processed Alt+Win transcript.
- Matching is case-insensitive and permits leading whitespace.
- Accepted prefixes are `Hey Alba` and `Alba`.
- A prefix is recognised only at end of text or before an explicit separator: whitespace, comma, full stop, colon, semicolon, exclamation mark, question mark, en dash, em dash, or hyphen.
- Possessives and non-command continuations are rejected, including `Alba's...`, `Alba’s...`, `Alba@example...`, `Alba/...`, `Alba#...`, and `Albatrosses...`.
- Separator removal preserves content-bearing request punctuation, including `-42`, `.5`, and `--help`.
- A request remains only when the cleaned text contains at least one alphanumeric character.
- Matching is deterministic; there is no fuzzy matching or AI intent detection.

## Automated verification

Command reported:

```powershell
python -m unittest discover -s tests -p "test_alba_gating.py" -v
```

- 7 test methods passed.
- 25 table-driven subtest cases were covered.
- Tests exercised the production helper and `_process()` routing with external effects mocked. They did not write to real inboxes or contact Second Brain.

## Live acceptance results

1. **Ctrl+Win regression:** Luke dictated `Hey Alba, this is an ordinary dictation test`; normal dictation preserved the prefix.
2. **Ordinary Alt+Win note:** `This is a test note about a blue notebook.` was saved as Markdown. Capture-specific log evidence supported that the query writer did not run.
3. **Recognised Alba query:** Luke spoke `Hey Alba, find my note(s) about a blue notebook.` The processed capture was `Hey Alba, find my notes about Blue Notebook.` and the saved body was `find my notes about Blue Notebook.` One query JSON write was logged. The consumer processed and deleted that same query file, and its log reported `query_text` matching the saved body. The raw JSON was consumed before inspection, so the exact `captured_at` and `source` values for this capture were not directly verified. The exact generated answer was not retained.
4. **Trigger-only:** Processed `Alba` was saved unchanged as Markdown. Capture-specific evidence supported that the query writer was not invoked.
5. **Possessive rejection:** The planned live `Alba's notes are useful` boundary case was not exercised because speech recognition produced `I hope there's notes useful`. That altered text was safely saved as an ordinary note with no query. Automated tests cover both literal possessive forms, but the exact live possessive boundary remains unexercised.

## Blue-notebook timing investigation

- The original blue-notebook note was recorded at local `00:58`; its filename, date header, and filesystem evidence agree.
- The later question was recorded at local `01:17`.
- The query filename used UTC and correctly corresponded to `01:17` UK local time.
- The retained evidence shows that the retrieved record was the original `00:58` note, not the later question note.
- No timezone bug was demonstrated.
- The exact generated Alba answer was not retained.
- Current retrieval context exposes the timestamp through the filename rather than explicit created metadata. No metadata redesign is part of this checkpoint.

## Current status

- A2 Alba gating is functionally complete and live-tested.
- One literal live possessive-boundary case remains unexercised because transcription did not preserve the intended phrase.
- VoiceDesk remains usable and Luke is actively using it.
- Do not reopen reliability work unless fresh symptoms recur.

## Next work

- Optional future decision: whether to improve answer auditability or timestamp metadata on the Second Brain side.
- Then return to the existing VoiceDesk Phase 3 roadmap rather than inventing new Alba features.
- Neither item is scheduled or implemented by this documentation checkpoint.
