"""Font loading utilities for game images with emoji support."""

import logging
import os
from pathlib import Path
from PIL import ImageFont

# Font paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
FONT_DIR = PROJECT_ROOT / "data" / "assets" / "fonts"
EMOJI_FONT_PATH = FONT_DIR / "seguiemj.ttf"
PRIMARY_FONT_PATH = FONT_DIR / "arial.ttf"

logger = logging.getLogger(__name__)

def _load_emoji_font(size: int) -> ImageFont.ImageFont:
    """Load emoji-compatible font with fallback: seguiemj.ttf → arial.ttf → Pillow default."""
    for font_path in (EMOJI_FONT_PATH, PRIMARY_FONT_PATH):
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size)
            except OSError:
                continue
    logger.warning("No fonts found, using Pillow default font")
    return ImageFont.load_default()
