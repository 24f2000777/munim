<div align="center">

<br />

# मुनीम · Munim

### AI Business Intelligence for Indian Small Businesses

**Upload any financial file. Get instant AI analysis. Receive WhatsApp reports in Hindi or English.**
Built for Indian SMBs — kirana stores, medical shops, textile traders, and every business in between.

<br />

[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Gemini](https://img.shields.io/badge/Gemini_Flash-AI-4285f4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![PostgreSQL](https://img.shields.io/badge/Neon_PostgreSQL-4169e1?style=flat-square&logo=postgresql&logoColor=white)](https://neon.tech)
[![Tests](https://img.shields.io/badge/Tests-122_passing-2ea44f?style=flat-square&logo=pytest&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)]()

</div>

---

## What It Does

```
📤  Upload Tally XML / Excel / CSV
        ↓
🤖  Gemini AI detects your column names automatically — no setup needed
        ↓
📊  Analytics engine computes revenue, products, customers, anomalies
        ↓
✨  Gemini generates 4 business-specific AI insights
        ↓
💬  WhatsApp report sent in Hindi / English / Hinglish
```

| For **Business Owners** | For **CA Firms** |
|---|---|
| Upload Tally export → instant dashboard | Manage entire client portfolio |
| Revenue trends, top products, dead stock | At-risk client alerts |
| RFM customer segmentation | Bulk report generation |
| Anomaly detection (drops, spikes) | Per-client drill-down views |
| WhatsApp reports in your language | Client-level analytics |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                               │
│   📱 WhatsApp (Twilio / Meta)   🌐 Next.js 15 (App Router)       │
└────────────────┬─────────────────────────┬───────────────────────┘
                 │                         │
                 ▼                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                     API LAYER  (FastAPI)                          │
│   /upload  /analysis  /reports  /auth  /ca  /whatsapp            │
└───────────────┬─────────────────────────┬────────────────────────┘
                │                         │
       ┌────────▼──────────┐    ┌─────────▼──────────┐
       │    Ingestor        │    │     Analytics       │
       │  ───────────────  │    │  ─────────────────  │
       │  Tally XML        │    │  metrics.py         │
       │  Excel / XLSX     │    │  anomaly.py         │
       │  CSV              │    │  rfm.py             │
       │  Gemini schema    │    │  seasonality.py     │
       │  detection        │    │  ai_insights.py     │
       └────────┬──────────┘    └─────────┬──────────┘
                │                         │
                └──────────┬──────────────┘
                           ▼
               ┌───────────────────────┐
               │    Neon PostgreSQL    │
               │  ─────────────────── │
               │  users               │
               │  uploads             │
               │  analysis_results    │
               │  reports             │
               └───────────────────────┘
```

---

## Features

### 🤖 AI-Powered Schema Detection
Upload **any** financial file — Munim uses Gemini to understand your column names automatically. No configuration, no column mapping. Works with:
- `Bill Date`, `Invoice Date`, `Transaction Date`, `Date`, `तारीख`
- `Net Total`, `Amount`, `Total`, `Sale Value`
- `Party Name`, `Customer`, `Client`, `Buyer`
- Separate Debit / Credit columns from bank statements

### 📊 Complete Business Analytics
- **Revenue Metrics** — Current vs previous period with % change and trend direction
- **Top Products** — Ranked by revenue with trend indicators
- **Dead Stock Detection** — Products with no sales in 14+ days
- **Customer Segmentation** — RFM analysis: Champions, Loyal, At Risk, Lost
- **Anomaly Detection** — Revenue drops, unusual spikes, pattern breaks
- **Adaptive Periods** — Auto-detects if data spans a week, month, or quarter

### ✨ AI Business Insights
After every analysis, Gemini generates 4 actionable insights specific to your business type:
- 🟢 **Opportunity** — Growth levers to act on
- 🟡 **Warning** — Issues that need attention
- 🟠 **Celebration** — Wins worth acknowledging
- 🔵 **Action** — Specific things to do this week

### 💬 WhatsApp Reports
- Narrative reports in **Hindi**, **English**, or **Hinglish**
- Sent via **Twilio** sandbox (no business verification needed) or Meta Business API
- Written by Gemini like a trusted advisor, not a robot
- Template fallback if AI is unavailable — pipeline never fails

### 🏪 Supported File Formats
| Format | Description |
|--------|-------------|
| **Tally XML** | Export from TallyPrime — Gateway of Tally |
| **Excel (.xlsx, .xls)** | Any spreadsheet with date + amount columns |
| **CSV** | Any comma-separated file |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 15, TypeScript, Tailwind CSS, Recharts |
| **Backend** | FastAPI, Python 3.12, SQLAlchemy (async) |
| **Database** | Neon PostgreSQL (serverless) |
| **AI** | Google Gemini Flash (`google-genai` SDK) |
| **Auth** | NextAuth.js v5, Google OAuth |
| **WhatsApp** | Twilio (primary) + Meta Business API (fallback) |
| **File Parsing** | openpyxl, pandas, lxml |
| **Testing** | pytest — 122 tests |

---

## Quick Start

### Prerequisites
- Python 3.12+ and Node.js 20+
- [Neon PostgreSQL](https://neon.tech) database (free tier works)
- [Google AI Studio](https://aistudio.google.com) API key (free)
- [Google OAuth](https://console.cloud.google.com) client ID + secret

### 1 — Clone and set up backend

```bash
git clone https://github.com/your-username/munim.git
cd munim/backend

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # Then fill in your credentials
```

### 2 — Configure `.env`

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?sslmode=require

# Google AI (Gemini)
GOOGLE_API_KEY=AIza...

# Google OAuth
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
NEXTAUTH_SECRET=any-random-32-char-string

# WhatsApp via Twilio (sandbox — no business verification needed)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# App
APP_ENV=development
APP_SECRET_KEY=change-me-in-production
```

### 3 — Start backend

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
# Swagger docs: http://localhost:8000/docs
```

### 4 — Set up and start frontend

```bash
cd frontend
npm install

# Create frontend/.env.local
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=same-as-backend-secret
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

npm run dev
# App: http://localhost:3000
```

---

## WhatsApp Setup (5 minutes, free)

### Option A — Twilio Sandbox (Recommended for testing)

1. Sign up at [twilio.com](https://twilio.com) — no credit card needed
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. Send the activation code to **+1 415 523 8886** on WhatsApp
4. Copy **Account SID** and **Auth Token** from Console → Account Info
5. Paste into `.env` → done!

### Option B — Meta Business API (Production)

Set `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN` in `.env`.
Munim automatically uses whichever provider is configured.
Twilio takes priority if both are set.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | Neon PostgreSQL connection string |
| `GOOGLE_API_KEY` | ✅ | Gemini API key from Google AI Studio |
| `GOOGLE_CLIENT_ID` | ✅ | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google OAuth client secret |
| `NEXTAUTH_SECRET` | ✅ | Random string for session signing |
| `TWILIO_ACCOUNT_SID` | ⚡ | Twilio Account SID (WhatsApp) |
| `TWILIO_AUTH_TOKEN` | ⚡ | Twilio Auth Token (WhatsApp) |
| `TWILIO_WHATSAPP_FROM` | ⚡ | Sandbox number — default: `whatsapp:+14155238886` |
| `WHATSAPP_PHONE_NUMBER_ID` | — | Meta Business API phone number ID |
| `WHATSAPP_ACCESS_TOKEN` | — | Meta Business API access token |
| `APP_ENV` | — | `development` or `production` |
| `APP_SECRET_KEY` | — | JWT signing secret |

---

## How AI Schema Detection Works

Munim sends only the column headers and 8 sample rows to Gemini — never the full dataset:

```
Headers:  ["Bill Date", "Invoice No", "Party Name", "Item Name", "Net Total"]
Samples:  [{"Bill Date": "2026-01-15", "Party Name": "Sharma Medical", ...}]

Gemini returns:
{
  "date_column":     "Bill Date",
  "amount_column":   "Net Total",
  "customer_column": "Party Name",
  "product_column":  "Item Name",
  "business_type":   "medical pharmacy",
  "confidence":      0.97
}
```

If confidence < 0.65 or Gemini is unavailable, falls back to rule-based pattern matching.

---

## Project Structure

```
munim/
├── backend/
│   ├── routers/
│   │   ├── auth.py              # Google OAuth + profile management
│   │   ├── upload.py            # File upload + status polling
│   │   ├── analysis.py          # Metrics, anomalies, customers, history
│   │   ├── reports.py           # WhatsApp report generation + delivery
│   │   ├── ca.py                # CA firm portfolio endpoints
│   │   └── whatsapp.py          # Webhook + send endpoints
│   ├── services/
│   │   ├── ingestor/
│   │   │   ├── excel_parser.py           # Excel / CSV parsing
│   │   │   ├── tally_parser.py           # Tally XML parsing
│   │   │   ├── schema_detector.py        # Format detection + routing
│   │   │   └── gemini_schema_detector.py # AI column detection
│   │   ├── analytics/
│   │   │   ├── metrics.py       # Revenue, top products, dead stock
│   │   │   ├── anomaly.py       # Anomaly detection
│   │   │   ├── rfm.py           # RFM customer segmentation
│   │   │   ├── seasonality.py   # Seasonal context generation
│   │   │   └── ai_insights.py   # Gemini business insights
│   │   └── reporter/
│   │       └── llm_narrator.py  # WhatsApp report generation
│   ├── tasks/
│   │   └── process_upload.py    # Full analysis pipeline
│   ├── tests/                   # 122 pytest tests
│   └── config.py                # Settings via pydantic-settings
│
└── frontend/
    ├── app/
    │   ├── page.tsx                    # Public landing page
    │   ├── (auth)/login/               # Google sign-in
    │   ├── (dashboard)/
    │   │   ├── dashboard/              # Authenticated home with charts
    │   │   ├── upload/                 # Drag-and-drop file upload
    │   │   ├── analysis/[id]/          # Full business dashboard
    │   │   ├── reports/                # Upload history list
    │   │   ├── alerts/                 # Anomaly alerts
    │   │   └── settings/               # Profile + WhatsApp preferences
    │   └── (ca)/                       # CA firm portal
    ├── components/
    │   ├── layout/                     # AppShell, Sidebar, TopBar, MobileNav
    │   └── dashboard/                  # MetricCard, RevenueChart
    └── lib/
        ├── api/                        # React Query hooks
        └── types.ts                    # TypeScript interfaces
```

---

## Running Tests

```bash
cd backend
source venv/bin/activate

pytest tests/ -q                       # Quick summary — 122 tests
pytest tests/ -v                       # Verbose with test names
pytest tests/test_metrics.py -v        # Revenue + analytics
pytest tests/test_anomaly.py -v        # Anomaly detection
pytest tests/test_tally_parser.py -v   # Tally XML parser
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make changes and run tests: `pytest tests/ -q`
4. Commit: `git commit -m "feat: description"`
5. Open a pull request

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ for Indian businesses

*मुनीम — आपका भरोसेमंद डिजिटल हिसाबकिताब*

</div>
