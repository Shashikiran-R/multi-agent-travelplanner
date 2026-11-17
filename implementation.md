# Phase-Wise Implementation Guide: Dubai AI Travel Planner
### Production-Grade Stateful Multi-Agent System Using LangGraph ($0.00 Free API Architecture)

---

## 1. Project Overview & Implementation Strategy

This implementation guide translates [problemstatement.md](file:///Users/shashikiran/Desktop/tripplanner/problemstatement.md), [architecture.md](file:///Users/shashikiran/Desktop/tripplanner/architecture.md), and [research.md](file:///Users/shashikiran/Desktop/tripplanner/research.md) into an actionable, step-by-step engineering roadmap.

The project is structured into **7 sequential phases**, moving from an automated real-world data download pipeline and schema modeling to graph state-machine assembly and a polished Streamlit user interface.

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    IMPLEMENTATION ROADMAP                                        |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
| Phase 1: Environment Setup & Automated Data Download Pipeline (OSM, RTA & Open-Meteo)           |
| Phase 2: Strongly Typed Pydantic V2 Schemas & Data Contracts                                     |
| Phase 3: Deterministic Domain Tools & Dubai RTA Transit Engine                                    |
| Phase 4: Agent Reasoning Prompts & Logic Modules                                                 |
| Phase 5: LangGraph State Machine Assembly (Parallel Fan-Out & Cyclic Feedback Loops)             |
| Phase 6: Streamlit Interactive UI & Multi-Agent Observability Dashboard                         |
| Phase 7: Edge Case Verification, Testing & Circuit Breaker Auditing                              |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## Phase 1: Environment Setup & Automated Data Download Pipeline

### Objective
Establish the repository directory layout, configure the Python environment with required dependencies, and implement an **automated data acquisition pipeline** that downloads real-world Dubai geospatial and transit data from OpenStreetMap and Open-Meteo, enriches it with verified AED prices, and loads it into a high-performance local SQLite database (`data/dubai_travel.db`).

### Step 1.1: Virtual Environment & Dependencies
Create `requirements.txt` with locked, compatible packages:

```txt
# Core Multi-Agent & LLM Orchestration
langgraph>=0.2.34
langchain-core>=0.3.15
langchain-google-genai>=2.0.0
langchain-openai>=0.2.0

# Schema Validation & Data Modeling
pydantic>=2.9.2

# User Interface & Visualization
streamlit>=1.39.0
streamlit-folium>=0.22.1
folium>=0.17.0
plotly>=5.24.1

# Data Download, Processing & Utilities
requests>=2.32.3
tqdm>=4.66.5
python-dotenv>=1.0.1
```

### Step 1.2: Project Directory Initialization
Initialize the project structure, including a dedicated `scripts/` directory for data download and verification:
```bash
mkdir -p data/raw data/processed scripts src/models src/graph src/agents src/tools src/data_access src/utils tests
touch src/__init__.py src/models/__init__.py src/graph/__init__.py \
      src/agents/__init__.py src/tools/__init__.py src/data_access/__init__.py src/utils/__init__.py
```

### Step 1.3: Automated Geospatial Data Downloader (`scripts/download_dubai_data.py`)
Implement an automated ingestion script that queries the free OpenStreetMap Overpass API for Dubai's bounding box (`24.95, 54.95, 25.35, 55.50`):
- **Attractions & Museums**: Downloads real nodes and ways tagged with `tourism=attraction`, `tourism=museum`, and `historic=*`.
- **Dining Venues**: Downloads authentic restaurants and cafes (`amenity=restaurant`, `amenity=cafe`, `cuisine=*`).
- **Transit Infrastructure**: Downloads all Dubai Metro Red & Green line stations (`railway=station`, `railway=subway_entrance`).
- Saves raw fetched payloads directly to `data/raw/osm_dubai_raw.json`.

```python
# Code snippet outline for scripts/download_dubai_data.py
import requests
import json
import time

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OVERPASS_QUERY = """
[out:json][timeout:35];
(
  node["tourism"="attraction"](24.95, 54.95, 25.35, 55.50);
  node["tourism"="museum"](24.95, 54.95, 25.35, 55.50);
  node["historic"](24.95, 54.95, 25.35, 55.50);
  node["amenity"="restaurant"](24.95, 54.95, 25.35, 55.50);
  node["railway"="station"]["operator"~"RTA|Dubai Metro"](24.95, 54.95, 25.35, 55.50);
);
out center tags;
"""

def download_osm_data():
    print("Downloading live Dubai geospatial data from OpenStreetMap...")
    resp = requests.post(OVERPASS_URL, data={'data': OVERPASS_QUERY})
    resp.raise_for_status()
    raw_data = resp.json()
    with open("data/raw/osm_dubai_raw.json", "w") as f:
        json.dump(raw_data, f, indent=2)
    print(f"Downloaded {len(raw_data.get('elements', []))} raw elements.")
```

### Step 1.4: Automated Climate Profile Downloader (`scripts/download_climate_data.py`)
Queries the free Open-Meteo Archive & Forecast API for Dubai coordinates (`latitude=25.2048, longitude=55.2708`):
- Downloads monthly average temperatures, maximum daily heat index, and humidity across all 12 months.
- Saves structured climate risk profiles to `data/raw/dubai_climate.json` for the Review Agent's thermal comfort auditor.

### Step 1.5: Data Normalization & Pricing Enrichment Pipeline (`scripts/enrich_and_seed.py`)
While OpenStreetMap provides real coordinates and names, it lacks ticket prices in AED and dwell times. This script:
1. **Deduplicates & Normalizes**: Cleans up names (English/Arabic), extracts exact lat/long, and assigns venues to Dubai's 4 core tourism districts (`Old Dubai & Creek`, `Downtown & DIFC`, `Marina & JBR`, `Palm Jumeirah & Jumeirah`).
2. **Enriches Ticket Pricing**: Overlays verified public admission fees in AED (e.g. Burj Khalifa: AED 179, Museum of the Future: AED 149, Dubai Frame: AED 52.50, Al Shindagha Museum: AED 50, Gold & Spice Souks: Free, Kite Beach: Free).
3. **Classifies Dining Price Bands**: Categorizes restaurants into budget (AED 25–45), midscale (AED 70–130), and fine dining (AED 250+).
4. **Appends Hotel Benchmarks**: Ingests average nightly rates for budget, midscale, and luxury accommodations across districts.
5. **Generates Processed Store**: Outputs `data/processed/dubai_places_clean.json` and `data/seed_data.json`.

### Step 1.6: Local SQLite Database Initializer (`src/data_access/sqlite_client.py`)
- Initializes `data/dubai_travel.db` with structured tables:
  - `attractions`: `id`, `name`, `category`, `district`, `lat`, `lng`, `admission_fee_aed`, `dwell_time_mins`, `crowd_level`, `opening_hours_json`.
  - `restaurants`: `id`, `name`, `cuisine`, `district`, `price_tier`, `avg_cost_aed`, `lat`, `lng`.
  - `hotel_baselines`: `district`, `tier`, `avg_rate_aed`.
  - `metro_stations`: `name`, `line`, `zone`, `lat`, `lng`.
- Automatically executes on startup if the database file is not present, loading the enriched real data.

### Step 1.7: Data Integrity & Health Check (`scripts/verify_data.py`)
Validates the database before any agents run:
- Asserts at least 50 valid attractions and 30 restaurants exist.
- Confirms all coordinates fall within the Dubai bounding box.
- Confirms zero nulls for ticket prices, dwell times, and district tags.

#### Deliverables & Acceptance Criteria for Phase 1:
- [x] Running `python scripts/download_dubai_data.py` successfully downloads live OSM records to `data/raw/`.
- [x] Running `python scripts/enrich_and_seed.py` creates `data/dubai_travel.db` populated with real Dubai places and verified AED pricing.
- [x] Running `python scripts/verify_data.py` passes all data integrity checks.
- [x] SQLite queries return instant (< 5ms) results with zero runtime API dependency.

---

## Phase 2: Strongly Typed Pydantic V2 Schemas & Data Contracts

### Objective
Implement the immutable data contracts that govern agent communication, state persistence, and client output formatting.

### Step 2.1: User Request & Constraints Schema (`src/models/request.py`)
```python
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class UserConstraints(BaseModel):
    trip_duration_days: int = Field(..., ge=1, le=7, description="Trip duration in days (1-7)")
    total_budget_aed: float = Field(..., gt=0, description="Total budget in AED (excluding flights)")
    interests: List[str] = Field(default_factory=list, description="User interest tags (e.g., culture, food, beach)")
    accommodation_tier: Literal["budget", "midscale", "luxury"] = Field("budget")
    pacing_preference: Literal["relaxed", "moderate", "fast-paced"] = Field("moderate")
    avoid_crowds: bool = Field(False)
    travel_month: Optional[int] = Field(None, ge=1, le=12, description="Month of travel (1-12) for climate check")
```

### Step 2.2: Itinerary & Activity Schemas (`src/models/itinerary.py`)
Define `AttractionItem`, `RestaurantItem`, `TransitSegment`, `ActivitySlot`, `DayPlan`, and `TripItinerary`.
- Every `ActivitySlot` includes `time_slot` (`morning`, `afternoon`, `evening`), `duration_mins`, `cost_aed`, and an optional `transit_to_next: TransitSegment`.
- Every `DayPlan` specifies `primary_district`, `theme`, and `daily_spend_aed`.

### Step 2.3: Budget & Review Models (`src/models/budget.py` & `src/models/review.py`)
- `BudgetBreakdown`: Itemized costs for accommodation, dining, admissions, transit, grand total, and remaining balance.
- `ReviewFeedback`: `passed: bool`, `violations: List[str]`, `cost_delta_aed: float`, `recommended_swaps: List[str]`, and `revision_round: int`.

#### Deliverables & Acceptance Criteria for Phase 2:
- [x] Comprehensive unit test suite in `tests/test_schemas.py` validating schema serialization and constraints.
- [x] Rejection of invalid inputs (e.g., negative budgets, duration > 7 days) via standard Pydantic `ValidationError`.

---

## Phase 3: Deterministic Domain Tools & Dubai RTA Transit Engine

### Objective
Build deterministic mathematical engines and tool utilities that provide accurate numbers (distance, transit fees, ticket costs, and heat advisories) so the LLM never hallucinates calculations.

### Step 3.1: Deterministic RTA Transit Engine (`src/tools/routing_tool.py`)
Implement the official Dubai Roads and Transport Authority calculation models:
- **Haversine Distance**: Scaled by Dubai's urban highway detour coefficient ($1.28$).
- **Silver Nol Metro Fares**:
  - Distance $\le 10\text{ km}$: Tier 1 (Within 1 zone) = **AED 3.00**
  - Distance $10 - 25\text{ km}$: Tier 2 (2 adjacent zones) = **AED 5.00**
  - Distance $> 25\text{ km}$: Tier 3 (3+ zones) = **AED 7.50**
- **Dubai Taxi Corporation (DTC) Regulated Taxi Tariff**:
  $$\text{Fare (AED)} = \max\left(12.00, \; \text{Base Fare} + (\text{Distance km} \times 2.21)\right)$$
- **Walk Feasibility Guard**: Walking is only viable if distance $\le 1.2\text{ km}$.

### Step 3.2: Places & District Clustering Tool (`src/tools/places_tool.py`)
- Interfaces directly with `data/seed_data.json` / SQLite database containing **102 attractions** and **94 restaurants** across Dubai's **5 official tourism districts**:
  1. *Cluster A*: `Old Dubai & Creek` (41 attractions, 27 restaurants — Deira, Bur Dubai, Al Fahidi, Al Seef, Gold & Spice Souks, Heritage Village).
  2. *Cluster B*: `Downtown & DIFC` (23 attractions, 16 restaurants — Burj Khalifa, Dubai Mall, Museum of the Future, Dubai Frame, DIFC Gate).
  3. *Cluster C*: `Dubai Marina & JBR` (12 attractions, 12 restaurants — The Walk, Marina Promenade, Bluewaters Island & Ain Dubai Viewing Plaza).
  4. *Cluster D*: `Palm Jumeirah & Jumeirah` (11 attractions, 25 restaurants — The View at The Palm, Palm West Beach, Souk Madinat Jumeirah, Kite Beach).
  5. *Cluster E*: `Desert & Outskirts` (15 attractions, 14 restaurants — Al Marmoom Desert Conservation, Ras Al Khor Flamingo Sanctuary, Global Village, Miracle Garden).
- Recommends day-by-day district sequences for 1 to 7 days and chooses optimal base lodging areas.

### Step 3.3: Budget Calculation & Alternative Swap Tool (`src/tools/budget_tool.py`)
- Sums: `Hotel Cost + Total Dining + Total Admissions + Total Transit Fares`.
- Computes budget variance: `cost_delta_aed = grand_total_aed - total_budget_aed`.
- **Cost-Cutting Substitution Engine**: When `cost_delta_aed > 0`, deterministically scans the itinerary and generates prioritized swaps from the verified `seed_data.json` catalog:
  1. *Priority 1 (Transit)*: Replace metered DTC taxis with Dubai Metro Silver Nol (saves ~AED 40–80/day).
  2. *Priority 2 (Paid Admissions)*: Swap expensive attractions with iconic free/low-cost alternatives in the same district:
     - `Burj Khalifa — At The Top` (AED 179) $\rightarrow$ `The Dubai Fountain & Souk Al Bahar Boardwalk` (AED 0, saves AED 179).
     - `Atlantis Aquaventure Waterpark` (AED 345) $\rightarrow$ `Palm West Beach Boardwalk & Coastal Lagoon` (AED 0, saves AED 345).
     - `Museum of the Future` (AED 149) $\rightarrow$ `Dubai Frame (Zabeel Park)` (AED 52.50, saves AED 96.50).
     - `Dubai Desert Conservation Reserve Heritage Drive` (AED 220) $\rightarrow$ `Ras Al Khor Wildlife Sanctuary & Flamingo Hide` (AED 0, saves AED 220).
     - `The Lost Chambers Aquarium` (AED 135) $\rightarrow$ `Souk Madinat Jumeirah Traditional Waterways` (AED 0, saves AED 135).
     - `Ski Dubai Snow Park` (AED 220) $\rightarrow$ `Bluewaters Island & Ain Dubai Viewing Plaza` (AED 0, saves AED 220).
  3. *Priority 3 (Dining)*: Downgrade fine dining (AED 280+) to authentic midscale/street food (AED 35–75, saves AED 150–200/meal).
  4. *Priority 4 (Accommodation)*: Suggest downgrading hotel district (e.g. Downtown midscale AED 650/night to Old Dubai/Deira budget AED 210/night, saving ~AED 440/night).

### Step 3.4: Deterministic Constraint Auditor (`src/tools/validation_tool.py`)
- Audits schedules against hard rules:
  - Budget cap: `grand_total_aed <= total_budget_aed`.
  - Max activities per day: $\le 4$ activities ($\le 3$ for relaxed pacing) to prevent exhaustion.
  - Geographic coherence: Prevents mixing incompatible distant districts on the same day (e.g. `Old Dubai & Creek` with `Dubai Marina & JBR` or `Palm Jumeirah & Jumeirah`).
  - Transit feasibility: Flags any transit segment with `duration_mins > 60`.
  - Duplicate places check: Flags duplicate scheduling of the same attraction across multiple days.
  - Thermal Safety: Audits travel month against `seed_data.json` climate profiles (`climate_profiles`). Flags outdoor afternoon activities (11:30 AM to 04:30 PM) during summer months (`travel_month in [6, 7, 8, 9]`) where average highs exceed 41°C and heat indices exceed 48°C.

#### Deliverables & Acceptance Criteria for Phase 3:
- [x] Unit tests in `tests/test_tools.py` confirming exact RTA fare calculations against official tariffs.
- [x] The swap engine correctly reduces projected expenses below the specified budget threshold.

---

## Phase 4: Agent Reasoning Prompts & Node Logics

### Objective
Implement domain logic and specialized prompt templates for each of the 5 agents, powered by a hybrid multi-LLM architecture:
- **Orchestrator, Research (Destination), Logistics, Budget**: Powered by **Groq** (`openai/gpt-oss-120b` / `oss-120b`).
- **Review & Quality Assurance Agent**: Powered by **Ollama** (`nemotron-3-ultra` via `get_ollama_llm()`), supporting both local execution (`http://localhost:11434`) and remote/cloud endpoints configured via `OLLAMA_BASE_URL` and `OLLAMA_API_KEY` in `.env`.
- **100% Zero-Cost Fallback**: All agents automatically fall back to deterministic local processing using Phase 3 engines and SQLite data when services are offline or API keys are omitted ($0.00 cost).

### Step 4.1: Orchestrator Agent (`src/agents/orchestrator.py`)
- Powered by **Groq** (`openai/gpt-oss-120b` via `get_groq_llm()`).
- Uses structured output parsing to transform free-text user prompts into `UserConstraints` (with regex fallback).
- **Rejection Guardrail Grounded in Baseline Data**:
  - Minimum lodging baseline in `seed_data.json`: AED 200/night (`Desert & Outskirts`) or AED 210/night (`Old Dubai & Creek` budget).
  - Minimum food baseline: AED 70/day (2 meals @ AED 35 budget tier).
  - Minimum transit: AED 10/day (RTA Metro Silver Nol).
  - Absolute minimum threshold for $D$ days: $(D - 1) \times 200 + D \times 80\text{ AED}$.
  - If `total_budget_aed` falls below this minimum threshold (e.g. AED 300 for 4 days), the Orchestrator immediately aborts graph execution and returns an explanatory refusal citing real Dubai hotel rates (AED 210/night in Deira/Old Dubai) and daily living costs.
- Generates polished trip executive summaries via Groq upon itinerary finalization.

### Step 4.2: Destination Research Agent (`src/agents/destination.py`)
- Powered by **Groq** (`openai/gpt-oss-120b` via `get_groq_llm()`).
- Formulates queries against `places_tool.py` filtered by user interests (e.g. `culture`, `heritage`, `beach`, `adventure`, `views`, `shopping`) across the 102 attractions and 94 restaurants in `seed_data.json`.
- **Summer Climate Adaptation Guard**:
  - If `travel_month in [6, 7, 8, 9]`, enforces selection of indoor air-conditioned venues (`is_indoor == True` in `seed_data.json`, 33 verified venues like Dubai Mall, Museum of the Future, Green Planet, Ski Dubai, Lost Chambers) for midday/afternoon slots.
  - Outdoor venues (beaches, souks, desert drives) are strictly assigned to morning (< 11:30 AM) or evening (> 16:30 PM).
- Selects dining options matching user price tier from 49 authentic culinary cuisines in `seed_data.json` (e.g. Authentic Emirati, Persian, Lebanese, South Indian Seafood, Anatolian Turkish).
- Generates local insider concierge highlights (`concierge_notes`) via Groq covering signature dishes, cultural etiquette, and photography timing tips.

### Step 4.3: Logistics Agent (`src/agents/logistics.py`)
- Powered by **Groq** (`openai/gpt-oss-120b` via `get_groq_llm()`).
- Assigns candidate venues into daily geographical clusters across the 5 official districts:
  - Day 1: Old Dubai & Creek (Culture & Souks)
  - Day 2: Downtown & DIFC (Modern Architecture & Skylines)
  - Day 3: Dubai Marina & JBR (Coastal Promenade & Bluewaters)
  - Day 4: Palm Jumeirah & Jumeirah (Island Panoramas & Souk Madinat)
  - Day 5: Desert & Outskirts (Arabian Conservation & Flamingos)
  - Day 6: Downtown & Modern Arts (Contemporary Culture & Fine Dining)
  - Day 7: Old Dubai & Creekside Farewell (Abra Voyage & Heritage Museums)
- Selects optimal base lodging neighborhood using the 15 hotel baseline options in `seed_data.json`:
  - Budget $\rightarrow$ `Old Dubai & Creek` (Avg AED 210/night; e.g. Ibis Deira City Centre, Premier Inn Al Jaddaf).
  - Midscale $\rightarrow$ `Downtown & DIFC` (Avg AED 650/night; e.g. Vida Downtown, Millennium Central Downtown).
  - Luxury $\rightarrow$ `Dubai Marina & JBR` (Avg AED 1,750/night; e.g. The Ritz-Carlton JBR, Address Beach Resort) or `Palm Jumeirah & Jumeirah` (Avg AED 2,200/night; e.g. Atlantis The Royal).
- Constructs chronological sequences (`morning`, `afternoon`, `evening`) and generates deterministic `TransitSegment` records using `RTATransitEngine`:
  - Identifies walkable transitions ($\le 1.2\text{ km}$, AED 0.00).
  - Identifies Traditional Abra creek crossings between Bur Dubai and Deira (AED 2.00).
  - Routes longer urban legs via Dubai Metro Silver Nol (AED 3.00, 5.00, 7.50) or DTC Metered Taxi.
- Refines daily themes and formulates urban mobility briefings via Groq.

### Step 4.4: Budget Agent (`src/agents/budget.py`)
- Powered by **Groq** (`openai/gpt-oss-120b` via `get_groq_llm()`).
- Formats the complete itemized cost ledger in AED across Accommodations, Dining, Attractions, and Transit using exact figures from `seed_data.json` and `RTATransitEngine`.
- Computes `cost_delta_aed = grand_total_aed - total_budget_aed`.
- When `cost_delta_aed > 0`, invokes `BudgetTool.generate_cost_cutting_swaps()` to assemble prioritized substitutions to eliminate the deficit.
- Formulates executive financial assessment narratives and substitution rationales in AED via Groq.

### Step 4.5: Review Agent (`src/agents/review.py`)
- Powered by **Ollama** (`nemotron-3-ultra` via `get_ollama_llm()`).
- Executes the deterministic audit suite via `ValidationTool.audit_itinerary()`:
  - Validates budget ceiling (`grand_total_aed <= total_budget_aed`).
  - Enforces max activity density ($\le 4$ activities/day, $\le 3$ for relaxed).
  - Validates single-day district isolation (zero cross-city jumps between incompatible districts).
  - Audits transit feasibility ($\le 60$ mins transit duration).
  - Checks for duplicate attraction scheduling.
  - Enforces thermal safety for extreme summer months (June–September) using `climate_profiles`.
- Uses Ollama (`nemotron-3-ultra`) to generate comprehensive Quality Assurance commentary and compliance audits (`audit_notes`), explaining why violations represent risks in Dubai and endorsing corrective substitutions.
- Emits a structured `ReviewFeedback` report detailing `passed: bool`, `violations: List[str]`, `structured_violations: List[ViolationItem]`, `cost_delta_aed: float`, and `recommended_swaps: List[str]`.

#### Deliverables & Acceptance Criteria for Phase 4:
- [x] Orchestrator, Research, Logistics, and Budget agents integrated with **Groq** (`ChatGroq`).
- [x] Review Agent integrated with **Ollama** (`nemotron-3-ultra` via `ChatOllama`).
- [x] 100% deterministic fallback operational for all 5 agents when running offline or without services.
- [x] Comprehensive test suite in `tests/test_agents.py` passing with 46+ tests covering schema, tools, and agent reasoning.

---

## Phase 5: LangGraph State Machine Assembly

### Objective
Assemble the agents into a stateful, cyclic computational graph using LangGraph's `StateGraph`, implementing concurrent fan-out, fan-in join, bounded feedback loops, and early rejection circuit breakers.

### Step 5.1: State Definition (`src/graph/state.py`)
```python
from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

class PlannerState(TypedDict):
    raw_prompt: str
    constraints: Optional[Dict[str, Any]]
    candidate_attractions: List[Dict[str, Any]]
    candidate_restaurants: List[Dict[str, Any]]
    daily_schedules: List[Dict[str, Any]]
    recommended_hotel_area: str
    hotel_tier: str
    climate_profile: Optional[Dict[str, Any]]
    budget_breakdown: Optional[Dict[str, Any]]
    review_feedback: Optional[Dict[str, Any]]
    revision_count: int
    agent_logs: Annotated[List[Dict[str, Any]], operator.add]
    final_itinerary: Optional[Dict[str, Any]]
    is_rejected: bool
    rejection_reason: Optional[str]
```

### Step 5.2: Node Implementation (`src/graph/nodes.py`)
Wrap agent functions into LangGraph nodes that accept `state: PlannerState` and return state updates:
- `orchestrator_parse_node`: Parses prompt into `UserConstraints` and runs early rejection guardrail against minimum Dubai baselines.
- `destination_node`: Queries `places_tool.py` for candidate attractions & restaurants, applying summer climate filters when applicable.
- `logistics_node`: Partitions venues across the 5 districts and generates chronological slots with `RTATransitEngine` segments.
- `join_node`: Combines destination choices and logistics routing into complete draft day plans.
- `budget_node`: Invokes `budget_tool.py` to calculate itemized costs and variance.
- `review_node`: Invokes `validation_tool.py` to audit draft itinerary.
- `revision_node`: Applies top recommended substitutions via `BudgetTool.apply_swap_to_itinerary()`.
- `finalize_node`: Assembles the final validated `TripItinerary` object.
- `fallback_finalize_node`: When 3 revision cycles are reached, finalizes best-effort itinerary with explicit advisory notes.

### Step 5.3: Conditional Edge Router (`src/graph/edges.py`)
```python
def route_after_parse(state: PlannerState) -> str:
    """Early exit circuit breaker if budget is mathematically impossible."""
    if state.get("is_rejected", False):
        return "finalize_rejection"
    return "destination_research"

def should_continue(state: PlannerState) -> str:
    """Decides whether to finalize, revise, or fallback after review audit."""
    review = state.get("review_feedback", {})
    count = state.get("revision_count", 0)
    
    if review.get("passed", False):
        return "finalize"
    if count >= 3:
        return "fallback_finalize"
    return "revise"
```

### Step 5.4: Graph Construction & Compilation (`src/graph/workflow.py`)
Wire nodes, parallel edges, conditional edges, and attach `MemorySaver`:
```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def create_planner_graph():
    graph = StateGraph(PlannerState)
    
    # Register nodes
    graph.add_node("parse_request", orchestrator_parse_node)
    graph.add_node("destination_research", destination_node)
    graph.add_node("logistics_planning", logistics_node)
    graph.add_node("join_findings", join_node)
    graph.add_node("calculate_budget", budget_node)
    graph.add_node("review_itinerary", review_node)
    graph.add_node("apply_revisions", revision_node)
    graph.add_node("finalize_itinerary", finalize_node)
    graph.add_node("fallback_finalize", fallback_finalize_node)
    graph.add_node("finalize_rejection", finalize_rejection_node)
    
    # Connect edges
    graph.set_entry_point("parse_request")
    graph.add_conditional_edges(
        "parse_request",
        route_after_parse,
        {"finalize_rejection": "finalize_rejection", "destination_research": "destination_research"}
    )
    graph.add_edge("destination_research", "logistics_planning")
    graph.add_edge("logistics_planning", "join_findings")
    graph.add_edge("join_findings", "calculate_budget")
    graph.add_edge("calculate_budget", "review_itinerary")
    
    graph.add_conditional_edges(
        "review_itinerary",
        should_continue,
        {"finalize": "finalize_itinerary", "revise": "apply_revisions", "fallback_finalize": "fallback_finalize"}
    )
    graph.add_edge("apply_revisions", "calculate_budget")
    graph.add_edge("finalize_itinerary", END)
    graph.add_edge("fallback_finalize", END)
    graph.add_edge("finalize_rejection", END)
    
    return graph.compile(checkpointer=MemorySaver())
```

#### Deliverables & Acceptance Criteria for Phase 5:
- [x] Execution trace proves correct node sequencing and state persistence.
- [x] Bounded revision cycle: Injected over-budget condition triggers the revision loop and terminates within 3 cycles.
- [x] Circuit breaker: Impossible budget requests trigger `finalize_rejection` without running research loops.

---

## Phase 6: Streamlit Interactive UI & Observability Dashboard

### Objective
Create an intuitive, modern Streamlit user interface (`app.py`) allowing users to configure travel parameters, watch agent reasoning in real time, and explore the finalized itinerary across timelines, interactive maps, and budget charts.

### Step 6.1: Sidebar Configuration Panel
- **Natural Language Prompt Area**: Free-text trip prompt with quick preset buttons grounded in `seed_data.json`:
  - *"4-Day Cultural & Heritage Explorer"* (Old Dubai & Downtown, Budget: AED 2,800, Tier: Budget)
  - *"3-Day Modern Icons & Beachfront"* (Downtown & Marina/JBR, Budget: AED 4,500, Tier: Midscale)
  - *"5-Day Complete Dubai & Desert Grand Tour"* (All 5 districts, Budget: AED 8,500, Tier: Luxury)
  - *"2-Day Stopover Essentials"* (Downtown & Creek, Budget: AED 1,500, Tier: Budget)
- **Parameter Controls**:
  - Trip Duration slider (1–7 days).
  - Total Budget input in AED.
  - Travel Month selector (1–12): Dynamically displays an Open-Meteo Climate Advisory card based on `seed_data.json` (e.g. Month 7: *"☀️ Extreme Summer Warning: Average High 41.3°C, Heat Index 48.7°C. Afternoon outdoor activities will automatically be routed to indoor air-conditioned venues."*).
  - Interest multi-select tags (`culture`, `beach`, `adventure`, `views`, `shopping`, `nature`, `free`).
  - Accommodation Tier selector showing real baseline rates (Budget ~AED 210/night in Deira, Midscale ~AED 650/night in Downtown, Luxury ~AED 1,750/night in Marina).
- "Generate Dubai Itinerary" action button.

### Step 6.2: Tabbed Output Dashboard
- **Tab 1: Itinerary Timeline**: Chronological cards for Day 1..N showing:
  - Timing badges (`morning`, `afternoon`, `evening`).
  - Venue name, category icon, and district color tag (5 distinct colors for 5 districts).
  - Dwell time badges (from `recommended_duration_mins`).
  - Admission fee in AED (or highlighted "FREE" badge).
  - Transit step cards between consecutive stops (specifying Dubai Metro Silver Nol tier fare, DTC metered taxi fare, or Traditional Abra creek crossing).
- **Tab 2: Interactive Map**: Built using `folium` and `streamlit-folium`:
  - Pins for all scheduled venues color-coded by day.
  - Interactive popup cards showing photo/description, dwell time, and cost.
  - Overlay layer showing the 35 Dubai Metro Red and Green line stations from `seed_data.json`.
  - Polyline transit routes connecting daily stops.
- **Tab 3: Budget Breakdown**:
  - Plotly donut chart comparing expenditure across Accommodations, Dining, Attractions, and Transit.
  - Remaining balance gauge (showing budget buffer or deficit).
  - Detailed itemized cost ledger table.
  - Substitution savings summary card detailing any cost-cutting swaps applied during review.
- **Tab 4: Agent Reasoning & Trace Inspector**:
  - Step-by-step logs from Orchestrator $\rightarrow$ Destination $\rightarrow$ Logistics $\rightarrow$ Budget $\rightarrow$ Review $\rightarrow$ Revision loops.
  - Review Agent audit report: pass/fail status, violation badges, and swap directives.

### Step 6.3: Telemetry Bar
- Execution status badge (`APPROVED`, `APPROVED WITH REVISIONS`, or `REJECTED`).
- Total Execution Latency (seconds).
- Total Revision Cycles count.
- Data Source Attribution (Curated SQLite + OpenStreetMap + Open-Meteo + RTA Math Model).
- Operational API Cost Display: **$0.00**.

#### Deliverables & Acceptance Criteria for Phase 6:
- [x] `streamlit run app.py` launches cleanly without deprecation warnings.
- [x] All interactive elements (map pins, timeline cards, plotly charts, climate cards) render smoothly.

---

## Phase 7: Edge Case Verification, Testing & Circuit Breaker Auditing

### Objective
Validate system stability across challenging edge cases, extreme budgets, climate anomalies, and network failures using concrete test cases grounded in `data/seed_data.json`.

### Step 7.1: Automated Integration Test Suite (`tests/test_scenarios.py`)
Implement end-to-end integration tests covering:
- **Scenario A (Standard Cultural Trip)**:
  - Input: 4 Days, AED 5,000, January (Month 1), Cultural interest, Budget accommodation.
  - Expected: Assigns Old Dubai & Downtown districts, passes on Round 0 with zero critical violations.
- **Scenario B (Strict Low Budget with Luxury Swaps)**:
  - Input: 3 Days, AED 1,800, requesting Burj Khalifa (AED 179) and taxis.
  - Expected: Initial draft exceeds budget $\rightarrow$ Review Agent triggers revision $\rightarrow$ Revision Node swaps Burj Khalifa to Dubai Fountain (saves AED 179) and Taxis to Dubai Metro $\rightarrow$ Passes on Round 1 with total spend $\le$ AED 1,800.
- **Scenario C (Extreme Summer Midday Heat Test)**:
  - Input: 3 Days, AED 4,000, July travel (Month 7, avg high 41.3°C).
  - Expected: Thermal Safety check flags any outdoor afternoon activities $\rightarrow$ Itinerary selects indoor air-conditioned venues (`is_indoor == True` in `seed_data.json`, e.g. Museum of the Future, Dubai Mall, Green Planet) for 11:30 AM to 04:30 PM slots.
- **Scenario D (Impossible Budget Circuit Breaker)**:
  - Input: 4 Days, AED 300 total budget.
  - Expected: Below minimum baseline of $(4-1)\times 200 + 4\times 80 = \text{AED } 920$. Orchestrator rejects immediately with explanatory guidance citing AED 210/night lodging baseline in Old Dubai.
- **Scenario E (Zero-Cost Deterministic Resilience)**:
  - Input: Disconnected network simulation.
  - Expected: Entire generation runs locally against SQLite and mathematical transit models in < 25ms with zero external HTTP requests.

#### Deliverables & Acceptance Criteria for Phase 7:
- [ ] All test scenarios pass with clear assertions in `tests/test_scenarios.py`.
- [ ] Zero unhandled exceptions or crashes across all test runs.

## Summary of File Implementation Order

| Step # | File to Create / Modify | Phase | Purpose |
| :---: | :--- | :---: | :--- |
| **1** | `requirements.txt` | Phase 1 | Python dependencies (LangGraph, Pydantic, Streamlit, Requests) |
| **2** | `scripts/download_dubai_data.py` | Phase 1 | Automated downloader for OpenStreetMap attractions, dining & transit |
| **3** | `scripts/download_climate_data.py` | Phase 1 | Automated downloader for Open-Meteo Dubai climate profiles |
| **4** | `scripts/enrich_and_seed.py` | Phase 1 | Pricing enrichment pipeline & seed JSON generator |
| **5** | `src/data_access/sqlite_client.py` | Phase 1 | SQLite schema & auto-seed loader (`data/dubai_travel.db`) |
| **6** | `scripts/verify_data.py` | Phase 1 | Data integrity and coverage verification script |
| **7** | `src/models/request.py` | Phase 2 | UserConstraints schema |
| **8** | `src/models/itinerary.py` | Phase 2 | DayPlan, ActivitySlot, TripItinerary |
| **9** | `src/models/budget.py` & `review.py` | Phase 2 | BudgetBreakdown & ReviewFeedback |
| **10** | `src/tools/routing_tool.py` | Phase 3 | Deterministic RTA Nol & DTC Taxi engine |
| **11** | `src/tools/places_tool.py` | Phase 3 | District clustering & place lookup |
| **12** | `src/tools/budget_tool.py` | Phase 3 | Itemized calculator & alternative swap finder |
| **13** | `src/tools/validation_tool.py` | Phase 3 | Constraint & thermal comfort auditor |
| **14** | `src/agents/orchestrator.py` | Phase 4 | Prompt & structured extractor |
| **15** | `src/agents/destination.py` | Phase 4 | Destination research agent logic |
| **16** | `src/agents/logistics.py` | Phase 4 | Route clustering & hotel selector |
| **17** | `src/agents/budget.py` | Phase 4 | Budget analysis & overflow handler |
| **18** | `src/agents/review.py` | Phase 4 | QA audit report generator |
| **19** | `src/graph/state.py` | Phase 5 | LangGraph PlannerState definition |
| **20** | `src/graph/nodes.py` | Phase 5 | Node wrapper functions |
| **21** | `src/graph/edges.py` | Phase 5 | Conditional edge router (`should_continue`) |
| **22** | `src/graph/workflow.py` | Phase 5 | StateGraph builder & compiler |
| **23** | `app.py` | Phase 6 | Interactive Streamlit application |
| **24** | `tests/test_scenarios.py` | Phase 7 | Comprehensive edge case test suite |
