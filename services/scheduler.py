# services/scheduler.py

import logging
from datetime import datetime, timedelta # Import timedelta
import pytz
from enum import Enum
from typing import Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.job_stores.base import JobLookupError
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

# Import necessary components for job execution and reconstruction
# We will pass necessary services/bot instance to the task functions via args
# Import models for type hinting in reconstruct_and_sync_jobs
from models.post import Post, ScheduleTypeEnum, PostStatusEnum
from models.rss_feed import RssFeed

# Import the helper for ensuring UTC timezone
from utils.datetime_utils import _ensure_utc_aware


# Настройка логирования
logger = logging.getLogger(__name__)
# Note: Actual handler configuration is in utils.logger.py

# Глобальная переменная для экземпляра планировщика
scheduler: Optional[AsyncIOScheduler] = None # Allow None initially

# Строковые константы для путей к функциям-исполнителям задач
# Эти пути должны быть доступны для импорта в среде выполнения APScheduler
# Update these paths to reflect actual location, assuming they are in bot_tasks.py
TASK_MODULE_PATH = "bot_tasks" # Assuming bot_tasks.py is at the top level and functions are global
# Corrected task paths based on bot_tasks.py content
POST_PUBLISH_TASK_PATH = f"{TASK_MODULE_PATH}.execute_scheduled_post"
MESSAGE_DELETE_TASK_PATH = f"{TASK_MODULE_PATH}.execute_message_deletion"
RSS_CHECK_TASK_PATH = f"{TASK_MODULE_PATH}.execute_rss_feed_check" # This tasks checks *one* feed


# Enum для типизации задач планировщика
class JobType(Enum):
    """Перечисление типов задач для стандартизации ID."""
    POST_PUBLISH = "POST_PUBLISH"
    MESSAGE_DELETE = "MESSAGE_DELETE" # Задача на удаление конкретного сообщения
    RSS_CHECK = "RSS_CHECK" # Task for checking a specific RSS feed


# Вспомогательная функция для генерации стандартизированных ID задач
def _generate_job_id(job_type: JobType, entity_id: int, sub_identifier: str | int | None = None) -> str:
    """
    Генерирует стандартизированный строковый ID задачи.
    Используется для уникальной идентификации задачи в хранилище.
    """
    base_id = f"{job_type.value}_{entity_id}"
    if sub_identifier is not None:
        # Convert sub_identifier to string safely, replace chars that might cause issues
        sub_id_str = str(sub_identifier).replace(':', '_').replace('-', '_').replace('.', '_') # Sanitize for ID
        # Truncate long identifiers if necessary to avoid hitting DB limits for job ID
        if len(sub_id_str) > 50: # Example limit
             sub_id_str = sub_id_str[:50]
        return f"{base_id}_{sub_id_str}"
    return base_id

# --- Functions to manage the global scheduler instance ---

def init_scheduler(database_url: str): # Removed bot_instance from init, pass via services_container instead
    """
    Инициализирует глобальный экземпляр APScheduler с SQLAlchemyJobStore.

    Args:
        database_url: Строка URL для подключения к базе данных.
    """
    global scheduler
    if scheduler is not None:
        # Use logger instead of print
        logger.warning("Scheduler уже инициализирован.")
        return

    try:
        # Настройка хранилища задач
        jobstores = {
            'default': SQLAlchemyJobStore(url=database_url)
        }
        # Настройка параметров задач по умолчанию
        job_defaults = {
            'coalesce': True,       # Объединять пропущенные запуски в один
            'max_instances': 5,     # Максимальное количество одновременно запущенных экземпляров одной задачи
            # Services/bot instance will be passed explicitly via job args/kwargs
        }

        # Создание экземпляра планировщика
        # Устанавливаем часовой пояс на UTC для согласованности
        scheduler = AsyncIOScheduler(jobstores=jobstores, job_defaults=job_defaults, timezone=pytz.utc)
        logger.info("Планировщик инициализирован с SQLAlchemyJobStore.")

    except Exception as e:
        logger.critical(f"Ошибка при инициализации планировщика: {e}", exc_info=True)
        # In main.py, this exception should be caught and handled.


async def start_scheduler_process():
    """Запускает процесс планировщика."""
    global scheduler
    if scheduler is None:
        logger.error("Планировщик не инициализирован. Невозможно запустить.")
        # Should not happen if init_scheduler is called first, but defensive check
        return
    if not scheduler.running:
        try:
            scheduler.start()
            logger.info("Планировщик запущен.")
        except Exception as e:
             logger.critical(f"Ошибка при запуске планировщика: {e}", exc_info=True)
    else:
        logger.info("Планировщик уже запущен.")


async def shutdown_scheduler_process(wait: bool = True):
    """
    Останавливает процесс планировщика.

    Args:
        wait: Если True, дожидается завершения всех текущих задач.
    """
    global scheduler
    if scheduler is None:
        logger.warning("Планировщик не инициализирован. Нечего останавливать.")
        return
    if scheduler.running:
        try:
            # Pass the scheduler instance explicitly to shutdown method if required,
            # though calling shutdown on the instance itself is standard.
            scheduler.shutdown(wait=wait)
            logger.info(f"Планировщик остановлен (wait={wait}).")
        except Exception as e:
             logger.error(f"Ошибка при остановке планировщика: {e}", exc_info=True)
    else:
        logger.info("Планировщик не запущен.")


# --- Helper function to get services for job args ---
def _get_job_services(services_container: Any) -> dict:
    """
    Retrieves necessary services from a container object to pass as job arguments.
    The container should have attributes like bot, db_service, telegram_api_service, etc.
    This helps standardize passing dependencies to task executors.
    """
    # List the services required by tasks in bot_tasks.py
    # These names must match attributes in the services_container object passed from bot.py
    required_services = {
        'bot',
        'db_service',
        'telegram_api_service',
        'content_manager_service',
        'scheduler_service', # Pass scheduler_service itself for tasks that need to schedule other tasks (like post publish schedules deletion)
        'rss_service', # Pass rss_service itself for RSS check task (it calls functions within rss_service)
    }
    job_services = {}
    for service_name in required_services:
        service = getattr(services_container, service_name, None)
        if service is None:
            # Log a warning if a required service is missing
             logger.warning(f"Required service '{service_name}' not found in services_container for job arguments.")
        job_services[service_name] = service
    return job_services


# --- Functions for adding APScheduler tasks ---

async def schedule_one_time_post_publication(post_id: int, run_date_utc: datetime, services_container: Any):
    """
    Планирует разовую задачу на публикацию поста.

    Args:
        post_id: ID поста из БД.
        run_date_utc: Время запланированной публикации в UTC (timezone-aware).
        services_container: Объект, содержащий ссылки на необходимые сервисы (bot, db_service и т.д.).
    """
    global scheduler
    if scheduler is None:
        logger.error(f"Планировщик не инициализирован. Невозможно запланировать публикацию поста {post_id}.")
        return

    # Ensure the run_date is timezone-aware UTC
    run_date_utc_aware = _ensure_utc_aware(run_date_utc)
    if run_date_utc_aware is None:
         logger.error(f"Некорректное время выполнения ({run_date_utc}) для публикации поста {post_id}. Пропускаю планирование.")
         return

    job_id = _generate_job_id(JobType.POST_PUBLISH, post_id)

    # Prepare arguments to be passed to execute_scheduled_post
    job_args = [post_id] # First argument is the post_id
    job_kwargs = _get_job_services(services_container) # Services as keyword arguments

    try:
        scheduler.add_job(
            func=POST_PUBLISH_TASK_PATH,
            trigger=DateTrigger(run_date=run_date_utc_aware),
            args=job_args,
            kwargs=job_kwargs, # Pass services as keyword arguments
            id=job_id,
            replace_existing=True, # Replaces existing job with the same ID
            misfire_grace_time=600 # 10 minutes grace time for missed jobs
        )
        logger.info(f"Запланирована разовая публикация поста (job_id={job_id}) на {run_date_utc_aware} UTC.")
    except Exception as e:
        logger.error(f"Ошибка при планировании разовой публикации поста (job_id={job_id}): {e}", exc_info=True)

async def schedule_recurring_post_publication(
    post_id: int,
    cron_params: dict,
    start_date_utc: datetime | None = None,
    end_date_utc: datetime | None = None,
    services_container: Any
):
    """
    Планирует циклическую задачу на публикацию поста по расписанию Cron.

    Args:
        post_id: ID поста из БД.
        cron_params: Словарь параметров для CronTrigger (например, {'hour': '10', 'minute': '0'}).
                     Can also include 'day', 'month', 'day_of_week' etc.
        start_date_utc: Дата и время начала действия расписания в UTC (timezone-aware).
        end_date_utc: Дата и время окончания действия расписания в UTC (timezone-aware).
        services_container: Объект, содержащий ссылки на необходимые сервисы.
    """
    global scheduler
    if scheduler is None:
        logger.error(f"Планировщик не инициализирован. Невозможно запланировать циклическую публикацию поста {post_id}.")
        return

    # Ensure start/end dates are timezone-aware UTC if provided
    start_date_utc_aware = _ensure_utc_aware(start_date_utc)
    end_date_utc_aware = _ensure_utc_aware(end_date_utc)

    # Check if end_date is in the past relative to now (UTC)
    now_utc_aware = datetime.now(pytz.utc)
    if end_date_utc_aware is not None and end_date_utc_aware <= now_utc_aware:
        logger.warning(f"Пост {post_id} (циклический) имеет время окончания {end_date_utc_aware} в прошлом. Пропускаю планирование.")
        # Consider marking the post as INVALID in DB here or let reconstruct handle it
        return

    job_id = _generate_job_id(JobType.POST_PUBLISH, post_id) # Use the same ID for recurring tasks

    job_args = [post_id] # First argument is the post_id
    job_kwargs = _get_job_services(services_container) # Services as keyword arguments

    try:
        scheduler.add_job(
            func=POST_PUBLISH_TASK_PATH,
            trigger=CronTrigger(start_date=start_date_utc_aware, end_date=end_date_utc_aware, timezone=pytz.utc, **cron_params),
            args=job_args,
            kwargs=job_kwargs, # Pass services as keyword arguments
            id=job_id,
            replace_existing=True, # Replaces existing job with the same ID
            misfire_grace_time=600 # 10 minutes grace time
        )
        logger.info(f"Запланирована циклическая публикация поста (job_id={job_id}) с параметрами Cron: {cron_params} (start={start_date_utc_aware}, end={end_date_utc_aware}).")
    except Exception as e:
        logger.error(f"Ошибка при планировании циклической публикации поста (job_id={job_id}) с параметрами {cron_params}: {e}", exc_info=True)

async def schedule_message_deletion(post_id: int, chat_id: int, message_id: int, delete_at_utc: datetime, services_container: Any):
    """
    Планирует разовую задачу на удаление конкретного сообщения в Telegram.

    Args:
        post_id: ID поста, к которому относится сообщение (для контекста ID задачи).
        chat_id: ID чата/канала, где было опубликовано сообщение.
        message_id: ID сообщения для удаления.
        delete_at_utc: Время запланированного удаления в UTC (timezone-aware).
        services_container: Объект, содержащий ссылки на необходимые сервисы (bot, db_service, telegram_api_service).
    """
    global scheduler
    if scheduler is None:
        logger.error(f"Планировщик не инициализирован. Невозможно запланировать удаление сообщения {message_id} в чате {chat_id}.")
        return

    # Ensure delete_at_utc is timezone-aware UTC
    delete_at_utc_aware = _ensure_utc_aware(delete_at_utc)
    if delete_at_utc_aware is None:
         logger.error(f"Некорректное время удаления ({delete_at_utc}) для сообщения {message_id} в чате {chat_id}. Пропускаю планирование.")
         return

    # Check if deletion time is in the past
    now_utc_aware = datetime.now(pytz.utc)
    if delete_at_utc_aware <= now_utc_aware:
        logger.warning(f"Время удаления ({delete_at_utc_aware}) для сообщения {message_id} в чате {chat_id} уже в прошлом. Пропускаю планирование.")
        return # No need to schedule for the past

    # ID задачи на удаление сообщения должен быть уникальным для конкретного сообщения в контексте поста
    # Including chat_id and message_id in the ID makes it unique per message
    job_id = _generate_job_id(JobType.MESSAGE_DELETE, post_id, f"{chat_id}_{message_id}")

    # Prepare arguments to be passed to execute_message_deletion
    # The task function execute_message_deletion expects chat_id, message_id first, then services as kwargs
    job_args = [chat_id, message_id] # Arguments the task function expects first
    job_kwargs = _get_job_services(services_container) # Services as keyword arguments

    try:
        scheduler.add_job(
            func=MESSAGE_DELETE_TASK_PATH,
            trigger=DateTrigger(run_date=delete_at_utc_aware),
            args=job_args,
            kwargs=job_kwargs, # Pass services as keyword arguments
            id=job_id,
            replace_existing=True,
            misfire_grace_time=60 # Small grace time for deletion (1 minute)
        )
        logger.info(f"Запланировано удаление сообщения (job_id={job_id}) на {delete_at_utc_aware} UTC.")
    except Exception as e:
        logger.error(f"Ошибка при планировании удаления сообщения (job_id={job_id}): {e}", exc_info=True)


async def schedule_rss_feed_check(feed_id: int, interval_minutes: int, services_container: Any):
    """
    Планирует циклическую задачу на проверку RSS-ленты.
    Note: In this model, a periodic job per feed is scheduled.
    The master check_all_feeds in rss.py (if used) would need a different scheduler approach.
    Sticking to the per-feed task as implied by the initial structure.

    Args:
        feed_id: ID RSS-ленты из БД.
        interval_minutes: Интервал проверки в минутах.
        services_container: Объект, содержащий ссылки на необходимые сервисы (bot, db_service, rss_service).
    """
    global scheduler
    if scheduler is None:
        logger.error(f"Планировщик не инициализирован. Невозможно запланировать проверку RSS-ленты {feed_id}.")
        return

    if interval_minutes is None or interval_minutes <= 0:
        logger.error(f"Некорректный интервал проверки для RSS-ленты {feed_id}: {interval_minutes} минут. Пропускаем планирование.")
        return

    job_id = _generate_job_id(JobType.RSS_CHECK, feed_id)

    # Prepare arguments to be passed to execute_rss_feed_check
    job_args = [feed_id] # First argument is the feed_id
    job_kwargs = _get_job_services(services_container) # Services as keyword arguments

    try:
        scheduler.add_job(
            func=RSS_CHECK_TASK_PATH,
            trigger=IntervalTrigger(minutes=interval_minutes, timezone=pytz.utc), # Interval is often timezone-agnostic, but setting UTC for consistency
            args=job_args,
            kwargs=job_kwargs, # Pass services as keyword arguments
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300 # 5 minutes grace time
        )
        logger.info(f"Запланирована проверка RSS-ленты (job_id={job_id}) каждые {interval_minutes} минут.")
    except Exception as e:
        logger.error(f"Ошибка при планировании проверки RSS-ленты (job_id={job_id}): {e}", exc_info=True)

# --- Functions for cancelling tasks ---

async def cancel_job_by_id(job_id: str):
    """
    Отменяет (удаляет) задачу планировщика по ее ID.

    Args:
        job_id: ID задачи.

    Returns:
        True, если задача успешно отменена или не найдена; False в случае другой ошибки.
    """
    global scheduler
    if scheduler is None:
        logger.error(f"Планировщик не инициализирован. Невозможно отменить задачу {job_id}.")
        return False
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Задача {job_id} успешно отменена.")
        return True
    except JobLookupError:
        logger.warning(f"Попытка отменить задачу {job_id}, но она не найдена.")
        return True # Consider successful if the job was already gone
    except Exception as e:
        logger.error(f"Ошибка при отмене задачи {job_id}: {e}", exc_info=True)
        return False

async def cancel_all_jobs_for_post(post_id: int):
    """
    Отменяет все известные задачи планировщика, связанные с конкретным постом.
    Отменяет основную задачу публикации. Tasks for deleting *sent messages* for this post
    are not cancelled here as their IDs depend on chat_id and message_id.

    Args:
        post_id: ID поста из БД.
    """
    logger.info(f"Попытка отменить задачи публикации для поста {post_id}.")
    # Cancel the main publication task (one-time or recurring uses the same ID format)
    pub_job_id = _generate_job_id(JobType.POST_PUBLISH, post_id)
    await cancel_job_by_id(pub_job_id)
    logger.info(f"Завершено действие по отмене задачи публикации для поста {post_id}.")

    # Note: Cancelling deletion jobs would require querying the DB for all sent messages
    # related to this post and generating deletion job IDs, which is more complex
    # and might not be necessary if messages are deleted anyway or if the post is just marked deleted.
    # Leaving deletion jobs might be fine; they will attempt to delete but might fail if message is gone.


async def cancel_all_jobs_for_rss_feed(feed_id: int):
    """
    Отменяет все задачи планировщика, связанные с конкретной RSS-лентой.

    Args:
        feed_id: ID RSS-ленты из БД.
    """
    logger.info(f"Попытка отменить задачи для RSS-ленты {feed_id}.")
    # Cancel the recurring check job for this specific feed
    rss_job_id = _generate_job_id(JobType.RSS_CHECK, feed_id)
    await cancel_job_by_id(rss_job_id)
    logger.info(f"Завершено действие по отмене задач для RSS-ленты {feed_id}.")


# --- Function for reconstructing/syncing jobs on startup ---

async def reconstruct_and_sync_jobs(db_service: Any, services_container: Any):
    """
    Восстанавливает и синхронизирует задачи планировщика на основе текущего состояния базы данных.
    Планирует задачи для всех постов со статусом 'scheduled' и всех активных RSS-лент.

    Args:
        db_service: Объект/модуль, предоставляющий доступ к БД (must have methods like get_all_scheduled_posts_for_reload, get_all_active_rss_feeds, update_post_status).
        services_container: Объект, содержащий ссылки на необходимые сервисы для передачи в задачи (must contain bot, db_service, scheduler_service, etc.).
    """
    global scheduler
    if scheduler is None:
        logger.error("Планировщик не инициализирован. Невозможно восстановить задачи.")
        return

    logger.info("Начат процесс восстановления и синхронизации задач из базы данных.")

    # 1. Восстановление задач для запланированных постов
    try:
        # Use async_session_maker from db_service to get a session
        async with db_service.async_session_maker() as session:
            # db_service.get_all_scheduled_posts_for_reload expects a session
            # It should retrieve posts with status PostStatusEnum.SCHEDULED.value
            scheduled_posts: list[Post] = await db_service.get_all_scheduled_posts_for_reload(session)
            logger.info(f"Найдено {len(scheduled_posts)} постов со статусом '{PostStatusEnum.SCHEDULED.value}' для восстановления расписания.")

        for post in scheduled_posts:
            try:
                logger.debug(f"Восстановление задачи для поста {post.id}, тип: {post.schedule_type}")
                # Ensure times are timezone-aware UTC for comparison
                now_utc_aware = datetime.now(pytz.utc)

                if post.schedule_type == ScheduleTypeEnum.ONE_TIME.value:
                    # For one-time posts, schedule if the run_date is in the future
                    # Post.run_date_utc is DateTime (naive), assuming it stores UTC naive. Convert to aware for comparison.
                    run_date_utc_aware = pytz.utc.localize(post.run_date_utc) if post.run_date_utc and post.run_date_utc.tzinfo is None else post.run_date_utc # Ensure it's aware UTC if not already

                    if run_date_utc_aware is not None and run_date_utc_aware > now_utc_aware:
                        await schedule_one_time_post_publication(
                            post_id=post.id,
                            run_date_utc=run_date_utc_aware, # Pass the aware datetime
                            services_container=services_container
                        )
                    else:
                        # If run_date is in the past or not set, mark the post as INVALID
                        logger.warning(f"Пост {post.id} (разовый) пропущен при восстановлении: время публикации {run_date_utc_aware} уже в прошлом или не задано. Обновляю статус на '{PostStatusEnum.INVALID.value}'.")
                        if post.status == PostStatusEnum.SCHEDULED.value: # Only change status if it was scheduled
                            try:
                                # Use db_service from services_container for updates outside the loop's potential session
                                await services_container.db_service.update_post_status(post.id, PostStatusEnum.INVALID.value)
                            except Exception as update_ex:
                                logger.error(f"Error updating post {post.id} status to INVALID after missing schedule: {update_ex}", exc_info=True)


                elif post.schedule_type == ScheduleTypeEnum.RECURRING.value:
                    # For recurring posts, schedule if parameters are valid and end date is not in the past
                    if post.schedule_params:
                        # Post start/end dates are DateTime (naive), assuming UTC naive. Convert to aware.
                        start_date_utc_aware = pytz.utc.localize(post.start_date_utc) if post.start_date_utc and post.start_date_utc.tzinfo is None else post.start_date_utc
                        end_date_utc_aware = pytz.utc.localize(post.end_date_utc) if post.end_date_utc and post.end_date_utc.tzinfo is None else post.end_date_utc

                        # CronTrigger handles start/end dates. Schedule if end_date is not explicitly in the past.
                        # An end_date in the past means the job won't trigger again, but APScheduler should clean it up.
                        # However, it's cleaner not to schedule if the end date is already passed.
                        if end_date_utc_aware is not None and end_date_utc_aware <= now_utc_aware:
                             logger.warning(f"Пост {post.id} (циклический) пропущен при восстановлении: время окончания {end_date_utc_aware} уже в прошлом. Обновляю статус на '{PostStatusEnum.INVALID.value}'.")
                             if post.status == PostStatusEnum.SCHEDULED.value:
                                 try:
                                      await services_container.db_service.update_post_status(post.id, PostStatusEnum.INVALID.value)
                                 except Exception as update_ex:
                                      logger.error(f"Error updating post {post.id} status to INVALID after past end date: {update_ex}", exc_info=True)
                             continue # Skip scheduling

                        await schedule_recurring_post_publication(
                            post_id=post.id,
                            cron_params=post.schedule_params,
                            start_date_utc=start_date_utc_aware,
                            end_date_utc=end_date_utc_aware,
                            services_container=services_container
                        )

                    else:
                        logger.warning(f"Post {post.id} (циклический) пропущен при восстановлении: не заданы параметры Cron. Обновляю статус на '{PostStatusEnum.INVALID.value}'.")
                        if post.status == PostStatusEnum.SCHEDULED.value:
                            try:
                                 await services_container.db_service.update_post_status(post.id, PostStatusEnum.INVALID.value)
                            except Exception as update_ex:
                                 logger.error(f"Error updating post {post.id} status to INVALID after missing cron params: {update_ex}", exc_info=True)

                # Handle other schedule types if added later
                # elif post.schedule_type == 'other_type': ...

                # Tasks for deleting messages are not restored here; they are scheduled
                # by the post publication task executor AFTER sending the message.

            except Exception as e:
                logger.error(f"Ошибка при обработке поста {post.id} во время восстановления задач: {e}", exc_info=True)

    except Exception as e:
         logger.error(f"Ошибка при получении запланированных постов для восстановления: {e}", exc_info=True)


    # 2. Восстановление задач для активных RSS-лент
    try:
        # Assuming db_service.get_all_active_rss_feeds manages its own session
        active_rss_feeds: list[RssFeed] = await db_service.get_all_active_rss_feeds()
        logger.info(f"Найдено {len(active_rss_feeds)} активных RSS-лент для восстановления расписания.")

        for feed in active_rss_feeds:
            try:
                logger.debug(f"Восстановление задачи для RSS-ленты {feed.id}")
                if feed.frequency_minutes is not None and feed.frequency_minutes > 0:
                    await schedule_rss_feed_check(
                        feed_id=feed.id,
                        interval_minutes=feed.frequency_minutes,
                        services_container=services_container
                    )
                else:
                    logger.warning(f"RSS-лента {feed.id} пропущена при восстановлении: некорректная частота проверки ({feed.frequency_minutes} минут).")
                    # TODO: Optionally update feed status to invalid
            except Exception as e:
                logger.error(f"Ошибка при обработке RSS-ленты {feed.id} во время восстановления задач: {e}", exc_info=True)

    except Exception as e:
         logger.error(f"Ошибка при получении активных RSS-лент для восстановления: {e}", exc_info=True)


    # 3. APScheduler automatically handles removing outdated jobs from the job store.
    # (e.g., one-time jobs after execution, recurring jobs after end_date).
    # Explicit cleanup logic might be needed for jobs in ERROR state or similar,
    # but is not typically required for basic startup sync.

    logger.info("Процесс восстановления и синхронизации задач завершен.")

# Alias for the main startup logic for clarity in bot.py
# This function will be called by bot.py to initialize and start the scheduler
async def initialize_and_start_scheduler(database_url: str, bot_instance: Any, services_container: Any):
    """
    Combines scheduler initialization, startup process, and job reconstruction.
    This is the primary entry point for the scheduler from bot.py.

    Args:
        database_url: DB URL for job store.
        bot_instance: Bot instance to be potentially used by tasks.
        services_container: Object with references to necessary services.
    Returns:
        The initialized and started scheduler instance.
    """
    # Ensure services_container contains the bot instance and db_service instance
    # db_service is needed by reconstruct_and_sync_jobs
    if not hasattr(services_container, 'bot') or services_container.bot is None:
        services_container.bot = bot_instance # Add bot instance to the container if not present
    if not hasattr(services_container, 'db_service') or services_container.db_service is None:
        logger.error("DB Service not found in services_container. Scheduler reconstruction will fail.")
        # Potentially raise an error or exit here if DB service is critical

    init_scheduler(database_url) # Initialize scheduler with job store

    # Reconstruct jobs from DB *before* starting, so they are ready when scheduler starts
    try:
        await reconstruct_and_sync_jobs(services_container.db_service, services_container)
        logger.info("Initial job reconstruction from DB completed.")
    except Exception as e:
        logger.critical(f"Critical error during scheduler job reconstruction: {e}", exc_info=True)
        # Decide if this is a fatal error for the application

    # Start the scheduler process
    await start_scheduler_process()

    global scheduler
    # Return the global scheduler instance
    if scheduler is None:
         logger.error("Scheduler is None after initialization and start process.")
         # This indicates a failure in init_scheduler or start_scheduler_process
    return scheduler


# Alias for the shutdown logic for clarity in bot.py
async def shutdown_scheduler(scheduler_instance: AsyncIOScheduler, wait: bool = True):
    """
    Calls the internal shutdown process.
    Args:
        scheduler_instance: The scheduler instance to shut down (should be the global one obtained from initialize_and_start_scheduler).
        wait: If True, waits for currently running jobs to finish.
    """
    # Ensure the instance passed is the global one if needed, or just rely on it being correct
    global scheduler
    if scheduler is None or scheduler_instance != scheduler:
         logger.warning("Attempted to shut down a scheduler instance that does not match the global one.")
         # Proceed with shutting down the provided instance anyway? Or error?
         # Let's assume the caller passes the correct instance.
         pass # Allow shutdown of provided instance

    await shutdown_scheduler_process(wait=wait)

