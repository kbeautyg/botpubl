import logging
import sys

# Определение формата логирования
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'

# Получение корневого логгера
# Можно использовать logging.getLogger(__name__) для логгера конкретного модуля,
# но для централизованной настройки часто используют корневой логгер или логгер с определенным именем,
# чтобы все модули могли его использовать.
# Используем корневой логгер для простой настройки приложения
logger = logging.getLogger() # Get the root logger

# Установка общего уровня логирования для логгера
# Сообщения ниже этого уровня будут игнорироваться логгером
logger.setLevel(logging.INFO)

# Создание обработчика для стандартного вывода (stdout)
stream_handler = logging.StreamHandler(sys.stdout)
# Установка уровня для обработчика (необходимо, даже если уровень логгера уже установлен)
stream_handler.setLevel(logging.INFO)
# Создание форматтера
formatter = logging.Formatter(LOG_FORMAT)
# Установка форматтера для обработчика стандартного вывода
stream_handler.setFormatter(formatter)

# Создание обработчика для файла
file_handler = logging.FileHandler('bot.log', encoding='utf-8') # Указываем кодировку для совместимости с русским языком
# Установка уровня для обработчика
file_handler.setLevel(logging.INFO)
# Установка форматтера для файлового обработчика
file_handler.setFormatter(formatter)

# Добавление обработчиков к логгеру
# Проверяем, чтобы обработчики не были добавлены повторно, если скрипт выполняется несколько раз (например, в Jupyter или при перезагрузке модуля)
if not logger.handlers:
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

# Пример использования (можно удалить в финальной версии файла utils/logger.py,
# но полезно для проверки настройки)
if __name__ == "__main__":
    logging.info("Это информационное сообщение.")
    logging.warning("Это предупреждение.")
    logging.error("Это ошибка.")
    logging.debug("Это отладочное сообщение (не должно отображаться, т.к. уровень INFO).")

    # Пример использования логгера с именем (для лучшей идентификации в логах)
    # После настройки корневого логгера, логгеры с именами наследуют его настройки,
    # если у них нет своих обработчиков или уровня.
    module_logger = logging.getLogger("my_module")
    module_logger.info("Сообщение из модуля.")
