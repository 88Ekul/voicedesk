# VoiceDesk — Reliability Capture Protocol

Created: 1 October 2026. Use immediately when dictation misbehaves or hotkeys stop responding. Keep this beside the append-only incident entries in [LEARNINGS.md](LEARNINGS.md).

## Capture before recovery

1. Do not restart VoiceDesk, stop its worker, edit code/config, or change logging first. Record evidence while the affected instance is still running.
2. Note the exact local date/time, timezone/UTC offset, hotkey used, visible symptom, and when normal behaviour returns. Distinguish the incident time from the time of this inspection. Note whether the Sound output panel appeared instead of a paste.
3. Note whether Ctrl+Win and Alt+Win still respond: yes, no, or not tested, with times and visible results. Prefer observations already available; do not provoke repeated shortcuts. If a brief check is needed while the failure persists, use harmless input and record the attempt. Alt+Win can save a note; avoid an Alba-prefixed diagnostic phrase. If VoiceDesk has already recovered, record that rather than trying to recreate the failure.
4. Note whether ordinary keyboard input behaves as if Win is held, such as unexpected Windows shortcuts. Record naturally observed behaviour; do not deliberately trigger shortcuts to prove it.
5. Identify the exact worker and Scheduled Task using the read-only checks below. Record PID, parent PID, executable, complete command line, process creation time, task name/path/state, last run time/result, and configured action/arguments/working directory. Include all matching candidates if there is ambiguity; do not choose one by process name alone.

Run in PowerShell; these commands only inspect state:

```powershell
Get-CimInstance Win32_Process |
    Where-Object { $_.Name -in @('python.exe', 'pythonw.exe') -and $_.CommandLine -match 'main\.py.*--worker' } |
    Select-Object ProcessId, ParentProcessId, ExecutablePath, CommandLine, CreationDate |
    Format-List

$voiceDeskTasks = Get-ScheduledTask -TaskName 'VoiceDesk'
$voiceDeskTasks | Select-Object TaskName, TaskPath, State | Format-List
$voiceDeskTasks | ForEach-Object {
    $_.Actions | Select-Object Execute, Arguments, WorkingDirectory | Format-List
    $_ | Get-ScheduledTaskInfo |
        Select-Object LastRunTime, LastTaskResult, NextRunTime | Format-List
}
```

Match the worker to `C:\Users\luke_\Documents\voicedesk\main.py --worker` and the task action. If the command uses a relative path, corroborate it with the task's working directory; if identity remains ambiguous, do not stop anything. Missing fields or access errors are evidence gaps, not proof that the worker is absent. A Running task or live worker alone does not prove a healthy hotkey listener. Never reuse a PID from a handover.

## Relevant INFO log window

Inspect `C:\Users\luke_\Documents\voicedesk\logs\voicedesk.log` locally. Check rotated `voicedesk.log.1`–`.3` only if the incident crosses a rotation. Capture only the relevant recent window: start with two minutes before and after the incident, then extend only enough to include the affected capture and any observed recovery or later hotkey attempt. Record the actual window and source files. If inspection is immediate, capture what is available and append relevant later activity when observed.

Keep existing INFO logging, including WARNING/ERROR entries and associated exception traces. Redact transcription contents before saving or sharing an extract, including `Transcription (...)`, rejected-hallucination text, and any dictated content in paths or exception messages. Keep timestamps, event labels, modes, character counts, and diagnostic details where safe. Do not copy the full log, clipboard contents, audio, or note bodies.

For the affected attempt, mark each item as observed, absent from the captured window, or unknown:

- Recording started and stopped; any samples/audio file recorded.
- Transcription started and completed, or was skipped/rejected.
- Paste path ran; clipboard population was logged.
- `Sent Ctrl+V to active window` was logged. This proves the send path ran, not that the intended application received the paste.
- Audio/device errors, exceptions, shutdowns, new startup entries, or worker PID changes occurred.
- Later hotkey activity appears, correlated with the timed observations above. Quiet logs without a known attempted hotkey do not establish a deaf hook.

## Classify only what the evidence supports

| Classification | Evidence to record |
| --- | --- |
| Transient stuck/logically-held Win state | Paste send path completed, but Windows behaved as if Win was held; later recovery supports a transient event. INFO alone cannot establish the internal cause or prove the July race recurred. |
| Suspected deaf hook | Worker stays alive while known, timed hotkey attempts fail and corresponding activity is absent. Note whether both hotkeys fail; exclude other plausible causes before calling this confirmed. Log silence alone is insufficient. |
| Audio failure | Capture/device errors or recording failure align with the incident; distinguish RMS rejection or empty transcription from device failure. |
| Process/task failure | Missing or exited worker, restart/PID change, or task launch failure is supported by process/task evidence and logs. |
| Other / undetermined | Evidence is incomplete, conflicting, or supports another failure path. State what is missing rather than forcing a diagnosis. |

Retain a concise dated incident entry in `LEARNINGS.md`: incident/inspection times, observations, worker/task identity, redacted log window or its local location, classification and uncertainty, recovery action (if any), and outcome. Keep any longer redacted extract separately and link it from the entry. Do not create a handover solely for an incident.

## Safe recovery — only after capture

If VoiceDesk has recovered and works normally, no restart or recovery test is needed. If recovery is still needed:

1. Recheck the positively identified VoiceDesk worker's PID, executable, command line, and creation time immediately before stopping it. Stop only that exact PID with `Stop-Process -Id <confirmed-worker-pid> -Force` (replace the placeholder). Never kill all Python processes or use a blanket `taskkill /IM` sweep.
2. Confirm that worker has exited and no other VoiceDesk worker remains. Relaunch through the established Scheduled Task `VoiceDesk`, using its verified task path. Its action must launch `main.py --worker`; the `--worker` flag is mandatory. Do not change the task, add a Startup shortcut, or start a parallel manual instance.
3. Record the new PID, task state and startup log, then check ordinary dictation once with harmless text and note the result.

This follows amended Rule 3 in `PROJECT_SPEC.md`; it supersedes the older blanket-kill wording still present in that document's Launch discipline paragraph.

Do not enable DEBUG by default. Only consider it later as a deliberate, short diagnostic window: it logs keystrokes in plaintext. Plan the capture and handling of sensitive data first, then restore INFO immediately afterwards. This protocol does not authorise a logging change.
