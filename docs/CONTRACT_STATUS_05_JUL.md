# Cross-project note — VoiceDesk ↔ Second Brain OS contract status

**Date:** 5 July 2026.
**Applies to:** VoiceDesk and Second Brain OS (drop a copy in each `docs` folder).
**Supersedes the framing in:** VoiceDesk → Second-Brain-OS convergence note, 8 June 2026.

---

## Status change

The query-JSON contract between VoiceDesk and Second Brain OS is **live, not
frozen.** The 8 June convergence note treated the schema
`{ query_text, captured_at, source }` as fixed. That was premature.

The contract will need to widen once Second Brain's answer-synthesis step is
built, because synthesis may require richer input than `query_text` alone —
likely candidates are a query-type field and/or conversation-threading for
spoken follow-ups. The exact fields are **not** designed yet, and deliberately
so: they cannot be specified until synthesis is built far enough to reveal what
it actually needs. Designing them now would be guessing.

## Sequence agreed (order unchanged, framing corrected)

1. **VoiceDesk — reliability first.** The deaf-hook / watchdog-blindness /
   kill-ritual cluster is independent of the contract and ranks above all
   feature work. The watchdog only restarts on process *exit*; a deaf-hook
   instance stays alive (tray up, mutex held, Qt loop running), so the watchdog
   is structurally blind to it.
2. **VoiceDesk — Alba gating.** Ships under the *current* three-field contract;
   no synthesis dependency. Ends with the trigger-word-set handshake back to
   Second Brain.
3. **Second Brain — answer synthesis.** The structurally-hard project. Building
   this is what reveals what the contract must grow into.
4. **VoiceDesk — second act.** Produce the richer JSON fields the now-built
   synthesiser has told you it needs. Small, because reality has specified it.

The two projects are **not** built in sync. Still one build at a time, still
cleanly decoupled by the contract — the seam widens once, at step 3 → 4, driven
by a concrete need surfaced in building, not by speculation up front.

## Principle to bank in both specs — the contract is append-only

Consumers ignore fields they do not recognise. Second Brain reads `query_text`
and tolerates any additional fields it does not understand; VoiceDesk may add
fields later without breaking the far side. This is what makes the future
widening painless, and is the reason the projects do not need merging.

## Fable 5 implication

Plan VoiceDesk and Second Brain **separately, not in one window.** Planning them
together would force the enriched contract to be designed on speculation — the
exact guessing this sequence avoids. VoiceDesk warrants only a light pass (docs
already strong; the reliability cluster is the payload). Second Brain's
synthesis is the frontier-worthy pass.

## Still open

- Is Second Brain's answer-synthesis reasoning step local, or does it reach a
  cloud model? Determines whether "no cloud" holds for the full user-experienced
  path or only within VoiceDesk. (Left blank pending confirmation from the
  Second Brain side.)