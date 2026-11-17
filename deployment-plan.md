# Deployment Plan: Dubai AI Travel Planner on Streamlit Community Cloud

This document outlines the step-by-step deployment procedure for the **Dubai AI Travel Planner** on **Streamlit Community Cloud** (hosting both the autonomous multi-agent backend and the Nocturne Oasis dark luxury frontend).

---

## 1. Architecture & Deployment Model

The application uses a **unified single-stack deployment model**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Streamlit Community Cloud                         │
│                                                                        │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────┐  │
│  │     Nocturne Oasis Frontend     │  │  Autonomous Backend Engine  │  │
│  │                                 │  │                             │  │
│  │ • Collapsible Planner Sidebar   │  │ • LangGraph StateGraph      │  │
│  │ • Syne & Geist Custom CSS       │◄─┼─│ • Groq LLM (oss-120b)     │  │
│  │ • Real-time Budget Feasibility  │  │ • Ollama (nemotron-3-ultra) │  │
│  │ • Leaflet / Folium Map & Metro  │  │ • Deterministic Fallback    │  │
│  │ • Plotly Financial Charts       │  │ • SQLite DB (data/...)      │  │
│  │ • Agent Observability Trace     │  │                             │  │
│  └─────────────────────────────────┘  └─────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

- **Runtime**: Python 3.11 / 3.12 container managed by Streamlit Community Cloud.
- **Entry Point**: `app.py`.
- **Database**: Local SQLite database (`data/dubai_travel.db`) automatically seeded from `data/seed_data.json` on cold start (0 external database hosting required).
- **LLM Infrastructure**:
  - **Groq API**: Free-tier LPUs for Orchestrator, Destination, Logistics, and Budget agents (`openai/gpt-oss-120b`).
  - **Ollama Cloud**: Cloud-hosted endpoint or remote proxy for Review & QA Agent (`nemotron-3-ultra`).
  - **Deterministic Zero-Cost Fallback**: If external LLMs or networks are temporarily unreachable, the deterministic calculation engine takes over automatically ($0.00 operational cost).

---

## 2. Pre-Deployment Checklist

Ensure the following configuration files exist in your repository root before pushing:

| File | Purpose | Status |
|---|---|---|
| `app.py` | Main application entry point | ✅ Ready |
| `requirements.txt` | Python packages for Streamlit Cloud builder | ✅ Ready |
| `.streamlit/config.toml` | Server headless settings & dark theme | ✅ Ready |
| `.gitignore` | Prevents pushing virtualenvs, `.env`, and secret keys | ✅ Ready |
| `data/seed_data.json` | 196 venues & 35 metro stations seed data | ✅ Ready |
| `data/rta_transit_matrix.json`| Dubai RTA transit matrix | ✅ Ready |
| `src/` | Full multi-agent orchestration code | ✅ Ready |

---

## 3. Step 1: Prepare Git Repository

Streamlit Community Cloud deploys directly from a **GitHub repository** (public or private).

### 3.1 Initialize Git (if not already initialized)
Open your terminal in `/Users/shashikiran/Desktop/tripplanner` and run:

```bash
cd /Users/shashikiran/Desktop/tripplanner

# Initialize git repository
git init

# Verify .gitignore is in place to protect .env
git status
```

### 3.2 Commit Project Files
```bash
# Stage all project files (excluding .venv, .env, and cache ignored by .gitignore)
git add .

# Initial commit
git commit -m "feat: complete Dubai AI Travel Planner multi-agent system with Nocturne Oasis UI"
```

### 3.3 Push to GitHub
1. Create a new repository on [GitHub](https://github.com/new) named `tripplanner` (can be **Public** or **Private**).
2. Link your local repo and push:

```bash
# Rename branch to main
git branch -M main

# Add your remote repository (replace with your actual GitHub username)
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/tripplanner.git

# Push to GitHub
git push -u origin main
```

---

## 4. Step 2: Deploy to Streamlit Community Cloud

### 4.1 Sign In to Streamlit Cloud
1. Navigate to [share.streamlit.io](https://share.streamlit.io).
2. Sign in using your **GitHub account**.

### 4.2 Create a New App
1. Click **"New app"** (or **"Create app"**).
2. Choose **"Deploy a public app from GitHub"** (or your existing repo).
3. Fill in the repository settings:
   - **Repository**: `<YOUR_GITHUB_USERNAME>/tripplanner`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL** (Optional): Choose a custom subdomain, e.g., `dubai-ai-travel-planner.streamlit.app`

---

## 5. Step 3: Configure Cloud Secrets

In Streamlit Community Cloud, secrets are managed securely via the web console (never commit `.env` or raw keys to Git).

### 5.1 Open the Secrets Manager
Before clicking Deploy (or under **App Settings → Secrets** after creation):
1. In the deploy modal, click **"Advanced settings..."**
2. In the **Secrets** text area, paste the following TOML configuration:

```toml
# ==============================================================================
# Dubai AI Travel Planner - Streamlit Cloud Production Secrets
# ==============================================================================

# 1. Groq API Key (Orchestrator, Destination, Logistics, Budget Agents)
# Get a free key at https://console.groq.com
GROQ_API_KEY = "gsk_your_actual_groq_api_key_here"
GROQ_MODEL = "openai/gpt-oss-120b"

# 2. Ollama Cloud Endpoint (Review & QA Agent)
# • If using Ollama Cloud or a remote GPU instance:
OLLAMA_BASE_URL = "https://api.ollama.ai"
OLLAMA_API_KEY = "your_actual_ollama_api_key_here"
OLLAMA_MODEL = "nemotron-3-ultra"

# • If you do NOT have a cloud Ollama URL, leave empty:
#   The system will automatically engage the 100% deterministic quality audit ($0.00).
# OLLAMA_BASE_URL = ""
# OLLAMA_API_KEY = ""

# 3. Optional Gemini API Key (Legacy Fallback)
# GEMINI_API_KEY = "your_gemini_key_here"
```

> **Note on Ollama in Streamlit Cloud**:
> Standard Streamlit Cloud containers do not run background daemons like `localhost:11434`.
> - If you have an Ollama Cloud key or remote URL, supply `OLLAMA_BASE_URL` and `OLLAMA_API_KEY`.
> - If omitted, `app.py` automatically utilizes its built-in deterministic validation engine with zero errors.

3. Click **"Save"**.
4. Click **"Deploy!"**.

---

## 6. Step 4: Verification & Smoke Testing

Once Streamlit Cloud completes the build (typically 1–2 minutes), verify each component:

### 6.1 Visual & Design Checks
- [ ] **Background & Theme**: Deep obsidian background (`#10131a`) with gold (`#ffb95f`) and violet accents.
- [ ] **Typography**: Headings render in `Syne` and body text in `Geist`.
- [ ] **Collapsible Sidebar**: Left sidebar is responsive and can be collapsed using the Streamlit arrow icon.
- [ ] **Dubai Skyline Silhouette**: Faint architectural skyline watermark displays along the bottom.

### 6.2 Interactive Controls & Real-Time Validation
- [ ] **Preset Buttons**: Clicking **"🏛️ 4D Heritage"**, **"🏙️ 3D Modern"**, **"🐪 5D Complete"**, or **"⏱️ 2D Stopover"** instantly updates duration, budget, tier, and interests.
- [ ] **Real-Time Budget Tag**:
  - Select **Luxury Tier** with **4 Days** and budget **AED 4,500**.
  - Verify red warning tag displays: `⚠️ You have to increase the budget (+AED 1,070)`.
  - Click **`⚡ Set Budget to AED 5,570`** and verify the budget updates without errors, switching to `✅ Budget sufficient`.
- [ ] **Climate Advisory**: Change month to **July (7)** → verify amber summer warning banner renders. Change to **February (2)** → verify green optimal banner renders.

### 6.3 Itinerary Generation & Tabs
- [ ] Click **"🚀 Generate Dubai Itinerary"**.
- [ ] **Telemetry Bar**: Status updates to `Approved (Round 0)` or `Approved with Revisions`, latency shows `< 15s`, cost displays `$0.00`.
- [ ] **Tab 1 (Timeline)**: Day accordions expand/collapse with district badges, activity cards, and transit steps.
- [ ] **Tab 2 (Map & Metro)**: Folium map renders Dubai with colored day pins, connecting route polylines, and 35 Metro stations.
- [ ] **Tab 3 (Financials)**: 4 metrics, category donut chart, budget utilization gauge, and itemized cost table.
- [ ] **Tab 4 (Observability)**: Review Agent audit card and sequential multi-agent execution timeline.

---

## 7. Production Operations & Troubleshooting

### Common Deployment Issues & Resolutions

| Issue | Root Cause | Solution |
|---|---|---|
| `ModuleNotFoundError` during cloud build | Missing package in `requirements.txt` | Ensure all dependencies are in `requirements.txt`. |
| `sqlite3.OperationalError: unable to open database file` | Relative path issue | `DubaiSQLiteClient` automatically uses `data/dubai_travel.db` relative to repo root and creates parent directories. Ensure `data/seed_data.json` is committed in git. |
| `StreamlitWidgetAlreadyInstantiatedError` | Directly mutating widget keys in session state | Already solved via `on_click=set_auto_budget` pre-instantiation callbacks. |
| Groq `RateLimitError: 429` | Exceeded 8,000 TPM limit on free tier | Handled automatically: agents fall back to deterministic local heuristic extraction with zero crash. |
| Ollama `[Errno 8] nodename nor servname provided` | Unreachable Ollama cloud host | Handled automatically: review agent falls back to deterministic rule-based audit and flags advisory. |
| App goes to sleep after inactivity | Streamlit Community Cloud free tier idle timeout | Click "Yes, get this app back up!" on the sleeping screen. Cold start takes ~10 seconds. |

---

## 8. Continuous Updates & Maintenance

Whenever you push changes to your GitHub `main` branch:
1. Streamlit Cloud automatically detects the commit via webhook.
2. The cloud container pulls the latest code and hot-reloads the application within seconds.
3. To view live logs or restart the app manually:
   - Click **"Manage app"** in the bottom right corner of your deployed URL.
   - Click the three-dots menu `⋮` → **"Reboot app"** or **"Clear cache"**.
