import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DROP_DIR = BASE_DIR / "data_drop"
LOG_DIR = BASE_DIR / "logs"

# Database URLs
DB_URL = os.getenv("DB_URL", f"sqlite:///{BASE_DIR}/chat_analytics.db") # Default to SQLite for ease of dev if not provided
GLLIT_DB_URL = os.getenv("GLLIT_DB_URL")

# Email Config (Optional but recommended for run_pipeline)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
ALERT_EMAIL_RECIPIENT = os.getenv("ALERT_EMAIL_RECIPIENT")

# Ensure directories exist
DATA_DROP_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
