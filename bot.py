import asyncio
import logging
import sys
import os

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage # Using MemoryStorage for simplicity in this example
# If you need persistent FSM state, consider SQLAlchemyStorage or RedisStorage
# from aiogram.fsm.storage.redis import RedisStorage, Redis
from aiogram.fsm.storage.sqlalchemy import SQLAlchemyStorage

# Import database and scheduler initialization functions and services
import services.db as db_service
import services.scheduler as scheduler_service
import services.telegram_api as telegram_api_service # Assuming this exists and is needed
import services.content_manager as content_manager_service # Assuming this exists and is needed
import services.rss as rss_service # Assuming this exists and is needed

# Import handlers
from handlers import (
    commands as commands_handler,
    post_creation as post_creation_handler,
    inline_buttons as inline_buttons_handler,
    rss_integration as rss_integration_handler,
    post_management as post_management_handler,
    channel_management as channel_management_handler,
    timezone_management as timezone_management_handler
)

# Import ReplyKeyboard from keyboards
from keyboards.reply_keyboards import get_main_menu_keyboard

# Configure logging
# The utils.logger module should handle the actual configuration (console and file output)
# Import the logger config to ensure handlers are added
import utils.logger # This import alone should configure the root logger

# Get a logger instance for this module
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get bot token from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical("BOT_TOKEN environment variable not set!")
    sys.exit(1)

# Get database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.critical("DATABASE_URL environment variable not set!")
    sys.exit(1)

# Get logging level from environment variables
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# Set the logging level based on environment variable
logging.getLogger().setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


async def main() -> None:
    """
    Entry point function to initialize and start the bot and scheduler.
    """
    logger.info("Starting bot...")

    # Initialize database
    try:
        await db_service.init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}", exc_info=True)
        # Depending on requirements, you might want to exit here if DB is essential
        # sys.exit(1) # Uncomment to exit on DB init failure


    # Initialize Bot, Dispatcher and Storage
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)

    # Use SQLAlchemyStorage for persistent FSM state
    # Pass the async_session_maker from db_service
    # Need to ensure async_session_maker is accessible from db_service module
    # Assuming db_service.async_session_maker is available after db_service.init_db()
    try:
        # Check if async_session_maker is available and is a sessionmaker
        if not hasattr(db_service, 'async_session_maker') or not isinstance(db_service.async_session_maker, type(db_service.sessionmaker(db_service.engine, class_=db_service.AsyncSession))):
             raise AttributeError("db_service.async_session_maker not found or not correctly initialized.")

        storage = SQLAlchemyStorage(db_service.async_session_maker)
        logger.info("Using SQLAlchemyStorage for FSM state.")
    except Exception as e:
        logger.critical(f"Failed to initialize SQLAlchemyStorage: {e}", exc_info=True)
        logger.warning("Falling back to MemoryStorage. FSM state will not persist across restarts.")
        storage = MemoryStorage()


    dp = Dispatcher(storage=storage)

    # Pass necessary services to workflow_data
    # These services can then be accessed in handlers using dependency injection
    services_container = type('ServicesContainer', (object,), {
        'bot': bot, # Pass bot instance
        'db_service': db_service,
        'scheduler_service': scheduler_service,
        'telegram_api_service': telegram_api_service,
        'content_manager_service': content_manager_service,
        'rss_service': rss_service,
        # Add other services/dependencies here
    })() # Create a simple object to hold services

    # Make services available to handlers via workflow_data
    dp["services"] = services_container


    # Register routers
    # Ensure all routers are imported and included
    dp.include_routers(
        commands_handler.commands_router, # Assuming router is named commands_router
        post_creation_handler.router, # Assuming router is named router in post_creation
        inline_buttons_handler.router, # Assuming router is named router in inline_buttons
        rss_integration_handler.router, # Assuming router is named router in rss_integration
        post_management_handler.router, # Assuming router is named router in post_management
        channel_management_handler.router, # Assuming router is named router in channel_management
        timezone_management_handler.router # Assuming router is named router in timezone_management
    )

    # Initialize and start the scheduler
    # Pass services_container to the scheduler initialization/sync function
    try:
        # scheduler_service.initialize_and_start_scheduler handles init, start, and sync
        await scheduler_service.initialize_and_start_scheduler(
            database_url=DATABASE_URL,
            bot_instance=bot, # Pass bot instance
            services_container=services_container # Pass services
        )
        logger.info("Scheduler initialized and jobs synced/started.")
    except Exception as e:
        logger.critical(f"Failed to initialize or start scheduler: {e}", exc_info=True)
        # Decide if this is a fatal error. Bot can potentially run without scheduler, but core functionality is lost.


    # Register a handler for the start command to set up user and reply keyboard
    @dp.message(commands_handler.CommandStart()) # Use the filter from commands.py
    async def handle_start_command(message: types.Message, db_service: db_service): # DI for db_service
        user_id = message.from_user.id
        telegram_user_id = message.from_user.id
        # Use get_or_create_user from db_service
        try:
            user = await db_service.get_or_create_user(telegram_user_id)
            logger.info(f"User {user_id} started bot.")
            await message.answer(
                f"Привет, {message.from_user.full_name}! Я бот для отложенного постинга. Используй меню ниже для управления.",
                reply_markup=get_main_menu_keyboard() # Use the correct function name
            )
        except Exception as e:
            logger.error(f"Error handling start command for user {user_id}: {e}", exc_info=True)
            await message.answer("Произошла ошибка при инициализации вашего аккаунта. Попробуйте позже.")


    # Start polling
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Bot polling stopped due to an error: {e}", exc_info=True)
    finally:
        # Ensure scheduler is shut down gracefully
        logger.info("Shutting down scheduler...")
        # Pass the scheduler instance to shutdown
        await scheduler_service.shutdown_scheduler(scheduler_service.scheduler, wait=True) # Wait for jobs to finish
        logger.info("Scheduler shutdown complete.")

        # Ensure database connection pool is disposed
        logger.info("Disposing database connection pool...")
        await db_service.close_db_connection(db_service.engine)
        logger.info("Database connection pool disposed.")

        logger.info("Bot stopped.")


if __name__ == "__main__":
    # Run the main function
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred during bot execution: {e}", exc_info=True)
