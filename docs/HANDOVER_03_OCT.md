# VoiceDesk — Handover, 3 October 2026

Continuing from HANDOVER_24_SEP.md. A2 Alba-prefix gating is now committed. The optional whisper vocabulary prompt is on GitHub master and is not running yet.

## What changed

- Alt+Win Alba-prefix gating is committed: extract_alba_request in text_processing.py, used only on the inbox route in main.py, with tests/test_alba_gating.py. Ctrl+Win is unchanged. ADR-012 is in PROJECT_SPEC.md.
- GitHub master also has the optional whisper_prompt from voicedesk pull request 1, squash commit d7a19192733cae70ea7af42f499abc3b458b4258. An empty or missing prompt leaves transcribe unchanged. It hot-reloads from config.yaml.
- The running VoiceDesk process was not restarted, so it does not have the whisper prompt. Do not restart it unless Luke asks. Do not kill Python by image name.

## Left alone

- Reliability work stays closed unless the Sound output panel or a deaf hook happens again. Use RELIABILITY_CAPTURE_PROTOCOL.md before changing anything.
- Phase 3 after F1 is still F2 Settings tile, then F3 style pass. F1 is merged on GitHub but not loaded in the running process.
