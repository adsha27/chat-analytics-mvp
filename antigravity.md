# ANTIGRAVITY.md — Unified Chat Analytics MVP (Wati + Gllitedge)

## Project Overview & Philosophy

Simple, reliable MVP for ingesting, merging, analyzing, and visualizing chat data from:
- Wati (.txt manual uploads)
- Gllitedge (PostgreSQL pull)

**Core constraint (NEVER violate):**  
Phone number is the **ONLY** user identity.  
No fuzzy matching, no deduplication across numbers, no heuristics.  
Different phone number = different user.

**Goal:**  
Surface trends and insights (query types, sentiment, volume changes).  
Accuracy good enough for trends (70–80%) > perfection.

**Operating model:**  
- Append-only
- Batch / cron-based
- No real-time processing
- No ML training
- No external services beyond SMTP for alerts

**Vibe:**  
Boring, simple, robust.  
Prefer obvious over clever.  
Fail loudly at system level, softly at row level.  
Build incrementally, test ruthlessly, revert freely.  
YAGNI.

---

## Directory Structure

```

data_drop/          ← manual Wati .txt uploads
logs/               ← pipeline.log
config.py           ← constants + .env loader
db.py               ← SQLAlchemy connection & models
ingest.py           ← Wati parser + Gllitedge fetch
analyze.py          ← TextBlob sentiment + keyword topics
run_pipeline.py     ← main orchestrator (ingest → analyze → alert)
dashboard.py        ← Streamlit frontend
requirements.txt    ← pinned: sqlalchemy pandas textblob streamlit psycopg2 pytest python-dotenv

````

---

## Critical Rules & Boundaries

### Phone Number Normalization (Identity — Non-Negotiable)

- Strip **all non-digits**  
- Remove a leading `+` if present  
- **No length checks**
- **No country code assumptions**
- **No prefixing**
- **No validation patterns**

Whatever remains is the canonical phone identity string.

Examples:
- `+91-9876543210` → `919876543210`
- `09876543210` → `09876543210`
- `919876543210` → `919876543210`

**Store as string (VARCHAR).**  
This normalized value is the **only** user identity used anywhere in the system.

---

### Always

- **Idempotency**
  - Hash Wati files and skip already-processed files by default
  - Maintain a `ProcessedFiles` table
  - Support a **manual override / force flag** to reprocess specific files if parsing logic changes
  - Default behavior remains strict idempotency

- **Deduplication**
  - Enforce uniqueness on `(phone_number_normalized, timestamp, source)`
  - If timestamp is missing or duplicated, include a stable hash of raw content in deduplication

- **Incremental Processing**
  - Only ingest new Gllitedge rows (max timestamp or cursor)
  - Only analyze unanalyzed rows
  - Process in small, configurable batches (default ~100)

- **Raw Data Preservation**
  - Always store raw Wati line and raw Gllitedge JSON
  - Never mutate or delete raw inputs

- **Failure Handling Principle**
  - **Fail Row, Survive Batch**
  - If a single message/line fails to parse:
    - log the error with raw content
    - skip only that row
    - continue processing the file
  - Never crash the entire pipeline due to one bad line

- **Logging & Alerts**
  - try/except around all I/O boundaries
  - structured logging with row counts and error counts
  - email alerts on crash, staleness, or suspicious ingestion

- **Testing**
  - Unit + integration tests required for every meaningful change
  - Tests are not optional or “later”

---

### Ask First

- Adding new tables or breaking schema changes
- Architectural changes
- New libraries or dependencies
- Real-time / streaming features

(Additive, backward-safe columns and indexes are allowed without asking.)

---

### Never

- Fuzzy match or merge users across phone numbers
- Assume phone number validity or correctness
- Commit secrets or hardcode credentials (use `.env` only)
- Use heavy NLP / ML (spaCy, transformers, LLM inference)
- Introduce Airflow, Kafka, Celery, queues, or microservices
- Skip tests or lint before commit
- Use `print()` in production code (logger only)
- Silently swallow errors
- Leave critical TODOs — implement or remove

---

## Cognitive Process (Silent Review)

Before writing or changing code, internally check:
1. **Context Check** — do I understand the full pipeline impact?
2. **Dependency Check** — could this break existing behavior?
3. **Simplicity Check** — is there a simpler, more boring way?
4. **Security Check** — secrets, injection, PII handling?

---

## Technical Constraints

- Python 3.10+
- Always use type hints
- Prefer `pathlib` over `os.path`

### I/O Model
- Prefer **simple synchronous I/O** for this MVP
- Use async/await **only if a real performance bottleneck is measured and documented**
- “Boring” code is usually synchronous

- SQLAlchemy:
  - always use context-managed sessions
  - parameterized queries only (no string concatenation)

- Streamlit:
  - small reusable components
  - explicit loading and empty states

- Secrets:
  - `os.getenv()` only
  - assume `.env` exists
  - never log secrets

---

## Code Style

- PEP 8
- `ruff` for lint + format
- Google-style docstrings **only for non-obvious logic**
- Imports: stdlib → third-party → local (absolute)
- Naming:
  - `snake_case` for functions/variables
  - `CamelCase` for classes
- Logging:
  - Python `logging` module
  - INFO / ERROR levels
  - output to `logs/pipeline.log`

---

## Important Commands

```bash
# DB setup
python -c "from db import init_db; init_db()"

# Ingest only
python ingest.py

# Full pipeline
python run_pipeline.py

# Dashboard
streamlit run dashboard.py

# Tests & quality
pytest -v
ruff check --fix . && ruff format .
````

---

## Monitoring & Alerts (Minimal, Actionable)

Alert **only** on:

* Pipeline crash / DB unreachable
* No new Wati file for > 7 days (configurable)
* Zero rows ingested
* Parse success rate < 80%

**Parse success rate definition:**
Parsed message rows ÷ total candidate message lines in file

Every alert email must include:

* What happened
* When it happened
* Impact window (e.g., “data missing since …”)
* One clear next action

---

## Dashboard Goals (Minimal & Correct)

Must answer:

1. Is the data fresh?
2. How much data do we have?
3. What are top categories / sentiments?
4. How are trends changing over time?

Always show:

* Last Wati upload timestamp
* Last successful pipeline run
* Total messages (lifetime + last 7 / 30 days)
* One trend chart
* One top-N table

Avoid:

* Per-message drill-down
* Per-user profiles
* Complex filters

---

## Workflows

### Add New Ingestion Rule

1. Update parser
2. Add realistic unit test sample
3. Run full test suite
4. Log row counts and parse error rate
5. Document supported formats and failure behavior

### DB Schema Change

1. Write migration SQL (or Alembic revision)
2. Document rollback steps
3. Update integration smoke test
4. Ensure indexes on `phone_number_normalized` and `timestamp`

### Add New Trend / Metric

1. Define it in one sentence
2. Implement aggregation/query
3. Add snapshot test
4. Show on dashboard **only** if it answers one of the four core questions

---

## When to Ask Instead of Assume

Stop and ask **only** if blocked by:

* Unknown DB credentials or connection details
* No example of current Wati `.txt` format
* No decision on stale threshold or alert rules

Otherwise:
→ Make the safest, most boring assumption
→ Implement it
→ Document it clearly

```