# utils/datetime_utils.py

import pytz
from datetime import datetime, timedelta
from typing import Optional

# Note: The list of timezones is extensive. Using pytz.all_timezones is sufficient.
# A limited list could be used for a more user-friendly selection interface if needed.

def _ensure_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensures a datetime object is timezone-aware UTC.
    Assumes naive datetime is UTC if no timezone is provided.
    Returns None if input is None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        return pytz.utc.localize(dt)
    else:
        # Convert to UTC if already timezone-aware
        return dt.astimezone(pytz.utc)


def format_datetime(dt_utc: datetime, user_tz_str: str) -> str:
    """
    Formats a UTC timezone-aware datetime object into a string
    using the specified user timezone.

    Args:
        dt_utc (datetime): Timezone-aware datetime object in UTC.
        user_tz_str (str): String representation of the user's timezone (IANA Zoneinfo Name).

    Returns:
        str: Formatted datetime string (e.g., "01.01.2024 15:30"). Returns empty string on error.
    """
    if dt_utc is None or dt_utc.tzinfo is None or dt_utc.tzinfo.utcoffset(dt_utc) != timedelta(0):
        # Input is not a timezone-aware UTC datetime
        # Try to convert it to UTC first, assuming naive is UTC
        dt_utc = _ensure_utc_aware(dt_utc)
        if dt_utc is None:
             return "" # Cannot format invalid input

    try:
        user_tz = pytz.timezone(user_tz_str)
        dt_user_tz = dt_utc.astimezone(user_tz)
        return dt_user_tz.strftime('%d.%m.%Y %H:%M')
    except pytz.UnknownTimeZoneError:
        # Fallback to UTC if user timezone is invalid
        return dt_utc.strftime('%d.%m.%Y %H:%M (UTC)')
    except Exception:
        # Catch any other formatting errors
        return ""


def convert_to_utc(naive_dt_user_tz: datetime, user_tz_str: str) -> Optional[datetime]:
    """
    Converts a naive datetime object (representing time in user's timezone) to a
    UTC timezone-aware datetime object.

    Args:
        naive_dt_user_tz (datetime): Naive datetime object.
        user_tz_str (str): String representation of the user's timezone (IANA Zoneinfo Name).

    Returns:
        Optional[datetime]: Timezone-aware datetime object in UTC, or None on error.
    """
    if naive_dt_user_tz is None:
        return None

    try:
        user_tz = pytz.timezone(user_tz_str)
        # Localize the naive datetime with the user's timezone
        localized_dt = user_tz.localize(naive_dt_user_tz)
        # Convert the localized datetime to UTC
        utc_dt = localized_dt.astimezone(pytz.utc)
        return utc_dt
    except pytz.UnknownTimeZoneError:
        # Invalid user timezone
        return None
    except Exception:
         # Catch any other errors during localization or conversion
        return None


def convert_from_utc(dt_utc: datetime, target_tz_str: str) -> Optional[datetime]:
    """
    Converts a UTC timezone-aware datetime object to a timezone-aware datetime object
    in the specified target timezone.

    Args:
        dt_utc (datetime): Timezone-aware datetime object in UTC.
        target_tz_str (str): String representation of the target timezone (IANA Zoneinfo Name).

    Returns:
        Optional[datetime]: Timezone-aware datetime object in the target timezone, or None on error.
    """
    if dt_utc is None or dt_utc.tzinfo is None or dt_utc.tzinfo.utcoffset(dt_utc) != timedelta(0):
         # Input is not a timezone-aware UTC datetime, try to convert first
         dt_utc = _ensure_utc_aware(dt_utc)
         if dt_utc is None:
              return None # Cannot process invalid input

    try:
        target_tz = pytz.timezone(target_tz_str)
        dt_target_tz = dt_utc.astimezone(target_tz)
        return dt_target_tz
    except pytz.UnknownTimeZoneError:
        # Invalid target timezone
        return None
    except Exception:
         # Catch any other errors during conversion
         return None

def get_user_timezone_str(user_id: int, db_service: Any) -> str:
    """
    Retrieves the user's timezone string from the database asynchronously.
    Note: This function requires an async context and a db_service instance.
    This is a placeholder implementation. In a real handler/task, you would await
    the actual async db call.

    Args:
        user_id (int): The user's Telegram ID.
        db_service: An instance of the database service with an async method like get_user_timezone.

    Returns:
        str: The user's timezone string or a default.
    """
    # This function is designed to be a placeholder example.
    # Actual usage in async code:
    # user_tz = await db_service.get_user_timezone(user_id)
    # return user_tz or 'Europe/Berlin'
    # To make this callable in a mock scenario or for basic demonstration:
    # This implementation is NOT ASYNC and should not be used directly in aiogram handlers.
    # It's here as a conceptual helper illustration.
    # For actual use in async handlers, you must await the DB call.
    # We'll remove the sync implementation and keep the docstring.
    raise NotImplementedError("get_user_timezone_str requires an async db call and should be implemented accordingly in handlers/services.")

# Example Placeholder - Do not use this sync version in async handlers
# async def get_user_timezone_str_async(user_id: int, db_service: Any) -> str:
#      """
#      Async version to retrieve user timezone string.
#      """
#      try:
#          user_tz = await db_service.get_user_timezone(user_id)
#          return user_tz if user_tz else 'Europe/Berlin'
#      except Exception as e:
#          logging.error(f"Failed to get user timezone from DB for user {user_id}: {e}")
#          return 'Europe/Berlin' # Return default on error


# Example Usage (for testing purposes, requires installing pytz)
if __name__ == '__main__':
    print("Datetime Utility functions defined.")

    # Example conversion and formatting
    dt_naive_berlin = datetime(2024, 1, 1, 15, 30, 0)
    user_tz_berlin = 'Europe/Berlin'
    user_tz_ny = 'America/New_York'

    # Convert naive Berlin time to UTC
    dt_utc_from_berlin = convert_to_utc(dt_naive_berlin, user_tz_berlin)
    print(f"Naive Berlin time: {dt_naive_berlin}")
    print(f"Converted to UTC: {dt_utc_from_berlin}")

    if dt_utc_from_berlin:
        # Format UTC time for the user's original timezone (Berlin)
        formatted_for_berlin = format_datetime(dt_utc_from_berlin, user_tz_berlin)
        print(f"Formatted back for Berlin ({user_tz_berlin}): {formatted_for_berlin}")

        # Format UTC time for a different timezone (New York)
        formatted_for_ny = format_datetime(dt_utc_from_berlin, user_tz_ny)
        print(f"Formatted for New York ({user_tz_ny}): {formatted_for_ny}")

        # Convert UTC time to New York timezone-aware datetime
        dt_aware_ny = convert_from_utc(dt_utc_from_berlin, user_tz_ny)
        print(f"Converted UTC to NY aware: {dt_aware_ny}")

    # Example with invalid timezone
    invalid_tz = 'Invalid/TimeZone'
    dt_utc_invalid = convert_to_utc(dt_naive_berlin, invalid_tz)
    print(f"\nConverting naive Berlin time with invalid TZ '{invalid_tz}': {dt_utc_invalid}") # Should be None

    # Example formatting invalid UTC input
    dt_naive_local_unspecified = datetime.now()
    print(f"\nFormatting naive local time '{dt_naive_local_unspecified}' for Berlin: {format_datetime(dt_naive_local_unspecified, user_tz_berlin)}") # Should treat as UTC by default formatting fallback

    dt_aware_local = datetime.now().astimezone() # System local timezone
    print(f"Formatting aware local time '{dt_aware_local}' for Berlin: {format_datetime(dt_aware_local, user_tz_berlin)}") # Should convert to UTC then format for Berlin


