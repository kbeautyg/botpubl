# models/rss_feed.py

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, func
# from sqlalchemy.ext.declarative import declarative_base # Removed local Base definition

# Import Base from a common location
from services.db_base import Base

class RssFeed(Base):
    """
    SQLAlchemy ORM model for the rss_feeds table.
    Manages configuration for user-subscribed RSS feeds.
    """
    __tablename__ = 'rss_feeds'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    feed_url = Column(String, nullable=False)
    channels = Column(JSON, nullable=False, comment="JSON-массив chat_id")
    filter_keywords = Column(JSON, nullable=True, comment="JSON-массив строк ключевых слов")
    frequency_minutes = Column(Integer, nullable=False, default=30)
    next_check_utc = Column(DateTime(timezone=True), nullable=True, comment="Время следующей проверки ленты в UTC")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Время создания записи")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Время последнего обновления записи")

    def __repr__(self):
        return f"<RssFeed(id={self.id}, user_id={self.user_id}, feed_url='{self.feed_url[:50]}...', frequency_minutes={self.frequency_minutes})>"

# Example of how to import and use the model (for reference, not part of the model file itself):
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
#
# # Assuming you have an engine configured
# # engine = create_engine('your_database_url')
#
# # Create tables (if they don't exist)
# # Base.metadata.create_all(engine)
#
# # Create a session
# # SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# # db = SessionLocal()
#
# # Example usage:
# # new_feed = RssFeed(
# #     user_id=1,
# #     feed_url="http://example.com/rss",
# #     channels=[12345],
# #     frequency_minutes=60
# # )
# # db.add(new_feed)
# # db.commit()
# # db.refresh(new_feed)
# # print(new_feed)
#
# # Close the session
# # db.close()
