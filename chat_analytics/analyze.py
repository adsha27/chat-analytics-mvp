from db import get_session, UnifiedChats, SenderType
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Refined Keyword Mapping
TOPIC_KEYWORDS = {
    "price": ["price", "cost", "how much", "rate", "fees", "expensive", "cheap", "payment", "installment"],
    "property": ["flat", "apartment", "house", "plot", "villa", "bhk", "sqft", "location", "view", "balcony"],
    "support": ["help", "issue", "problem", "complaint", "not working", "error", "fail", "contact", "support"],
    "availability": ["available", "inventory", "sold out", "ready to move", "possession", "vacant"],
    "meeting": ["schedule", "appointment", "book a slot", "tour", "viewing", "office visit"],
}

from textblob import TextBlob

# ... (Previous code remains same until analyze_batch)

def analyze_sentiment(text: str) -> str:
    """
    Determine sentiment using TextBlob.
    Returns: 'positive', 'negative', or 'neutral'
    """
    if not text:
        return "neutral"
    
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    
    if polarity > 0.1:
        return "positive"
    elif polarity < -0.1:
        return "negative"
    else:
        return "neutral"

def determine_topic(text: str) -> str:
    """
    Determine chat topic based on keyword matching.
    Returns: matched topic or 'unknown'
    """
    if not text:
        return "unknown"
    
    text_lower = text.lower()
    
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            return topic
            
    return "unknown"

def analyze_batch(batch_size: int = 100):
    """
    Fetch unanalyzed USER chats and apply NLP.
    """
    session = get_session()
    
    try:
        # Fetch unanalyzed USER messages only (System/Bot messages are noise)
        chats = session.query(UnifiedChats).filter(
            UnifiedChats.is_analyzed == False,
            UnifiedChats.sender_type == SenderType.USER
        ).limit(batch_size).all()
        
        if not chats:
            logger.info("No unanalyzed user chats found.")
            return

        count = 0
        for chat in chats:
            sent = analyze_sentiment(chat.message_text)
            topic = determine_topic(chat.message_text)
            
            chat.sentiment = sent
            chat.topic = topic
            chat.is_analyzed = True
            count += 1
            
        session.commit()
        logger.info(f"Analyzed {count} user chats.")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error during analysis batch: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyze_batch()
