#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль с функциями валидации для Telegram-бота.
Содержит функции для проверки различных типов данных, используемых в боте.
"""

from datetime import datetime
import pytz
import re
from typing import Optional, Dict, Any
# Для Python < 3.9, импортировать Dict из typing
# from typing import Dict

# Ограничение на размер медиафайлов в байтах (20 МБ)
MAX_MEDIA_SIZE_BYTES = 20 * 1024 * 1024

# Разрешенные MIME-типы для медиафайлов
ALLOWED_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'video/mp4',
    'image/gif',
    'application/pdf'
}

def validate_datetime(text_datetime: str, user_tz_str: str) -> Optional[datetime]:
    """
    Проверяет текстовую дату и время на соответствие формату DD.MM.YYYY HH:MM
    и на то, что оно находится в будущем относительно текущего момента в часовом поясе пользователя.

    Args:
        text_datetime (str): Строка с датой и временем в формате 'DD.MM.YYYY HH:MM'.
        user_tz_str (str): Строка с названием часового пояса пользователя (IANA Zoneinfo Name).

    Returns:
        Optional[datetime]: Объект datetime в UTC, если валидация успешна и время в будущем,
                            иначе None.
    """
    try:
        # Парсим строку в наивный объект datetime
        naive_dt = datetime.strptime(text_datetime, '%d.%m.%Y %H:%M')
    except ValueError:
        # Ошибка парсинга формата
        return None

    try:
        # Получаем объект часового пояса пользователя
        user_tz = pytz.timezone(user_tz_str)
    except pytz.UnknownTimeZoneError:
        # Некорректный часовой пояс пользователя
        return None

    # Локализуем наивный datetime с учетом часового пояса пользователя
    localized_dt = user_tz.localize(naive_dt)

    # Получаем текущее время в часовом поясе пользователя
    now_in_user_tz = datetime.now(user_tz)

    # Проверяем, что указанная дата и время находятся в будущем
    if localized_dt <= now_in_user_tz:
        return None # Время не в будущем

    # Конвертируем локализованное время в UTC
    utc_dt = localized_dt.astimezone(pytz.utc)

    return utc_dt

def validate_cron_params(params: Dict[str, Any]) -> bool:
    """
    Проверяет словарь параметров для APScheduler cron-задач.
    Выполняет базовую проверку наличия и типа необходимых полей
    для каждого типа расписания ('daily', 'weekly', 'monthly', 'yearly').

    Args:
        params (Dict[str, Any]): Словарь с параметрами cron.

    Returns:
        bool: True, если параметры кажутся корректными для APScheduler, иначе False.
    """
    if not isinstance(params, dict) or 'type' not in params:
        return False # Параметры не словарь или отсутствует тип

    schedule_type = params['type']

    # Базовая проверка формата времени HH:MM (опционально, APScheduler более гибок, но для формы ввода может быть полезно)
    def is_valid_time_format(time_str):
        if not isinstance(time_str, str):
            return False
        try:
            datetime.strptime(time_str, '%H:%M')
            return True
        except ValueError:
            return False

    # Проверка параметров в зависимости от типа расписания
    if schedule_type == 'daily':
        # Ожидаем поле 'time' в формате 'HH:MM'
        if 'time' not in params or not is_valid_time_format(params['time']):
            return False

    elif schedule_type == 'weekly':
        # Ожидаем поля 'time' и 'days_of_week'
        if 'time' not in params or not is_valid_time_format(params['time']):
            return False
        if 'days_of_week' not in params or not isinstance(params['days_of_week'], (str, int, list)):
             # APScheduler принимает str (напр. 'mon,fri'), int (0-6), или list
             # Базовая проверка: просто убедимся, что поле присутствует и имеет ожидаемый тип (str/int/list)
             return False

    elif schedule_type == 'monthly':
        # Ожидаем поля 'time' и 'day_of_month'
        if 'time' not in params or not is_valid_time_format(params['time']):
            return False
        if 'day_of_month' not in params or not isinstance(params['day_of_month'], (str, int)):
            # APScheduler принимает str (напр. '1-5') или int (1-31)
            # Базовая проверка: просто убедимся, что поле присутствует и имеет ожидаемый тип (str/int)
             return False
        # Можно добавить проверку на диапазон 1-31, если day_of_month int/str число
        # if isinstance(params['day_of_month'], int) and not (1 <= params['day_of_month'] <= 31):
        #    return False
        # if isinstance(params['day_of_month'], str) and not re.fullmatch(r'\d+', params['day_of_month']) and not re.fullmatch(r'\d+-\d+', params['day_of_month']):
        #     return False


    elif schedule_type == 'yearly':
        # Ожидаем поля 'time', 'month' и 'day'
        if 'time' not in params or not is_valid_time_format(params['time']):
            return False
        if 'month' not in params or not isinstance(params['month'], (str, int)):
             # APScheduler принимает str (напр. '1-3') или int (1-12)
             return False
        if 'day' not in params or not isinstance(params['day'], (str, int)):
            # APScheduler принимает str (напр. '1-5') или int (1-31)
            return False
        # Можно добавить проверку на диапазон month (1-12) и day (1-31)
        # if isinstance(params['month'], int) and not (1 <= params['month'] <= 12): return False
        # if isinstance(params['day'], int) and not (1 <= params['day'] <= 31): return False


    else:
        # Неизвестный тип расписания
        return False

    # Если проверки для конкретного типа прошли, считаем параметры корректными
    return True

def validate_media_file(file_size: int, mime_type: Optional[str]) -> bool:
    """
    Проверяет размер и MIME-тип медиафайла.

    Args:
        file_size (int): Размер файла в байтах.
        mime_type (Optional[str]): MIME-тип файла или None.

    Returns:
        bool: True, если файл допустим по размеру и типу, иначе False.
    """
    # Проверка размера файла (должен быть больше 0 и не превышать MAX_MEDIA_SIZE_BYTES)
    if not (0 < file_size <= MAX_MEDIA_SIZE_BYTES):
        return False

    # Проверка MIME-типа
    if mime_type is None or mime_type not in ALLOWED_MIME_TYPES:
        return False

    return True

def validate_url(url_text: str) -> bool:
    """
    Проверяет, является ли строка корректным URL, начинающимся с http:// или https://.

    Args:
        url_text (str): Строка для проверки.

    Returns:
        bool: True, если строка соответствует формату URL, иначе False.
    """
    # Используем регулярное выражение для проверки начала строки
    # Это базовая проверка, не гарантирующая полную валидность URL
    url_regex = re.compile(r'^https?://.+')
    return bool(url_regex.match(url_text))

def validate_username(username: str) -> bool:
    """
    Проверяет, является ли строка корректным username для Telegram-канала.
    Учитывает необязательный префикс '@' и проверяет допустимые символы и длину.

    Args:
        username (str): Строка с потенциальным username.

    Returns:
        bool: True, если username валиден, иначе False.
    """
    if not isinstance(username, str) or not username:
        return False

    # Удаляем необязательный символ '@' в начале
    cleaned_username = username.lstrip('@')

    # Проверяем длину (от 5 до 32 символов)
    if not (5 <= len(cleaned_username) <= 32):
        return False

    # Проверяем допустимые символы: латинские буквы, цифры и подчеркивания
    username_regex = re.compile(r'^[a-zA-Z0-9_]+$')
    return bool(username_regex.fullmatch(cleaned_username))

def validate_timezone(tz_str: str) -> bool:
    """
    Проверяет, является ли строка корректным названием часового пояса из базы данных IANA.

    Args:
        tz_str (str): Строка с названием часового пояса.

    Returns:
        bool: True, если название часового пояса корректно, иначе False.
    """
    if not isinstance(tz_str, str):
        return False

    # Проверяем наличие строки в наборе всех известных часовых поясов IANA
    return tz_str in pytz.all_timezones_set

if __name__ == '__main__':
    # Пример использования функций валидации

    # --- validate_datetime ---
    print("--- Проверка validate_datetime ---")
    user_tz = 'Europe/Moscow' # Пример часового пояса пользователя
    now_plus_1min = datetime.now(pytz.timezone(user_tz)) + pytz.timedelta(minutes=1)
    future_time_str = now_plus_1min.strftime('%d.%m.%Y %H:%M')
    past_time_str = (datetime.now(pytz.timezone(user_tz)) - pytz.timedelta(minutes=1)).strftime('%d.%m.%Y %H:%M')

    print(f"Текущее время в {user_tz}: {datetime.now(pytz.timezone(user_tz)).strftime('%d.%m.%Y %H:%M')}")
    print(f"Проверяем будущее время ('{future_time_str}') в '{user_tz}': {validate_datetime(future_time_str, user_tz)}")
    print(f"Проверяем прошлое время ('{past_time_str}') в '{user_tz}': {validate_datetime(past_time_str, user_tz)}")
    print(f"Проверяем неверный формат ('01-01-2023 10:00') в '{user_tz}': {validate_datetime('01-01-2023 10:00', user_tz)}")
    print(f"Проверяем неверный часовой пояс ('Invalid/TimeZone'): {validate_datetime(future_time_str, 'Invalid/TimeZone')}")

    print("\n--- Проверка validate_cron_params ---")
    # --- validate_cron_params ---
    print(f"Проверяем daily (ok): {validate_cron_params({'type': 'daily', 'time': '10:30'})}")
    print(f"Проверяем daily (no time): {validate_cron_params({'type': 'daily'})}")
    print(f"Проверяем weekly (ok): {validate_cron_params({'type': 'weekly', 'time': '11:00', 'days_of_week': 'mon,wed,fri'})}")
    print(f"Проверяем weekly (no days): {validate_cron_params({'type': 'weekly', 'time': '11:00'})}")
    print(f"Проверяем monthly (ok): {validate_cron_params({'type': 'monthly', 'time': '12:00', 'day_of_month': 15})}")
    print(f"Проверяем monthly (no day): {validate_cron_params({'type': 'monthly', 'time': '12:00'})}")
    print(f"Проверяем yearly (ok): {validate_cron_params({'type': 'yearly', 'time': '13:00', 'month': 6, 'day': 20})}")
    print(f"Проверяем yearly (no month): {validate_cron_params({'type': 'yearly', 'time': '13:00', 'day': 20})}")
    print(f"Проверяем неизвестный тип: {validate_cron_params({'type': 'every_minute'})}")
    print(f"Проверяем пустой dict: {validate_cron_params({})}")

    print("\n--- Проверка validate_media_file ---")
    # --- validate_media_file ---
    print(f"Проверяем файл (ok): {validate_media_file(10 * 1024 * 1024, 'image/jpeg')}") # 10 MB
    print(f"Проверяем файл (слишком большой): {validate_media_file(21 * 1024 * 1024, 'image/png')}") # 21 MB
    print(f"Проверяем файл (нулевой размер): {validate_media_file(0, 'video/mp4')}")
    print(f"Проверяем файл (недопустимый тип): {validate_media_file(1 * 1024 * 1024, 'application/zip')}")
    print(f"Проверяем файл (тип None): {validate_media_file(1 * 1024 * 1024, None)}")

    print("\n--- Проверка validate_url ---")
    # --- validate_url ---
    print(f"Проверяем URL (http ok): {validate_url('http://example.com')}")
    print(f"Проверяем URL (https ok): {validate_url('https://www.google.com/search?q=test')}")
    print(f"Проверяем URL (без схемы): {validate_url('example.com')}")
    print(f"Проверяем URL (неверная схема): {validate_url('ftp://example.com')}")
    print(f"Проверяем URL (пустая строка): {validate_url('')}")

    print("\n--- Проверка validate_username ---")
    # --- validate_username ---
    print(f"Проверяем username (ok без @): {validate_username('channel_name')}")
    print(f"Проверяем username (ok с @): {validate_username('@channel_name')}")
    print(f"Проверяем username (слишком короткий): {validate_username('chan')}")
    print(f"Проверяем username (слишком длинный): {validate_username('a' * 33)}")
    print(f"Проверяем username (недопустимые символы): {validate_username('channel-name!')}")
    print(f"Проверяем username (пустая строка): {validate_username('')}")

    print("\n--- Проверка validate_timezone ---")
    # --- validate_timezone ---
    print(f"Проверяем часовой пояс (ok): {validate_timezone('Europe/London')}")
    print(f"Проверяем часовой пояс (ok): {validate_timezone('Asia/Tokyo')}")
    print(f"Проверяем часовой пояс (неверный): {validate_timezone('Invalid/TimeZone')}")
    print(f"Проверяем часовой пояс (пустая строка): {validate_timezone('')}")
