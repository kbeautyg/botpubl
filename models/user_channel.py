# models/user_channel.py

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey, func, Index
)
# Импортируем Base из центрального файла определения декларативной базы
from services.db_base import Base


class UserChannel(Base):
    """
    SQLAlchemy ORM модель для таблицы 'user_channels'.
    Представляет связь между пользователем и каналом (чатом),
    на который он подписан или который отслеживает.
    """
    __tablename__ = 'user_channels'

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Уникальный идентификатор записи"
    )
    user_id = Column(
        Integer,
        ForeignKey('users.id'),
        nullable=False,
        index=True, # Добавляем индекс для ускорения поиска по пользователю
        comment="ID пользователя из таблицы 'users'"
    )
    chat_id = Column(
        BigInteger,
        nullable=False,
        comment="ID чата (канала или группы) в Telegram"
        # Уникальность chat_id в рамках user_id не обеспечивается на уровне БД
        # для гибкости, но комбинация user_id + chat_id часто уникальна
    )
    chat_username = Column(
        String(255),
        nullable=True,
        comment="Юзернейм чата/канала (может меняться или отсутствовать)"
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Флаг активности связи (true = отслеживается, false = отключено)"
    )
    added_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(), # Время добавления записи (на сервере БД)
        comment="Время добавления связи пользователь-канал"
    )
    removed_at = Column(
        DateTime,
        nullable=True,
        comment="Время удаления/отключения связи пользователь-канал"
    )

    # Добавляем составной индекс по user_id и chat_id для ускорения запросов
    # и помощи в обеспечении логической уникальности (user, chat) комбинации
    __table_args__ = (
        Index('idx_user_channel', 'user_id', 'chat_id'),
    )

    def __repr__(self):
        return (
            f"<UserChannel(id={self.id}, user_id={self.user_id}, chat_id={self.chat_id}, "
            f"is_active={self.is_active}, added_at='{self.added_at.strftime('%Y-%m-%d %H:%M') if self.added_at else None}')>"
        )
