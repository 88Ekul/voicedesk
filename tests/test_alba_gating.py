import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

import text_processing


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _Signal:
    def connect(self, *_args, **_kwargs):
        pass

    def emit(self, *_args, **_kwargs):
        pass


def _stub_module(name: str) -> types.ModuleType:
    return types.ModuleType(name)


def _load_isolated_main():
    numpy = _stub_module("numpy")
    wavfile = _stub_module("scipy.io.wavfile")
    wavfile.read = lambda *_args, **_kwargs: None

    scipy = _stub_module("scipy")
    scipy.__path__ = []
    scipy_io = _stub_module("scipy.io")
    scipy_io.__path__ = []
    scipy.io = scipy_io
    scipy_io.wavfile = wavfile

    qtcore = _stub_module("PyQt6.QtCore")
    qtcore.QObject = object
    qtcore.QTimer = object
    qtcore.pyqtSignal = lambda *_args, **_kwargs: _Signal()
    qtwidgets = _stub_module("PyQt6.QtWidgets")
    qtwidgets.QApplication = object
    pyqt6 = _stub_module("PyQt6")
    pyqt6.__path__ = []
    pyqt6.QtCore = qtcore
    pyqt6.QtWidgets = qtwidgets

    paste = _stub_module("paste")
    paste.save_to_inbox = lambda *_args, **_kwargs: None
    paste.paste_text = lambda *_args, **_kwargs: None
    overlay = _stub_module("overlay")
    overlay.hide_overlay = lambda: None
    transcribe = _stub_module("transcribe")
    transcribe.transcribe = lambda *_args, **_kwargs: ""
    tray = _stub_module("tray")
    tray.TrayIcon = type("TrayIcon", (), {})
    config_loader = _stub_module("config_loader")
    config_loader.CONFIG_PATH = str(PROJECT_ROOT / "config" / "config.yaml")

    stubs = {
        "audio": _stub_module("audio"),
        "config_loader": config_loader,
        "hotkey": _stub_module("hotkey"),
        "keyboard": _stub_module("keyboard"),
        "menu": _stub_module("menu"),
        "numpy": numpy,
        "overlay": overlay,
        "paste": paste,
        "PyQt6": pyqt6,
        "PyQt6.QtCore": qtcore,
        "PyQt6.QtWidgets": qtwidgets,
        "scipy": scipy,
        "scipy.io": scipy_io,
        "scipy.io.wavfile": wavfile,
        "transcribe": transcribe,
        "tray": tray,
        "winsound": _stub_module("winsound"),
    }

    spec = importlib.util.spec_from_file_location(
        "_voicedesk_main_test", PROJECT_ROOT / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


MAIN = _load_isolated_main()


class AlbaExtractionTests(unittest.TestCase):
    def test_extract_alba_request_cases(self):
        cases = (
            ("Hey Alba, find my notes.", "find my notes."),
            ("Hey Alba find my notes.", "find my notes."),
            ("Alba: find my notes.", "find my notes."),
            ("  hEy aLbA, Find my notes.", "Find my notes."),
            ("An ordinary note.", None),
            ("I want to improve how Alba handles questions.", None),
            ("Albatrosses fly over the sea.", None),
            ("Alba's notes are useful.", None),
            ("Alba\u2019s notes are useful.", None),
            ("But what was the next step?", None),
            ("Alba", None),
            ("Hey Alba!!!", None),
            ("Hey Alba, 42", "42"),
            ("Hey Alba, -42", "-42"),
            ("Hey Alba, .5", ".5"),
            ("Hey Alba, --help", "--help"),
            ("Alba@example.com is the address to save.", None),
            ("Alba/notes is the folder name.", None),
            ("Alba#1 is the label.", None),
        )

        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(text_processing.extract_alba_request(text), expected)


class AlbaRoutingTests(unittest.TestCase):
    def setUp(self):
        MAIN._config = {
            "auto_paste": True,
            "inbox_path": "isolated-test-inbox",
            "rms_threshold": 0.001,
        }

        samples = mock.MagicMock()
        samples.astype.return_value = samples
        MAIN.wav.read = mock.Mock(return_value=(16000, samples))
        MAIN.np.float32 = object()
        MAIN.np.mean = mock.Mock(return_value=1.0)
        MAIN.np.sqrt = mock.Mock(return_value=1000.0)

        self.transcribe = mock.patch.object(
            MAIN.transcribe, "transcribe", return_value="raw transcript"
        ).start()
        self.corrections = mock.patch.object(
            text_processing, "apply_corrections", side_effect=lambda text: text
        ).start()
        self.snippets = mock.patch.object(
            text_processing, "apply_snippets", side_effect=lambda text: text
        ).start()
        self.fillers = mock.patch.object(
            text_processing, "apply_fillers", side_effect=lambda text: text
        ).start()
        self.recent = mock.patch.object(MAIN, "_append_recent").start()
        self.save = mock.patch.object(MAIN.paste, "save_to_inbox").start()
        self.paste = mock.patch.object(MAIN.paste, "paste_text").start()
        self.query = mock.patch.object(MAIN, "_write_query_json").start()
        self.beep = mock.patch.object(MAIN, "_beep").start()
        self.triple_beep = mock.patch.object(MAIN, "_triple_beep").start()
        self.hide_overlay = mock.patch.object(
            MAIN.overlay_module, "hide_overlay"
        ).start()
        self.remove = mock.patch.object(MAIN.os, "remove").start()
        self.logger = mock.patch.object(MAIN, "logger").start()

        self.original_ctypes = MAIN.ctypes
        self.set_foreground = mock.Mock()
        MAIN.ctypes = types.SimpleNamespace(
            windll=types.SimpleNamespace(
                user32=types.SimpleNamespace(
                    SetForegroundWindow=self.set_foreground
                )
            )
        )

        self.addCleanup(mock.patch.stopall)
        self.addCleanup(self._restore_ctypes)

    def _restore_ctypes(self):
        MAIN.ctypes = self.original_ctypes

    def _set_final_text(self, text: str):
        self.transcribe.return_value = text

    def test_inbox_command_saves_then_queries_same_cleaned_text_and_keeps_recent(self):
        self.transcribe.return_value = "raw"
        self.corrections.side_effect = None
        self.corrections.return_value = "corrected"
        self.snippets.side_effect = None
        self.snippets.return_value = "expanded"
        self.fillers.side_effect = None
        self.fillers.return_value = "Hey Alba, find my notes."

        order = mock.Mock()
        order.attach_mock(self.save, "save")
        order.attach_mock(self.query, "query")

        MAIN._process("isolated.wav", "inbox")

        self.corrections.assert_called_once_with("raw")
        self.snippets.assert_called_once_with("corrected")
        self.fillers.assert_called_once_with("expanded")
        self.recent.assert_called_once_with("Hey Alba, find my notes.", "inbox")
        self.assertEqual(
            order.mock_calls,
            [
                mock.call.save("find my notes.", "isolated-test-inbox"),
                mock.call.query("find my notes."),
            ],
        )

    def test_inbox_without_command_saves_original_without_query(self):
        self._set_final_text("An ordinary note.")

        MAIN._process("isolated.wav", "inbox")

        self.save.assert_called_once_with(
            "An ordinary note.", "isolated-test-inbox"
        )
        self.query.assert_not_called()

    def test_inbox_empty_command_saves_original_without_query(self):
        self._set_final_text("Hey Alba!!!")

        MAIN._process("isolated.wav", "inbox")

        self.save.assert_called_once_with("Hey Alba!!!", "isolated-test-inbox")
        self.query.assert_not_called()

    def test_inbox_boundary_rejections_save_original_without_query(self):
        cases = (
            "Alba@example.com is the address to save.",
            "Alba/notes is the folder name.",
            "Alba#1 is the label.",
        )

        for text in cases:
            with self.subTest(text=text):
                self.save.reset_mock()
                self.query.reset_mock()
                self.recent.reset_mock()
                self._set_final_text(text)

                MAIN._process("isolated.wav", "inbox")

                self.save.assert_called_once_with(text, "isolated-test-inbox")
                self.query.assert_not_called()
                self.recent.assert_called_once_with(text, "inbox")

    def test_inbox_save_failure_prevents_query(self):
        self._set_final_text("Alba: find my notes.")
        self.save.side_effect = OSError("isolated save failure")

        MAIN._process("isolated.wav", "inbox")

        self.save.assert_called_once_with(
            "find my notes.", "isolated-test-inbox"
        )
        self.query.assert_not_called()

    def test_non_inbox_routes_do_not_apply_alba_gating(self):
        text = "Hey Alba, find my notes."
        self._set_final_text(text)

        with mock.patch.object(
            text_processing,
            "extract_alba_request",
            wraps=text_processing.extract_alba_request,
        ) as extract:
            for mode in ("dictate", "inbox_fallback", "inbox_and_paste"):
                with self.subTest(mode=mode):
                    for effect in (
                        self.recent,
                        self.save,
                        self.paste,
                        self.query,
                        self.triple_beep,
                        self.set_foreground,
                        extract,
                    ):
                        effect.reset_mock()

                    paste_hwnd = 123 if mode == "dictate" else None
                    MAIN._process("isolated.wav", mode, paste_hwnd=paste_hwnd)

                    self.recent.assert_called_once_with(text, mode)
                    self.query.assert_not_called()
                    extract.assert_not_called()

                    if mode == "dictate":
                        self.save.assert_not_called()
                        self.paste.assert_called_once_with(text, auto_paste=True)
                        self.set_foreground.assert_called_once_with(123)
                    else:
                        self.save.assert_called_once_with(
                            text, "isolated-test-inbox"
                        )
                        self.paste.assert_not_called()


def tearDownModule():
    MAIN._process_executor.shutdown(wait=False)


if __name__ == "__main__":
    unittest.main()
