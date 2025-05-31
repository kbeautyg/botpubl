# keyboards/reply_keyboards.py

from typing import Optional

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_main_menu_keyboard(preferred_mode: Optional[str] = None) -> ReplyKeyboardMarkup:
    """
    Generates the main menu reply keyboard.

    Args:
        preferred_mode: Reserved parameter for future use.

    Returns:
        ReplyKeyboardMarkup: Main menu keyboard.
    """
    builder = ReplyKeyboardBuilder()
    # Buttons for post creation and management
    builder.row(
        KeyboardButton(text="➕ Новый пост"),
        KeyboardButton(text="🗂 Мои посты")
    )
    # Buttons for channel management
    builder.row(
        KeyboardButton(text="➕ Добавить канал"),
        KeyboardButton(text="🗑 Удалить канал")
    )
    builder.row(
        KeyboardButton(text="📋 Мои каналы"),
        KeyboardButton(text="🕑 Установить часовой пояс")
    )
    # Buttons for RSS integration and help
    builder.row(
        KeyboardButton(text="📰 Добавить RSS"),
        KeyboardButton(text="❓ Помощь")
    )
    # Optional: Add a button for managing RSS feeds (view/delete/edit filter)
    builder.row(KeyboardButton(text="🗞 Мои RSS-ленты"))


    # Reply keyboards typically resize to fit content
    # Use one_time_keyboard=True if the keyboard should hide after one use
    # Use is_persistent=True if the keyboard should always be visible
    return builder.as_markup(resize_keyboard=True)

def get_post_content_keyboard() -> ReplyKeyboardMarkup:
    """
    Generates the reply keyboard for the post content creation step.
    Used after text input, before media input.
    """
    builder = ReplyKeyboardBuilder()
    # Allow adding media or skipping
    builder.row(
        KeyboardButton(text="Добавить медиа"),
        KeyboardButton(text="Пропустить")
    )
    # Allow cancelling the process
    builder.row(
        KeyboardButton(text="Отменить") # This button should be handled by a state-specific or global cancel handler
    )
    return builder.as_markup(resize_keyboard=True)

# Removed get_channel_options_keyboard as per vS0zE review (use inline or main menu)
# Removed get_post_delete_options_keyboard as per vS0zE review (use inline)

def get_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Generates a simple reply keyboard with only a "Отменить" button.
    Useful for flows where only cancellation is possible via reply keyboard.
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="Отменить") # Handled by a state-specific or global cancel handler
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


# Example Usage (optional - can be removed from final file)
if __name__ == '__main__':
    print("Reply Keyboard functions defined.")
    print("\nMain Menu Keyboard:")
    print(get_main_menu_keyboard().to_python())
    print("\nPost Content Keyboard:")
    print(get_post_content_keyboard().to_python())
    print("\nCancel Reply Keyboard:")
    print(get_cancel_reply_keyboard().to_python())
