# VoiceDesk

Local speech-to-text dictation tool for Windows 11. Press a hotkey to start recording, press again to stop — the transcription is pasted into whatever window is focused.

GPU acceleration uses **Vulkan** (AMD Radeon 860M). No ROCm or CUDA required.

---

## Prerequisites

### 1. whisper.cpp Vulkan binary

Download `whisper-cpp.exe` from the Vulkan Windows binary release:

> **https://github.com/jerryshell/whisper.cpp-windows-vulkan-bin**

Place `whisper-cpp.exe` in the **project root** (same folder as `main.py`).

### 2. Whisper model weights

Download `ggml-medium.en.bin` from Hugging Face:

> **https://huggingface.co/ggerganov/whisper.cpp**

Place the file in the `models/` folder:

```
voicedesk/
  models/
    ggml-medium.en.bin
```

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Configuration

Edit `config/config.yaml` to adjust settings:

| Key | Default | Description |
|-----|---------|-------------|
| `hotkey` | `ctrl+win` | Global toggle hotkey |
| `model` | `medium.en` | Whisper model name |
| `model_path` | `./models/` | Directory containing model weights |
| `vulkan` | `true` | Enable Vulkan GPU acceleration |
| `auto_paste` | `true` | Automatically paste after transcription |
| `max_duration_seconds` | `120` | Maximum recording length |
| `audio_device` | `null` | Input device (null = system default) |
| `fallback_to_cpu` | `true` | Use faster-whisper CPU if whisper.cpp fails |

---

## Usage

```bash
python main.py
```

A grey circle appears in the system tray.

- **Press `Ctrl+Win`** — icon turns red, recording begins
- **Press `Ctrl+Win` again** — recording stops, transcription runs, text is pasted

Logs are written to `logs/voicedesk.log`.

---

## Architecture

| Module | Responsibility |
|--------|---------------|
| `main.py` | Entry point, logging, wires all modules together |
| `config_loader.py` | Loads and validates `config/config.yaml` |
| `audio.py` | Mic capture via sounddevice → 16kHz mono WAV |
| `transcribe.py` | whisper.cpp subprocess (Vulkan) + faster-whisper fallback |
| `paste.py` | Clipboard save/restore + Ctrl+V |
| `tray.py` | pystray system tray icon (idle/recording states) |
| `hotkey.py` | Global toggle hotkey via keyboard library |

---

## Troubleshooting

**Hotkey not working** — Run `main.py` as Administrator (the `keyboard` library requires elevated privileges for global hooks on Windows).

**whisper.cpp not found** — Ensure `whisper-cpp.exe` is in the project root. VoiceDesk will automatically fall back to faster-whisper CPU if the exe is missing and `fallback_to_cpu: true` is set.

**No audio captured** — Check that your microphone is set as the default recording device in Windows Sound settings. Set `audio_device` in config to a specific device name or index if needed.
