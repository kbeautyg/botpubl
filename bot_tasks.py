# bot_tasks.py
import logging
import datetime
import pytz

# Assume these classes/types are defined elsewhere in your project
# Import actual models and services
from models.post import Post, PostStatusEnum, ScheduleTypeEnum # Import Enums for use
# Import actual services - these will be passed as kwargs by the scheduler
# import services.db as db_service
# import services.telegram_api as telegram_api_service
# import services.content_manager as content_manager_service
# import services.scheduler as scheduler_service # Needed to schedule deletion tasks
# import services.rss as rss_service # Needed for RSS check task

# Configure logging
logger = logging.getLogger(__name__)
# Note: Actual handler configuration is in utils.logger.py


# Update function signatures to accept services and bot as keyword arguments
# This aligns with _get_job_services in scheduler.py
async def execute_scheduled_post(post_id: int, *, bot, db_service, telegram_api_service, content_manager_service, scheduler_service):
    """
    Исполнитель задачи APScheduler для публикации отложенного поста.

    Извлекает данные поста из БД, публикует его в указанных каналах,
    и при необходимости планирует задачу автоудаления сообщения.

    Args:
        post_id (int): ID поста для публикации.
        bot: Экземпляр объекта бота (aiogram.Bot).
        db_service: Экземпляр сервиса для работы с БД.
        telegram_service: Экземпляр сервиса для работы с Telegram API.
        content_manager_service: Экземпляр сервиса для подготовки контента.
        scheduler_service: Экземпляр сервиса для планирования задач.
    """
    logger.info(f"Запущена задача execute_scheduled_post для поста ID: {post_id}")

    post = None
    try:
        # Извлекаем пост из БД
        post: Post = await db_service.get_post_by_id(post_id)
        if not post:
            logger.warning(f"Пост с ID {post_id} не найден в БД. Пропускаю публикацию.")
            # If post is not found, APScheduler should likely remove the job automatically if misfire_grace_time passes.
            # We don't need to mark status here as the post doesn't exist.
            return # Задача выполнена, но пост не найден

        # Проверяем статус поста, чтобы не публиковать уже опубликованные или отмененные
        if post.status != PostStatusEnum.SCHEDULED.value:
             logger.info(f"Пост ID {post_id} имеет статус '{post.status.value}'. Ожидался статус '{PostStatusEnum.SCHEDULED.value}'. Пропускаю публикацию.")
             # Optionally mark job as finished or remove it if status is not scheduled
             # APScheduler might handle this based on configuration
             return

        # Placeholder: предполагается, что post.chat_ids - это список int chat_id из JSON
        if not post.chat_ids:
            logger.warning(f"Пост ID {post_id} не имеет привязанных каналов для публикации. Обновляю статус на INVALID.")
            # Обновляем статус поста на 'invalid'
            await db_service.update_post_status(post_id, PostStatusEnum.INVALID.value)
            # No channels, cannot publish, mark as failed/invalid
            return

        sent_to_count = 0
        failed_to_count = 0
        successfully_sent_messages = [] # Store successfully sent message objects

        # Prepare content using content_manager_service
        # content_manager_service.prepare_content needs Post object data
        # It should return a dict like {'text': ..., 'media_files': [...]}
        try:
            # Assuming content_manager.prepare_content takes post data dictionary
            content_to_send = await content_manager_service.prepare_content(post_data={
                'text': post.text,
                'media_paths': post.media_paths, # Pass media paths from DB
                # Add other post data if needed by prepare_content (e.g., individual captions if stored)
            })
            post_text_prepared = content_to_send.get('text')
            media_files_prepared = content_to_send.get('media_files')
        except Exception as cm_ex:
             logger.error(f"Error preparing content for post ID {post_id}: {cm_ex}", exc_info=True)
             await db_service.update_post_status(post_id, PostStatusEnum.ERROR.value)
             return # Cannot publish if content preparation fails


        for chat_id in post.chat_ids:
            # Ensure chat_id is int for telegram_api_service calls
            try:
                chat_id_int = int(chat_id)
            except (ValueError, TypeError):
                 logger.error(f"Invalid chat_id found in post {post_id}: '{chat_id}'. Skipping.")
                 failed_to_count += 1
                 continue


            logger.info(f"Пост ID {post_id}: Попытка публикации в канал {chat_id_int}")

            # TODO: Реализовать проверку прав бота на публикацию в конкретном канале
            # Это можно сделать здесь или в telegram_api_service.send_post
            # Let's assume send_post in telegram_api_service handles basic errors like permissions.
            # A dedicated check_bot_permissions here would be more proactive.
            # is_bot_admin, bot_can_post = await telegram_api_service.is_bot_admin_in_channel(bot, chat_id_int)
            # if not is_bot_admin or not bot_can_post:
            #      logger.error(f"Пост ID {post_id}: Боту не хватает прав для публикации в канале {chat_id_int}. Пропускаю этот канал.")
            #      failed_to_count += 1
            #      # TODO: Возможно, уведомить пользователя об ошибке отправки в конкретный канал
            #      continue # Skip this channel

            try:
                # Отправляем сообщение
                # telegram_api_service.send_post returns Optional[List[Message]]
                sent_messages_list = await telegram_api_service.send_post(
                    bot=bot,
                    chat_id=chat_id_int,
                    text=post_text_prepared,
                    media_files=media_files_prepared,
                    # parse_mode could be passed from post data if stored, default to HTML/MarkdownV2
                    parse_mode='HTML' # Or get from post or user settings
                )

                if sent_messages_list:
                    logger.info(f"Пост ID {post_id} успешно отправлен в канал {chat_id_int}. Message IDs: {[m.message_id for m in sent_messages_list]}")
                    sent_to_count += 1
                    # Store successfully sent message objects info for potential deletion
                    successfully_sent_messages.extend([(chat_id_int, m.message_id) for m in sent_messages_list]) # Store chat_id and message_id tuple


                    # Планируем автоудаление для КАЖДОГО отправленного сообщения, если настроено
                    # This requires the specific message_id that was just sent.
                    # The send_post function should return the message(s) object(s).
                    if post.delete_after_seconds is not None or post.delete_at_utc is not None:
                        # Determine the deletion time in UTC
                        delete_run_date_utc = None
                        if post.delete_after_seconds is not None:
                            # Calculate deletion time based on *now* + seconds
                            delete_run_date_utc = datetime.datetime.now(pytz.utc) + datetime.timedelta(seconds=post.delete_after_seconds)
                        elif post.delete_at_utc is not None:
                            # Use the stored delete_at_utc from the post data (should be UTC naive or aware based on model)
                            # Ensure it's timezone-aware UTC for the scheduler
                            delete_run_date_utc = post.delete_at_utc.astimezone(pytz.utc) if post.delete_at_utc.tzinfo is not None else pytz.utc.localize(post.delete_at_utc)


                        if delete_run_date_utc and delete_run_date_utc > datetime.datetime.now(pytz.utc): # Only schedule if time is in the future
                            for sent_msg in sent_messages_list:
                                try:
                                    # Plan the deletion job for this specific message
                                    # scheduler_service.schedule_message_deletion expects post_id, chat_id, message_id, delete_at_utc, and services
                                    await scheduler_service.schedule_message_deletion(
                                        post_id=post.id,
                                        chat_id=chat_id_int, # Pass the integer chat_id
                                        message_id=sent_msg.message_id,
                                        delete_at_utc=delete_run_date_utc, # Pass the determined UTC time
                                        services_container={ # Pass necessary services as a container object
                                             'bot': bot,
                                             'db_service': db_service,
                                             'telegram_api_service': telegram_api_service
                                             # Add other services if execute_message_deletion needs them
                                        }
                                    )
                                    logger.info(f"Задача удаления сообщения (Пост ID: {post.id}, Чат ID: {chat_id_int}, Msg ID: {sent_msg.message_id}) запланирована на {delete_run_date_utc}")
                                except Exception as scheduler_ex:
                                    logger.error(f"Ошибка при планировании задачи удаления сообщения (Пост ID: {post.id}, Чат ID: {chat_id_int}, Msg ID: {sent_msg.message_id}): {scheduler_ex}", exc_info=True)

                        elif delete_run_date_utc:
                             # If deletion time is in the past, log a warning but don't schedule
                             logger.warning(f"Deletion time {delete_run_date_utc} for message {sent_msg.message_id} in chat {chat_id_int} is not in the future. Skipping deletion scheduling.")
                        # else: Neither delete_after_seconds nor delete_at_utc is set, no deletion needed

                else:
                    logger.error(f"Пост ID {post.id}: Не удалось получить message_id(s) после отправки в канал {chat_id_int} (send_post returned None/empty).")
                    failed_to_count += 1

            except Exception as telegram_ex:
                # Catch exceptions during send_post or message ID handling for a specific channel
                logger.error(f"Пост ID {post.id}: Ошибка при отправке в канал {chat_id_int}: {telegram_ex}", exc_info=True)
                failed_to_count += 1
                # TODO: Уведомить пользователя об ошибке отправки в конкретный канал

        # Обновляем статус поста в БД по результатам
        new_status = PostStatusEnum.ERROR.value # Default to error if any failure
        if sent_to_count > 0 and failed_to_count == 0:
            new_status = PostStatusEnum.SENT.value # Successfully sent to all
        elif sent_to_count > 0 and failed_to_count > 0:
            new_status = PostStatusEnum.SENT.value # Sent to at least one, mark as SENT, issues logged (or partially_sent if that status exists)
            # Note: The prompt's PostStatusEnum includes SENT, ERROR, INVALID, DELETED, DRAFT, SCHEDULED.
            # A 'partially_sent' status could be useful but doesn't exist in the model.
            # Marking as SENT if sent to at least one channel seems reasonable for tracking.
        elif sent_to_count == 0 and failed_to_count > 0:
            new_status = PostStatusEnum.ERROR.value # Failed to send to all channels attempted
        elif sent_to_count == 0 and failed_to_count == 0 and post.chat_ids:
             # Attempted to send to channels but neither success nor failure counted?
             # This case is unlikely if failed_to_count is incremented on any error.
             # If post.chat_ids was empty, we would have returned earlier.
             # If post.chat_ids existed but send_post was skipped (e.g., permissions check added later),
             # failed_to_count should increment. Let's assume this case implies a logic error or skipped channels.
             new_status = PostStatusEnum.INVALID.value # Mark as invalid if attempted but nothing sent/failed


        # Update post status and potentially save sent message info if needed later (e.g. for deletion management)
        # Need to pass the list of sent messages if storing them.
        # Example: await db_service.update_post_details(post.id, status=new_status, sent_messages_info=successfully_sent_messages)
        # This requires a new column in Post model (e.g., sent_messages JSONB list of {'chat_id': ..., 'message_id': ...})
        # For now, just update status:
        # Always attempt status update if post object was retrieved
        if post:
            try:
                 await db_service.update_post_status(post.id, new_status)
                 logger.info(f"Пост ID {post.id}: Обновлен статус на '{new_status}'. Отправлено в {sent_to_count}, не отправлено в {failed_to_count}.")
            except Exception as db_update_ex:
                 logger.error(f"Error updating post {post.id} status to '{new_status}': {db_update_ex}", exc_info=True)


    except Exception as e:
        # Catch critical errors during the task execution (e.g., DB access failure before getting post)
        logger.critical(f"Критическая ошибка при выполнении задачи execute_scheduled_post для поста ID {post_id}: {e}", exc_info=True)
        # In case of critical error, try to mark the post as 'error' if we have post_id and db_service
        if post_id and db_service:
            try:
                await db_service.update_post_status(post_id, PostStatusEnum.ERROR.value)
            except Exception as db_ex:
                 logger.error(f"Ошибка при обновлении статуса поста ID {post_id} на '{PostStatusEnum.ERROR.value}' после критической ошибки: {db_ex}", exc_info=True)

    logger.info(f"Задача execute_scheduled_post для поста ID: {post_id} завершена.")


# Update function signature to accept services as keyword arguments
async def execute_message_deletion(chat_id: int, message_id: int, *, bot, db_service, telegram_api_service):
    """
    Исполнитель задачи APScheduler для удаления сообщения Telegram.

    Args:
        chat_id (int): ID чата/канала, где находится сообщение.
        message_id (int): ID сообщения для удаления.
        bot: Экземпляр объекта бота.
        db_service: Экземпляр сервиса БД (может понадобиться для логирования удаления в БД).
        telegram_service: Экземпляр сервиса для работы с Telegram API.
    """
    # Note: post_id is not directly used by the task function itself based on the provided args,
    # but it's used to generate the job ID in scheduler.py.
    # If needed in the task function, it must be passed as an argument.
    # The scheduler.py schedule_message_deletion passes [chat_id, message_id] as args.
    # If post_id is needed, change schedule_message_deletion args to [post_id, chat_id, message_id]
    # And update this function signature to execute_message_deletion(post_id: int, chat_id: int, message_id: int, ...)
    # Let's keep it as is based on the scheduler.py args definition.

    logger.info(f"Запущена задача execute_message_deletion для Чат ID: {chat_id}, Msg ID: {message_id}")

    try:
        # telegram_api_service.delete_message returns True on success or if already deleted
        # This function handles logging success/failure internally
        await telegram_api_service.delete_message(bot, chat_id, message_id)

        # TODO: Опционально: обновить статус сообщения в БД, если вы храните информацию об отправленных сообщениях
        # This requires a DB method like db_service.mark_message_as_deleted(chat_id, message_id)
        # which in turn requires storing sent message info (chat_id, message_id, post_id etc.) in DB.
        # Example:
        # if success: # delete_message returns success flag
        #     try:
        #         # Assuming you have a table or JSON column storing sent messages and their status
        #         await db_service.mark_sent_message_deleted(chat_id, message_id)
        #         logger.debug(f"Marked message {message_id} in chat {chat_id} as deleted in DB.")
        #     except Exception as db_ex:
        #         logger.error(f"Error marking message {message_id} in chat {chat_id} as deleted in DB: {db_ex}", exc_info=True)
        # else:
        #      # Handle deletion failure logging in DB if needed
        #      pass


    except Exception as e:
        # Catch unexpected errors during the task execution
        logger.error(f"Ошибка при выполнении задачи execute_message_deletion для Чат ID: {chat_id}, Msg ID: {message_id}: {e}", exc_info=True)
        # TODO: Опционально: отметить в БД как 'ошибка удаления'


    logger.info(f"Задача execute_message_deletion для Чат ID: {chat_id}, Msg ID: {message_id} завершена.")


# Update function signature to accept services as keyword arguments
# This task executor is for a job scheduled per RSS feed ID by scheduler.py
async def execute_rss_feed_check(feed_id: int, *, bot, db_service, telegram_api_service, content_manager_service, rss_service):
    """
    Исполнитель задачи APScheduler для проверки RSS-ленты на наличие новых записей.
    Вызывается планировщиком для конкретной RSS-ленты.

    Args:
        feed_id (int): ID RSS-ленты для проверки.
        bot: Экземпляр объекта бота.
        db_service: Экземпляр сервиса для работы с БД.
        telegram_service: Экземпляр сервиса для работы с Telegram API.
        content_manager_service: Экземпляр сервиса для подготовки контента.
        rss_service: Экземпляр сервиса для работы с RSS (парсинг, публикация).
    """
    logger.info(f"Запущена задача execute_rss_feed_check для RSS-ленты ID: {feed_id}")

    rss_feed = None
    try:
        # Извлекаем данные RSS-ленты из БД
        rss_feed: Post = await db_service.get_rss_feed_by_id(feed_id) # Use RssFeed model type hint
        if not rss_feed:
            logger.warning(f"RSS-лента с ID {feed_id} не найдена в БД. Пропускаю проверку.")
            # If feed is not found, job should ideally be removed by APScheduler JobStore automatically.
            return # Задача выполнена, но лента не найдена

        # Проверяем, активна ли лента (if is_active column is added later)
        # if not rss_feed.is_active:
        #     logger.info(f"RSS-лента ID {feed_feed} неактивна. Пропускаю проверку.")
        #     return

        if not rss_feed.feed_url:
             logger.warning(f"RSS-лента ID {feed_id} не имеет URL. Пропускаю проверку.")
             # TODO: Обновить статус ленты на ошибку в БД if status column exists
             return

        # Вызываем сервис RSS для обработки конкретной ленты
        # process_single_feed expects db, telegram_api, content_manager, bot_instance, rss_feed_obj
        published_count = await rss_service.process_single_feed(
            db=db_service,
            telegram_api=telegram_api_service,
            content_manager=content_manager_service,
            bot_instance=bot,
            rss_feed_obj=rss_feed # Pass the RssFeed object from DB
        )
        logger.info(f"RSS-лента ID {feed_id}: Завершена обработка. Опубликовано новых элементов: {published_count}.")

    except Exception as e:
        logger.error(f"Ошибка при выполнении задачи execute_rss_feed_check для RSS-ленты ID {feed_id}: {e}", exc_info=True)
        # TODO: Возможно, обновить статус ленты на ошибку в БД if status column exists
        # if feed_id and db_service:
        #    try:
        #        # await db_service.update_rss_feed_status(feed_id, 'failed', error_message=str(e)) # Requires this method/column
        #        pass
        #    except Exception as db_ex:
        #         logger.error(f"Ошибка при обновлении статуса RSS-ленты ID {feed_id} на 'failed' после ошибки обработки: {db_ex}")


    logger.info(f"Задача execute_rss_feed_check для RSS-ленты ID: {feed_id} завершена.")

# TODO: Добавить любые другие функции-исполнители по мере необходимости
