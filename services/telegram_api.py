import logging
from typing import Any, Optional, List, Union, Tuple

from aiogram import Bot
from aiogram.types import (
    Message, ChatMember, InputMediaPhoto, InputMediaVideo,
    InputMediaDocument, InputMediaAudio, InputMediaAnimation,
    BufferedInputFile # Assuming BufferInputFile is used for bytes, or FSInputFile for paths
)
from aiogram.types import FSInputFile # Need this for sending local files by path
from aiogram.exceptions import (
    TelegramAPIError, MessageToDeleteNotFound, MessageCantBeDeleted,
    UserNotFoundError, TelegramBadRequest
)

# Assuming ContentManagerService is available and has a prepare_content method
# from services.content_manager import ContentManagerService # Import if needed for type hinting prepare_content input


logger = logging.getLogger(__name__)

# Telegram API limits
MAX_CAPTION_LENGTH_PHOTO_VIDEO_GROUP = 1024
MAX_CAPTION_LENGTH_DOCUMENT = 4096 # Although not explicitly used for post text here, good to know


async def send_post(
    bot: Bot,
    chat_id: Union[int, str],
    text: Optional[str], # Full text of the post
    media_files: Optional[List[dict[str, Any]]], # List of media items (format TBD by content_manager)
    parse_mode: str = 'HTML'
) -> Optional[List[Message]]:
    """
    Отправляет пост в указанный чат, поддерживая текст, одиночные медиа или медиагруппы.
    Текст поста используется как подпись к медиа, если помещается, иначе отправляется отдельно.
    Возвращает список отправленных сообщений (list of Message objects) или None при критической ошибке.
    Каждый элемент media_files должен быть словарем с ключами 'type' (str, e.g., 'photo', 'video')
    and 'media' (Any, e.g., file_id, bytes, InputFile object), optionally 'caption' (str).
    """
    sent_messages: List[Message] = []
    main_text_sent_separately = False

    # Define combined caption and separate text based on media presence
    # If media is present, main text becomes caption for the first media item.
    # If text exceeds caption limit for the first media, or if there are multiple media items
    # (where only the first can have a full caption), the full text is sent as a separate message.
    # If no media, text is sent as a regular message.

    try:
        # Validate chat_id format if necessary (e.g., ensure it's int for channel IDs)
        # For simplicity, assume chat_id is valid (int or '@username') as passed from handlers/DB.

        if not media_files:
            # Отправка только текста
            if text:
                logger.info(f"Sending text-only post to chat {chat_id}")
                try:
                    message = await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=parse_mode
                    )
                    sent_messages.append(message)
                    logger.info(f"Text-only post sent to chat {chat_id}, message_id: {message.message_id}")
                except TelegramAPIError as e:
                     logger.error(f"Failed to send text-only post to chat {chat_id}: {e}", exc_info=True)
                     return None # Indicate critical failure for this chat_id

            else:
                # Ни текста, ни медиа - нечего отправлять
                logger.warning(f"Attempted to send empty post to chat {chat_id}")
                return None # Nothing sent

        elif len(media_files) == 1:
            # Отправка одиночного медиафайла
            media_item = media_files[0]
            media_type = media_item.get('type')
            media_data = media_item.get('media') # This should be the file content or file_id
            individual_caption = media_item.get('caption', '') # Individual caption from content_manager

            if media_data is None:
                logger.error(f"Media data is missing for single item in chat {chat_id}. Type: {media_type}. Attempting text fallback.")
                # Try to send text as a fallback if media is invalid
                if text:
                     try:
                          message = await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
                          sent_messages.append(message)
                          main_text_sent_separately = True
                     except TelegramAPIError as text_e:
                          logger.error(f"Failed text fallback to chat {chat_id}: {text_e}", exc_info=True)
                return sent_messages if sent_messages else None # Return text messages if sent, else None


            # Combined caption logic: full post text + individual media caption
            # Post text goes first, then maybe a separator, then individual caption
            combined_caption = ""
            if text:
                combined_caption += text
                if individual_caption:
                    combined_caption += "\n\n" # Separator
            if individual_caption:
                combined_caption += individual_caption


            # Determine caption limit based on media type
            # Note: In media groups, photo/video/document captions are all limited to 1024.
            # For single items: photo/video 1024, document 4096. Using correct limits here.
            caption_limit = MAX_CAPTION_LENGTH_DOCUMENT if media_type == 'document' else MAX_CAPTION_LENGTH_PHOTO_VIDEO_GROUP # This limit is 1024 for photo/video

            # Determine which caption to send with media and if text needs separate message
            send_caption = None
            send_full_text_separately = False

            if combined_caption:
                if len(combined_caption) <= caption_limit:
                    send_caption = combined_caption
                else:
                    # Combined caption is too long for media caption.
                    # If there is main post text, it must be sent separately.
                    # The media will be sent with only its individual_caption if it exists and fits.
                    if text: # If main post text exists
                         send_full_text_separately = True
                         # The caption for the media should then only be the individual_caption if it fits the limit
                         if individual_caption and len(individual_caption) <= caption_limit:
                             send_caption = individual_caption
                         else:
                             send_caption = None # Individual caption also too long or doesn't exist
                    else:
                        # Only individual_caption exists and is too long -> send with no caption
                        send_caption = None # Individual caption too long


            logger.info(f"Sending single media item ({media_type}) to chat {chat_id}")
            try:
                # Send full text separately if it was too long for combined caption and there was main text
                if send_full_text_separately and text:
                    try:
                        text_message = await bot.send_message(
                            chat_id=chat_id,
                            text=text, # Send full original text
                            parse_mode=parse_mode
                        )
                        sent_messages.append(text_message)
                        main_text_sent_separately = True
                        logger.debug(f"Sent separate text message to chat {chat_id}, message_id: {text_message.message_id}")
                    except TelegramAPIError as text_e:
                        logger.error(f"Failed to send separate text message to chat {chat_id}: {text_e}", exc_info=True)
                        # Decide whether to proceed with media sending or return None.
                        # Let's proceed with media, as text failure shouldn't block media.


                # Send the media with the determined caption
                message = None
                if media_type == 'photo':
                    message = await bot.send_photo(
                        chat_id=chat_id,
                        photo=media_data, # media_data should be InputFile, bytes, or file_id
                        caption=send_caption,
                        parse_mode=parse_mode
                    )
                elif media_type == 'video':
                    message = await bot.send_video(
                        chat_id=chat_id,
                        video=media_data,
                        caption=send_caption,
                        parse_mode=parse_mode
                    )
                elif media_type == 'document':
                     message = await bot.send_document(
                        chat_id=chat_id,
                        document=media_data,
                        caption=send_caption,
                        parse_mode=parse_mode
                    )
                elif media_type == 'audio':
                     message = await bot.send_audio(
                        chat_id=chat_id,
                        audio=media_data,
                        caption=send_caption,
                        parse_mode=parse_mode
                    )
                elif media_type == 'animation':
                     message = await bot.send_animation(
                        chat_id=chat_id,
                        animation=media_data,
                        caption=send_caption,
                        parse_mode=parse_mode
                    )
                else:
                    logger.error(f"Unsupported media type '{media_type}' for single item in chat {chat_id}. Skipping media send.")
                    # If media sending failed due to unsupported type, but text was sent, return the text message(s).
                    return sent_messages if sent_messages else None # Indicate media failure


                if message:
                    sent_messages.append(message)
                    logger.info(f"Single media item ({media_type}) sent to chat {chat_id}, message_id: {message.message_id}")

            except TelegramAPIError as e:
                 logger.error(f"Failed to send single media item of type {media_type} to chat {chat_id}: {e}", exc_info=True)
                 # If media failed, but text was sent separately, return the text messages.
                 # If text was not sent separately, try to send it now as a fallback.
                 if text and not main_text_sent_separately:
                      logger.warning(f"Single media failed, attempting text fallback to chat {chat_id}")
                      try:
                          text_message = await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
                          sent_messages.append(text_message)
                      except TelegramAPIError as text_e:
                          logger.error(f"Failed text fallback to chat {chat_id} after media failure: {text_e}", exc_info=True)
                 # Return whatever was successfully sent (text messages) or None if nothing was sent at all
                 return sent_messages if sent_messages else None


        else: # len(media_files) > 1
            # Attempt to send a media group
            input_media_items: List[Union[InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InputMediaAnimation]] = []
            can_form_media_group = True
            send_full_text_separately_flag = False # Flag to indicate if full text must be sent separately

            # Determine caption for the first item in the group
            group_caption_for_first_item = ""
            if text:
                 group_caption_for_first_item += text
                 # No separator needed if individual_caption for the first item is appended below

            for i, media_item in enumerate(media_files):
                media_type = media_item.get('type')
                media_data = media_item.get('media') # This should be InputFile, bytes, or file_id
                individual_caption = media_item.get('caption', '') # Individual caption from content_manager

                if media_data is None:
                    logger.warning(f"Skipping media item {i} due to missing data in chat {chat_id}. Cannot form media group.")
                    can_form_media_group = False # Cannot form group with missing data
                    # No break here, continue checking other items for errors, but the flag is set
                    continue

                # Only the first item can have a caption for the group
                item_caption_for_group = None
                if i == 0:
                     # For the first item, use the combined post text + its individual caption if they fit
                     first_item_full_caption_candidate = group_caption_for_first_item
                     if individual_caption:
                         first_item_full_caption_candidate += "\n\n" + individual_caption if first_item_full_caption_candidate else individual_caption

                     # Media group caption limit is same as photo/video limit (1024)
                     caption_limit_group = MAX_CAPTION_LENGTH_PHOTO_VIDEO_GROUP

                     if first_item_full_caption_candidate and len(first_item_full_caption_candidate) <= caption_limit_group:
                          item_caption_for_group = first_item_full_caption_candidate
                     elif text:
                          # If the combined caption is too long for the group, the full post text will be sent separately.
                          send_full_text_separately_flag = True # Mark that text will be separate
                          # The first media item's caption in the group should then only be its individual caption if it fits
                          if individual_caption and len(individual_caption) <= caption_limit_group:
                               item_caption_for_group = individual_caption
                          # Otherwise, send with no caption
                     # else: If text is empty and individual caption is too long, send with no caption.
                else:
                    # Subsequent items in a media group can have individual captions, but limited to 1024 chars.
                    # However, Telegram API generally only displays the caption of the *first* item.
                    # Aiogram's InputMedia objects have a caption parameter, but Telegram ignores it for subsequent items in the group.
                    # So, we technically *can* pass captions for subsequent items, but they won't be shown.
                    # Let's pass individual captions anyway, in case Telegram API changes or for different client behaviors, but be aware they won't appear.
                    # The limit is still 1024 for captions *within* a media group.
                    caption_limit_group_item = MAX_CAPTION_LENGTH_PHOTO_VIDEO_GROUP # Apply the same limit as the group caption
                    if individual_caption and len(individual_caption) <= caption_limit_group_item:
                         item_caption_for_group = individual_caption
                    else:
                         item_caption_for_group = None # Individual caption too long or empty


                # Create InputMedia object
                try:
                    input_media_obj = None
                    # Need to use FSInputFile for local paths, file_id string directly for Telegram file_ids
                    media_source = FSInputFile(media_data) if isinstance(media_data, str) and os.path.exists(media_data) else media_data

                    if media_type == 'photo':
                        input_media_obj = InputMediaPhoto(media=media_source, caption=item_caption_for_group, parse_mode=parse_mode)
                    elif media_type == 'video':
                         input_media_obj = InputMediaVideo(media=media_source, caption=item_caption_for_group, parse_mode=parse_mode)
                    elif media_type == 'document':
                         # Documents can be in media groups. Caption limit is 1024 in group.
                         input_media_obj = InputMediaDocument(media=media_source, caption=item_caption_for_group, parse_mode=parse_mode)
                    # Audio and Animation generally cannot be mixed with photo/video/document in a single group.
                    # They can form media groups *with themselves*, but not with photo/video/doc.
                    elif media_type in ['audio', 'animation']:
                         # If *any* audio/animation is present, the whole group cannot be sent mixed.
                         # This logic is simplified; a more robust approach would try to form multiple groups or send individually.
                         # For simplicity, we mark as cannot form group if mixed types are attempted.
                         logger.warning(f"Media type '{media_type}' at index {i} is usually not supported in media groups with other types. Cannot form media group.")
                         can_form_media_group = False
                         # No break here, just mark that group is not possible and fall through to individual send later
                    else:
                         logger.warning(f"Unsupported media type '{media_type}' at index {i}. Cannot form media group.")
                         can_form_media_group = False
                         # No break

                    if input_media_obj:
                        input_media_items.append(input_media_obj)

                except Exception as e: # Catch exceptions during InputMedia object creation (e.g., invalid data format)
                    logger.warning(f"Failed to create InputMedia object for item {i} of type {media_type} in chat {chat_id}: {e}")
                    can_form_media_group = False # Cannot form group if any item creation fails


            if can_form_media_group and input_media_items:
                 # Attempt to send as a media group
                 logger.info(f"Attempting to send media group ({len(input_media_items)} items) to chat {chat_id}")
                 try:
                    # Send full text separately BEFORE the media group if needed
                    # This happens if the combined caption was too long for the first item
                    if send_full_text_separately_flag and text and not main_text_sent_separately:
                        try:
                            text_message = await bot.send_message(
                                chat_id=chat_id,
                                text=text, # Send full original text
                                parse_mode=parse_mode
                            )
                            sent_messages.append(text_message)
                            main_text_sent_separately = True
                            logger.debug(f"Sent separate text message BEFORE media group to chat {chat_id}, message_id: {text_message.message_id}")
                        except TelegramAPIError as text_e:
                            logger.error(f"Failed to send separate text message BEFORE media group to chat {chat_id}: {text_e}", exc_info=True)
                            # Decide whether to proceed with media group sending. Yes, proceed.


                    messages = await bot.send_media_group(chat_id=chat_id, media=input_media_items)
                    sent_messages.extend(messages)
                    logger.info(f"Media group sent to chat {chat_id}. Message IDs: {[m.message_id for m in messages]}")

                 except TelegramBadRequest as e:
                      # This often happens if the media group is invalid (e.g., unsupported mix of types by Telegram)
                      logger.warning(f"Failed to send media group to chat {chat_id} due to BadRequest: {e}. Attempting to send items individually.", exc_info=True)
                      can_form_media_group = False # Group sending failed, fall through to individual send logic
                      # If text was marked for separate send but sending media group failed, ensure text is sent now
                      if send_full_text_separately_flag and text and not main_text_sent_separately:
                           logger.warning(f"Media group failed, attempting text fallback BEFORE individual media items to chat {chat_id}")
                           try:
                               text_message = await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
                               sent_messages.append(text_message)
                               main_text_sent_separately = True
                           except TelegramAPIError as text_e:
                                logger.error(f"Failed text fallback after media group BadRequest to chat {chat_id}: {text_e}", exc_info=True)

                 except TelegramAPIError as e:
                      logger.error(f"Failed to send media group to chat {chat_id}: {e}", exc_info=True)
                      # In case of other API errors during group send, attempt text fallback if needed
                      if text and not main_text_sent_separately:
                           logger.warning(f"Media group failed, attempting text fallback to chat {chat_id}")
                           try:
                                text_message = await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
                                sent_messages.append(text_message)
                                main_text_sent_separately = True
                           except TelegramAPIError as text_e:
                                logger.error(f"Failed text fallback to chat {chat_id} after media group failure: {text_e}", exc_info=True)
                      # Return whatever was successfully sent (text or nothing) or None if nothing was attempted/sent
                      return sent_messages if sent_messages else None


            if not can_form_media_group or not input_media_items:
                 # If group couldn't be formed or sending group failed, send items individually
                 # This block is only reached if can_form_media_group is False or input_media_items was empty initially.
                 # If input_media_items was empty, we would have returned earlier (no media).
                 # So this means can_form_media_group is False (due to type mix, missing data, or group API failure).
                 logger.info(f"Cannot send as media group or group sending failed. Sending {len(media_files)} media items individually to chat {chat_id}.")

                 # First send the main post text if it exists and hasn't been sent separately yet
                 # This covers cases where group failed or text was too long for group caption
                 if text and not main_text_sent_separately:
                     try:
                         text_message = await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
                         sent_messages.append(text_message)
                         main_text_sent_separately = True
                         logger.debug(f"Sent separate text message before individual media items to chat {chat_id}, message_id: {text_message.message_id}")
                     except TelegramAPIError as e:
                         logger.error(f"Failed to send text before individual media items to chat {chat_id}: {e}", exc_info=True)
                         # Proceed with sending media even if text failed

                 # Send each media item individually
                 for i, media_item in enumerate(media_files):
                    media_type = media_item.get('type')
                    media_data = media_item.get('media') # This should be InputFile, bytes, or file_id
                    individual_caption = media_item.get('caption', '') # Individual caption from content_manager

                    if media_data is None:
                        logger.warning(f"Skipping individual media item {i} due to missing data in chat {chat_id}")
                        continue

                    # When sending individually, the main post text is NOT automatically the caption.
                    # Use only the individual caption for the media item if it exists and fits its type's limit.
                    # Apply specific caption limits for individual items.
                    caption_limit_individual = MAX_CAPTION_LENGTH_DOCUMENT if media_type == 'document' else MAX_CAPTION_LENGTH_PHOTO_VIDEO_GROUP # 1024 for photo/video/animation/audio

                    send_caption = individual_caption if individual_caption and len(individual_caption) <= caption_limit_individual else None


                    try:
                        message = None
                        # Need to use FSInputFile for local paths, file_id string directly for Telegram file_ids
                        media_source = FSInputFile(media_data) if isinstance(media_data, str) and os.path.exists(media_data) else media_data

                        if media_type == 'photo':
                            message = await bot.send_photo(
                                chat_id=chat_id,
                                photo=media_source,
                                caption=send_caption,
                                parse_mode=parse_mode
                            )
                        elif media_type == 'video':
                            message = await bot.send_video(
                                chat_id=chat_id,
                                video=media_source,
                                caption=send_caption,
                                parse_mode=parse_mode
                            )
                        elif media_type == 'document':
                             message = await bot.send_document(
                                chat_id=chat_id,
                                document=media_source,
                                caption=send_caption,
                                parse_mode=parse_mode
                            )
                        elif media_type == 'audio':
                             message = await bot.send_audio(
                                chat_id=chat_id,
                                audio=media_source,
                                caption=send_caption,
                                parse_mode=parse_mode
                            )
                        elif media_type == 'animation':
                             message = await bot.send_animation(
                                chat_id=chat_id,
                                animation=media_source,
                                caption=send_caption,
                                parse_mode=parse_mode
                            )
                        else:
                            logger.warning(f"Unsupported media type '{media_type}' for individual sending at index {i} in chat {chat_id}. Skipping.")
                            continue # Skip unsupported file type

                        if message:
                            sent_messages.append(message)
                            logger.info(f"Sent individual media item {i+1} ({media_type}) to chat {chat_id}, message_id: {message.message_id}")

                    except TelegramAPIError as e:
                        logger.error(f"Failed to send individual media item {i+1} of type {media_type} to chat {chat_id}: {e}", exc_info=True)
                        # Continue attempting to send other media items even if one fails


    except TelegramAPIError as e:
        logger.critical(f"A critical Telegram API error occurred during send_post to chat {chat_id}: {e}", exc_info=True)
        return None # Indicate critical failure for this chat_id
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred during send_post to chat {chat_id}: {e}", exc_info=True)
        return None # Indicate critical failure for this chat_id

    # Return the list of successfully sent messages
    return sent_messages if sent_messages else None # Return None if nothing was sent at all


async def delete_message(
    bot: Bot,
    chat_id: Union[int, str],
    message_id: int
) -> bool:
    """
    Удаляет сообщение в указанном чате.

    :param bot: Экземпляр aiogram.Bot.
    :param chat_id: ID целевого чата.
    :param message_id: ID сообщения для удаления.
    :return: True при успехе или если сообщение уже удалено/не найдено, False при ошибке разрешений или другой APIError.
    """
    try:
        # Aiogram's delete_message returns True on success.
        # It raises exceptions for MessageToDeleteNotFound and MessageCantBeDeleted.
        # We wrap it to handle these exceptions and return True/False accordingly.
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Message {message_id} successfully deleted in chat {chat_id}.")
        return True # Successfully deleted

    except MessageToDeleteNotFound:
        logger.warning(f"Attempted to delete message {message_id} in chat {chat_id}, but it was not found or already deleted.")
        return True # Consider it a success if the desired state (message gone) is achieved

    except MessageCantBeDeleted:
        logger.warning(f"Attempted to delete message {message_id} in chat {chat_id}, but the bot does not have permissions or it's a service message.")
        # This indicates a permission issue or message type that cannot be deleted by the bot
        return False # Indicate failure due to permissions/type

    except TelegramAPIError as e:
        # Catch other API errors
        logger.error(f"Failed to delete message {message_id} in chat {chat_id} due to API error: {e}", exc_info=True)
        return False # Indicate other API error

    except Exception as e:
        logger.error(f"An unexpected error occurred while deleting message {message_id} in chat {chat_id}: {e}", exc_info=True)
        return False


async def get_chat_member_status(
    bot: Bot,
    chat_id: Union[int, str],
    user_id: int
) -> Optional[ChatMember]:
    """
    Получает информацию о статусе пользователя в чате.

    :param bot: Экземпляр aiogram.Bot.
    :param chat_id: ID целевого чата.
    :param user_id: ID пользователя.
    :return: Объект ChatMember или None при ошибке/пользователь не найден в чате.
    """
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        # logger.debug(f"Got chat member status for user {user_id} in chat {chat_id}: {member.status}")
        return member
    except UserNotFoundError:
        logger.info(f"User {user_id} not found in chat {chat_id}.")
        return None
    except TelegramAPIError as e:
        logger.error(f"Failed to get chat member status for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while getting chat member status for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        return None


async def is_bot_admin_in_channel(
    bot: Bot,
    chat_id: Union[int, str]
) -> Tuple[bool, bool]:
    """
    Проверяет, является ли бот администратором в указанном канале и имеет ли право публиковать сообщения.

    :param bot: Экземпляр aiogram.Bot.
    :param chat_id: ID канала.
    :return: Кортеж (является ли администратором, имеет ли право публиковать сообщения).
    """
    try:
        # Get bot's own ID first
        me = await bot.get_me()
        bot_id = me.id
        # Then get the bot's member status in the chat
        member = await get_chat_member_status(bot, chat_id, bot_id)

        # Check if member exists and status is administrator
        if member and member.status == 'administrator':
            # Check specific permission for posting messages
            can_post = member.can_post_messages if hasattr(member, 'can_post_messages') else False
            logger.debug(f"Bot is admin in chat {chat_id}, can_post_messages: {can_post}")
            return True, can_post
        else:
            logger.debug(f"Bot is not an administrator in chat {chat_id}.")
            return False, False
    except Exception as e:
        logger.error(f"An error occurred while checking bot admin status in chat {chat_id}: {e}", exc_info=True)
        # In case of any error (e.g., chat_id is not a channel/group, bot is not in chat), return False
        return False, False


async def check_user_channel_permissions(
    bot: Bot,
    chat_id: Union[int, str],
    user_id: int
) -> Tuple[bool, bool, bool]:
    """
    Проверяет права пользователя (является ли администратором с правом публикации) и бота
    (является ли администратором, имеет ли право публикации) в канале.

    :param bot: Экземпляр aiogram.Bot.
    :param chat_id: ID канала.
    :param user_id: ID пользователя.
    :return: Кортеж (user_is_admin_with_post_rights, bot_is_admin, bot_can_post_messages).
    """
    user_is_admin_with_post_rights = False
    bot_is_admin = False
    bot_can_post_messages = False

    try:
        # Check user status
        user_member = await get_chat_member_status(bot, chat_id, user_id)
        # User is considered admin with post rights if status is 'administrator' or 'creator' AND they have can_post_messages permission
        if user_member and user_member.status in ['administrator', 'creator']:
             # Check if the user admin specifically has post messages permission
             # For creator this is usually true, for admin it might be explicit
             # Default to True if attribute missing, assuming older API or chat type where all admins can post
             user_has_post_perm = user_member.can_post_messages if hasattr(user_member, 'can_post_messages') else True # Assume creator/full admin can post if field missing
             if user_has_post_perm:
                 user_is_admin_with_post_rights = True
                 logger.debug(f"User {user_id} is admin with post rights in chat {chat_id}.")
             else:
                 logger.debug(f"User {user_id} is admin but NO post rights in chat {chat_id}.")
        else:
            logger.debug(f"User {user_id} is not an administrator or creator in chat {chat_id}.")


        # Check bot status
        bot_is_admin, bot_can_post_messages = await is_bot_admin_in_channel(bot, chat_id)

    except Exception as e:
        logger.error(f"An unexpected error occurred while checking user/bot permissions in chat {chat_id} for user {user_id}: {e}", exc_info=True)
        # In case of any error, assume no sufficient permissions
        return False, False, False

    # Also check if the chat_id is valid and the bot is actually in the chat.
    # get_chat_member_status and is_bot_admin_in_channel handle some cases (UserNotFoundError, general APIError).
    # A separate bot.get_chat() call could verify chat existence and bot presence more explicitly,
    # but relying on member checks is often sufficient. If bot_is_admin is False, bot_can_post_messages will also be False,
    # correctly indicating bot cannot post, whether it's not admin or not in chat.
    # user_is_admin_with_post_rights being False correctly indicates the user cannot add the channel for posting.

    return user_is_admin_with_post_rights, bot_is_admin, bot_can_post_messages

