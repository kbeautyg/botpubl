# models/user.py

import enum
from sqlalchemy import (
    Column, Integer, String, DateTime, Enum, BigInteger, func
)
# Импортируем Base из файла, где определена декларативная база
from services.db_base import Base


class UserPreferredModeEnum(enum.Enum):
    """
    Enum для предпочтительного режима взаимодействия пользователя.
    """
    BUTTONS = 'buttons'
    COMMANDS = 'commands'


class User(Base):
    """
    SQLAlchemy ORM модель для таблицы 'users'.
    """
    __tablename__ = 'users'

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    telegram_user_id = Column(
        BigInteger,
        unique=True,
        nullable=False
    )
    preferred_mode = Column(
        Enum(UserPreferredModeEnum, name='user_preferred_mode_enum'),
        nullable=False,
        default=UserPreferredModeEnum.BUTTONS.value # Храним строковое значение enum
    )
    timezone = Column(
        String(50),
        nullable=False,
        default='Europe/Berlin'
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now() # Время создания записи на сервере БД
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(), # Изначальное время обновления
        onupdate=func.now()        # Время обновления при каждом изменении записи
    )

    def __repr__(self):
        return (
            f"<User(id={self.id}, telegram_user_id={self.telegram_user_id}, "
            f"preferred_mode='{self.preferred_mode}', timezone='{self.timezone}')>"
        )

