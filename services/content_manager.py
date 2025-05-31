import logging
import os
from typing import Any, Optional, List, Dict, Union, Tuple

from aiogram import Bot
from aiogram.types import (
    Message, InputMediaPhoto, InputMediaVideo,
    InputMediaDocument, InputMediaAudio, InputMediaAnimation,
    BufferedInputFile # For sending bytes
)
from aiogram.types import FSInputFile # For sending local files by path
from aiogram.exceptions import TelegramAPIError

# Try importing Pillow for watermarking (lazy import)
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None
    logging.warning("Pillow library not found. Watermarking functionality will be disabled. Install with 'pip install Pillow'.")


# Configure logging
logger = logging.getLogger(__name__)


# Configuration constants and limits
MEDIA_DIR = "media_temp"
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Allowed MIME types and their extensions
ALLOWED_MIME_TYPES: Dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "video/mp4": "mp4",
    "image/gif": "gif",
    "application/pdf": "pdf",
    "audio/mpeg": "mp3", # Added common audio type
    "video/quicktime": "mov", # Added common video type
    "image/webp": "webp", # Added webp image format
    # Add other types as needed and supported by Telegram (e.g., webm, avi)
    # Note: Telegram has specific support for different file types.
    # Using send_document is a fallback for unsupported types.
}

# Telegram API limits (re-defined or imported if available elsewhere)
TELEGRAM_MAX_CAPTION_LENGTH_PHOTO_VIDEO_GROUP = 1024 # Used for photos, videos, animations, and documents in media groups
TELEGRAM_MAX_CAPTION_LENGTH_DOCUMENT_SINGLE = 4096 # Used for single documents
TELEGRAM_MAX_MESSAGE_LENGTH = 4096 # Max length for text-only message


def validate_text(text: Optional[str], is_caption: bool = False, is_document_caption: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validates text against Telegram length limits.

    Args:
        text: The text string to validate. Can be None or "-".
        is_caption: If True, validate against caption limit (default 1024).
        is_document_caption: If True AND is_caption is True, validate against document caption limit (4096).

    Returns:
        A tuple (is_valid, error_message_or_none).
    """
    if text is None or text.strip() == "-":
        return True, None # None or "-" is considered valid (no text)

    if not isinstance(text, str):
        return False, "Input is not a string."

    max_len = TELEGRAM_MAX_MESSAGE_LENGTH # Default to message limit

    if is_caption:
        if is_document_caption:
            max_len = TELEGRAM_MAX_CAPTION_LENGTH_DOCUMENT_SINGLE # Use doc limit if specified
        else:
             max_len = TELEGRAM_MAX_CAPTION_LENGTH_PHOTO_VIDEO_GROUP # Use default caption limit

    if len(text) > max_len:
        return False, f"Текст превышает максимально допустимую длину ({max_len} символов)." # Error message in Russian

    return True, None


async def save_media_file(
    bot: Bot,
    file_id: str,
    file_unique_id: str,
    file_name: Optional[str] = None,
    mime_type: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Downloads a media file from Telegram, validates it, and saves it to a temporary directory.

    Args:
        bot: The aiogram Bot instance.
        file_id: The file_id from Telegram.
        file_unique_id: The file_unique_id from Telegram (for unique naming).
        file_name: Optional original file name.
        mime_type: Optional MIME type.

    Returns:
        A dictionary with saved file info ('path', 'type', 'original_name', 'file_id', 'mime_type', 'file_unique_id')
        or None if validation or saving fails.
    """
    try:
        # Ensure media directory exists
        os.makedirs(MEDIA_DIR, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create media directory {MEDIA_DIR}: {e}", exc_info=True)
        return None # Cannot proceed without directory

    logger.debug(f"Attempting to get file info for file_id: {file_id}")
    try:
        file_info = await bot.get_file(file_id)
        file_size = file_info.file_size
        file_path_telegram = file_info.file_path # Path on Telegram servers
        logger.debug(f"Got file info from Telegram: size={file_size}, path={file_path_telegram}, mime_type={mime_type}, file_unique_id={file_unique_id}")

    except TelegramAPIError as e:
        logger.error(f"Failed to get file info for file_id {file_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting file info for file_id {file_id}: {e}", exc_info=True)
        return None


    # Basic validation against max size
    if file_size is None or file_size == 0 or file_size > MAX_FILE_SIZE_BYTES:
        logger.warning(f"File {file_id} skipped due to invalid size: {file_size} bytes (Max {MAX_FILE_SIZE_BYTES})")
        return None # {"error": "File size exceeded or invalid"}

    # Determine file extension and Telegram media type ('photo', 'video', etc.)
    ext = None
    media_telegram_type = None # 'photo', 'video', etc.

    # 1. Try to infer from provided mime_type
    if mime_type:
        if mime_type in ALLOWED_MIME_TYPES:
            ext = ALLOWED_MIME_TYPES[mime_type]
            # Infer media type from MIME prefix
            if mime_type.startswith('image/'):
                 # Telegram treats most images as 'photo', but gif is 'animation'
                 media_telegram_type = 'animation' if mime_type == 'image/gif' else 'photo'
            elif mime_type.startswith('video/'): media_telegram_type = 'video'
            elif mime_type == 'application/pdf': media_telegram_type = 'document'
            elif mime_type.startswith('audio/'): media_telegram_type = 'audio'
        else:
             logger.warning(f"Provided MIME type '{mime_type}' is not in ALLOWED_MIME_TYPES. Attempting inference from file path.")


    # 2. Fallback: Try to infer from Telegram's file_path
    if (not ext or media_telegram_type is None) and file_path_telegram:
        # Get extension from Telegram's file path
        _, path_ext = os.path.splitext(file_path_telegram)
        ext = path_ext.lstrip('.').lower() if path_ext else None

        # Infer type from extension (less reliable)
        if ext in ['jpg', 'jpeg', 'png', 'webp']: media_telegram_type = 'photo'
        elif ext in ['mp4', 'mov']: media_telegram_type = 'video'
        elif ext == 'gif': media_telegram_type = 'animation'
        elif ext == 'pdf': media_telegram_type = 'document'
        elif ext == 'mp3': media_telegram_type = 'audio'
        # Add other common extensions/types if needed

    # 3. Final check for unsupported type
    if not ext or media_telegram_type is None:
        logger.warning(f"File {file_id} skipped due to unknown or unsupported type based on MIME ({mime_type}) or path extension ({ext}).")
        return None # {"error": "Unsupported file type"}


    # Generate a unique local file name using file_unique_id
    local_file_name = f"{file_unique_id}.{ext}"
    local_file_path = os.path.join(MEDIA_DIR, local_file_name)

    logger.debug(f"Downloading file_id {file_id} to {local_file_path}")
    try:
        # Download the file
        await bot.download_file(file_path_telegram, local_file_path)
        logger.info(f"File {file_id} successfully downloaded to {local_file_path}")

        # Return info about the saved file
        return {
            'path': local_file_path,
            'type': media_telegram_type, # e.g., 'photo', 'video'
            'original_name': file_name if file_name else local_file_name, # Keep original name if available
            'file_id': file_id, # Keep Telegram file_id
            'mime_type': mime_type, # Keep original MIME if available
            'file_unique_id': file_unique_id # Keep unique ID
        }

    except TelegramAPIError as e:
        logger.error(f"Failed to download file {file_id} to {local_file_path}: {e}", exc_info=True)
        # Clean up partially downloaded file if it exists
        if os.path.exists(local_file_path):
             try:
                 os.remove(local_file_path)
                 logger.debug(f"Cleaned up partial download {local_file_path}")
             except OSError:
                 pass # Ignore cleanup errors
        return None # {"error": "Failed to download file"}
    except Exception as e:
        logger.error(f"Unexpected error downloading file {file_id}: {e}", exc_info=True)
        if os.path.exists(local_file_path):
             try:
                 os.remove(local_file_path)
                 logger.debug(f"Cleaned up partial download {local_file_path}")
             except OSError:
                 pass # Ignore cleanup errors
        return None # {"error": "Unexpected download error"}


# Note: prepare_media_group is NOT needed here if telegram_api.send_post
# takes the list format produced by this service (list of dicts) and handles
# creating InputMedia objects itself. This was confirmed in vS0zE review.


async def apply_watermark(image_path: str, watermark_text: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Applies a text watermark to an image. Requires Pillow.
    Currently applies a basic watermark to the bottom right.

    Args:
        image_path: Path to the source image file.
        watermark_text: Text to use as the watermark.
        output_path: Optional path to save the watermarked image. If None, overwrites source.

    Returns:
        The path to the watermarked file, or None on failure.
    """
    # Check if Pillow is available
    if Image is None or ImageDraw is None or ImageFont is None:
        logger.warning("Pillow not installed. Cannot apply watermark.")
        return None

    if not os.path.exists(image_path):
        logger.error(f"Image file not found for watermarking: {image_path}")
        return None

    try:
        # Open image and convert to RGBA for transparency layer
        image = Image.open(image_path).convert("RGBA")
        img_width, img_height = image.size

        # Create a transparent layer for the watermark
        watermark_layer = Image.new("RGBA", (img_width, img_height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark_layer)

        # Define font and size (adjust as needed, scale with image size)
        # A smaller font size might be better for small images
        font_size = int(min(img_width, img_height) * 0.04) # Scale font size based on smaller dimension
        if font_size < 10: font_size = 10 # Minimum font size

        try:
            # Try a common font (Arial)
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            # Fallback to default PIL font if Arial is not found
            logger.warning("Arial font not found. Using default PIL font for watermark.")
            # PIL.ImageFont.load_default() returns a font object, not a path.
            # We need to handle this if using the default font, it might not support size scaling easily.
            # For simplicity, let's just use load_default() which is fixed size, or raise error if Truetype is needed.
            # Let's stick to Truetype and require a font or handle the error.
            # A better fallback is to use a font included with Pillow or find one.
            # For demonstration, we'll raise the error if Arial isn't found.
            raise FileNotFoundError("Arial.ttf not found. Please install a common font or specify a font file.")
        except Exception as font_ex:
             logger.error(f"Error loading font for watermark: {font_ex}", exc_info=True)
             return None # Cannot watermark without a font


        # Calculate text size using textbbox
        # The position (0,0) in textbbox is relative to where the text would start drawing
        text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Position (bottom right corner with padding)
        padding = int(min(img_width, img_height) * 0.02) # Padding scales with image size
        position = (img_width - text_width - padding, img_height - text_height - padding)

        # Ensure position is within image bounds (might happen with very long text/small image)
        if position[0] < 0: position = (0, position[1])
        if position[1] < 0: position = (position[0], 0)


        # Add text to the watermark layer with partial transparency (e.g., 128 alpha out of 255)
        # Color white (255,255,255), alpha 128 (approx 50% transparent)
        draw.text(position, watermark_text, font=font, fill=(255, 255, 255, 128))

        # Combine image and watermark layer
        watermarked_image = Image.alpha_composite(image, watermark_layer)

        # Convert back to RGB if saving as JPEG (JPEG does not support alpha channel)
        # Or save as PNG to preserve transparency if original was PNG.
        # Let's save in the original format if possible, or convert to RGB for JPG/JPEG.
        original_format = image.format
        final_path = output_path if output_path else image_path

        if original_format in ['JPEG', 'JPG'] and not (final_path.lower().endswith('.png')):
             # Convert to RGB if saving to JPEG format or overwriting original JPG
             watermarked_image = watermarked_image.convert("RGB")
             # If saving to JPG, specify quality
             watermarked_image.save(final_path, format='JPEG', quality=90) # Adjust quality as needed
        elif original_format == 'PNG':
            # Save as PNG to preserve transparency
             watermarked_image.save(final_path, format='PNG')
        else:
             # For other formats, try saving with the original format or default
             try:
                 watermarked_image.save(final_path, format=original
