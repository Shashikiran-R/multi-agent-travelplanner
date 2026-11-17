"""
Dubai AI Travel Planner - Autonomous Multi-Agent Itinerary Orchestrator
Streamlit Interactive UI & Observability Dashboard (Phase 6)
Powered by Groq (openai/gpt-oss-120b), Ollama (nemotron-3-ultra), and Local SQLite.
Operational API Cost: $0.00.
"""

import os
import time
from typing import Dict, Any, List, Optional
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go

from src.data_access.sqlite_client import DubaiSQLiteClient
from src.graph.workflow import run_travel_planner
from src.models.itinerary import TripItinerary


# Bridge Streamlit Cloud secrets to os.environ for multi-agent LLM factory
try:
    if hasattr(st, "secrets"):
        for secret_key, secret_val in st.secrets.items():
            if secret_key not in os.environ and isinstance(secret_val, str):
                os.environ[secret_key] = secret_val
except Exception:
    pass


# =============================================================================
# Streamlit Page Configuration
# =============================================================================
st.set_page_config(
    page_title="Dubai AI Travel Planner",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# =============================================================================
# Custom Modern Luxury CSS Design System (Nocturne Oasis Concierge Theme)
# Aligned with stitch_dubai_ai_travel_planner design tokens & typography
# =============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Syne:wght@600;700;800&family=Outfit:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Geist', 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Deep Obsidian Base Void Background with Desert Glow */
.stApp {
    background: radial-gradient(circle at 80% 20%, rgba(238, 152, 0, 0.05), transparent 50%),
                radial-gradient(circle at 20% 80%, rgba(124, 58, 237, 0.07), transparent 55%),
                #10131a;
    color: #e1e2ec;
}

/* Sidebar Styling */
section[data-testid="stSidebar"] {
    background-color: #191b23 !important;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

section[data-testid="stSidebar"] h3 {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #f1f5f9;
}

/* Nocturne Crystalline Cards */
.dxb-card {
    background: rgba(29, 31, 39, 0.75);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.dxb-card:hover {
    border-color: rgba(255, 185, 95, 0.4);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
}

/* Hero Banner */
.hero-header {
    background: linear-gradient(135deg, rgba(29, 31, 39, 0.95) 0%, rgba(16, 19, 26, 0.98) 100%);
    border: 1px solid rgba(255, 185, 95, 0.25);
    border-radius: 8px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    position: relative;
    overflow: hidden;
}
.hero-header::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #ffb95f, #7c3aed, transparent);
}
.hero-title {
    font-family: 'Syne', sans-serif;
    font-size: 2.3rem;
    font-weight: 800;
    background: linear-gradient(90deg, #ffb95f 0%, #ee9800 45%, #e1e2ec 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    letter-spacing: -0.02em;
}
.hero-subtitle {
    font-family: 'Geist', sans-serif;
    font-size: 1.0rem;
    color: #ccc3d8;
    margin-top: 0.35rem;
    font-weight: 400;
    letter-spacing: 0.01em;
}

/* Telemetry Bar */
.telemetry-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1.25rem;
    background: #191b23;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 0.85rem 1.25rem;
    margin-bottom: 1.5rem;
}
.telemetry-item {
    display: flex;
    flex-direction: column;
}
.telemetry-label {
    font-family: 'Geist', sans-serif;
    font-size: 0.70rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #958da1;
    font-weight: 600;
}
.telemetry-value {
    font-family: 'Geist', sans-serif;
    font-size: 0.95rem;
    font-weight: 700;
    color: #e1e2ec;
    margin-top: 0.15rem;
}

/* Status Badges */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.7rem;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.status-approved {
    background: rgba(16, 185, 129, 0.15);
    color: #34D399;
    border: 1px solid rgba(16, 185, 129, 0.35);
}
.status-revisions {
    background: rgba(255, 185, 95, 0.15);
    color: #ffb95f;
    border: 1px solid rgba(255, 185, 95, 0.35);
}
.status-rejected {
    background: rgba(239, 68, 68, 0.15);
    color: #ffb4ab;
    border: 1px solid rgba(239, 68, 68, 0.35);
}
.status-ready {
    background: rgba(124, 58, 237, 0.15);
    color: #d2bbff;
    border: 1px solid rgba(124, 58, 237, 0.35);
}

/* District Badges */
.badge-district {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.district-old-dubai { background: rgba(217, 119, 6, 0.2); color: #ffb95f; border: 1px solid #D97706; }
.district-downtown { background: rgba(37, 99, 235, 0.2); color: #b4c5ff; border: 1px solid #2563EB; }
.district-marina { background: rgba(5, 150, 105, 0.2); color: #34D399; border: 1px solid #059669; }
.district-palm { background: rgba(124, 58, 237, 0.2); color: #d2bbff; border: 1px solid #7C3AED; }
.district-desert { background: rgba(220, 38, 38, 0.2); color: #ffb4ab; border: 1px solid #DC2626; }

/* Climate Advisory Card */
.climate-box-warning {
    background: rgba(238, 152, 0, 0.12);
    border: 1px solid rgba(238, 152, 0, 0.35);
    border-radius: 6px;
    padding: 0.85rem 1rem;
    margin-top: 0.75rem;
    font-size: 0.85rem;
    color: #ffddb8;
    line-height: 1.4;
}
.climate-box-optimal {
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 6px;
    padding: 0.85rem 1rem;
    margin-top: 0.75rem;
    font-size: 0.85rem;
    color: #A7F3D0;
    line-height: 1.4;
}

/* Real-Time Budget Feasibility Tags */
.budget-alert-tag {
    background: rgba(147, 0, 10, 0.25);
    border: 1px solid rgba(255, 180, 171, 0.35);
    border-left: 4px solid #ffb4ab;
    border-radius: 6px;
    padding: 0.75rem 0.9rem;
    margin-top: 0.35rem;
    margin-bottom: 0.75rem;
    font-size: 0.83rem;
    color: #ffdad6;
    line-height: 1.4;
    box-shadow: 0 4px 14px rgba(147, 0, 10, 0.3);
}
.budget-alert-header {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-weight: 700;
    color: #ffb4ab;
    font-size: 0.88rem;
    margin-bottom: 0.3rem;
    letter-spacing: 0.02em;
}
.budget-alert-body ul {
    margin: 0.25rem 0 0.35rem 1.1rem;
    padding: 0;
}
.budget-alert-body li {
    margin-bottom: 0.15rem;
}
.budget-ok-tag {
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-left: 4px solid #10B981;
    border-radius: 6px;
    padding: 0.55rem 0.85rem;
    margin-top: 0.35rem;
    margin-bottom: 0.75rem;
    font-size: 0.82rem;
    color: #A7F3D0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    line-height: 1.35;
}

/* Timeline Activity Card */
.activity-card {
    background: rgba(29, 31, 39, 0.65);
    border-left: 4px solid #ffb95f;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 0 6px 6px 0;
    padding: 0.9rem 1.15rem;
    margin-bottom: 0.65rem;
    transition: transform 0.15s ease-in-out;
}
.activity-card:hover {
    transform: translateX(3px);
}
.activity-card-downtown { border-left-color: #2563EB; }
.activity-card-marina { border-left-color: #059669; }
.activity-card-palm { border-left-color: #7C3AED; }
.activity-card-desert { border-left-color: #DC2626; }

/* Transit Step Card */
.transit-step-card {
    background: rgba(16, 19, 26, 0.7);
    border: 1px dashed rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 0.65rem 1rem;
    margin-left: 1.5rem;
    margin-bottom: 0.65rem;
    font-size: 0.85rem;
    color: #ccc3d8;
    display: flex;
    align-items: center;
    gap: 0.85rem;
}

/* Free badge */
.badge-free {
    background: rgba(16, 185, 129, 0.2);
    color: #10B981;
    font-weight: 700;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
}

/* Fixed Bottom Dubai Skyline Silhouette */
.skyline-watermark {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60px;
    pointer-events: none;
    z-index: 0;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    opacity: 0.15;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# Database & Utility Initialization
# =============================================================================
@st.cache_resource
def get_db_client() -> DubaiSQLiteClient:
    return DubaiSQLiteClient()

db = get_db_client()

DISTRICT_COLORS = {
    "Old Dubai & Creek": "#D97706",
    "Downtown & DIFC": "#2563EB",
    "Dubai Marina & JBR": "#059669",
    "Palm Jumeirah & Jumeirah": "#7C3AED",
    "Desert & Outskirts": "#DC2626"
}

DISTRICT_CSS_CLASSES = {
    "Old Dubai & Creek": "district-old-dubai",
    "Downtown & DIFC": "district-downtown",
    "Dubai Marina & JBR": "district-marina",
    "Palm Jumeirah & Jumeirah": "district-palm",
    "Desert & Outskirts": "district-desert"
}

PRESETS = {
    "4-Day Cultural & Heritage Explorer": {
        "prompt": "4-Day Cultural & Heritage Explorer focusing on historic souks, creekside culture, and downtown icons",
        "duration": 4,
        "budget": 2800.0,
        "tier": "budget",
        "month": 11,
        "interests": ["culture", "free"]
    },
    "3-Day Modern Icons & Beachfront": {
        "prompt": "3-Day Modern Icons & Beachfront exploring Burj Khalifa, Dubai Mall, and Dubai Marina",
        "duration": 3,
        "budget": 4500.0,
        "tier": "midscale",
        "month": 2,
        "interests": ["views", "beach", "shopping"]
    },
    "5-Day Complete Dubai & Desert Grand Tour": {
        "prompt": "5-Day Complete Dubai & Desert Grand Tour covering all 5 districts with desert safari and luxury skyline views",
        "duration": 5,
        "budget": 8500.0,
        "tier": "luxury",
        "month": 1,
        "interests": ["culture", "adventure", "views", "shopping"]
    },
    "2-Day Stopover Essentials": {
        "prompt": "2-Day Stopover Essentials with Downtown landmarks and traditional Creek abra crossing",
        "duration": 2,
        "budget": 1500.0,
        "tier": "budget",
        "month": 3,
        "interests": ["culture", "views"]
    }
}


# =============================================================================
# Session State Initialization
# =============================================================================
if "prompt_input" not in st.session_state:
    st.session_state["prompt_input"] = "Plan a 3-day cultural and foodie trip to Dubai with AED 4,500 budget in February"
if "duration_input" not in st.session_state:
    st.session_state["duration_input"] = 3
if "budget_input" not in st.session_state:
    st.session_state["budget_input"] = 4500.0
if "tier_input" not in st.session_state:
    st.session_state["tier_input"] = "midscale"
if "month_input" not in st.session_state:
    st.session_state["month_input"] = 2
if "interests_input" not in st.session_state:
    st.session_state["interests_input"] = ["culture", "views"]
if "planner_result" not in st.session_state:
    st.session_state["planner_result"] = None
if "execution_latency" not in st.session_state:
    st.session_state["execution_latency"] = None


# =============================================================================
# Helper: Preset Loader
# =============================================================================
def load_preset(preset_name: str):
    p = PRESETS[preset_name]
    st.session_state["prompt_input"] = p["prompt"]
    st.session_state["duration_input"] = p["duration"]
    st.session_state["budget_input"] = p["budget"]
    st.session_state["tier_input"] = p["tier"]
    st.session_state["month_input"] = p["month"]
    st.session_state["interests_input"] = p["interests"]


def set_auto_budget(target_amount: float):
    """Callback triggered before widget instantiation to safely adjust budget."""
    st.session_state["budget_input"] = float(target_amount)


# =============================================================================
# Sidebar Configuration Panel (Step 6.1)
# =============================================================================
with st.sidebar:
    st.markdown("### 🎛️ Trip Planner Controls")
    st.caption("Configure parameters or choose a curated travel persona.")

    # 1. Preset Selector Buttons
    st.markdown("**Quick Curated Presets:**")
    p_cols1 = st.columns(2)
    with p_cols1[0]:
        if st.button("🏛️ 4D Heritage", width="stretch", help="Old Dubai & Downtown | AED 2,800"):
            load_preset("4-Day Cultural & Heritage Explorer")
            st.rerun()
    with p_cols1[1]:
        if st.button("🏙️ 3D Modern", width="stretch", help="Downtown & Marina/JBR | AED 4,500"):
            load_preset("3-Day Modern Icons & Beachfront")
            st.rerun()

    p_cols2 = st.columns(2)
    with p_cols2[0]:
        if st.button("🐪 5D Complete", width="stretch", help="All 5 Districts & Desert | AED 8,500"):
            load_preset("5-Day Complete Dubai & Desert Grand Tour")
            st.rerun()
    with p_cols2[1]:
        if st.button("⏱️ 2D Stopover", width="stretch", help="Downtown & Creek | AED 1,500"):
            load_preset("2-Day Stopover Essentials")
            st.rerun()

    st.markdown("---")

    # 2. Natural Language Prompt
    st.text_area(
        "Natural Language Request",
        key="prompt_input",
        height=95,
        help="Specify your travel goals, interests, or style in free-form English."
    )

    # 3. Parameters
    st.slider(
        "Trip Duration (Days)",
        min_value=1,
        max_value=7,
        key="duration_input"
    )

    tier_labels = {
        "budget": "Budget (~AED 210/night in Deira)",
        "midscale": "Midscale (~AED 650/night in Downtown)",
        "luxury": "Luxury (~AED 1,750/night in Marina)"
    }
    st.selectbox(
        "Accommodation Tier",
        options=["budget", "midscale", "luxury"],
        format_func=lambda t: tier_labels[t],
        key="tier_input"
    )

    st.number_input(
        "Total Budget (AED)",
        min_value=300.0,
        max_value=100000.0,
        step=250.0,
        key="budget_input"
    )

    # -------------------------------------------------------------------------
    # Real-Time Budget Feasibility Validation Tag (Prompt under Budget Field)
    # -------------------------------------------------------------------------
    tier_val = st.session_state.get("tier_input", "midscale")
    duration_val = int(st.session_state.get("duration_input", 3))
    budget_val = float(st.session_state.get("budget_input", 4500.0))

    tier_nightly_map = {
        "budget": 210.0,
        "midscale": 650.0,
        "luxury": 1750.0
    }
    tier_display_names = {
        "budget": "Budget (~AED 210/night in Deira)",
        "midscale": "Midscale (~AED 650/night in Downtown)",
        "luxury": "Luxury (~AED 1,750/night in Marina)"
    }

    nights_val = max(1, duration_val - 1)
    nightly_rate = tier_nightly_map.get(tier_val, 650.0)
    est_lodging_total = nights_val * nightly_rate
    min_subsistence_total = duration_val * 80.0  # AED 70 food + AED 10 transit baseline
    min_required_budget = est_lodging_total + min_subsistence_total

    if budget_val < min_required_budget:
        deficit_aed = min_required_budget - budget_val
        st.markdown(f"""
        <div class="budget-alert-tag">
            <div class="budget-alert-header">
                <span>⚠️</span>
                <span>You have to increase the budget (+AED {deficit_aed:,.0f})</span>
            </div>
            <div class="budget-alert-body">
                A <strong>{duration_val}-day</strong> trip with <strong>{tier_display_names.get(tier_val, tier_val)}</strong> lodging requires at least <strong>AED {min_required_budget:,.0f}</strong>:
                <ul>
                    <li>Estimated Lodging ({nights_val} nights): <strong>AED {est_lodging_total:,.0f}</strong></li>
                    <li>Basic Meals & Metro ({duration_val} days): <strong>AED {min_subsistence_total:,.0f}</strong></li>
                    <li><strong>Total Minimum Required: AED {min_required_budget:,.0f}</strong></li>
                </ul>
                👉 <em>Your current budget of <strong>AED {budget_val:,.0f}</strong> is insufficient by <strong>AED {deficit_aed:,.0f}</strong>. Please increase your budget or choose a lower tier.</em>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.button(
            f"⚡ Set Budget to AED {int(min_required_budget):,}",
            key="btn_fix_budget_auto",
            on_click=set_auto_budget,
            args=(min_required_budget,),
            help="Click to automatically adjust budget to the required minimum threshold"
        )
    else:
        st.markdown(f"""
        <div class="budget-ok-tag">
            <span>✅</span>
            <span>Budget sufficient for <strong>{duration_val}D {tier_val.capitalize()}</strong> (Min. required: AED {min_required_budget:,.0f})</span>
        </div>
        """, unsafe_allow_html=True)

    month_names = {
        1: "1 - January (Winter Peak)",
        2: "2 - February (Pleasant)",
        3: "3 - March (Spring)",
        4: "4 - April (Warm)",
        5: "5 - May (Hot)",
        6: "6 - June (Extreme Summer)",
        7: "7 - July (Extreme Summer)",
        8: "8 - August (Extreme Summer)",
        9: "9 - September (Late Summer)",
        10: "10 - October (Autumn)",
        11: "11 - November (Pleasant)",
        12: "12 - December (Winter Peak)"
    }
    month_val = st.session_state["month_input"]
    st.selectbox(
        "Travel Month",
        options=list(range(1, 13)),
        format_func=lambda m: month_names[m],
        key="month_input"
    )

    # Dynamic Climate Advisory Card
    climate = db.get_climate_profile(month_val)
    if climate:
        if climate["is_extreme_summer"]:
            st.markdown(f"""
            <div class="climate-box-warning">
                <strong>☀️ Extreme Summer Warning ({month_names[month_val].split(' - ')[1]}):</strong><br>
                Average High: <strong>{climate['avg_high_c']}°C</strong> | Heat Index: <strong>{climate['peak_apparent_temp_c']}°C</strong>.<br>
                <em>{climate['outdoor_recommendation']}</em><br>
                Outdoor midday activities will automatically be routed to air-conditioned indoor venues.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="climate-box-optimal">
                <strong>🌤️ Optimal Travel Season ({month_names[month_val].split(' - ')[1]}):</strong><br>
                Average High: <strong>{climate['avg_high_c']}°C</strong> | Peak Apparent: <strong>{climate['peak_apparent_temp_c']}°C</strong>.<br>
                <em>{climate['outdoor_recommendation']}</em>
            </div>
            """, unsafe_allow_html=True)

    all_tags = ["culture", "beach", "adventure", "views", "shopping", "nature", "free"]
    st.multiselect(
        "Traveler Interests",
        options=all_tags,
        key="interests_input"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Generate Action Button
    generate_pressed = st.button("🚀 Generate Dubai Itinerary", type="primary", width="stretch")


# =============================================================================
# Graph Execution Trigger
# =============================================================================
if generate_pressed:
    overrides = {
        "trip_duration_days": int(st.session_state["duration_input"]),
        "total_budget_aed": float(st.session_state["budget_input"]),
        "travel_month": int(st.session_state["month_input"]),
        "accommodation_tier": st.session_state["tier_input"],
        "interests": st.session_state["interests_input"]
    }
    
    with st.spinner("🤖 LangGraph Multi-Agent Engine orchestrating itinerary across Groq & Ollama..."):
        t0 = time.perf_counter()
        result = run_travel_planner(prompt=st.session_state["prompt_input"], overrides=overrides)
        latency = round(time.perf_counter() - t0, 3)
        st.session_state["planner_result"] = result
        st.session_state["execution_latency"] = latency
    st.rerun()


# =============================================================================
# Main Dashboard Display
# =============================================================================

# 1. Hero Header
st.markdown("""
<div class="hero-header">
    <h1 class="hero-title">DUBAI AI TRAVEL PLANNER</h1>
    <div class="hero-subtitle">
        Autonomous Multi-Agent Itinerary Orchestrator powered by LangGraph, Groq <code>oss-120b</code>, and Ollama <code>nemotron-3-ultra</code>.
    </div>
</div>
""", unsafe_allow_html=True)

result = st.session_state.get("planner_result")
latency = st.session_state.get("execution_latency")

# 2. Telemetry Bar (Step 6.3)
if result is None:
    status_html = '<span class="status-badge status-ready">Ready For Request</span>'
    latency_str = "--"
    revisions_str = "--"
else:
    if result.get("is_rejected"):
        status_html = '<span class="status-badge status-rejected">Circuit Breaker: Rejected</span>'
    else:
        rev_count = result.get("revision_count", 0)
        if rev_count > 0:
            status_html = f'<span class="status-badge status-revisions">Approved with {rev_count} Revision(s)</span>'
        else:
            status_html = '<span class="status-badge status-approved">Approved (Round 0)</span>'
    latency_str = f"{latency}s" if latency else "--"
    revisions_str = str(result.get("revision_count", 0))

st.markdown(f"""
<div class="telemetry-bar">
    <div class="telemetry-item">
        <span class="telemetry-label">Status</span>
        <span class="telemetry-value">{status_html}</span>
    </div>
    <div class="telemetry-item">
        <span class="telemetry-label">Execution Latency</span>
        <span class="telemetry-value">{latency_str}</span>
    </div>
    <div class="telemetry-item">
        <span class="telemetry-label">Revision Cycles</span>
        <span class="telemetry-value">{revisions_str} / 3 Max</span>
    </div>
    <div class="telemetry-item">
        <span class="telemetry-label">Operational API Cost</span>
        <span class="telemetry-value" style="color: #34D399;">$0.00 (Zero-Cost LPUs)</span>
    </div>
    <div class="telemetry-item">
        <span class="telemetry-label">Data Sources</span>
        <span class="telemetry-value" style="font-size: 0.85rem; color: #94A3B8;">SQLite (196 Venues, 35 Metro) + Open-Meteo + RTA Math</span>
    </div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# Result Handling: Rejection vs Approved Dashboard
# =============================================================================
if result is None:
    st.info("👈 Use the sidebar configuration panel to customize your travel parameters, or click one of the quick presets to generate a complete Dubai itinerary.")

elif result.get("is_rejected"):
    # Circuit Breaker Rejection Display
    rejection_reason = result.get("rejection_reason", "Budget below minimal mathematical baseline.")
    st.error(f"### 🚫 Request Rejected by Orchestrator Circuit Breaker\n\n**Reason:** {rejection_reason}")
    st.markdown("""
    <div class="dxb-card" style="border-left: 4px solid #EF4444;">
        <h4>💡 Guidance for Valid Travel Requests</h4>
        <ul>
            <li><strong>Minimum Baseline:</strong> Dubai municipal hotel taxes, Nol metro transit, and basic meals require at least <strong>~AED 230/day</strong> for budget tier accommodations.</li>
            <li><strong>Action:</strong> Increase your total budget ceiling or reduce the requested duration slider in the sidebar, then re-click <strong>Generate Dubai Itinerary</strong>.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Display Orchestrator Logs in expander
    with st.expander("🔍 Inspect Circuit Breaker Audit Log", expanded=True):
        st.json(result.get("agent_logs", []))

else:
    # Itinerary Successfully Created
    itinerary_data = result.get("final_itinerary")
    if not itinerary_data:
        st.warning("No itinerary data returned in final state.")
        st.stop()

    itinerary = TripItinerary(**itinerary_data)
    budget = itinerary.budget
    review = itinerary.review

    # Dashboard Tabs (Step 6.2)
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Itinerary Timeline",
        "🗺️ Interactive Map & Metro",
        "💰 Financial Breakdown",
        "🤖 Multi-Agent Observability Trace"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: ITINERARY TIMELINE
    # -------------------------------------------------------------------------
    with tab1:
        st.markdown(f"### {itinerary.title}")
        st.write(itinerary.summary)

        # Iterate over days
        for day in itinerary.days:
            dist_css = DISTRICT_CSS_CLASSES.get(day.primary_district, "district-downtown")
            dist_color = DISTRICT_COLORS.get(day.primary_district, "#2563EB")
            
            with st.expander(f"**Day {day.day_number}: {day.theme}** ({day.primary_district})", expanded=True):
                # Day metadata badges
                st.markdown(f"""
                <div style="margin-bottom: 0.85rem;">
                    <span class="badge-district {dist_css}">📍 {day.primary_district}</span>
                    <span style="background: rgba(255,255,255,0.08); padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.8rem; margin-right: 0.5rem;">
                        🏨 Base Hotel: <strong>{day.hotel_area}</strong>
                    </span>
                    <span style="background: rgba(255,255,255,0.08); padding: 0.2rem 0.6rem; border-radius: 6px; font-size: 0.8rem;">
                        💳 Estimated Daily Spend: <strong>AED {day.daily_spend_aed:.2f}</strong>
                    </span>
                </div>
                """, unsafe_allow_html=True)

                if day.transit_summary:
                    st.caption(f"🚇 *Mobility Briefing:* {day.transit_summary}")

                # Activities
                for slot in day.activities:
                    cat_icon = "🏛️" if slot.category == "attraction" else "🍽️" if slot.category == "dining" else "🏖️"
                    slot_icon = "🌅 Morning" if slot.time_slot == "morning" else "☀️ Afternoon" if slot.time_slot == "afternoon" else "🌙 Evening"
                    cost_badge = '<span class="badge-free">FREE</span>' if slot.cost_aed == 0 else f"<strong>AED {slot.cost_aed:.2f}</strong>"

                    st.markdown(f"""
                    <div class="activity-card" style="border-left-color: {dist_color};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 700; font-size: 1.05rem;">{cat_icon} {slot.place_name}</span>
                            <span style="font-size: 0.85rem; color: #94A3B8;">{slot_icon}</span>
                        </div>
                        <div style="margin-top: 0.35rem; font-size: 0.88rem; color: #CBD5E1; display: flex; gap: 1.25rem;">
                            <span>⏱️ Duration: <strong>{slot.duration_mins} mins</strong></span>
                            <span>💵 Admission/Meal: {cost_badge}</span>
                            <span>📍 District: <strong>{slot.district}</strong></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Inter-activity transit step
                    if slot.transit_to_next:
                        t = slot.transit_to_next
                        mode_icon = "🚇" if t.mode == "metro" else "🚕" if t.mode == "taxi" else "⛵" if "abra" in (t.notes or "").lower() else "🚶"
                        dist_str = f"({t.distance_km:.2f} km)" if t.distance_km else ""
                        st.markdown(f"""
                        <div class="transit-step-card">
                            <span style="font-size: 1.2rem;">{mode_icon}</span>
                            <div style="flex-grow: 1;">
                                <strong>Transit:</strong> {t.origin} ➔ {t.destination} {dist_str}<br>
                                <span style="font-size: 0.8rem; color: #64748B;">⏱️ {t.duration_mins} mins | 💳 Fare: AED {t.fare_aed:.2f} | <em>{t.notes or ''}</em></span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # TAB 2: INTERACTIVE MAP & METRO
    # -------------------------------------------------------------------------
    with tab2:
        st.markdown("### 🗺️ Geographic Itinerary & Dubai Metro Network")
        st.caption("Inspect scheduled venues color-coded by day, connected by transit routes, with Dubai Metro Red & Green line stations.")

        # Folium base map centered on Dubai
        m = folium.Map(location=[25.2048, 55.2708], zoom_start=11, tiles="OpenStreetMap")

        day_palette = ["#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#06B6D4", "#EC4899"]

        # 1. Overlay 35 Metro Stations
        metro_group = folium.FeatureGroup(name="Dubai Metro Stations (35)", show=True)
        stations = db.get_metro_stations()
        for s in stations:
            is_red = "Red" in s["line"]
            line_color = "#EF4444" if is_red else "#10B981"
            popup_html = f"""
            <div style="font-family: sans-serif; min-width: 140px;">
                <h4 style="margin: 0; color: {line_color};">🚇 {s['name']}</h4>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: #555;">
                    Line: <strong>{s['line']}</strong><br>
                    RTA Fare Zone: <strong>Zone {s['zone']}</strong>
                </p>
            </div>
            """
            folium.CircleMarker(
                location=[s["lat"], s["lng"]],
                radius=4,
                color=line_color,
                fill=True,
                fill_color=line_color,
                fill_opacity=0.9,
                popup=folium.Popup(popup_html, max_width=220),
                tooltip=f"🚇 {s['name']} ({s['line']})"
            ).add_to(metro_group)
        metro_group.add_to(m)

        # 2. Daily Venue Markers and Polylines
        for idx, day in enumerate(itinerary.days):
            day_color = day_palette[idx % len(day_palette)]
            day_group = folium.FeatureGroup(name=f"Day {day.day_number}: {day.primary_district}", show=True)
            day_coords = []

            for slot in day.activities:
                day_coords.append((slot.lat, slot.lng))
                popup_html = f"""
                <div style="font-family: sans-serif; min-width: 180px;">
                    <h4 style="margin: 0 0 4px 0; color: #1E293B;">{slot.place_name}</h4>
                    <span style="font-size: 11px; font-weight: bold; background: #E2E8F0; padding: 2px 6px; border-radius: 4px;">{slot.category.upper()}</span>
                    <p style="margin: 6px 0 0 0; font-size: 12px; color: #475569;">
                        District: <strong>{slot.district}</strong><br>
                        Duration: <strong>{slot.duration_mins} mins</strong><br>
                        Admission: <strong>AED {slot.cost_aed:.2f}</strong>
                    </p>
                </div>
                """
                folium.Marker(
                    location=[slot.lat, slot.lng],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"Day {day.day_number}: {slot.place_name}",
                    icon=folium.Icon(color="blue" if idx==0 else "green" if idx==1 else "orange" if idx==2 else "purple", icon="info-sign")
                ).add_to(day_group)

            # Draw route polyline connecting day's stops
            if len(day_coords) > 1:
                folium.PolyLine(
                    locations=day_coords,
                    color=day_color,
                    weight=3.5,
                    opacity=0.85,
                    dash_array="6, 6"
                ).add_to(day_group)

            day_group.add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)
        st_folium(m, width=None, height=560, returned_objects=[])

    # -------------------------------------------------------------------------
    # TAB 3: FINANCIAL BREAKDOWN
    # -------------------------------------------------------------------------
    with tab3:
        st.markdown("### 💰 Financial Breakdown & Expense Ledger")

        # Metric summary row
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric("Total Budget Limit", f"AED {budget.budget_limit_aed:,.2f}")
        with m_col2:
            st.metric("Grand Total Cost", f"AED {budget.grand_total_aed:,.2f}")
        with m_col3:
            rem = budget.remaining_balance_aed
            st.metric("Remaining Buffer", f"AED {rem:,.2f}", delta=f"{rem:,.2f} AED")
        with m_col4:
            compliance = "✅ Under Budget" if budget.is_within_budget else "⚠️ Over Budget"
            st.metric("Compliance Status", compliance)

        st.markdown("---")

        chart_col1, chart_col2 = st.columns([3, 2])

        with chart_col1:
            st.markdown("#### Category Expense Allocation")
            cat_data = {
                "Category": ["Accommodations", "Dining", "Attractions", "Transit"],
                "Amount (AED)": [
                    budget.accommodation_total_aed,
                    budget.dining_total_aed,
                    budget.attractions_total_aed,
                    budget.transit_total_aed
                ]
            }
            fig = px.pie(
                cat_data,
                values="Amount (AED)",
                names="Category",
                hole=0.55,
                color="Category",
                color_discrete_map={
                    "Accommodations": "#F59E0B",
                    "Dining": "#10B981",
                    "Attractions": "#3B82F6",
                    "Transit": "#8B5CF6"
                }
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                margin=dict(t=20, b=30, l=20, r=20)
            )
            st.plotly_chart(fig, width="stretch")

        with chart_col2:
            st.markdown("#### Budget Utilization Gauge")
            gauge_fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=budget.grand_total_aed,
                number={'prefix': "AED ", 'valueformat': ",.0f"},
                delta={'reference': budget.budget_limit_aed, 'increasing': {'color': "#EF4444"}, 'decreasing': {'color': "#10B981"}},
                gauge={
                    'axis': {'range': [None, max(budget.budget_limit_aed * 1.25, budget.grand_total_aed * 1.1)]},
                    'bar': {'color': "#3B82F6"},
                    'steps': [
                        {'range': [0, budget.budget_limit_aed], 'color': "rgba(16, 185, 129, 0.2)"},
                        {'range': [budget.budget_limit_aed, max(budget.budget_limit_aed * 1.25, budget.grand_total_aed * 1.1)], 'color': "rgba(239, 68, 68, 0.2)"}
                    ],
                    'threshold': {
                        'line': {'color': "#EF4444", 'width': 3},
                        'thickness': 0.75,
                        'value': budget.budget_limit_aed
                    }
                }
            ))
            gauge_fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=30, b=30, l=30, r=30),
                height=280
            )
            st.plotly_chart(gauge_fig, width="stretch")

        # Substitution savings card
        if review.recommended_swaps:
            st.markdown("#### 🔄 Substitution Savings Directives Applied During Review")
            for swap in review.recommended_swaps:
                st.markdown(f"- 💡 {swap}")

        # Itemized cost records table
        st.markdown("#### 📋 Itemized Cost Ledger")
        if budget.itemized_records:
            records_table = [
                {
                    "Day": f"Day {r.day_number}" if r.day_number else "Trip-wide",
                    "Category": r.category.title(),
                    "Item Description": r.item_name,
                    "Cost (AED)": f"{r.cost_aed:,.2f}",
                    "Notes": r.notes or ""
                }
                for r in budget.itemized_records
            ]
            st.dataframe(records_table, width="stretch", hide_index=True)

    # -------------------------------------------------------------------------
    # TAB 4: MULTI-AGENT OBSERVABILITY TRACE
    # -------------------------------------------------------------------------
    with tab4:
        st.markdown("### 🤖 Multi-Agent Execution Trace & Quality Assurance")
        st.caption("Inspect the reasoning chain across Orchestrator, Destination, Logistics, Budget, Review, and Revision agents.")

        # Review Agent Audit Card
        ollama_target_desc = "Cloud" if (os.getenv("OLLAMA_API_KEY") or "localhost" not in os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")) else "Local"
        audit_status_badge = '<span class="status-badge status-approved">PASSED</span>' if review.passed else '<span class="status-badge status-revisions">REVISED</span>'
        st.markdown(f"""
        <div class="dxb-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <h4 style="margin: 0;">🛡️ Review Agent Audit Report (Ollama {ollama_target_desc} nemotron-3-ultra)</h4>
                {audit_status_badge}
            </div>
            <p><strong>Traveler Advisory & Audit Notes:</strong><br>
            <em>{review.audit_notes or "Itinerary satisfies all Dubai municipal, transit, and thermal constraints."}</em></p>
        </div>
        """, unsafe_allow_html=True)

        if review.violations:
            st.markdown("**Constraint Violations Identified:**")
            for v in review.violations:
                st.markdown(f"- ⚠️ {v}")

        # Agent execution timeline
        st.markdown("#### ⚡ Sequential Agent Execution Logs")
        logs = result.get("agent_logs", [])
        if logs:
            for l in logs:
                agent_name = l.get("agent", "Agent")
                node_name = l.get("node", "Node")
                status = l.get("status", "info")
                msg = l.get("message", "")
                ts = l.get("timestamp", "").split("T")[-1][:8]

                status_color = "#34D399" if status in ["success", "approved"] else "#FBBF24" if status in ["revision_applied", "revised"] else "#F87171" if status == "rejected" else "#94A3B8"

                st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.6); border-left: 3px solid {status_color}; padding: 0.5rem 0.85rem; margin-bottom: 0.45rem; border-radius: 0 6px 6px 0; font-size: 0.88rem;">
                    <span style="color: #64748B; font-family: monospace; font-size: 0.78rem;">[{ts}]</span>
                    <strong>{agent_name}</strong> ➔ <code>{node_name}</code>:
                    <span style="color: #E2E8F0;">{msg}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No agent telemetry logs recorded.")


# =============================================================================
# Ambient Dubai Skyline Silhouette (from Stitch Design)
# =============================================================================
st.markdown("""
<div class="skyline-watermark">
    <svg style="width: 100%; height: 50px; fill: #272a32;" preserveAspectRatio="none" viewBox="0 0 1200 120">
        <path d="M0,120 L0,95 L40,95 L40,80 L48,80 L48,95 L70,95 L70,110 L120,110 L120,60 L125,60 L125,10 L127,0 L129,10 L129,60 L134,60 L134,110 L180,110 L180,85 L210,85 L210,120 L300,120 L300,70 L305,65 L315,65 L320,70 L320,120 L450,120 L450,90 L480,90 L480,120 L580,120 L580,50 L588,50 L588,15 L590,5 L592,15 L592,50 L600,50 L600,120 L750,120 L750,75 L790,75 L790,120 L880,120 L880,40 L895,40 L910,120 L1020,120 L1020,80 L1060,80 L1060,120 L1200,120 Z"></path>
    </svg>
</div>
""", unsafe_allow_html=True)
