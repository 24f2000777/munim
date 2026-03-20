# Munim — AI Business Intelligence for Indian SMBs

> *Munim* (मुनीम) — the trusted accountant who knows your business inside out.

Munim converts raw business data from Tally exports and Excel files into plain-language WhatsApp reports in Hindi and English — automatically, every week, with zero technical skill required from the business owner.

---

## What It Does

```
Business owner uploads Tally XML / Excel
              ↓
Munim cleans data, detects anomalies, computes metrics
              ↓
Gemini 2.0 Flash narrates results in Hindi or English
              ↓
WhatsApp report delivered every Monday at 8 AM
              ↓
Owner replies with questions → instant answers via WhatsApp
```

---

## Business Model

**B2B2C — CA Firms First**

| Who | Role | Value |
|-----|------|-------|
| CA Firm | Paying customer (₹5,000–15,000/month) | Manages 50–200 SMB clients from one dashboard |
| SMB Owner | End user | Receives WhatsApp reports under CA's white-label brand |

1 CA sale = 50–200 SMB users. CA firms already have their clients' Tally data and trust.

---

## Core Features (MVP — 8 Weeks)

| # | Feature | Description |
|---|---------|-------------|
| 1 | Universal Data Ingestion | Auto-parse Tally XML (TallyPrime + ERP9), Excel, CSV — no manual column mapping |
| 2 | Data Cleaning Pipeline | Fuzzy deduplication, date normalisation, outlier flagging, Data Health Score (0–100) |
| 3 | Business Health Dashboard | 5 KPIs always above the fold: revenue, top products, dead stock, margins, customer split |
| 4 | Anomaly Detection | Z-score + IsolationForest + 5 rule-based triggers with severity levels |
| 5 | India Seasonality Engine | Hardcoded Indian festival/event calendar suppresses false anomaly alerts |
| 6 | WhatsApp Delivery + Q&A | Monday 8 AM report + real-time HIGH alerts + LangGraph Q&A in Hindi/Hinglish/English |
| 7 | CA Multi-Client Console | Traffic lights per client, bulk upload, white-label reports, one-click send |

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Next.js 14 + TypeScript + Tailwind + shadcn/ui | SSR, App Router, fast solo development |
| Backend | FastAPI (Python 3.11) + Pydantic v2 | Async, same language as data pipeline |
| Auth | NextAuth.js v5 + Google OAuth | Zero third-party dependency, sessions in own DB |
| LLM | Google Gemini 2.0 Flash | Free tier (1M tokens/day), excellent Hindi support |
| Database | Neon PostgreSQL | No auto-pause, full RLS, India-accessible |
| File Storage | Cloudflare R2 | Free 10GB, zero egress fees, S3-compatible |
| Task Queue | Celery + Upstash Redis | Async file processing (30–90s jobs) |
| WhatsApp | Meta Business API + LangGraph | Delivery + stateful Q&A conversations |
| Payments | Razorpay | Indian UPI/cards, subscription billing |
| Frontend Deploy | Vercel | Free, global CDN |
| Backend Deploy | Railway | $5 credit/month, sufficient for early stage |

**Total infrastructure cost: ₹0/month until ~300 active users**

---

## Repository Structure

```
munim/
├── backend/                        # FastAPI Python backend
│   ├── main.py                     # App entry point
│   ├── requirements.txt
│   ├── routers/                    # API route handlers
│   │   ├── upload.py               # File upload endpoints
│   │   ├── analysis.py             # Trigger analysis, fetch results
│   │   ├── reports.py              # Report generation + delivery
│   │   ├── whatsapp.py             # WhatsApp webhook handler
│   │   ├── auth.py                 # Auth middleware
│   │   └── ca.py                   # CA firm endpoints
│   ├── services/
│   │   ├── ingestor/               # Data ingestion
│   │   │   ├── tally_parser.py     # Tally XML → DataFrame [CRITICAL]
│   │   │   ├── excel_parser.py     # Excel/CSV → DataFrame
│   │   │   └── schema_detector.py  # Auto-detect column meanings
│   │   ├── cleaner/                # Data quality
│   │   │   ├── deduplicator.py     # RapidFuzz product name dedup
│   │   │   ├── normaliser.py       # Dates, currency, text
│   │   │   └── health_scorer.py    # Data Health Score 0–100
│   │   ├── analytics/              # Core analytics
│   │   │   ├── metrics.py          # 5 core KPI calculations
│   │   │   ├── anomaly.py          # IsolationForest + Z-score + rules
│   │   │   ├── rfm.py              # RFM customer segmentation
│   │   │   └── seasonality.py      # India festival calendar engine
│   │   ├── reporter/               # Report generation
│   │   │   ├── llm_narrator.py     # Gemini: numbers → Hindi/English text
│   │   │   ├── templates.py        # Report structure templates
│   │   │   └── formatter.py        # WhatsApp message formatting
│   │   └── whatsapp/               # WhatsApp integration
│   │       ├── sender.py           # Meta API message sending
│   │       ├── qa_agent.py         # LangGraph Q&A state machine
│   │       └── intent_router.py    # Route messages to correct handler
│   ├── models/                     # Pydantic models
│   ├── tasks/                      # Celery async tasks
│   ├── db/                         # Database layer
│   │   ├── neon_client.py          # Neon PostgreSQL client
│   │   └── migrations/             # SQL migration files
│   └── tests/                      # Test suite
│
├── frontend/                       # Next.js 14 App
│   ├── app/
│   │   ├── (auth)/                 # Login / Signup
│   │   ├── (dashboard)/            # SMB owner dashboard
│   │   └── (ca)/                   # CA firm console
│   ├── components/
│   ├── lib/
│   └── messages/                   # i18n: en.json + hi.json
│
└── data/
    └── samples/                    # Synthetic test files (no real data)
```

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- A Neon PostgreSQL account (free at neon.tech)
- A Google Cloud project with OAuth 2.0 credentials
- A Google AI Studio API key (free at aistudio.google.com)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
# Fill in DATABASE_URL, GOOGLE_API_KEY, and other values in .env

# Run database migrations
python -m db.migrations.run

# Start the API server
uvicorn main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A tasks.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
# Fill in NEXT_PUBLIC_API_URL, GOOGLE_CLIENT_ID, NEXTAUTH_SECRET in .env.local

npm run dev
# Opens at http://localhost:3000
```

### Run Tests

```bash
cd backend
pytest tests/ -v --tb=short
```

---

## Data Quality Standards

- All monetary values use Python `Decimal` — never `float` (prevents ₹0.01 rounding errors)
- Revenue figures must match Tally source data exactly (±₹1 tolerance)
- If Data Health Score < 40 → refuse analysis, explain to user
- LLM never receives raw financial data — only pre-computed summaries
- All LLM outputs validated against pre-computed analytics before sending
- Uploaded files deleted from storage after 30 days (privacy)
- Financial figures never logged in plain text (logged as `[AMOUNT_REDACTED]`)

---

## Security

- Neon PostgreSQL Row Level Security (RLS) on all tables — no cross-user data access
- All file uploads virus-scanned before processing
- WhatsApp webhook verified with HMAC-SHA256 signature
- Google OAuth tokens never stored — only session JWTs
- Input validation on all endpoints via Pydantic v2
- Rate limiting on all public endpoints
- SQL injection prevented via parameterised queries (SQLAlchemy core)

---

## Build Order (8-Week Plan)

| Week | Focus |
|------|-------|
| 1 | Tally XML parser + Excel parser + schema detector + health scorer |
| 2 | Analytics engine (metrics, anomaly, RFM, seasonality) |
| 3 | LLM narrator (Gemini) — Hindi/English quality testing |
| 4 | FastAPI backend + Celery + Neon DB + Cloudflare R2 |
| 5 | WhatsApp delivery + LangGraph Q&A agent |
| 6–7 | Next.js frontend dashboard + i18n + CA console |
| 8 | Integration testing + deploy + soft launch |

---

## Decisions Log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-03-20 | FastAPI over Django | Lighter, async-native, same language as ML pipeline |
| 2026-03-20 | Next.js 14 over plain React | SSR, App Router, multi-layout support |
| 2026-03-20 | Gemini 2.0 Flash over Claude Haiku | Free tier (1M tokens/day), no API cost |
| 2026-03-20 | Neon over Supabase PostgreSQL | No auto-pause, no India blocking risk |
| 2026-03-20 | Cloudflare R2 over Supabase Storage | Zero egress fees, S3-compatible, globally distributed |
| 2026-03-20 | NextAuth.js v5 over Clerk | Self-hosted, no third-party dependency, sessions in own Neon DB |
| 2026-03-20 | Decimal over float for money | Prevents rounding errors in financial calculations |
| 2026-03-20 | CA-first GTM over direct SMB | 1 CA = 50 clients, trust bypass, CAs already have client data |

---

## Author

**Akshit Garg** — [akshitgarg928@gmail.com](mailto:akshitgarg928@gmail.com)

*Munim — Because every business deserves a trusted accountant.*
