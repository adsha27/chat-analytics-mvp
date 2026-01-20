from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Enum as SQLAREnum
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
import enum
from datetime import datetime
from config import DB_URL

# Define Base
Base = declarative_base()

# Enums
class ChatSource(enum.Enum):
    WATI = "wati"
    GLLITEDGE = "gllitedge"

class SenderType(enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM" # Templates, Auto-responses
    BOT = "BOT" # KnowBot, etc.

class AppConfig(Base):
    __tablename__ = 'app_config'
    
    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)

class UnifiedChats(Base):
    __tablename__ = 'unified_chats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String, index=True, nullable=False) # Normalized phone
    source = Column(SQLAREnum(ChatSource), nullable=False)
    sender_type = Column(SQLAREnum(SenderType), default=SenderType.USER, nullable=False)
    message_text = Column(Text, nullable=True) # Text content of the message
    timestamp = Column(DateTime, nullable=True, index=True)
    
    # Analysis fields
    is_analyzed = Column(Boolean, default=False, index=True)
    sentiment = Column(String, nullable=True) # 'positive', 'neutral', 'negative'
    topic = Column(String, nullable=True) # e.g. 'pricing', 'support'

    created_at = Column(DateTime, server_default=func.now())

class ProcessedFiles(Base):
    __tablename__ = 'processed_files'

    filename = Column(String, primary_key=True)
    file_hash = Column(String, nullable=False, index=True)
    processed_at = Column(DateTime, default=datetime.utcnow)

def get_db_engine():
    return create_engine(DB_URL)

def get_session():
    engine = get_db_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    engine = get_db_engine()
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
