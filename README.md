# Chat Analytics MVP

Batch pipeline for ingesting WhatsApp chat exports, running sentiment and topic analysis, and surfacing trends in a Streamlit dashboard.

Built for a real-estate sales team to understand query patterns across hundreds of customer conversations.

## What it does

- Ingests Wati `.txt` chat exports and pulls from an external PostgreSQL source
- Normalizes phone numbers as the single user identity (no deduplication across numbers)
- Runs sentiment analysis (TextBlob) and keyword-based topic classification (price, property, availability, meeting, support)
- Idempotent batch pipeline — safe to re-run, skips already-processed messages
- Streamlit dashboard for KPI monitoring and trend views

## Setup

```bash
cd chat_analytics
pip install -r requirements.txt
cp .env.template .env   # fill in DB connection details
python db.py            # initialize schema
```

## Run

```bash
# Ingest + analyze (run manually or schedule via cron)
python run_pipeline.py

# Dashboard
streamlit run dashboard.py
```

Drop new Wati exports into `data_drop/` before running the pipeline — they get picked up automatically.

## Architecture

```
data_drop/ (Wati .txt files)
    |
    v
ingest.py --> PostgreSQL (unified_chats table)
    |
    v
analyze.py --> sentiment + topic labels written back to DB
    |
    v
dashboard.py (Streamlit) reads from DB
```

## Stack

Python, PostgreSQL, SQLAlchemy, TextBlob, Streamlit, pytest
