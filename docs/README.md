# VoiceDesk — Documentation Folder

Canonical documentation for VoiceDesk. Mirrors the four-layer pattern 
used by Second-Brain-OS.

## How this folder works

Four layers of documentation, each with a distinct role.

### 1. Canonical spec — durable
`PROJECT_SPEC.md` holds vision, stack, rules, module map, and an 
append-only architecture decisions log. Does not hold current build 
status or session-specific prose. Updated only when architecture or 
rules change.

### 2. Feature specs — durable per feature
Files like `FEATURE_X_SPEC.md` hold design specs for specific 
components. Scoped, durable, updated when the component's design 
evolves. None exist yet.

### 3. Handovers — append-only session history
`HANDOVER_DD_MMM.md` files capture session deltas. One per significant 
session. Never edited after the date. The most recent is the source of 
truth for current detailed state.

### 4. Learnings log — append-only knowledge
`LEARNINGS.md` captures failure modes, surprising findings, null 
results. Triggered explicitly ("log this learning"). Kept short.

## How to start a new chat for VoiceDesk

Direct the assistant to read this folder at session start. Specifically:
- `PROJECT_SPEC.md` for canonical state
- The latest `HANDOVER_*.md` for current detail
- `LEARNINGS.md` for accumulated findings

## Discipline

Append-only for handovers, ADRs, and learnings. Old handovers do not 
get edited. Old ADRs do not get rewritten. Old learnings stay. This 
creates an audit trail.
