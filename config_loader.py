"""Loads and validates config/config.yaml using ruamel.yaml."""

import os
from ruamel.yaml import YAML

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.yaml")

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

    return config


def save_output_style(style: str, path: str = CONFIG_PATH) -> None:
    """Persist output_style to config.yaml without disturbing other keys or comments."""
    yaml = YAML()
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.load(f)
    data["output_style"] = style
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
