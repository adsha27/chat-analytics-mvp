import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import sys

# Add project root to path if needed, though typically run from root or via python -m
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_session, ProcessedFiles, init_db, AppConfig
import ingest
import analyze
from config import LOG_DIR, SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_RECIPIENT

# Configure logging
log_file = LOG_DIR / "pipeline.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Pipeline")

def get_alert_email():
    """Fetch alert email from DB config, fallback to Env."""
    session = get_session()
    try:
        config = session.query(AppConfig).filter_by(key="alert_email").first()
        if config and config.value:
            return config.value
    except Exception:
        pass
    finally:
        session.close()
    return ALERT_EMAIL_RECIPIENT

def send_alert_email(subject, body):
    """Send an email alert using SMTP configuration."""
    recipient = get_alert_email()
    
    if not all([SMTP_USER, SMTP_PASSWORD, recipient]):
        logger.warning("SMTP not configured or no recipient. Skipping email alert.")
        logger.warning(f"Subject: {subject}\nBody: {body}")
        return

    msg = MIMEText(body)
    msg['Subject'] = f"[Chat Analytics Alert] {subject}"
    msg['From'] = SMTP_USER
    msg['To'] = recipient

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Alert email sent.")
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")

def check_staleness(days_threshold=7):
    """Check if no files processed in X days."""
    session = get_session()
    try:
        last_processed = session.query(ProcessedFiles).order_by(ProcessedFiles.processed_at.desc()).first()
        
        if not last_processed:
            # Maybe it's a fresh install, logic depends on requirements. 
            # If system is up for > 7 days and no files, maybe alert?
            # For now, ignore if truly empty.
            return

        delta = datetime.utcnow() - last_processed.processed_at
        if delta.days >= days_threshold:
            subject = "Stale Data Ingestion"
            body = f"No new Wati files have been processed in {delta.days} days. Last processed: {last_processed.processed_at}."
            logger.warning(subject)
            send_alert_email(subject, body)
            
    except Exception as e:
        logger.error(f"Error checking staleness: {e}")
    finally:
        session.close()

def run():
    logger.info("Starting Pipeline Run")
    
    # 0. Ensure DB is Init (Idempotent)
    init_db()

    # 1. Ingestion
    try:
        ingest.process_wati_files()
        ingest.fetch_gllitedge_data()
    except Exception as e:
        logger.critical(f"Ingestion Failed: {e}", exc_info=True)
        send_alert_email("Ingestion Failed", str(e))
        return # Stop if ingestion fails hard

    # 2. Analysis
    try:
        # Loop until all done? Or just one batch? User said "batch-based".
        # Typically run loops until nothing left to analyze to catch up.
        # But to prevent infinite loops, we cap it.
        MAX_BATCHES = 50
        for i in range(MAX_BATCHES):
            # We can check if any were analyzed by checking return or logs,
            # but simplest is just calling it. Ideally analyze_batch returns count.
            # For now, we blindly call it.
            analyze.analyze_batch(batch_size=200)
            
    except Exception as e:
        logger.error(f"Analysis Failed: {e}", exc_info=True)
        send_alert_email("Analysis Failed", str(e))

    # 3. Health Checks
    check_staleness()

    logger.info("Pipeline Run Completed")

if __name__ == "__main__":
    run()
