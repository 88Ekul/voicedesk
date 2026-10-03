"""Loads and validates config/config.yaml using ruamel.yaml."""

import logging
import os
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.yaml")

# path -> (mtime, last good whisper_prompt). Same mtime pattern as the
# JSON config files in text_processing: re-read only after the file is saved.
_whisper_prompt_cache: dict[str, tuple[float, str]] = {}

REQUIRED_KEYS = [
    "hotkey",
    "model",
    "model_path",
    "auto_paste",
    "max_duration_seconds",
]


def load_config(path: str = CONFIG_PATH) -> dict:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the YAML config file. Defaults to config/config.yaml.

    Returns:
        Configuration as a plain dict.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If any required keys are missing from the config.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    yaml = YAML()
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.load(f)

    if raw is None:
        raise ValueError("Config file is empty.")

    config = dict(raw)

    missing = [key for key in REQUIRED_KEYS if key not in config]
    if missing:
        raise ValueError(f"Config is missing required keys: {', '.join(missing)}")

    config.setdefault("output_style", "formal")
    config.setdefault("rms_threshold", 0.001)
    # Optional. Empty until set, so transcription is unchanged for existing configs.
    config["whisper_prompt"] = _normalise_whisper_prompt(config.get("whisper_prompt", ""))

    return config


def _normalise_whisper_prompt(value) -> str:
    """Return a stripped prompt, or "" when the field is unset.

    Null and non-strings count as unset so a blank field cannot change
    what is passed to faster-whisper.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        logger.warning(
            "config_loader: whisper_prompt must be a string; ignoring %r",
            value,
        )
        return ""
    return value.strip()


def get_whisper_prompt(path: str | None = None) -> str:
    """Return whisper_prompt, hot-reloading when the config file changes.

    Matches the mtime pattern used for corrections, snippets, and fillers:
    the file is re-read only when its modification time changes, and a
    parse failure keeps the previous prompt. Absent, blank, and non-string
    values return "" so callers omit faster-whisper's initial_prompt and
    leave transcription behaviour unchanged.

    Args:
        path: Config file to read. Defaults to config/config.yaml, resolved
            on each call.

    Returns:
        The stripped prompt, or "" when unset.
    """
    if path is None:
        path = CONFIG_PATH

    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return ""

    cached = _whisper_prompt_cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    previous = cached[1] if cached is not None else ""
    try:
        prompt = load_config(path)["whisper_prompt"]
    except Exception as exc:
        logger.warning(
            "config_loader: could not parse %s: %s — using previous whisper_prompt",
            path,
            exc,
        )
        return previous

    _whisper_prompt_cache[path] = (mtime, prompt)
    return prompt


def save_output_style(style: str, path: str = CONFIG_PATH) -> None:
    """Persist output_style to config.yaml without disturbing other keys or comments."""
    yaml = YAML()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.load(f)
    data["output_style"] = style
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
