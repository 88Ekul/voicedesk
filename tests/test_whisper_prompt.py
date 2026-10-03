"""whisper_prompt is optional, hot-reloaded, and omitted from the transcribe call when empty."""

import os
import tempfile
import unittest
from unittest import mock

import config_loader
import transcribe

_REQUIRED = """\
hotkey: ctrl+win
model: small.en
model_path: ./models/
auto_paste: true
max_duration_seconds: 120
"""

# Keyword arguments WhisperModel.transcribe received before this field existed.
_HISTORICAL_KWARGS = {
    "vad_filter": True,
    "vad_parameters": {
        "min_silence_duration_ms": 500,
        "min_speech_duration_ms": 150,
    },
    "condition_on_previous_text": False,
}


class _Segment:
    def __init__(self, text: str) -> None:
        self.text = text


class _Info:
    duration = 1.25


class _FakeModel:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def transcribe(self, audio_path, **kwargs):
        self.calls.append((audio_path, kwargs))
        return [_Segment("hello")], _Info()


class WhisperPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        config_loader._whisper_prompt_cache.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _write(self, body: str, name: str = "config.yaml") -> str:
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_REQUIRED + body)
        return path

    def _bump(self, path: str) -> None:
        later = os.stat(path).st_mtime + 10
        os.utime(path, (later, later))

    def _transcribe(self, path: str, config: dict | None = None) -> dict:
        model = _FakeModel()
        if config is None:
            config = {"model": "small.en", "model_path": "./models/"}
        with mock.patch.object(config_loader, "CONFIG_PATH", path), \
                mock.patch.object(transcribe, "_get_model", return_value=model):
            text = transcribe.transcribe("clip.wav", config)
        self.assertEqual(text, "hello")
        self.assertEqual(model.calls, [("clip.wav", model.calls[0][1])])
        return model.calls[0][1]

    def test_example_and_blank_values_default_to_empty(self) -> None:
        example = os.path.join(
            os.path.dirname(__file__), "..", "config", "config.example.yaml"
        )
        self.assertEqual(config_loader.load_config(example)["whisper_prompt"], "")

        self.assertEqual(config_loader.load_config(self._write(""))["whisper_prompt"], "")
        self.assertEqual(
            config_loader.get_whisper_prompt(self._write('whisper_prompt: ""\n', "empty.yaml")),
            "",
        )
        self.assertEqual(
            config_loader.get_whisper_prompt(self._write('whisper_prompt: "   "\n', "spaces.yaml")),
            "",
        )
        self.assertEqual(
            config_loader.get_whisper_prompt(self._write("whisper_prompt:\n", "null.yaml")),
            "",
        )
        self.assertEqual(
            config_loader.load_config(self._write("whisper_prompt: 3\n", "number.yaml"))["whisper_prompt"],
            "",
        )
        missing = os.path.join(self._tmp.name, "missing.yaml")
        self.assertEqual(config_loader.get_whisper_prompt(missing), "")

    def test_empty_prompt_does_not_alter_transcribe_call(self) -> None:
        cases = (
            ("", "absent.yaml"),
            ('whisper_prompt: ""\n', "empty.yaml"),
            ('whisper_prompt: "  "\n', "spaces.yaml"),
        )
        for body, name in cases:
            with self.subTest(name=name):
                path = self._write(body, name)
                # A prompt left on the startup snapshot must not be passed
                # once the file itself is empty.
                kwargs = self._transcribe(
                    path,
                    {"model": "small.en", "whisper_prompt": "VoiceDesk"},
                )
                self.assertEqual(kwargs, _HISTORICAL_KWARGS)

    def test_prompt_is_passed_and_hot_reloads(self) -> None:
        path = self._write('whisper_prompt: "  VoiceDesk, OnCall-Desk  "\n')
        kwargs = self._transcribe(path)
        self.assertEqual(kwargs["initial_prompt"], "VoiceDesk, OnCall-Desk")
        self.assertEqual(
            {key: value for key, value in kwargs.items() if key != "initial_prompt"},
            _HISTORICAL_KWARGS,
        )

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_REQUIRED + 'whisper_prompt: "St. Vincent"\n')
        self._bump(path)
        self.assertEqual(self._transcribe(path)["initial_prompt"], "St. Vincent")

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_REQUIRED + 'whisper_prompt: ""\n')
        self._bump(path)
        self.assertEqual(self._transcribe(path), _HISTORICAL_KWARGS)

    def test_parse_failure_keeps_previous_prompt(self) -> None:
        path = self._write('whisper_prompt: "VoiceDesk"\n')
        self.assertEqual(config_loader.get_whisper_prompt(path), "VoiceDesk")

        with open(path, "w", encoding="utf-8") as fh:
            fh.write("whisper_prompt: [\n")
        self._bump(path)
        self.assertEqual(config_loader.get_whisper_prompt(path), "VoiceDesk")

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_REQUIRED + 'whisper_prompt: "laggy"\n')
        self._bump(path)
        self.assertEqual(config_loader.get_whisper_prompt(path), "laggy")


if __name__ == "__main__":
    unittest.main()
