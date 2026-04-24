"""Microphone capture using sounddevice. Outputs 16kHz mono WAV to a temp file."""

import logging
import os
import threading
import uuid

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav

logger = logging.getLogger(__name__)

SAMPLERATE = 16000
CHANNELS = 1
DTYPE = "int16"

# Write temp audio files here instead of %TEMP% so whisper-cli.exe can also
# write its .txt sidecar without hitting Windows Defender Controlled Folder Access.
_TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")

_stop_event = threading.Event()


def record_audio(max_duration: int, device=None, volume_cb=None) -> str:
    """Record audio from the microphone until stopped or max_duration is reached.

    Args:
        max_duration: Maximum recording length in seconds.
        device: Sounddevice input device index or name. None uses the system default.
        volume_cb: Optional callable(rms: float) called with each block's RMS value
            (0.0–1.0 range) for real-time visualisation.  Exceptions are silently
            swallowed so a failing callback never interrupts recording.

    Returns:
        Path to a temporary WAV file containing the recording.
        The caller is responsible for deleting this file.
    """
    _stop_event.clear()
    frames = []
    block_size = SAMPLERATE // 10  # 100ms blocks

    logger.info("Recording started (max %ds, device=%s)", max_duration, device)

    max_blocks = int(max_duration * SAMPLERATE / block_size)

    with sd.InputStream(
        samplerate=SAMPLERATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=device,
        blocksize=block_size,
    ) as stream:
        for _ in range(max_blocks):
            block, _ = stream.read(block_size)
            frames.append(block.copy())
            if volume_cb is not None:
                try:
                    # RMS normalised to 0.0–1.0 for int16 samples.
                    rms = float(
                        np.sqrt(np.mean(block.astype(np.float32) ** 2))
                    ) / 32768.0
                    volume_cb(rms)
                except Exception:  # noqa: BLE001
                    pass
            if _stop_event.is_set():
                break

    if not frames:
        raise RuntimeError("No audio frames captured (recording stopped before first block)")

    audio_data = np.concatenate(frames, axis=0).flatten()
    logger.info("Recording stopped, %d samples captured", len(audio_data))

    os.makedirs(_TEMP_DIR, exist_ok=True)
    tmp_path = os.path.join(_TEMP_DIR, f"rec_{uuid.uuid4().hex}.wav")
    wav.write(tmp_path, SAMPLERATE, audio_data)
    logger.info("Audio written to %s", tmp_path)

    return tmp_path


def stop_recording() -> None:
    """Signal the active recording loop to stop early."""
    _stop_event.set()
