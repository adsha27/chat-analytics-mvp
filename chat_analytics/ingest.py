import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
import logging

from db import get_session, UnifiedChats, ProcessedFiles, ChatSource, SenderType
from config import DATA_DROP_DIR

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def normalize_phone_number(raw_phone: str) -> str:
    """
    Normalize phone number to digits only.
    Add '91' prefix if 10 digits.
    """
    digits = re.sub(r"\D", "", raw_phone)
    if len(digits) == 10:
        return "91" + digits
    return digits

def parse_wati_line(line: str) -> Optional[dict]:
    """
    Parse a single line from a Wati chat export.
    Format assumption: "DD/MM/YY, HH:MM AM - Sender: Message"
    or "MM/DD/YY, HH:MM PM - Sender: Message"
    """
    # Regex for standard WhatsApp/Wati export format
    # matches: date, time, sender, message
    pattern = r"(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)?) - (.*?): (.*)"
    match = re.match(pattern, line)
    
    if not match:
        return None

    date_str, time_str, sender, message = match.groups()
    
    # Attempt to join and parse timestamp
    full_ts_str = f"{date_str} {time_str}"
    
    try:
        # Try dayfirst=True (DD/MM/YY) first as it's common in India (91 prefix implication)
        timestamp = pd.to_datetime(full_ts_str, dayfirst=True)
    except Exception:
        try:
             # Fallback
            timestamp = pd.to_datetime(full_ts_str)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{full_ts_str}': {e}")
            return None

    return {
        "timestamp": timestamp.to_pydatetime(),
        "phone_number": normalize_phone_number(sender),
        "message_text": message.strip(),
        "source": ChatSource.WATI
    }

def parse_wati_timestamp(ts_str: str) -> Optional[datetime]:
    """
    Parse timestamp from format [MM/DD/YYYY HH:MM:SS]
    """
    try:
        return datetime.strptime(ts_str, "%m/%d/%Y %H:%M:%S")
    except ValueError:
        return None

def process_wati_files():
    """
    Scan DATA_DROP_DIR recursively, check hashes, parse, and insert new chats.
    """
    session = get_session()
    # Recursive glob to find all .txt files in subfolders
    files = list(Path(DATA_DROP_DIR).rglob("*.txt"))
    
    if not files:
        logger.info("No text files found in data_drop.")
        return

    logger.info(f"Found {len(files)} files to process.")

    for file_path in files:
        try:
            current_hash = calculate_file_hash(file_path)
            
            # Check if processed
            existing_file = session.query(ProcessedFiles).filter_by(filename=file_path.name).first()
            if existing_file:
                if existing_file.file_hash == current_hash:
                    # logger.info(f"Skipping {file_path.name}: unchanged.")
                    continue
                else:
                    logger.info(f"Re-processing {file_path.name}: content changed.")
                    existing_file.file_hash = current_hash # Update hash
                    existing_file.processed_at = datetime.utcnow()
            else:
                logger.info(f"Processing new file: {file_path.name}")
                new_file_record = ProcessedFiles(filename=file_path.name, file_hash=current_hash)
                session.add(new_file_record)
            
            # Extract Phone Number from Filename
            # Format: 971505382128-68a07fb78a31f777cf5bc3a0.txt -> 971505382128
            filename_match = re.match(r"^(\d+)-", file_path.name)
            if filename_match:
                file_phone = normalize_phone_number(filename_match.group(1))
            else:
                logger.warning(f"Could not extract phone from filename: {file_path.name}")
                continue

            new_chats = []
            
            # Multi-line parsing logic
            current_msg_data = None
            
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.rstrip() # Keep indentation if any, remove newline
                    if not line:
                        if current_msg_data:
                            current_msg_data['message_text'] += "\n"
                        continue

                    # Regex for new message start: [MM/DD/YYYY HH:MM:SS]
                    # pattern: ^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\] (.*)$
                    # We accept user might say "Sender: Message" or just "Message"
                    match = re.match(r"^\[(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\] (.*)$", line)
                    
                    if match:
                        # Save previous message if exists
                        if current_msg_data:
                            new_chats.append(current_msg_data)
                        
                        ts_str, remaining = match.groups()
                        timestamp = parse_wati_timestamp(ts_str)
                        
                        # Determine Sender Type
                        s_type = SenderType.USER
                        clean_msg = remaining
                        
                        # Check for System Template
                        if remaining.startswith('Template "'):
                            s_type = SenderType.SYSTEM
                        
                        # Check for Bot
                        elif remaining.startswith('KnowBot:') or remaining.startswith('Bot:'):
                            s_type = SenderType.BOT
                            clean_msg = re.sub(r'^(KnowBot|Bot):\s*', '', remaining)

                        # Check for specific user name prefix
                        else:
                            name_match = re.match(r'^([^:]+):\s+(.*)', remaining)
                            if name_match:
                                potential_name = name_match.group(1)
                                if len(potential_name) < 30:
                                    clean_msg = name_match.group(2)
                        
                        current_msg_data = {
                            "timestamp": timestamp,
                            "phone_number": file_phone,
                            "message_text": clean_msg,
                            "source": ChatSource.WATI,
                            "sender_type": s_type
                        }
                    else:
                        # Append to current message
                        if current_msg_data:
                            current_msg_data['message_text'] += "\n" + line

                # Append the last message
                if current_msg_data:
                    new_chats.append(current_msg_data)
            
            if new_chats:
                added_count = 0
                for chat in new_chats:
                    # Simple duplication check (Phone + Timestamp + Source)
                    exists = session.query(UnifiedChats).filter_by(
                        phone_number=chat['phone_number'],
                        timestamp=chat['timestamp'],
                        source=ChatSource.WATI
                    ).first()
                    
                    if not exists:
                        session.add(UnifiedChats(**chat))
                        added_count += 1
                
                # logger.info(f"Added {added_count} new chats from {file_path.name}")
            
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Error processing {file_path.name}: {e}")

    session.close()

def fetch_gllitedge_data():
    """
    Fetch new data from external Gllitedge DB.
    """
    logger.info("Fetching data from Gllitedge (Stub)...")
    # Stub implementation as per instructions for MVP structure
    # Real impl would use create_engine(GLLIT_DB_URL) and pd.read_sql
    pass

if __name__ == "__main__":
    process_wati_files()
