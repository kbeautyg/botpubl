# keyboards/inline_keyboards.py
from typing import Optional, List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData # Import CallbackData


# --- Callback Data Prefixes/Formats ---
# Draft Confirmation (Used in Post Creation FSM)
CB_POST_DRAFT_CONFIRM = 'post_draft:confirm'
CB_POST_DRAFT_EDIT = 'post_draft:edit'
CB_POST_DRAFT_CANCEL = 'post_draft:cancel'

# Schedule Type Selection (Used in Post Creation FSM)
CB_SCHEDULE_TYPE_SINGLE = 'schedule_type:single'
CB_SCHEDULE_TYPE_RECURRING = 'schedule_type:recurring'
CB_SCHEDULE_TYPE_BACK = 'schedule_type:back' # Used by recurring type to go back

# Recurring Type Selection (Used in Post Creation FSM)
CB_RECURRING_TYPE_DAILY = 'recurring_type:daily'
CB_RECURRING_TYPE_WEEKLY = 'recurring_type:weekly'
CB_RECURRING_TYPE_MONTHLY = 'recurring_type:monthly'
CB_RECURRING_TYPE_ANNUALLY = 'recurring_type:annually'
CB_RECURRING_TYPE_BACK = 'recurring_type:back' # Used by weekday selection to go back

# Day of Week Selection (for weekly recurring) (Used in Post Creation FSM)
CB_WEEKDAY_SELECT_PREFIX = 'weekday:select:' # Followed by day code, e.g., 'weekday:select:mon'
CB_WEEKDAY_DONE = 'weekday:done'
CB_WEEKDAY_BACK = 'weekday:back' # Used by this keyboard to go back (likely to recurring type)

# Auto-deletion options (Used in Post Creation FSM)
# Example: 'autodeletion:never', 'autodeletion:after_1_hour', 'autodeletion:after_7_days'
CB_AUTODELETION_PREFIX = 'autodeletion:'
CB_AUTODELETION_NEVER = f'{CB_AUTODELETION_PREFIX}never'
CB_AUTODELETION_AFTER_TIME_PREFIX = f'{CB_AUTODELETION_PREFIX}after_' # e.g. autodeletion:after_1_hour, autodeletion:after_7_days


# Post List Item Actions (Used in Post Management/Inline Buttons handlers)
CB_POST_SELECT_FOR_MANAGE_PREFIX = 'post_manage:select:' # Followed by post_id (used in post_management list)
# Actions on a selected post: Edit/Delete (used in post_management after selection)
CB_POST_ACTION_EDIT = 'post_manage:action:edit'
CB_POST_ACTION_DELETE = 'post_manage:action:delete'
CB_POST_ACTION_BACK_TO_LIST = 'post_manage:back:list'


# Post Delete Confirmation (Used in Post Management/Inline Buttons handlers)
# Using a generic callback data class for confirmation
class ConfirmDeletionCallbackData(CallbackData, prefix="confirm_delete"):
    entity_id: int # ID of the entity being deleted (post or rss feed DB ID)
    confirm: bool # True for yes, False for no
    entity_type: str # 'post' or 'rss' to differentiate


# RSS Feed Item Actions (Used in RSS Integration/Inline Buttons handlers)
CB_RSS_SELECT_FOR_MANAGE_PREFIX = 'rss_manage:select:' # Followed by feed_id (used in inline_buttons list)
# Actions on a selected RSS feed: Delete/Edit Settings (used in inline_buttons after selection)
CB_RSS_ACTION_DELETE = 'rss_manage:action:delete'
CB_RSS_ACTION_EDIT_SETTINGS = 'rss_manage:action:edit'
CB_RSS_ACTION_BACK_TO_LIST = 'rss_manage:back:list'


# RSS Delete Confirmation - Using the generic ConfirmDeletionCallbackData
# Callback will be e.g. confirm_delete:123:True:rss or confirm_delete:456:False:rss

# Post Edit Options (Used in Post Creation/Inline Buttons handlers - shown on preview or after selecting edit)
CB_POST_EDIT_OPTION_PREFIX = 'post_edit_option:'
CB_POST_EDIT_OPTION_CONTENT = f'{CB_POST_EDIT_OPTION_PREFIX}content' # Text and Media
CB_POST_EDIT_OPTION_CHANNELS = f'{CB_POST_EDIT_OPTION_PREFIX}channels'
CB_POST_EDIT_OPTION_SCHEDULE = f'{CB_POST_EDIT_OPTION_PREFIX}schedule' # Schedule type, params, dates
CB_POST_EDIT_OPTION_DELETION = f'{CB_POST_EDIT_OPTION_PREFIX}autodeletion' # Auto-deletion settings
CB_POST_EDIT_OPTION_BACK_TO_PREVIEW = f'{CB_POST_EDIT_OPTION_PREFIX}back_to_preview'


# Generic Buttons (Used across multiple handlers)
# Use specific callback data for 'Назад' and 'Отменить' to indicate context
CB_BUTTON_BACK_PREFIX = 'btn:back:' # e.g., btn:back:post_creation_schedule
CB_BUTTON_CANCEL_PREFIX = 'btn:cancel:' # e.g., btn:cancel:post_creation_main

# Specific cancel data for flows (can use generic prefix)
CB_CANCEL_POST_CREATION = f'{CB_BUTTON_CANCEL_PREFIX}post_creation' # Used in post_creation FSM
CB_CANCEL_RSS_ADD = f'{CB_BUTTON_CANCEL_PREFIX}rss_add' # Used in rss_integration FSM
CB_CANCEL_RSS_FILTER_CHANGE = f'{CB_BUTTON_CANCEL_PREFIX}rss_filter_change' # Used in rss_integration FSM


# Channel Management Callbacks (Used in Channel Management handlers)
class ChannelActionCallbackData(CallbackData, prefix="channel_action"):
    action: str # e.g., 'select_remove', 'select_add'
    channel_db_id: Optional[int] = None # DB ID of the UserChannel entry (for remove)
    channel_tg_id: Optional[int] = None # Telegram chat_id (for add selection confirmation)


# RSS Integration FSM Callbacks (Used in RSS Integration handlers)
CB_RSS_ADD_CHANNELS_SELECT_PREFIX = 'rss_add_channel:select:' # Followed by chat_id (Telegram ID)
CB_RSS_ADD_CHANNELS_CONFIRM = 'rss_add_channels:confirm'
CB_RSS_ADD_CHANNELS_CANCEL = 'rss_add_channels:cancel' # Can use generic cancel? Keep specific for clarity

CB_RSS_ADD_FILTER_SKIP = 'rss_add_filter:skip'

CB_RSS_ADD_FREQUENCY_SELECT_PREFIX = 'rss_add_freq:select:' # Followed by minutes, e.g., 'rss_add_freq:select:60'
CB_RSS_ADD_FREQUENCY_CUSTOM = 'rss_add_freq:custom'

CB_RSS_ADD_CONFIRM = 'rss_add:confirm' # Confirm adding RSS feed after preview
# Edit buttons on RSS Add Preview (use specific edit section prefix)
CB_RSS_ADD_EDIT_SECTION_PREFIX = 'rss_add:edit:' # Followed by section name, e.g., 'rss_add:edit:url'
CB_RSS_ADD_EDIT_CANCEL = 'rss_add:edit:cancel' # Can use generic cancel? Keep specific for clarity


# RSS Set Filter FSM Callbacks (Used in RSS Integration handlers for editing filters of EXISTING feeds)
CB_RSS_SET_FILTER_SELECT_FEED_PREFIX = 'rss_set_filter:select_feed:' # Followed by feed_id
CB_RSS_SET_FILTER_SKIP = 'rss_set_filter:skip' # Skip filter for existing feed
CB_RSS_SET_FILTER_CONFIRM = 'rss_set_filter:confirm' # Confirm filter change for existing feed
CB_RSS_SET_FILTER_CANCEL = 'rss_set_filter:cancel' # Cancel filter change for existing feed


# --- Day Mapping for Weekday Selection ---
WEEKDAYS = {
    'mon': 'Пн',
    'tue': 'Вт',
    'wed': 'Ср',
    'thu': 'Чт',
    'fri': 'Пт',
    'sat': 'Сб',
    'sun': 'Вс',
}


# --- Keyboard Generation Functions ---

# Keyboards for Post Creation FSM
def get_confirm_draft_keyboard() -> InlineKeyboardMarkup:
    """
    Generates keyboard for confirming or editing a post draft (initial preview).
    Кнопки: «✅ Подтвердить», «✏️ Редактировать», «❌ Отменить».
    """
    builder = InlineKeyboardBuilder()
    # These buttons transition to the FSM states defined in handlers/post_creation or other handlers
    builder.button(text="✅ Подтвердить", callback_data=CB_POST_DRAFT_CONFIRM)
    builder.button(text="✏️ Редактировать", callback_data=CB_POST_DRAFT_EDIT) # Leads to selection of what to edit
    builder.button(text="❌ Отменить", callback_data=CB_POST_DRAFT_CANCEL) # Uses a specific cancel data for the flow
    builder.adjust(1) # Stack buttons vertically
    return builder.as_markup()

def get_skip_media_kb() -> InlineKeyboardMarkup:
    """
    Generates keyboard with only 'Пропустить медиа' button.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="⏩ Пропустить медиа", callback_data="skip_media") # Callback handled in post_creation
    # Optional: Add a cancel button? Depends on UX flow. Let's add generic cancel.
    # builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_CANCEL_POST_CREATION))
    builder.adjust(1)
    return builder.as_markup()


def get_channels_selection_kb(channels: List[Dict[str, Any]], selected_ids: List[int], include_cancel: bool = True) -> InlineKeyboardMarkup:
    """
    Generates keyboard for selecting channels for POST CREATION.
    channels: list of dicts with 'chat_id', 'chat_username' (or other display info)
    selected_ids: list of selected chat_ids
    """
    builder = InlineKeyboardBuilder()
    # Callback handled in post_creation FSM
    for channel in channels:
        chat_id = channel.get('chat_id')
        display_name = channel.get('chat_username') or str(chat_id) # Use username or ID for display
        text = f"✅ {display_name}" if chat_id in selected_ids else display_name
        # Use specific callback prefix for POST channel selection
        builder.button(text=text, callback_data=f"post_channel_select_{chat_id}") # Callback handled in post_creation
    builder.adjust(2) # Two channels per row

    # Add confirmation button and optional cancel
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="post_channels_confirm") # Callback handled in post_creation
    )
    if include_cancel:
         # Use a specific cancel callback for this context
         builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_CANCEL_POST_CREATION)) # Callback handled in post_creation
    builder.adjust(2, 1, 1) # Adjust layout: 2 channel buttons per row, then confirm, then cancel
    return builder.as_markup()


def get_schedule_type_keyboard() -> InlineKeyboardMarkup:
    """
    Generates keyboard for selecting post schedule type.
    Кнопки: «Разовый», «Циклический», «Назад».
    """
    builder = InlineKeyboardBuilder()
    # Callbacks handled in post_creation FSM
    builder.button(text="Разовый", callback_data=CB_SCHEDULE_TYPE_SINGLE)
    builder.button(text="Циклический", callback_data=CB_SCHEDULE_TYPE_RECURRING)
    # Add a 'Назад' button if this state is reachable from another state (e.g. preview)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{CB_BUTTON_BACK_PREFIX}post_creation_schedule_type")) # Callback handled in post_creation
    # Add a generic cancel button
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_CANCEL_POST_CREATION))
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_recurring_type_keyboard() -> InlineKeyboardMarkup:
    """
    Generates keyboard for selecting recurring schedule type.
    Кнопки: «Ежедневно», «Еженедельно», «Ежемесячно», «Ежегодно», «Назад».
    """
    builder = InlineKeyboardBuilder()
    # Callbacks handled in post_creation FSM
    builder.button(text="Ежедневно", callback_data=CB_RECURRING_TYPE_DAILY)
    builder.button(text="Еженедельно", callback_data=CB_RECURRING_TYPE_WEEKLY)
    builder.button(text="Ежемесячно", callback_data=CB_RECURRING_TYPE_MONTHLY)
    builder.button(text="Ежегодно", callback_data=CB_RECURRING_TYPE_ANNUALLY)
    # Add a 'Назад' button
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=CB_RECURRING_TYPE_BACK)) # Callback handled in post_creation
    # Add a generic cancel button for the flow
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_CANCEL_POST_CREATION))
    builder.adjust(2, 2, 1, 1) # Two buttons on first two rows, then Back, then Cancel
    return builder.as_markup()


def get_days_of_week_keyboard(selected_days: List[str] = None) -> InlineKeyboardMarkup:
    """
    Generates keyboard for selecting days of the week for weekly recurring.
    Кнопки дней недели («Пн», «Вт», ... «Вс») с возможностью отмечать выбранные
    (например, «✅ Пн»), плюс кнопки «Готово», «Назад».
    selected_days: list of selected day codes (e.g., ['mon', 'wed']).
    """
    builder = InlineKeyboardBuilder()
    selected_days = selected_days if selected_days is not None else []

    # Callbacks handled in post_creation FSM
    for code, name in WEEKDAYS.items():
        text = f"✅ {name}" if code in selected_days else name
        builder.button(text=text, callback_data=f"{CB_WEEKDAY_SELECT_PREFIX}{code}")

    builder.adjust(3, 3, 1) # 3 days per row, then 1 for Sunday

    # Add control buttons
    builder.row(
        InlineKeyboardButton(text="✅ Готово", callback_data=CB_WEEKDAY_DONE), # Callback handled in post_creation
        InlineKeyboardButton(text="⬅️ Назад", callback_data=CB_WEEKDAY_BACK) # Callback handled in post_creation
    )
    # Add a generic cancel button for the flow
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_CANCEL_POST_CREATION))
    builder.adjust(3, 3, 1, 2, 1) # Adjust layout

    return builder.as_markup()


def get_auto_deletion_keyboard() -> InlineKeyboardMarkup:
    """
    Generates keyboard for selecting post auto-deletion options.
    Кнопки: «Не удалять», «Через 1 час», «Через 24 часа», «Через 7 дней», «По дате/времени» (Future), «Назад».
    """
    builder = InlineKeyboardBuilder()
    # Callbacks handled in post_creation FSM
    builder.button(text="Не удалять", callback_data=CB_AUTODELETION_NEVER)
    # Using string values for duration - map these to seconds in handler
    builder.button(text="Через 1 час", callback_data=f"{CB_AUTODELETION_AFTER_TIME_PREFIX}1h") # Use compact codes
    builder.button(text="Через 24 часа", callback_data=f"{CB_AUTODELETION_AFTER_TIME_PREFIX}24h")
    builder.button(text="Через 7 дней", callback_data=f"{CB_AUTODELETION_AFTER_TIME_PREFIX}7d")
    # Add option for specific date/time if needed later - requires another state
    # builder.button(text="По дате/времени", callback_data=f"{CB_AUTODELETION_PREFIX}specific_datetime")

    builder.adjust(1, 2, 1) # Adjust layout

    # Add Back and Cancel buttons
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{CB_BUTTON_BACK_PREFIX}post_creation_autodeletion")) # Example back context
    # Add a generic cancel button for the flow
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_CANCEL_POST_CREATION))
    builder.adjust(1, 2, 1, 1, 1) # Adjust layout: 1, 2, 1, Back, Cancel


    return builder.as_markup()

# Keyboard for Post Management List (shown by /myposts)
def get_post_list_keyboard(posts: List[Any]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком постов пользователя для выбора управления.
    Используется в PostManagement FSM.
    """
    builder = InlineKeyboardBuilder()
    if not posts:
        builder.row(InlineKeyboardButton(text="Нет доступных постов", callback_data="ignore_post_manage_list")) # Dummy button
    else:
        for post in posts:
            # Assuming post object has 'id', 'text' attributes
            caption_preview = post.text[:40] + '...' if post.text and len(post.text) > 40 else post.text
            display_text = f"#{post.id} | {caption_preview if caption_preview else 'Без текста'} | {post.status.value}"
            # Use specific callback prefix for selecting post for management
            builder.button(text=display_text, callback_data=f"{CB_POST_SELECT_FOR_MANAGE_PREFIX}{post.id}")
        builder.adjust(1) # One button per row

    # Add cancel button for the flow (optional, depending on entry point)
    # If this is entered via /myposts, maybe no cancel needed, just /cancel command
    # If entered from main menu button, maybe go back to main menu?
    # Let's assume /cancel command is the way out.
    # builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=f"{CB_BUTTON_CANCEL_PREFIX}post_manage_list"))
    return builder.as_markup()


# Keyboard for Post Management / Inline Buttons Handlers (actions on selected post)
def get_post_action_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора действия над выбранным постом."""
    builder = InlineKeyboardBuilder()
    # Callbacks handled in PostManagement FSM
    builder.button(text="✏️ Редактировать", callback_data=CB_POST_ACTION_EDIT)
    builder.button(text="🗑️ Удалить", callback_data=CB_POST_ACTION_DELETE)
    builder.row(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data=CB_POST_ACTION_BACK_TO_LIST)) # Back to post list
    builder.adjust(2, 1) # Two buttons, then one on next row
    return builder.as_markup()


def get_edit_options_keyboard() -> InlineKeyboardMarkup:
    """
    Generates keyboard for selecting which part of a post to edit (shown after clicking 'Редактировать' on list item).
    Кнопки: «Контент», «Каналы», «Расписание», «Удаление» (автоудаление).
    """
    builder = InlineKeyboardBuilder()
    # Callbacks handled in handlers/post_creation.py (from preview state) or handlers/post_management.py
    builder.button(text="Контент (Текст/Медиа)", callback_data=CB_POST_EDIT_OPTION_CONTENT) # Text/Media
    builder.button(text="Каналы", callback_data=CB_POST_EDIT_OPTION_CHANNELS)
    builder.button(text="Расписание", callback_data=CB_POST_EDIT_OPTION_SCHEDULE)
    builder.button(text="Автоудаление", callback_data=CB_POST_EDIT_OPTION_DELETION) # Corrected name based on FSM state
    builder.adjust(1) # One button per row for clarity
    # Add a "Назад" button to return to the post action menu
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{CB_BUTTON_BACK_PREFIX}post_manage_edit_options")) # Example back context
    builder.adjust(1, 1, 1, 1, 1) # 4 options + Back
    return builder.as_markup()

# Keyboard for Confirmation (Post or RSS deletion)
# get_delete_confirmation_keyboard is already defined above using ConfirmDeletionCallbackData

# Keyboard for RSS List (shown by main menu button "Мои RSS-ленты")
def get_rss_list_keyboard(feeds: List[Any]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком RSS-лент пользователя для выбора управления.
    Используется в InlineButtonsHandler (или новом RSS Management Handler).
    """
    builder = InlineKeyboardBuilder()
    if not feeds:
        builder.row(InlineKeyboardButton(text="Нет доступных RSS-лент", callback_data="ignore_rss_manage_list")) # Dummy button
    else:
        # Callback handled in inline_buttons.py
        for feed in feeds:
            # Assuming feed object has 'id', 'feed_url' attributes
            url_display = feed.feed_url[:50] + '...' if len(feed.feed_url) > 50 else feed.feed_url
            builder.button(text=f"ID {feed.id}: {url_display}", callback_data=f"{CB_RSS_SELECT_FOR_MANAGE_PREFIX}{feed.id}")
        builder.adjust(1) # One button per row

    # Add a back button to main menu? Or just rely on reply keyboard?
    # builder.row(InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_to_main_menu")) # Example
    return builder.as_markup()

# Keyboard for RSS Feed Management Actions (shown after selecting feed from list)
def get_rss_manage_action_keyboard(feed_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора действия над выбранной RSS-лентой."""
    builder = InlineKeyboardBuilder()
    # Callbacks handled in inline_buttons.py
    builder.button(text="⚙️ Настройки (фильтр, частота)", callback_data=f"{CB_RSS_ACTION_EDIT_SETTINGS}:{feed_id}") # Pass feed_id
    builder.button(text="🗑️ Удалить ленту", callback_data=f"{CB_RSS_ACTION_DELETE}:{feed_id}") # Pass feed_id
    builder.row(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data=CB_RSS_ACTION_BACK_TO_LIST)) # Back to RSS list
    builder.adjust(1, 1, 1)
    return builder.as_markup()


# Keyboard for RSS Integration FSM
def get_rss_channels_selection_keyboard(channels: List[Dict[str, Any]], selected_ids: List[int]) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру для выбора каналов для публикации RSS."""
    builder = InlineKeyboardBuilder()
    # Callbacks handled in rss_integration FSM
    for channel in channels:
        chat_id = channel.get('chat_id')
        display_name = channel.get('chat_username') or str(chat_id)
        text = f"✅ {display_name}" if chat_id in selected_ids else display_name
        # Use specific callback prefix for RSS channel selection
        builder.button(text=text, callback_data=f"{CB_RSS_ADD_CHANNELS_SELECT_PREFIX}{chat_id}")
    builder.adjust(2)

    # Add confirmation and cancel buttons
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data=CB_RSS_ADD_CHANNELS_CONFIRM), # Callback handled in rss_integration
        InlineKeyboardButton(text="❌ Отменить", callback_data=CB_RSS_ADD_CHANNELS_CANCEL) # Callback handled in rss_integration
    )
    builder.adjust(2, 1, 1) # Adjust layout
    return builder.as_markup()


def get_rss_frequency_keyboard() -> InlineKeyboardMarkup:
    """Генерирует клавиатуру для выбора частоты проверки RSS."""
    builder = InlineKeyboardBuilder()
    # Predefined options (in minutes) - Callbacks handled in rss_integration FSM
    builder.button(text="15 мин", callback_data=f"{CB_RSS_ADD_FREQUENCY_SELECT_PREFIX}15")
    builder.button(text="30 мин", callback_data=f"{CB_RSS_ADD_FREQUENCY_SELECT_PREFIX}30")
    builder.button(text="60 мин", callback_data=f"{CB_RSS_ADD_FREQUENCY_SELECT_PREFIX}60")
    builder.button(text="2 часа", callback_data=f"{CB_RSS_ADD_FREQUENCY_SELECT_PREFIX}120")
    builder.button(text="6 часов", callback_data=f"{CB_RSS_ADD_FREQUENCY_SELECT_PREFIX}360")
    builder.button(text="12 часов", callback_data=f"{CB_RSS_ADD_FREQUENCY_SELECT_PREFIX}720")
    # Custom frequency button
    builder.button(text="Своя частота", callback_data=CB_RSS_ADD_FREQUENCY_CUSTOM) # Callback handled in rss_integration
    builder.adjust(3, 3, 1)

    # Add cancel button for the flow
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_CANCEL_RSS_ADD)) # Use general RSS add cancel
    builder.adjust(3, 3, 1, 1)
    return builder.as_markup()


def get_rss_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Генерирует клавиатуру для подтверждения деталей RSS ленты перед добавлением."""
    builder = InlineKeyboardBuilder()
    # Callbacks handled in rss_integration FSM
    builder.button(text="✅ Подтвердить и добавить", callback_data=CB_RSS_ADD_CONFIRM) # Confirm adding
    # Edit buttons (use specific edit section prefix)
    builder.button(text="✏️ URL", callback_data=f"{CB_RSS_ADD_EDIT_SECTION_PREFIX}url")
    builder.button(text="✏️ Каналы", callback_data=f"{CB_RSS_ADD_EDIT_SECTION_PREFIX}channels")
    builder.button(text="✏️ Фильтр", callback_data=f"{CB_RSS_ADD_EDIT_SECTION_PREFIX}filter")
    builder.button(text="✏️ Частота", callback_data=f"{CB_RSS_ADD_EDIT_SECTION_PREFIX}frequency")
    builder.adjust(1, 2, 2)

    # Add cancel button for the flow
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_RSS_ADD_EDIT_CANCEL)) # Use specific RSS edit cancel
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()


# Keyboard for RSS Set Filter FSM (editing filter for EXISTING feeds)
def get_rss_list_for_filter_keyboard(feeds: List[Any]) -> InlineKeyboardMarkup: # Use Any for flexibility or define RssFeed type
    """Генерирует инлайн-клавиатуру со списком RSS-лент пользователя для выбора для изменения фильтра."""
    builder = InlineKeyboardBuilder()
    if not feeds:
        # Should not happen if called correctly, but as a fallback
        builder.row(InlineKeyboardButton(text="Нет доступных RSS-лент", callback_data="ignore_rss_set_filter_list")) # Dummy button
    else:
        # Callbacks handled in rss_integration FSM
        for feed in feeds:
            # Assuming feed object has 'id', 'feed_url' attributes
            url_display = feed.feed_url[:50] + '...' if len(feed.feed_url) > 50 else feed.feed_url
            builder.button(text=f"ID {feed.id}: {url_display}", callback_data=f"{CB_RSS_SET_FILTER_SELECT_FEED_PREFIX}{feed.id}")
        builder.adjust(1) # One button per row

    # Add cancel button for the flow
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CB_CANCEL_RSS_FILTER_CHANGE)) # Use specific filter change cancel
    return builder.as_markup()

def get_rss_set_filter_confirmation_keyboard(feed_id: int) -> InlineKeyboardMarkup:
    """Генерирует клавиатуру для подтверждения изменения фильтра для существующей ленты."""
    builder = InlineKeyboardBuilder()
    # Use specific CallbackData for filter confirmation
    builder.button(text="✅ Применить фильтр", callback_data=f"{CB_RSS_SET_FILTER_CONFIRM}:{feed_id}") # Pass feed_id
    builder.button(text="❌ Отменить", callback_data=f"{CB_RSS_SET_FILTER_CANCEL}:{feed_id}") # Pass feed_id
    builder.adjust(2)
    return builder.as_markup()


# Keyboard for Channel Management FSM
def get_channels_list_for_removal_keyboard(channels: List[Any]) -> InlineKeyboardMarkup: # Use Any for flexibility or define UserChannel type
    """
    Generates keyboard with a list of user's channels (UserChannel objects) for selection to remove.
    Uses ChannelActionCallbackData.
    """
    builder = InlineKeyboardBuilder()
    if not channels:
        builder.row(InlineKeyboardButton(text="Нет каналов для удаления", callback_data="ignore_channel_remove")) # Dummy button
    else:
        # Callbacks handled in channel_management FSM
        for channel in channels:
            # Assuming channel object has 'id' (DB PK), 'chat_id' (Telegram ID), 'chat_username'
            display_name = channel.chat_username or str(channel.chat_id)
            # Pass the UserChannel DB ID (channel.id) as entity_id in callback data
            builder.button(text=f"{display_name} (ID: {channel.id})", callback_data=ChannelActionCallbackData(action='select_remove', channel_db_id=channel.id).pack())
        builder.adjust(1) # One channel per row

    # Add cancel button for the flow
    # Use a generic cancel or specific channel management cancel if needed
    # Let's use a generic cancel for now, handled in commands.py or a global handler
    # builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data="channel_remove:cancel")) # Example
    return builder.as_markup()

# get_delete_confirmation_keyboard is used for channel removal confirmation (entity_type='channel')

# Generic Buttons (re-defining functions for clarity, using prefixes defined above)
def get_back_button_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """
    Generates a universal "Назад" button with a specific callback_data.
    callback_data: The callback data for the 'Назад' button.
    """
    builder = InlineKeyboardBuilder()
    # Use the generic back prefix + context
    # Ensure the provided callback_data already has the prefix if needed, or add it here
    # Let's assume the handler provides the full desired callback data string
    builder.button(text="⬅️ Назад", callback_data=callback_data)
    return builder.as_markup()


def get_cancel_button_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """
    Generates a universal "Отменить" button with a specific callback_data.
    callback_data: The callback data for the 'Отменить' button.
    """
    builder = InlineKeyboardBuilder()
    # Use the generic cancel prefix + context
    # Let's assume the handler provides the full desired callback data string
    builder.button(text="❌ Отменить", callback_data=callback_data)
    return builder.as_markup()


# Example Usage (for testing purposes, not part of the final file)
if __name__ == '__main__':
    print("Inline Keyboard functions and CallbackData defined.")
    # Example of packing/unpacking CallbackData
    cb_data_instance = ConfirmDeletionCallbackData(entity_id=123, confirm=True, entity_type='post')
    packed_data = cb_data_instance.pack()
    print(f"Packed ConfirmDeletionCallbackData: {packed_data}")
    unpacked_data = ConfirmDeletionCallbackData.unpack(packed_data)
    print(f"Unpacked ConfirmDeletionCallbackData: {unpacked_data}")

    cb_channel_action = ChannelActionCallbackData(action='select_remove', channel_db_id=456)
    packed_channel_data = cb_channel_action.pack()
    print(f"Packed Channel Action CallbackData: {packed_channel_data}")
    unpacked_channel_data = ChannelActionCallbackData.unpack(packed_channel_data)
    print(f"Unpacked Channel Action CallbackData: {unpacked_channel_data}")

    print("\nConfirm Draft Keyboard:")
    print(get_confirm_draft_keyboard().to_python())
    print("\nSkip Media Keyboard:")
    print(get_skip_media_kb().to_python())
    print("\nChannels Selection Keyboard (Example):")
    mock_channels = [{'chat_id': 101, 'chat_username': 'channel_a'}, {'chat_id': 102, 'chat_username': 'channel_b'}]
    print(get_channels_selection_kb(mock_channels, [101]).to_python())
    print("\nSchedule Type Keyboard:")
    print(get_schedule_type_keyboard().to_python())
    print("\nRecurring Type Keyboard:")
    print(get_recurring_type_keyboard().to_python())
    print("\nDays of Week Keyboard (Mon, Wed selected):")
    print(get_days_of_week_keyboard(selected_days=['mon', 'wed']).to_python())
    print("\nAuto-Deletion Keyboard:")
    print(get_auto_deletion_keyboard().to_python())
    print("\nPost List Keyboard (Example):")
    mock_posts = [type('obj', (object,), {'id': 1, 'text': 'Post 1 text...', 'status': type('enum', (object,), {'value': 'scheduled'})()})()]
    print(get_post_list_keyboard(mock_posts).to_python())
    print("\nPost Action Keyboard:")
    print(get_post_action_keyboard().to_python())
    print("\nEdit Options Keyboard:")
    print(get_edit_options_keyboard().to_python())
    print("\nGeneric Delete Confirmation Keyboard (post_id=123, type=post):")
    print(get_delete_confirmation_keyboard(entity_id=123, entity_type='post').to_python())
    print("\nRSS List Keyboard (Example):")
    mock_rss_feeds = [type('obj', (object,), {'id': 1, 'feed_url': 'http://example.com/rss'})()]
    print(get_rss_list_keyboard(mock_rss_feeds).to_python())
    print("\nRSS Manage Action Keyboard (feed_id=456):")
    print(get_rss_manage_action_keyboard(feed_id=456).to_python())
    print("\nRSS Add Channels Selection Keyboard (Example):")
    mock_rss_channels = [{'chat_id': 201, 'chat_username': 'rss_channel_x'}, {'chat_id': 202, 'chat_id': 202}]
    print(get_rss_channels_selection_keyboard(mock_rss_channels, [202]).to_python())
    print("\nRSS Add Frequency Keyboard:")
    print(get_rss_frequency_keyboard().to_python())
    print("\nRSS Add Confirmation Keyboard:")
    print(get_rss_confirmation_keyboard().to_python())
    print("\nRSS Set Filter List Keyboard (Example):")
    mock_rss_feeds_filter = [type('obj', (object,), {'id': 1, 'feed_url': 'http://example.com/rss'})()]
    print(get_rss_list_for_filter_keyboard(mock_rss_feeds_filter).to_python())
    print("\nRSS Set Filter Confirmation Keyboard (feed_id=789):")
    print(get_rss_set_filter_confirmation_keyboard(feed_id=789).to_python())
    print("\nChannels List for Removal Keyboard (Example):")
    mock_user_channels = [type('obj', (object,), {'id': 10, 'chat_id': -1001, 'chat_username': 'my_channel'})()]
    print(get_channels_list_for_removal_keyboard(mock_user_channels).to_python())
    print("\nGeneric Back Button (callback_data='some_back_data'):")
    print(get_back_button_keyboard(callback_data="some_back_data").to_python())
    print("\nGeneric Cancel Button (callback_data='some_cancel_data'):")
    print(get_cancel_button_keyboard(callback_data="some_cancel_data").to_python())
