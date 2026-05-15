"""Transcription via faster-whisper (CPU int8). Model is loaded once and kept in memory."""

import logging
import os

logger = logging.getLogger(__name__)

# Cached WhisperModel instance — loaded once at startup, reused on every call.
_fw_model = None
_fw_model_name: str | None = None

# Known faster-whisper hallucinations on silent/near-silent audio.
# These are the phrases the model emits when given non-speech input.
_HALLUCINATION_BLOCKLIST = frozenset({
    "you",
    "you.",
    "thank you.",
    "thank you",
    "thanks for watching.",
    "thanks for watching!",
    "thanks for watching",
    "bye.",
    "bye",
    ".",
    "um.",
    "um",
    "uh.",
    "uh",
})


def _get_model(config: dict):
    """Return the cached WhisperModel, loading it on first call."""
    global _fw_model, _fw_model_name
    if _fw_model is None or _fw_model_name != config["model"]:
        from faster_whisper import WhisperModel  # deferred — heavy import

        model_path = os.path.join(
            os.path.dirname(__file__), config["model_path"].lstrip("./")
        )
        logger.info("Loading faster-whisper model '%s' from %s", config["model"], model_path)
        try:
            _fw_model = WhisperModel(
                config["model"],
                device="cpu",
                compute_type="int8",
                download_root=model_path,
                local_files_only=True,
            )
        except Exception:
            logger.info("Local model cache miss — downloading from HuggingFace")
            _fw_model = WhisperModel(
                config["model"],
                device="cpu",
                compute_type="int8",
                download_root=model_path,
            )
        _fw_model_name = config["model"]
        logger.info("faster-whisper model loaded and cached")
    return _fw_model


def warmup(config: dict) -> None:
    """Pre-load the model at startup so the first transcription has no cold-start delay."""
    try:
        _get_model(config)
    except Exception as exc:
        logger.warning("Model warmup failed: %s", exc)


def transcribe(audio_path: str, config: dict) -> str:
    """Transcribe an audio file to text using faster-whisper (CPU int8).

    Uses Silero VAD to strip non-speech segments before transcription, which
    eliminates the common "You" / "Thank you" hallucinations on silent input.

    Args:
        audio_path: Path to the WAV file to transcribe.
        config: Application config dict (from config_loader.load_config).

    Returns:
        Transcribed text string.  Empty string if no speech detected.
    """
    model = _get_model(config)
    logger.info("faster-whisper: transcribing %s", os.path.basename(audio_path))
    segments, info = model.transcribe(
        audio_path,
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": 500,
            "min_speech_duration_ms": 150,
        },
        condition_on_previous_text=False,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()

    # Post-filter: catch residual hallucinations that VAD let through.
    if text.lower().strip() in _HALLUCINATION_BLOCKLIST:
        logger.info(
            "faster-whisper: rejected likely hallucination: %r (audio=%.2fs)",
            text, info.duration,
        )
        return ""

    logger.info(
        "faster-whisper: transcription done (%d chars, audio=%.2fs)",
        len(text), info.duration,
    )
    return text
