<div align="center">

# 🏪 मुनीम · Munim

### AI Business Intelligence for Indian Small Businesses

[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Gemini](https://img.shields.io/badge/Gemini_2.0_Flash-AI-4285f4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Business_API-25d366?style=for-the-badge&logo=whatsapp&logoColor=white)](https://business.whatsapp.com)

[![Tests](https://img.shields.io/badge/Tests-122_passing-2ea44f?style=for-the-badge&logo=pytest&logoColor=white)]()
[![Security](https://img.shields.io/badge/Bandit-0_issues-brightgreen?style=for-the-badge&logo=shield&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)]()

---

*मुनीम* (Mu·nim) — the trusted accountant who knows your business inside out.

**Munim converts raw Tally / Excel exports into plain-language WhatsApp reports in Hindi & English — automatically, every week, zero tech skills required.**

</div>

---

## ✨ What It Does

```
📤 Upload Tally XML or Excel   →   🧮 Auto-compute analytics   →   💬 WhatsApp report in Hindi/English
```

| For **SMB Owners** | For **CA Firms** |
|---|---|
| Upload Tally export → get WhatsApp summary | Manage multiple client portfolios |
| Revenue trends, top products, dead stock | At-risk client alerts |
| Hindi / Hinglish / English reports | Bulk report generation |
| Weekly & monthly automated delivery | Client drill-downs |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│   📱 WhatsApp Business API    🌐 Next.js 15 (App Router)        │
└───────────────┬──────────────────────────┬──────────────────────┘
                │                          │
                ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                            │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  /auth   │ │ /upload  │ │/analysis │ │    /reports      │   │
│  │  /ca     │ │          │ │          │ │    /whatsapp     │   │
│  └──────────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘   │
│                    │             │                │              │
│              ┌─────▼─────────────▼────────────────▼──────┐      │
│              │           CELERY WORKERS                   │      │
│              │  process_upload  ·  send_reports           │      │
│              └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
                    │                     │
        ┌───────────▼──────┐   ┌──────────▼────────────┐
        │  🐘 Neon Postgres │   │ ☁️ Cloudflare R2       │
        │  (persistent DB)  │   │ (file storage)         │
        └───────────────────┘   └───────────────────────┘
                    │
        ┌───────────▼───────────┐
        │ 🔴 Upstash Redis       │
        │ (Celery broker/cache) │
        └───────────────────────┘
                    │
        ┌───────────▼──────────────┐
        │ 🤖 Gemini 2.0 Flash       │
        │ (LLM narrator — free tier)│
        └──────────────────────────┘
```

---

## 🚀 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | FastAPI + Python 3.12 | Async-first, type-safe, auto-docs |
| **Frontend** | Next.js 15 + App Router | RSC, streaming, TypeScript |
| **Database** | Neon (serverless Postgres) | Free tier, pg_vector ready |
| **File Storage** | Cloudflare R2 | S3-compatible, free egress |
| **Task Queue** | Celery + Upstash Redis | Beat scheduler for weekly reports |
| **AI Narrator** | Gemini 2.0 Flash | 1M tokens/day free — perfect for MVP |
| **Auth** | NextAuth.js + PyJWT HS256 | CVE-hardened, no python-jose |
| **Messaging** | Meta WhatsApp Business API | Direct delivery to owner's phone |

---

## 📁 Repository Structure

```
munim/
├── 🔧 backend/
│   ├── routers/
│   │   ├── auth.py          # User sync, profile, account deletion
│   │   ├── upload.py        # Tally XML / Excel ingestion
│   │   ├── analysis.py      # Metrics, anomalies, customer segments
│   │   ├── reports.py       # LLM report generation + WhatsApp send
│   │   ├── whatsapp.py      # Meta webhook + opt-in
│   │   └── ca.py            # CA firm portfolio management
│   ├── services/
│   │   ├── analytics/
│   │   │   ├── metrics.py   # Revenue, top products, dead stock, RFM
│   │   │   └── anomaly.py   # Statistical anomaly detection
│   │   ├── reporter/
│   │   │   └── llm_narrator.py  # Gemini 2.0 Flash narrator
│   │   └── parsers/
│   │       ├── tally_xml.py     # TallyPrime XML parser
│   │       └── excel_parser.py  # Excel/CSV normaliser
│   ├── tasks/
│   │   ├── celery_app.py    # Celery + beat schedule
│   │   ├── process_upload.py
│   │   └── send_reports.py
│   ├── db/
│   │   └── neon_client.py   # Async SQLAlchemy session
│   ├── tests/
│   │   ├── conftest.py           # Synthetic fixtures (no real data)
│   │   ├── test_parsers.py       # XML + Excel parsing (36 tests)
│   │   ├── test_analytics.py     # Metrics + anomaly (40 tests)
│   │   └── test_routers.py       # All API endpoints (46 tests)
│   ├── auth.py              # JWT middleware (PyJWT HS256)
│   ├── config.py            # Pydantic Settings
│   ├── main.py              # FastAPI app + CORS + rate limiting
│   └── requirements.txt
└── 🌐 frontend/             # Next.js 15 (coming soon)
```

---

## 🔌 API Endpoints

### 🔐 Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/sync` | Upsert user after Google OAuth |
| `GET` | `/api/v1/auth/me` | Get current user profile |
| `PUT` | `/api/v1/auth/profile` | Update language / phone / WhatsApp |
| `DELETE` | `/api/v1/auth/account` | Permanent account deletion |

### 📤 Upload
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/upload` | Upload Tally XML or Excel file |
| `GET` | `/api/v1/upload/{id}/status` | Poll processing status |

### 📊 Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/analysis/{id}` | Full analysis bundle |
| `GET` | `/api/v1/analysis/{id}/metrics` | Revenue, products, dead stock |
| `GET` | `/api/v1/analysis/{id}/anomalies` | Anomalies (`?severity=HIGH`) |
| `GET` | `/api/v1/analysis/{id}/customers` | RFM customer segments |
| `GET` | `/api/v1/analysis/history/list` | Paginated history |

### 📝 Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reports/generate` | Generate LLM report (5/day) |
| `GET` | `/api/v1/reports` | List all reports |
| `GET` | `/api/v1/reports/{id}` | Get report content |
| `POST` | `/api/v1/reports/{id}/send` | Send to WhatsApp |

### 💬 WhatsApp
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/whatsapp/webhook` | Meta hub.challenge verification |
| `POST` | `/api/v1/whatsapp/webhook` | Receive inbound messages |
| `POST` | `/api/v1/whatsapp/optin` | Opt-in for WhatsApp reports |

### 🏢 CA Firm
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/ca/dashboard` | Portfolio stats |
| `GET` | `/api/v1/ca/clients` | List clients |
| `POST` | `/api/v1/ca/clients` | Add client |
| `GET` | `/api/v1/ca/clients/{id}` | Client detail |
| `PUT` | `/api/v1/ca/clients/{id}` | Update client |
| `DELETE` | `/api/v1/ca/clients/{id}` | Soft delete |
| `GET` | `/api/v1/ca/clients/{id}/uploads` | Upload history |

---

## ⚡ Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- A Neon Postgres database
- Upstash Redis instance

### 1. Clone & setup backend

```bash
git clone https://github.com/AkshitGarg24/munim.git
cd munim/backend

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

```env
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
NEXTAUTH_SECRET=your-32-char-secret
GOOGLE_API_KEY=your-gemini-key

# Optional (WhatsApp)
WHATSAPP_VERIFY_TOKEN=your-webhook-verify-token
WHATSAPP_ACCESS_TOKEN=your-meta-access-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id

# Optional (File Storage)
R2_BUCKET_NAME=munim-uploads
R2_ACCOUNT_ID=your-cf-account-id
R2_ACCESS_KEY_ID=your-r2-key
R2_SECRET_ACCESS_KEY=your-r2-secret

# Optional (Celery)
CELERY_BROKER_URL=rediss://default:pass@host:port
CELERY_RESULT_BACKEND=rediss://default:pass@host:port
```

### 3. Run the backend

```bash
uvicorn main:app --reload --port 8000
```

API docs at → http://localhost:8000/docs

### 4. Run tests

```bash
pytest tests/ -v
```

---

## 🧪 Test Coverage

```
Module                      Tests   Status
──────────────────────────────────────────
test_parsers.py               36    ✅ PASS
test_analytics.py             40    ✅ PASS
test_routers.py               46    ✅ PASS
──────────────────────────────────────────
Total                        122    ✅ ALL GREEN

Coverage areas:
  ████████████████████ Auth endpoints          (9 tests)
  ████████████████████ Analysis endpoints      (8 tests)
  ████████████████████ Reports endpoints       (8 tests)
  ████████████████████ WhatsApp endpoints      (8 tests)
  ████████████████████ CA firm endpoints      (10 tests)
  ████████████████████ Tally XML parsing      (18 tests)
  ████████████████████ Excel parsing          (18 tests)
  ████████████████████ Metrics & analytics    (40 tests)
```

---

## 🔒 Security

| Area | Implementation |
|------|----------------|
| **JWT Auth** | PyJWT HS256 with explicit algorithm allowlist — prevents algorithm confusion attacks |
| **No python-jose** | Removed (CVE-2024-33663, CVE-2024-33664) — replaced with PyJWT 2.10.1 |
| **WebHook HMAC** | X-Hub-Signature-256 verified with `hmac.compare_digest` (constant-time) |
| **Phone Privacy** | Phone numbers SHA-256 hashed in logs — never stored in plaintext in logs |
| **LLM Safety** | LLM receives only pre-computed summaries — never raw financial data |
| **Error Messages** | Internal errors sanitised — no DB strings, file paths, or stack traces to users |
| **File Uploads** | Magic bytes validation + size limits (50 MB) — MIME spoofing blocked |
| **CORS** | Allowlist-based — only configured origins allowed |
| **Rate Limiting** | Slowapi: 5 report generations/day, 60 webhook events/minute |
| **SQL Injection** | All queries use parameterised statements — no f-string SQL |
| **Bandit Scan** | 0 issues on all source files |

---

## 🤖 LLM Narrator Rules

The Gemini 2.0 Flash narrator follows strict rules to stay accurate and trustworthy:

```
✅  Only receives pre-computed analytics summaries (never raw data)
✅  All numbers validated against pre-computed metrics post-generation
✅  15-second timeout with template fallback
✅  Max 300 words per report
✅  Amounts always in Indian format: ₹1,24,300
✅  Never makes up data not in the input JSON
✅  Financial figures redacted in logs (privacy)
✅  Supports Hindi, English, and Hinglish
```

---

## 📈 Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Done | Tally XML + Excel parsers, analytics engine, anomaly detection |
| **Phase 2** | ✅ Done | All API routers, Celery tasks, LLM narrator, WhatsApp integration |
| **Phase 3** | 🔨 Building | Next.js frontend — dashboard, upload UI, report viewer |
| **Phase 4** | 📋 Planned | LangGraph Q&A agent — conversational queries over your data |
| **Phase 5** | 📋 Planned | Multi-language support (Tamil, Telugu, Marathi) |

---

## 🧠 Key Design Decisions

**Why Gemini 2.0 Flash (not GPT-4)?**
Free tier: 15 RPM, 1M tokens/day. Perfect for MVP without a billing surprise.

**Why Celery + Redis (not cron)?**
Beat scheduler handles both weekly Monday 8 AM reports and monthly 1st-of-month reports, with retry logic on worker crash.

**Why PyJWT (not python-jose)?**
python-jose has two unfixed CVEs (algorithm confusion attacks). PyJWT 2.10.1 with explicit `algorithms=["HS256"]` is the secure replacement.

**Why pre-compute analytics before LLM?**
LLMs hallucinate. By computing all numbers first and passing only summaries, every figure in the WhatsApp message is validated against the actual database values.

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/my-feature`
3. Run tests: `pytest tests/ -v`
4. Run security scan: `bandit -r . --exclude tests/`
5. Submit a pull request

---

<div align="center">

Made with ❤️ for Indian small businesses

**मुनीम — आपका digital मुनीम** 🙏

</div>
