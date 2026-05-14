VoiceDesk — Learnings Log
Append-only. Captures failure modes, surprising findings, things that turned out to be wrong, null results from VoiceDesk development.
Trigger: user says "log this learning" or "log this finding".
Format: dated entry. One short paragraph. "Tried X for Y, expected Z, got W, takeaway is [thing]." Brevity over completeness.
Discipline: signal over volume. Routine successes do not belong here. Only durable lessons worth recalling months later.
Entries
14 May 2026 — Verify bug shape in logs before writing any fix
The double-transcription bug consumed a full day chasing a false thread-race hypothesis. A single `Select-String "Hotkey down"` in the logs would have eliminated the thread-race theory in 30 seconds. Takeaway: before forming any hypothesis about a bug, check the logs for the bug's actual shape.
14 May 2026 — Use `print(..., flush=True)` at suspected call site to separate code-level from log-level doubling
When investigating a "duplicate event" symptom, a raw `print(..., flush=True)` at the suspected call site immediately distinguishes code being called twice from a single call producing two log lines. Takeaway: reach for unbuffered print as a quick isolation tool before architectural debugging.
14 May 2026 — Video-based AI diagnosis is reliable for observable symptoms, not for threading or process architecture causation
Gemini's diagnoses based on screen recordings (dual QWidget instances, singleton failure, watchdog spawning two UIs) were all disproved by runtime evidence. It is reliable for confirming what the user sees on screen. It is not reliable for causation in threading or process architecture. Takeaway: use video AI for symptom confirmation; use log analysis for causation.
14 May 2026 — `QTimer.singleShot(0, fn)` cannot be posted from the keyboard hook thread
The keyboard hook thread has no Qt event loop, so `QTimer.singleShot` posted from it silently fails to fire on the main thread. Use a `QObject` subclass with a `pyqtSignal` connected to a main-thread slot instead. Takeaway: cross-thread Qt marshalling requires a `QObject`/signal mechanism, not `QTimer.singleShot`.
14 May 2026 — `QGraphicsDropShadowEffect` does not work on translucent windows
The effect renders nothing on a window with `WA_TranslucentBackground`. Manual glow painting inside `paintEvent` using offset semi-transparent strokes works. Takeaway: for glow on translucent windows, paint it yourself.
14 May 2026 — Windows refuses foreground activation after first open (foreground-stealing prevention since Win2000)
Qt-based outside-click dismiss approaches (`WindowDeactivate`, `ApplicationDeactivated`, `eventFilter`) work on first open but fail on subsequent opens because Windows will not grant foreground status to the same application twice in quick succession. Use a low-level Windows mouse hook (`WH_MOUSE_LL` via `SetWindowsHookExW`) instead. Takeaway: if a Qt focus or activation behaviour works the first time and breaks afterwards, suspect Windows foreground-stealing prevention.
14 May 2026 — Task Scheduler and Startup folder shortcut launching the same app twice
Both auto-start mechanisms active simultaneously cause VoiceDesk to launch twice on login. Task Scheduler retained for its delay capability; Startup folder shortcut removed. Takeaway: pick one auto-start mechanism per app.
14 May 2026 — RMS threshold 0.01 rejects real speech; 0.003 is calibrated
The initial `rms_threshold` of `0.01` was too aggressive and rejected genuine quiet speech. Lowered to `0.003`. Takeaway: RMS thresholds need empirical calibration with DEBUG logging on real recordings; do not pick a value by intuition.
14 May 2026 — DPI scaling: Qt geometry is device-independent pixels, Win32 hook POINT is physical pixels
The `WH_MOUSE_LL` hook receives mouse coordinates in physical pixels. Qt widget geometry is in device-independent pixels. Comparing them directly produces wrong hit-test results on any display with scaling enabled. Convert via `devicePixelRatioF()` before comparison. Takeaway: any time Win32 coordinates meet Qt coordinates, check DPI scaling first.
