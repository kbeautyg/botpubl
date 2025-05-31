from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Этот файл определяет базовый декларативный класс для всех моделей SQLAlchemy в проекте.
# Другие модели должны импортировать Base из этого файла.
