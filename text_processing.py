"""Post-transcription text transforms: custom dictionary corrections and snippet expansion."""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "config")
_CORRECTIONS_PATH = os.path.join(_CONFIG_DIR, "corrections.json")
_SNIPPETS_PATH = os.path.join(_CONFIG_DIR, "snippets.json")
_FILLERS_PATH = os.path.join(_CONFIG_DIR, "fillers.json")

# Mtime cache: path -> (mtime_float, compiled_pattern | None, lookup_dict)
_cache: dict[str, tuple[float | None, re.Pattern | None, dict[str, str]]] = {}


def _load(path: str) -> tuple[re.Pattern | None, dict[str, str]]:
    """Return (combined_regex, lookup_dict), hot-reloading when the file changes.

    A single alternation regex is used so each position in the text is consumed
    exactly once — prevents a shorter key from re-matching inside text produced
    by a longer key.  Keys are sorted longest-first so regex alternation picks
    the longest match at each position.
    """
    try:
        mtime = os.stat(path).st_mtime
    except FileNotFoundError:
        return (None, {})

    cached_mtime, cached_pattern, cached_lookup = _cache.get(path, (None, None, {}))
    if cached_mtime == mtime:
        return (cached_pattern, cached_lookup)

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw: dict = json.load(fh)
    except json.JSONDecodeError as exc:
        logger.warning("text_processing: could not parse %s: %s — using previous cache", path, exc)
        return (cached_pattern, cached_lookup)

    # Sort longest key first so alternation regex picks the longest match.
    sorted_keys = sorted((k for k in raw if k), key=len, reverse=True)
    if not sorted_keys:
        _cache[path] = (mtime, None, {})
        return (None, {})

    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in sorted_keys) + r")\b",
        re.IGNORECASE,
    )
    lookup = {k.lower(): v for k, v in raw.items() if k}

    _cache[path] = (mtime, pattern, lookup)
    return (pattern, lookup)


def _apply(path: str, text: str, label: str) -> str:
    pattern, lookup = _load(path)
    if pattern is None:
        return text

    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        return lookup[m.group(0).lower()]

    result = pattern.sub(repl, text)
    if count:
        logger.info("text_processing: applied %d %s(s)", count, label)
    return result


def _load_list(path: str) -> re.Pattern | None:
    """Hot-reloading loader for JSON-array files. Returns combined regex or None."""
    try:
        mtime = os.stat(path).st_mtime
    except FileNotFoundError:
        return None

    cached_mtime, cached_pattern, _ = _cache.get(path, (None, None, {}))
    if cached_mtime == mtime:
        return cached_pattern

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        logger.warning("text_processing: could not parse %s: %s — using previous cache", path, exc)
        return cached_pattern

    items = sorted({s for s in raw if isinstance(s, str) and s.strip()}, key=len, reverse=True)
    if not items:
        _cache[path] = (mtime, None, {})
        return None

    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(s) for s in items) + r")\b\s*",
        re.IGNORECASE,
    )
    _cache[path] = (mtime, pattern, {})
    return pattern


def apply_corrections(text: str) -> str:
    """Apply custom-dictionary corrections. Case-insensitive, word-boundary, single-pass."""
    return _apply(_CORRECTIONS_PATH, text, "correction")


def apply_snippets(text: str) -> str:
    """Expand trigger phrases. Case-insensitive, word-boundary, partial-phrase, single-pass."""
    return _apply(_SNIPPETS_PATH, text, "snippet")


def apply_fillers(text: str) -> str:
    """Remove filler words/phrases from text. Case-insensitive, word-boundary, single-pass.

    Known limitation: orphaned punctuation is preserved — e.g. "Um, hello" → ", hello".
    """
    pattern = _load_list(_FILLERS_PATH)
    if pattern is None:
        return text

    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        count += 1
        return ""

    result = pattern.sub(repl, text)
    if count:
        logger.info("text_processing: removed %d filler(s)", count)

    result = re.sub(r" {2,}", " ", result)
    result = re.sub(r" +\n", "\n", result)
    return result.strip()
