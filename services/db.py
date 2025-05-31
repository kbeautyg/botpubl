# services/db.py

import asyncio
import os
import logging # Import logging
from datetime import datetime, timezone, timedelta # Import timezone, timedelta from datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, delete, exists, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
# Removed specific Column imports as they are not used for definitions here


# Import Base from a common location
from .db_base import Base # Assumes db_base.py is in the same services directory

# Import ORM models
from models.user import User, UserPreferredModeEnum
from models.user_channel import UserChannel
from models.post import Post, ScheduleTypeEnum, PostStatusEnum
from models.rss_feed import RssFeed
from models.rss_item import RssItem

# Configure logger for this module
logger = logging.getLogger(__name__)

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Use logger instead of print
    logger.critical("DATABASE_URL environment variable not set!")
    # Raise error immediately if DB URL is missing
    raise ValueError("DATABASE_URL environment variable not set")


# Use echo=True for detailed SQL logging, or link to a logging level
engine = create_async_engine(DATABASE_URL, echo=False)

# Async Session Maker
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Initializes the database by creating all tables."""
    logger.info("Initializing database...")
    try:
        async with engine.begin() as conn:
            # Base.metadata.drop_all(conn) # Optional: uncomment to drop tables before creating
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized and tables created.")
    except SQLAlchemyError as e:
         logger.critical(f"Error initializing database: {e}", exc_info=True)
         raise # Re-raise the exception

async def close_db_connection(engine_instance):
    """Disposes the database engine."""
    logger.info("Closing database connection pool...")
    if engine_instance:
        try:
            await engine_instance.dispose()
            logger.info("Database connection pool disposed.")
        except Exception as e:
            logger.error(f"Error disposing database connection pool: {e}", exc_info=True)
    else:
        logger.warning("Database engine instance is None, nothing to dispose.")


# --- CRUD FUNCTIONS ---

async def get_or_create_user(telegram_user_id: int, preferred_mode: str = UserPreferredModeEnum.BUTTONS.value, timezone: str = "Europe/Berlin") -> User:
    """
    Finds an existing user by telegram_user_id or creates a new one.
    """
    async with async_session_maker() as session:
        try:
            # Check if user exists
            result = await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
            user = result.scalars().first()

            if user:
                logger.debug(f"User found: {user}")
                return user
            else:
                # Create new user
                new_user = User(
                    telegram_user_id=telegram_user_id,
                    preferred_mode=preferred_mode,
                    timezone=timezone
                )
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                logger.info(f"New user created with telegram_user_id: {telegram_user_id}, user_id: {new_user.id}")
                return new_user
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in get_or_create_user for telegram_user_id {telegram_user_id}: {e}", exc_info=True)
            raise # Re-raise the exception after logging and rollback

async def set_user_timezone(telegram_user_id: int, timezone_str: str) -> bool:
    """
    Updates the timezone for a user. Returns True on success, False otherwise.
    """
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                update(User)
                .where(User.telegram_user_id == telegram_user_id)
                .values(timezone=timezone_str, updated_at=func.now()) # Ensure updated_at is set
                .returning(User.id) # Use returning to check if a row was updated
            )
            updated_id = result.scalar_one_or_none()
            await session.commit()
            if updated_id:
                 logger.info(f"Timezone updated for user {telegram_user_id} to {timezone_str}")
            else:
                 logger.warning(f"Could not update timezone for user {telegram_user_id}: user not found.")
            return updated_id is not None
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in set_user_timezone for telegram_user_id {telegram_user_id}, timezone {timezone_str}: {e}", exc_info=True)
            return False # Indicate failure

async def get_user_timezone(telegram_user_id: int) -> str:
    """
    Retrieves the timezone for a user. Returns default 'Europe/Berlin' if user not found.
    """
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                select(User.timezone)
                .where(User.telegram_user_id == telegram_user_id)
            )
            timezone = result.scalar_one_or_none()
            # Return stored timezone or default if user/timezone not found
            return timezone if timezone is not None else 'Europe/Berlin'
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_user_timezone for telegram_user_id {telegram_user_id}: {e}", exc_info=True)
            # Return default in case of error as well
            return 'Europe/Berlin'

async def add_user_channel(user_id: int, chat_id: int, chat_username: Optional[str]) -> UserChannel | None:
    """
    Adds a channel association for a user. user_id is the PK from the users table.
    Returns the created/reactivated UserChannel object or None on error/duplicate.
    Checks if the channel already exists for the user (active or inactive) and reactivates it if inactive.
    """
    async with async_session_maker() as session:
        try:
            # Check if the combination already exists
            existing_channel_stmt = select(UserChannel).where(
                UserChannel.user_id == user_id,
                UserChannel.chat_id == chat_id
            )
            existing_channel_result = await session.execute(existing_channel_stmt)
            existing_channel = existing_channel_result.scalars().first()

            if existing_channel:
                if not existing_channel.is_active:
                    # Reactivate the existing entry
                    existing_channel.is_active = True
                    existing_channel.removed_at = None # Clear removal timestamp
                    # Update username in case it changed
                    existing_channel.chat_username = chat_username
                    await session.commit()
                    await session.refresh(existing_channel)
                    logger.info(f"Reactivated user channel: user_id={user_id}, chat_id={chat_id}")
                    return existing_channel
                else:
                    # Already active, return the existing one
                    logger.info(f"User channel already exists and is active: user_id={user_id}, chat_id={chat_id}")
                    return existing_channel
            else:
                 # Does not exist, create new
                new_user_channel = UserChannel(
                    user_id=user_id,
                    chat_id=chat_id,
                    chat_username=chat_username,
                    is_active=True # Should be active by default on creation
                )
                session.add(new_user_channel)
                await session.commit()
                await session.refresh(new_user_channel)
                logger.info(f"Created new user channel: user_id={user_id}, chat_id={chat_id}")
                return new_user_channel

        except SQLAlchemyError as e: # Catch IntegrityError as part of general SQLAlchemyError
            await session.rollback()
            # Use logger instead of print
            logger.error(f"Database error in add_user_channel for user_id {user_id}, chat_id {chat_id}: {e}", exc_info=True)
            # Consider logging specific IntegrityError if needed, but general handler is often sufficient
            return None # Indicate failure


async def remove_user_channel(user_id: int, chat_id: int) -> bool:
    """
    Deactivates a user-channel association (soft delete). Returns True on success.
    """
    async with async_session_maker() as session:
        try:
            result = await session.execute(
                update(UserChannel)
                .where(UserChannel.user_id == user_id, UserChannel.chat_id == chat_id, UserChannel.is_active == True)
                # Use datetime.datetime.now(timezone.utc) if column is DateTime(timezone=True)
                # The model uses DateTime (naive) and expects UTC naive or timezone-aware stored as UTC naive depending on dialect/configuration.
                # Sticking to UTC naive as per original model definition implies database expects naive UTC.
                .values(is_active=False, removed_at=datetime.utcnow(), updated_at=func.now()) # Ensure updated_at is set
                .returning(UserChannel.id) # Use returning to check if a row was updated
            )
            updated_id = result.scalar_one_or_none()
            await session.commit()
            if updated_id:
                logger.info(f"User channel removed (deactivated): user_id={user_id}, chat_id={chat_id}")
            else:
                logger.warning(f"Could not remove user channel: user_id={user_id}, chat_id={chat_id} not found or already inactive.")
            return updated_id is not None
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in remove_user_channel for user_id {user_id}, chat_id {chat_id}: {e}", exc_info=True)
            return False # Indicate failure

async def get_user_channel_by_db_id(user_id: int, channel_db_id: int) -> Optional[UserChannel]:
    """
    Retrieves a user channel entry by its primary key (UserChannel.id) for a specific user.
    Ensures the channel belongs to the user.
    """
    async with async_session_maker() as session:
        try:
            stmt = select(UserChannel).where(UserChannel.id == channel_db_id, UserChannel.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_user_channel_by_db_id for user {user_id}, db_id {channel_db_id}: {e}", exc_info=True)
            return None


async def get_user_channels(user_id: int, active_only: bool = True) -> list[UserChannel]:
    """
    Retrieves channels associated with a user. user_id is PK from users table.
    """
    async with async_session_maker() as session:
        try:
            stmt = select(UserChannel).where(UserChannel.user_id == user_id)
            if active_only:
                stmt = stmt.where(UserChannel.is_active == True)
            result = await session.execute(stmt)
            channels = result.scalars().all()
            logger.debug(f"Retrieved {len(channels)} channels for user_id {user_id} (active_only={active_only}).")
            return channels
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_user_channels for user_id {user_id}: {e}", exc_info=True)
            return [] # Return empty list on error

async def add_scheduled_post(
    user_id: int,
    chat_ids: list[int],
    text: str | None,
    media_paths: list[str] | None, # Assuming this stores paths or file_ids
    schedule_type: str, # Assuming string matches Enum values
    schedule_params: dict | None,
    run_date_utc: datetime | None,
    delete_after_seconds: int | None,
    delete_at_utc: datetime | None,
    status: str = PostStatusEnum.SCHEDULED.value # Use Enum value directly
) -> Post:
    """
    Adds a new scheduled post entry to the database.
    Note: Ensure run_date_utc and delete_at_utc are timezone-aware UTC datetime objects
    if the column type is DateTime(timezone=True). Based on the Post model,
    it's DateTime (naive), so pass UTC naive datetime objects created with datetime.utcnow().
    """
    async with async_session_maker() as session:
        try:
            new_post = Post(
                user_id=user_id,
                chat_ids=chat_ids, # Stored as JSON
                text=text,
                media_paths=media_paths, # Stored as JSON
                schedule_type=schedule_type, # Stored as string Enum value
                schedule_params=schedule_params, # Stored as JSON
                # Convert timezone-aware UTC to naive UTC if column is DateTime (naive)
                run_date_utc=run_date_utc.replace(tzinfo=None) if run_date_utc and run_date_utc.tzinfo is not None else run_date_utc,
                delete_after_seconds=delete_after_seconds,
                 # Convert timezone-aware UTC to naive UTC if column is DateTime (naive)
                delete_at_utc=delete_at_utc.replace(tzinfo=None) if delete_at_utc and delete_at_utc.tzinfo is not None else delete_at_utc,
                status=status # Stored as string Enum value
            )
            session.add(new_post)
            await session.commit()
            await session.refresh(new_post)
            logger.info(f"Added new scheduled post with ID: {new_post.id} for user {user_id}")
            return new_post
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in add_scheduled_post for user {user_id}: {e}", exc_info=True)
            raise # Re-raise the exception

async def get_post_by_id(post_id: int) -> Post | None:
    """
    Retrieves a post by its ID.
    """
    async with async_session_maker() as session:
        try:
            result = await session.execute(select(Post).where(Post.id == post_id))
            post = result.scalars().first()
            if post:
                logger.debug(f"Retrieved post with ID: {post_id}")
            else:
                 logger.debug(f"Post with ID: {post_id} not found.")
            return post
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_post_by_id for post ID {post_id}: {e}", exc_info=True)
            return None # Return None on error

async def get_all_scheduled_posts_for_reload(session: AsyncSession) -> list[Post]:
    """
    Retrieves all posts with status 'scheduled'.
    This function is designed to be called with an existing session, e.g., during startup.
    """
    try:
        # Use the string value as per how it's stored by default in the model
        stmt = select(Post).where(Post.status == PostStatusEnum.SCHEDULED.value)
        result = await session.execute(stmt)
        posts = result.scalars().all()
        logger.info(f"Retrieved {len(posts)} scheduled posts for reload.")
        return posts
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_all_scheduled_posts_for_reload: {e}", exc_info=True)
        # Note: No rollback here as the session is managed by the caller
        return [] # Return empty list on error

async def get_user_posts(user_id: int, statuses: list[str] | None = None) -> list[Post]:
    """
    Retrieves posts for a specific user. user_id is PK from users table.
    Optionally filtered by statuses. Defaults to 'scheduled' status if statuses is None.
    """
    async with async_session_maker() as session:
        try:
            stmt = select(Post).where(Post.user_id == user_id)
            # Use string values for filtering as they are stored as strings
            if statuses is None:
                stmt = stmt.where(Post.status == PostStatusEnum.SCHEDULED.value)
            elif statuses:
                # Ensure the list contains valid string enum values if needed,
                # or just filter by the provided strings. Filtering by provided strings is simpler.
                stmt = stmt.where(Post.status.in_(statuses))
            else:
                 # If statuses is an empty list, return no posts
                 logger.debug(f"get_user_posts for user {user_id} called with empty statuses list, returning empty.")
                 return []

            result = await session.execute(stmt)
            posts = result.scalars().all()
            logger.debug(f"Retrieved {len(posts)} posts for user {user_id} with statuses {statuses}.")
            return posts
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_user_posts for user_id {user_id}, statuses {statuses}: {e}", exc_info=True)
            return [] # Return empty list on error

async def update_post_details(post_id: int, **kwargs: Any) -> Post | None:
    """
    Updates specific fields of a post. Returns the updated Post object or None.
    Handles potential conversion for datetime fields.
    """
    async with async_session_maker() as session:
        try:
            # Filter kwargs to only include valid updateable fields
            valid_keys = Post.__table__.columns.keys()
            update_values = {}
            for k, v in kwargs.items():
                if k in valid_keys:
                    # Handle specific conversions if needed, e.g., datetime timezone
                    # Assuming Post model has DateTime (naive) for these columns
                    if k in ['run_date_utc', 'delete_at_utc'] and isinstance(v, datetime):
                        if v.tzinfo is not None:
                             # If input is timezone-aware, convert to UTC naive for naive column
                             update_values[k] = v.astimezone(timezone.utc).replace(tzinfo=None)
                        else:
                             # If input is naive, use as is (assuming it's intended as UTC naive)
                             update_values[k] = v
                    elif k == 'schedule_type' and isinstance(v, ScheduleTypeEnum):
                         update_values[k] = v.value # Ensure storing string value of Enum
                    elif k == 'status' and isinstance(v, PostStatusEnum):
                         update_values[k] = v.value # Ensure storing string value of Enum
                    # Handle JSON fields - assume input is already list/dict
                    # Handle int/str/bool fields - assume input is already correct type
                    else:
                         update_values[k] = v
                else:
                    logger.warning(f"Attempted to update unknown field '{k}' for Post ID {post_id}.")


            if not update_values:
                logger.warning(f"No valid fields provided for update_post_details for post ID {post_id}.")
                # Fetch the existing post to return
                return await get_post_by_id(post_id)

            # Always update updated_at
            update_values['updated_at'] = func.now()

            stmt = update(Post).where(Post.id == post_id).values(**update_values)
            await session.execute(stmt)
            await session.commit()

            # Fetch the updated post to return
            updated_post = await get_post_by_id(post_id)
            if updated_post:
                 logger.info(f"Post ID {post_id} details updated.")
            else:
                 logger.warning(f"Post ID {post_id} updated but not found after update?") # Should not happen normally
            return updated_post
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in update_post_details for post ID {post_id}: {e}", exc_info=True)
            return None # Return None on error

# Alias update_post_details for clarity in task handlers
async def update_post_status(post_id: int, status: str) -> Post | None:
     """Helper to update only the status of a post."""
     try:
         # Validate status string against Enum values before updating
         # This will raise ValueError if status string is invalid
         status_enum = PostStatusEnum(status)
         return await update_post_details(post_id, status=status_enum.value)
     except ValueError:
         logger.error(f"Attempted to update post {post_id} with invalid status string: {status}")
         return None # Indicate failure due to invalid status


async def delete_post_by_id(post_id: int) -> bool:
    """
    Deletes a post by its ID. Returns True on success.
    """
    async with async_session_maker() as session:
        try:
            stmt = delete(Post).where(Post.id == post_id).returning(Post.id)
            result = await session.execute(stmt)
            deleted_id = result.scalar_one_or_none()
            await session.commit()
            if deleted_id:
                 logger.info(f"Post ID {post_id} successfully deleted.")
            else:
                 logger.warning(f"Post with ID {post_id} not found for deletion.")
            return deleted_id is not None # True if a row was actually deleted
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in delete_post_by_id for post ID {post_id}: {e}", exc_info=True)
            return False # Indicate failure

async def add_rss_feed(
    user_id: int, # PK from users table
    feed_url: str,
    channel_ids: list[int],
    filter_keywords: list[str] | None,
    frequency_minutes: int
) -> RssFeed:
    """
    Adds a new RSS feed subscription for a user.
    """
    async with async_session_maker() as session:
        try:
            new_feed = RssFeed(
                user_id=user_id,
                feed_url=feed_url,
                channels=channel_ids, # Stored as JSON
                filter_keywords=filter_keywords, # Stored as JSON
                frequency_minutes=frequency_minutes,
                # next_check_utc will be set by the scheduler logic upon first check or manually after adding
                # For simplicity, we can set it to now() UTC on creation, so scheduler picks it up soon
                next_check_utc=datetime.now(timezone.utc)
            )
            session.add(new_feed)
            await session.commit()
            await session.refresh(new_feed)
            logger.info(f"Added new RSS feed with ID: {new_feed.id} for user {user_id}, URL: {feed_url}")
            return new_feed
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in add_rss_feed for user {user_id}, URL {feed_url}: {e}", exc_info=True)
            raise # Re-raise the exception

async def get_rss_feed_by_id(feed_id: int) -> RssFeed | None:
    """
    Retrieves an RSS feed by its ID.
    """
    async with async_session_maker() as session:
        try:
            result = await session.execute(select(RssFeed).where(RssFeed.id == feed_id))
            feed = result.scalars().first()
            if feed:
                 logger.debug(f"Retrieved RSS feed with ID: {feed_id}")
            else:
                 logger.debug(f"RSS feed with ID: {feed_id} not found.")
            return feed
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_rss_feed_by_id for feed ID {feed_id}: {e}", exc_info=True)
            return None # Return None on error

async def get_all_active_rss_feeds() -> list[RssFeed]:
    """
    Retrieves all RSS feeds considered active for the scheduler.
    Assumes all entries are 'active' unless marked otherwise in a future column.
    Used for initial sync/reload.
    """
    async with async_session_maker() as session:
        try:
            # Add a filter if an 'is_active' column is added to RssFeed later
            stmt = select(RssFeed)
            result = await session.execute(stmt)
            feeds = result.scalars().all()
            logger.info(f"Retrieved {len(feeds)} active RSS feeds for reload.")
            return feeds
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_all_active_rss_feeds: {e}", exc_info=True)
            return [] # Return empty list on error

async def get_active_rss_feeds_due_for_check() -> list[RssFeed]:
    """
    Retrieves RSS feeds that are active and whose next_check_utc is now or in the past.
    Used by the periodic RSS checking task.
    """
    async with async_session_maker() as session:
        try:
            # Ensure comparison is timezone-aware as next_check_utc is stored as timezone-aware
            now_utc = datetime.now(timezone.utc)
            stmt = select(RssFeed).where(RssFeed.next_check_utc <= now_utc)
            # Add filter for is_active if that column is added later
            result = await session.execute(stmt)
            feeds = result.scalars().all()
            logger.debug(f"Retrieved {len(feeds)} RSS feeds due for check.")
            return feeds
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_active_rss_feeds_due_for_check: {e}", exc_info=True)
            return [] # Return empty list on error


async def get_user_rss_feeds(user_id: int) -> list[RssFeed]:
    """
    Retrieves RSS feeds subscribed to by a specific user. user_id is PK from users table.
    """
    async with async_session_maker() as session:
        try:
            stmt = select(RssFeed).where(RssFeed.user_id == user_id)
            result = await session.execute(stmt)
            feeds = result.scalars().all()
            logger.debug(f"Retrieved {len(feeds)} RSS feeds for user {user_id}.")
            return feeds
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_user_rss_feeds for user_id {user_id}: {e}", exc_info=True)
            return [] # Return empty list on error

async def update_rss_feed_details(feed_id: int, **kwargs: Any) -> RssFeed | None:
    """
    Updates specific fields of an RSS feed configuration. Returns the updated RssFeed object or None.
    Handles potential conversion for datetime fields like next_check_utc.
    """
    async with async_session_maker() as session:
        try:
            valid_keys = RssFeed.__table__.columns.keys()
            update_values = {}
            for k, v in kwargs.items():
                 if k in valid_keys:
                    # Handle specific conversions for DateTime(timezone=True) column
                    if k == 'next_check_utc' and isinstance(v, datetime):
                         if v.tzinfo is None:
                             # If input is naive, assume UTC and make it aware
                             update_values[k] = pytz.utc.localize(v)
                         else:
                             # If input is aware, convert to UTC
                             update_values[k] = v.astimezone(pytz.utc)
                    # Handle JSON fields - assume input is already list/dict
                    # Handle int/str fields - assume input is already correct type
                    else:
                         update_values[k] = v
                 else:
                     logger.warning(f"Attempted to update unknown field '{k}' for RSS Feed ID {feed_id}.")


            if not update_values:
                logger.warning(f"No valid fields provided for update_rss_feed_details for feed ID {feed_id}.")
                return await get_rss_feed_by_id(feed_id) # Return the existing feed

            # Always update updated_at
            update_values['updated_at'] = func.now()

            stmt = update(RssFeed).where(RssFeed.id == feed_id).values(**update_values)
            await session.execute(stmt)
            await session.commit()

            # Fetch the updated feed to return
            updated_feed = await get_rss_feed_by_id(feed_id)
            if updated_feed:
                logger.info(f"RSS Feed ID {feed_id} details updated.")
            else:
                 logger.warning(f"RSS Feed ID {feed_id} updated but not found after update?") # Should not happen
            return updated_feed
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in update_rss_feed_details for feed ID {feed_id}: {e}", exc_info=True)
            return None # Return None on error

async def update_rss_feed_next_check_utc(feed_id: int, frequency_minutes: int):
    """
    Updates the next check time for a feed based on its frequency.
    Schedules the next check `frequency_minutes` from now (UTC).
    """
    async with async_session_maker() as session:
        try:
            if frequency_minutes is None or frequency_minutes <= 0:
                 logger.warning(f"Cannot update next_check_utc for feed {feed_id} with non-positive frequency: {frequency_minutes}")
                 # Optionally update status to error/invalid
                 return False

            next_check = datetime.now(timezone.utc) + timedelta(minutes=frequency_minutes)

            result = await session.execute(
                update(RssFeed)
                .where(RssFeed.id == feed_id)
                .values(next_check_utc=next_check, updated_at=func.now()) # Ensure updated_at is set
                .returning(RssFeed.id)
            )
            updated_id = result.scalar_one_or_none()
            await session.commit()
            if updated_id:
                 logger.info(f"Updated next_check_utc for RSS feed {feed_id} to {next_check}.")
            else:
                 logger.warning(f"Could not update next_check_utc for RSS feed {feed_id}: feed not found.")
            return updated_id is not None
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in update_rss_feed_next_check_utc for feed {feed_id}: {e}", exc_info=True)
            return False


async def delete_rss_feed_by_id(feed_id: int) -> bool:
    """
    Deletes an RSS feed configuration and associated rss_items. Returns True on success.
    Assumes ON DELETE CASCADE is NOT set in DB, performs manual deletion of items.
    """
    async with async_session_maker() as session:
        try:
            # Delete associated RssItems first
            delete_items_stmt = delete(RssItem).where(RssItem.feed_id == feed_id)
            items_deleted = await session.execute(delete_items_stmt)
            logger.debug(f"Deleted {items_deleted.rowcount} RSS items for feed ID {feed_id}.")

            # Then delete the feed itself
            delete_feed_stmt = delete(RssFeed).where(RssFeed.id == feed_id).returning(RssFeed.id)
            result = await session.execute(delete_feed_stmt)
            deleted_id = result.scalar_one_or_none()
            await session.commit()

            if deleted_id:
                 logger.info(f"RSS Feed ID {feed_id} successfully deleted.")
            else:
                 logger.warning(f"RSS Feed with ID {feed_id} not found for deletion.")
            return deleted_id is not None # True if a row was actually deleted
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in delete_rss_feed_by_id for feed ID {feed_id}: {e}", exc_info=True)
            return False # Indicate failure

async def mark_rss_item_posted(feed_id: int, item_guid: str, published_at: datetime | None) -> RssItem:
    """
    Marks an RSS item as posted. Creates the item entry if it doesn't exist.
    Assumes published_at is timezone-aware UTC datetime object if column is DateTime(timezone=True).
    """
    async with async_session_maker() as session:
        try:
            # Check if item exists
            result = await session.execute(
                select(RssItem).where(RssItem.feed_id == feed_id, RssItem.item_guid == item_guid)
            )
            rss_item = result.scalars().first()

            if rss_item:
                # Item exists, mark as posted if not already
                if not rss_item.is_posted:
                    rss_item.is_posted = True
                    # Optional: update created_at/published_at if logic requires re-marking
                    # rss_item.created_at = datetime.now(timezone.utc)
                    # if published_at and published_at.tzinfo is not None:
                    #      rss_item.published_at = published_at.astimezone(timezone.utc)
                    # else: # Assume naive input is UTC if column expects aware
                    #      rss_item.published_at = published_at.replace(tzinfo=timezone.utc) if published_at else None
                    await session.commit()
                    await session.refresh(rss_item)
                    logger.debug(f"Marked existing RSS item as posted: feed={feed_id}, guid={item_guid}")
                else:
                     logger.debug(f"RSS item already marked as posted: feed={feed_id}, guid={item_guid}")
                return rss_item
            else:
                # Create new item and mark as posted
                new_rss_item = RssItem(
                    feed_id=feed_id,
                    item_guid=item_guid,
                     # Ensure published_at is timezone-aware UTC if column is DateTime(timezone=True)
                    published_at=published_at.astimezone(timezone.utc) if published_at and published_at.tzinfo is not None else (pytz.utc.localize(published_at) if published_at else None), # Localize naive to UTC
                    is_posted=True,
                    created_at=datetime.now(timezone.utc) # Ensure created_at is timezone-aware UTC
                )
                session.add(new_rss_item)
                await session.commit()
                await session.refresh(new_rss_item)
                logger.debug(f"Created and marked new RSS item as posted: feed={feed_id}, guid={item_guid}")
                return new_rss_item
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in mark_rss_item_posted (feed={feed_id}, guid={item_guid}): {e}", exc_info=True)
            raise # Re-raise the exception

async def is_rss_item_posted(feed_id: int, item_guid: str) -> bool:
    """
    Checks if an RSS item has already been marked as posted for a given feed.
    """
    async with async_session_maker() as session:
        try:
            exists_stmt = select(exists().where(
                RssItem.feed_id == feed_id,
                RssItem.item_guid == item_guid,
                RssItem.is_posted == True # Explicitly check for is_posted True
            ))
            result = await session.scalar(exists_stmt)
            logger.debug(f"Checked if RSS item is posted (feed={feed_id}, guid={item_guid}): {result}")
            return bool(result) # Ensure boolean return
        except SQLAlchemyError as e:
            logger.error(f"Database error in is_rss_item_posted (feed={feed_id}, guid={item_guid}): {e}", exc_info=True)
            return False # Return False on error (safer not to post again)

