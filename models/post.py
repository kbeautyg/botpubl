# models/post.py

import enum
from sqlalchemy import (
    Column, Integer, String, DateTime, Enum, BigInteger, func,
    ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship # Potentially useful for relationships, though not strictly required by the prompt

# Импортируем Base из центрального файла, где определена декларативная база
from services.db_base import Base


class ScheduleTypeEnum(enum.Enum):
    """
    Enum для типа расписания публикации поста.
    """
    ONE_TIME = 'one_time'
    RECURRING = 'recurring'


class PostStatusEnum(enum.Enum):
    """
    Enum для статуса поста.
    """
    DRAFT = 'draft'
    SCHEDULED = 'scheduled'
    SENT = 'sent'
    ERROR = 'error'
    DELETED = 'deleted'
    INVALID = 'invalid' # e.g., no valid channels to send to


class Post(Base):
    """
    SQLAlchemy ORM модель для таблицы 'posts'.
    """
    __tablename__ = 'posts'

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment='Уникальный идентификатор поста'
    )
    user_id = Column(
        Integer,
        ForeignKey('users.id'), # Ссылка на таблицу 'users'
        nullable=False,
        index=True,
        comment='ID пользователя, создавшего пост'
    )
    chat_ids = Column(
        JSON, # JSON-массив ID чатов/каналов для публикации
        nullable=False,
        comment='JSON-массив ID чатов/каналов для публикации'
    )
    text = Column(
        Text, # Текст поста, может быть пустым
        nullable=True,
        comment='Текст поста, может быть пустым'
    )
    media_paths = Column(
        JSON, # JSON-массив путей к медиафайлам или идентификаторов медиа
        nullable=True,
        comment='JSON-массив путей к медиафайлам или идентификаторов медиа'
    )
    schedule_type = Column(
        Enum(ScheduleTypeEnum, name='schedule_type_enum'),
        nullable=False,
        comment="Тип расписания: 'one_time' (разовый), 'recurring' (циклический)"
    )
    schedule_params = Column(
        JSON, # Параметры для циклического расписания
        nullable=True,
        comment='Параметры для циклического расписания (JSON)'
    )
    run_date_utc = Column(
        DateTime, # Время запуска для разового поста в UTC
        nullable=True,
        comment='Время запуска для разового поста в UTC'
    )
    start_date_utc = Column(
        DateTime, # Дата начала для циклического поста в UTC
        nullable=True,
        comment='Дата начала для циклического поста в UTC'
    )
    end_date_utc = Column(
        DateTime, # Дата окончания для циклического поста в UTC (может быть NULL)
        nullable=True,
        comment='Дата окончания для циклического поста в UTC (может быть NULL)'
    )
    delete_after_seconds = Column(
        Integer, # Время в секундах, через которое пост должен быть удален после публикации
        nullable=True,
        comment='Время в секундах, через которое пост должен быть удален после публикации'
    )
    delete_at_utc = Column(
        DateTime, # Точное время удаления поста в UTC
        nullable=True,
        comment='Точное время удаления поста в UTC'
    )
    status = Column(
        Enum(PostStatusEnum, name='post_status_enum'),
        nullable=False,
        default=PostStatusEnum.SCHEDULED.value, # Храним строковое значение enum
        index=True,
        comment="Статус поста: 'draft', 'scheduled', 'sent', 'error', 'deleted', 'invalid'"
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(), # Время создания записи на сервере БД
        comment='Время создания записи'
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(), # Изначальное время обновления
        onupdate=func.now(),       # Время обновления при каждом изменении записи
        comment='Время последнего обновления записи'
    )

    # Опционально можно добавить отношение к модели User, если она определена
    # user = relationship("User")

    def __repr__(self):
        return (
            f"<Post(id={self.id}, user_id={self.user_id}, "
            f"schedule_type='{self.schedule_type.value}', "
            f"status='{self.status.value}', run_date_utc={self.run_date_utc})>"
        )

