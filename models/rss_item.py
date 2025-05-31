# models/rss_item.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func

# Base импортируется из центрального файла, где определена декларативная база
# Это обеспечивает использование одной и той же метаданных для всех моделей
from services.db_base import Base


class RssItem(Base):
    """
    Модель SQLAlchemy для таблицы 'rss_items'.
    Представляет отдельный элемент (статью/запись) из RSS-ленты.
    """
    __tablename__ = 'rss_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_id = Column(Integer, ForeignKey('rss_feeds.id'), nullable=False, index=True)
    item_guid = Column(String, nullable=False, unique=True, index=True) # Уникальный идентификатор элемента
    published_at = Column(DateTime(timezone=True), nullable=True)      # Время публикации элемента в UTC
    is_posted = Column(Boolean, nullable=False, default=False, index=True) # Флаг, был ли элемент опубликован ботом
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Время создания записи

    def __repr__(self):
        """
        Строковое представление объекта RssItem для удобства отладки.
        """
        return f"<RssItem(id={self.id}, feed_id={self.feed_id}, item_guid='{self.item_guid[:30]}...', is_posted={self.is_posted})>"

# Пример использования (для демонстрации, не часть файла модели):
if __name__ == '__main__':
    # Этот блок не выполняется при обычном импорте файла
    # Демонстрирует структуру модели
    print("Структура модели RssItem определена.")
    # В реальном приложении, вы бы использовали это с движком SQLAlchemy
    # metadata = Base.metadata
    # print(metadata.tables['rss_items'])
