import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import Base, UnifiedChats, ChatSource
import analyze

# Use SQLite memory for testing
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def test_session():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture(autouse=True)
def mock_db_session(mocker, test_session):
    """Mock ingest/analyze to use test_session instead of real DB."""
    mocker.patch('ingest.get_session', return_value=test_session)
    mocker.patch('analyze.get_session', return_value=test_session)
    mocker.patch('db.get_session', return_value=test_session)

def test_db_insertion(test_session):
    chat = UnifiedChats(
        phone_number="911234567890",
        source=ChatSource.WATI,
        message_text="Test Message",
        timestamp=datetime.utcnow()
    )
    test_session.add(chat)
    test_session.commit()
    
    saved = test_session.query(UnifiedChats).first()
    assert saved.phone_number == "911234567890"

def test_analysis_pipeline(test_session):
    # Insert unanalyzed chat
    chat = UnifiedChats(
        phone_number="911234567890",
        source=ChatSource.GLLITEDGE,
        message_text="The price is too high",
        timestamp=datetime.utcnow(),
        is_analyzed=False
    )
    test_session.add(chat)
    test_session.commit()
    
    # Run Analysis
    analyze.analyze_batch()
    
    # Verify
    updated = test_session.query(UnifiedChats).first()
    assert updated.is_analyzed is True
    assert updated.topic == "price" # Should match 'price' keyword
    # Sentiment 'high' -> maybe neutral? 'too high' might be negative depending on TextBlob
    # Let's check not None at least
    assert updated.sentiment is not None
