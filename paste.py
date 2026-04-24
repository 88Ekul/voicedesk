"""Clipboard save/restore, auto-paste, and inbox save."""

import datetime
import logging
import os
import time

import keyboard
import pyperclip

logger = logging.getLogger(__name__)


def paste_text(text: str, auto_paste: bool = True) -> None:
    """Write text to the clipboard and optionally paste it into the active window.

    Saves the current clipboard contents before writing, then restores them
    after sending Ctrl+V so the user's prior clipboard data is not lost.

    Args:
        text: The transcribed text to paste.
        auto_paste: If True, send Ctrl+V to the active window after copying.
    """
    try:
        original = pyperclip.paste()
    except Exception:
        original = ""
        logger.warning("Could not read current clipboard contents.")

    try:
        pyperclip.copy(text)
        logger.info("Copied transcription to clipboard (%d chars)", len(text))

        if auto_paste:
            # Small delay ensures the clipboard is ready before sending the key.
            time.sleep(0.05)
            keyboard.send("ctrl+v")
            logger.info("Sent Ctrl+V to active window")
            # Wait for the paste to complete before restoring the clipboard.
            time.sleep(0.1)
    finally:
        try:
            pyperclip.copy(original)
            logger.debug("Clipboard restored to original contents")
        except Exception:
            logger.warning("Could not restore clipboard contents.")


def save_to_inbox(text: str, inbox_path: str) -> str:
    """Write *text* as a dated Markdown file inside *inbox_path*.

    Args:
        text: Transcript to save.
        inbox_path: Directory path.  Created if it does not exist.

    Returns:
        Absolute path of the file that was written.
    """
    os.makedirs(inbox_path, exist_ok=True)
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M")
    date_str = now.strftime("%Y-%m-%d %H:%M")
    filepath = os.path.join(inbox_path, f"{timestamp}_voice-note.md")
    frontmatter = f"---\ndate: {date_str}\nsource: voicedesk\ntype: voice-note\n---\n\n"
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(frontmatter + text)
    logger.info("Transcript saved to inbox: %s (%d chars)", filepath, len(text))
    return filepath
