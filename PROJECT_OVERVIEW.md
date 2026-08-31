# Spotify Insights — Project Overview

## 🎯 Project Goal
Build a **personal music analytics dashboard** that transforms raw Spotify listening data into actionable insights using **data visualization, machine learning, and reflective analytics**.

---

## 📊 Core Vision

**"Know your music taste better."**

- 📈 **Data Exploration**: Visualize your listening patterns (streams, hours, platforms, artists, tracks)
- 🎭 **Mood Discovery**: Understand emotional patterns through audio features (valence, energy, danceability)
- 🔍 **Artist Insights**: Loyalty, half-life, obsessions, and discovery timelines
- 🏆 **Milestones**: Streaks, top days, "firsts," and nostalgic flashbacks
- 🎬 **Session Clustering**: Automatically segment listening sessions (30-min gap) and find patterns
- 🤖 **Smart Recommendations**: Content-based suggestions with explainability ("why this song?")
- 🔮 **Predictive Simulator**: Markov-chain next-play prediction by artist and time-of-day

---

## 🏗️ Architecture

### Tech Stack

**Frontend:**
- **React 19** + **TypeScript** (Vite)
- **Material UI (MUI)** + **MUI X Charts** (data visualization)
- **Zustand** (state management)
- **React Router v6** (client-side routing)
- **Axios** (HTTP client)

**Backend:**
- **FastAPI** (Python async web framework)
- **PostgreSQL** (data persistence)
- **Spotify API** (source of truth)
- **Scikit-learn** (clustering, recommendations)

**DevOps & Tooling:**
- **Vite** (bundling & dev server)
- **ESLint + TypeScript** (code quality)
- **ts-node** (script execution)

### Directory Structure

```
spotify-insights/
├── apps/
│   ├── web/                          # React frontend (Vite)
│   │   ├── src/
│   │   │   ├── api/
│   │   │   │   └── client.ts          # Typed API client (axios)
│   │   │   ├── components/
│   │   │   │   ├── StatCard.tsx       # Reusable stat card
│   │   │   │   └── ErrorBanner.tsx    # Global error feedback
│   │   │   ├── layout/
│   │   │   │   └── AppLayout.tsx      # Left drawer nav + AppBar
│   │   │   ├── pages/
│   │   │   │   ├── Overview.tsx       # Phase 1: Main dashboard
│   │   │   │   ├── Moods.tsx          # Phase 2: Audio features
│   │   │   │   ├── Discovery.tsx      # Phase 3: Artists & insights
│   │   │   │   ├── Milestones.tsx     # Phase 4: Achievements
│   │   │   │   ├── Sessions.tsx       # Phase 5: Clustering
│   │   │   │   ├── Recommendations.tsx # Phase 6: ML reco (⚗️)
│   │   │   │   ├── Simulator.tsx      # Phase 7: Markov simulator (⚗️)
│   │   │   │   └── NotFound.tsx
│   │   │   ├── store/
│   │   │   │   └── app.ts             # Zustand: global state
│   │   │   ├── theme/
│   │   │   │   └── AppThemeProvider.tsx # Dark theme, MUI palette
│   │   │   ├── utils/
│   │   │   │   └── format.ts          # Number, duration formatting
│   │   │   ├── App.tsx                # Routes
│   │   │   └── main.tsx               # Entry point
│   │   ├── scripts/
│   │   │   └── writePhaseDoc.ts       # Auto-generates phase docs
│   │   ├── vite.config.ts
│   │   ├── tsconfig.json
│   │   ├── package.json
│   │   └── spotify-insights.env.example  # Env template
│   │
│   └── api/                           # FastAPI backend (Python)
│       ├── main.py                    # App entry point
│       ├── endpoints/
│       │   ├── stats.py               # /api/stats/* (overview, platforms, time)
│       │   ├── top.py                 # /api/top/* (artists, tracks)
│       │   ├── mood.py                # /api/mood/* (audio features)
│       │   ├── discovery.py           # /api/discovery/* (loyalty, obsessions)
│       │   ├── milestones.py          # /api/milestones/* (streaks, flashbacks)
│       │   ├── sessions.py            # /api/sessions/* (clustering)
│       │   ├── reco.py                # /api/reco/* (recommendations)
│       │   └── simulate.py            # /api/simulate/* (Markov)
│       ├── jobs/
│       │   ├── enrich_audio_features.py # Fetch audio features from Spotify
│       │   ├── sessionize.py           # 30-min gap sessionization
│       │   └── cluster_sessions.py     # k-means/GMM clustering
│       ├── models/
│       │   ├── schemas.py             # Pydantic DTOs
│       │   └── db.py                  # SQLAlchemy ORM models
│       ├── services/
│       │   ├── spotify_service.py     # Spotify API wrapper
│       │   ├── analytics.py           # Aggregation & stats
│       │   └── recommender.py         # Content-based scorer
│       ├── notebooks/
│       │   └── recommender_eval.ipynb # Offline evaluation (optional)
│       ├── requirements.txt           # Python dependencies
│       ├── spotify-insights.env.example  # Env template
│       └── README.md
│
└── documentation/                     # Phase reports (auto-generated)
    ├── 20260430_120000_phase_0_foundations.md
    ├── 20260430_120000_phase_1_basics.md
    ├── 20260430_120000_phase_2_moods.md
    └── ... (one per phase)
```

---

## 🎨 Design System

### Color Palette

| Name | Hex | Usage |
|------|-----|-------|
| **Dark Purple** | `#1c0b19` | Darkest backgrounds, borders |
| **Federal Blue** | `#140d4f` | Dark accents, secondary text |
| **Keppel** | `#4ea699` | Secondary/tertiary data series |
| **Emerald** | `#2dd881` | Primary accent, main data |
| **Aquamarine** | `#6fedb7` | Highlights, secondary series |

### Typography

- **Font Family**: [Inter Variable](https://rsms.me/inter/) (web-optimized)
- **Theme**: Dark mode by default
- **Responsive**: MUI typography scales with breakpoints

### Component Patterns

1. **Stat Cards**: KPIs with icons, values, and optional trends
2. **Line Charts**: Time-series with range selectors (All/12M/6M/3M)
3. **Bar Charts**: Top rankings (horizontal layout for long labels)
4. **Pie/Doughnut**: Platform or category distribution
5. **Tables**: Detailed rankings with sortable columns
6. **Chips**: Tag-based filters and categorization
7. **Tabs**: Multi-view sections (e.g., different time windows)

---

## 📋 Development Phases

### Phase 0: Foundations ✅
- Vite + React + TypeScript scaffold
- MUI theme & AppLayout with drawer nav
- 7 blank pages (Overview, Moods, Discovery, etc.)
- Axios client + Zustand store
- Auto-doc tooling (`writePhaseDoc.ts`)

### Phase 1: Basics (Overview Dashboard)
- **Stat Cards**: total streams, total hours, unique artists, tracks, albums
- **Line Chart**: monthly streams/hours
- **Pie Chart**: platform distribution (web, mobile, desktop)
- **Bar Charts**: top 10 artists, top 10 tracks
- **Loading states** + error handling

### Phase 2: Moods (Audio Features)
- **Valence, Energy, Danceability** metrics over time
- **Time Window Selector**: 7d / 30d / 90d
- **Context Comparisons**: weekday vs weekend, platform comparisons
- **Mood Ring**: circular progress for latest window
- **Accessibility**: labeled controls, color + text cues

### Phase 3: Discovery (Artist Insights)
- **Discovery Timeline**: new artists discovered per month
- **Loyalty Table**: artist, return probability %, half-life (days)
- **Obsessions Bar Chart**: top period-specific obsessions
- **Reflective Cards**: short KPI insights with context

### Phase 4: Milestones (Achievements)
- **Grouped List**: milestones by year
- **Type Badges**: streak, top day, first listen, etc.
- **Flashback Widget**: date picker → card with listening context
- **Export**: copy summary button

### Phase 5: Sessions (Clustering)
- **Session Definition**: 30-min gap threshold, 3–7 clusters via silhouette
- **Cluster Profiles**: centroid features (valence, energy, etc.)
- **Recent Sessions Table**: label, duration, skip ratio, start time
- **Cluster Share Timeline**: stacked area chart (optional)

### Phase 6: Recommendations (⚗️ Experimental)
- **Content-Based Scorer**: cosine similarity on normalized audio features
- **Preference Vector**: weighted combination of your listening patterns
- **Recency Weighting**: recent listens boost score
- **MMR Diversification**: avoid clustering similar recommendations
- **"Why This" Tooltips**: explain score drivers
- **CSV Export**: recommended songs + scores

### Phase 7: Simulator (⚗️ Experimental)
- **Markov Chains**: artist-level transition probabilities
- **Hour-of-Day Buckets**: predict next plays by time context
- **Seed Artist**: condition on artist you want to start from
- **HMM Optional**: mood-state sequences (experimental)
- **Probability Bars**: show predicted play order + confidence

---

## 🔗 API Endpoints

### Stats & Overview
```
GET /api/stats/overview
  → { total_streams, total_hours, unique_artists, unique_tracks, unique_albums }

GET /api/top/artists?limit=10
  → [{ artist, streams, hours }]

GET /api/top/tracks?limit=10
  → [{ track, artist, streams, platform }]

GET /api/time/monthly
  → [{ month, streams, hours }]

GET /api/platforms
  → { web: %, mobile: %, desktop: % }
```

### Moods (Audio Features)
```
GET /api/mood/summary?window=7d|30d|90d
  → { avg_valence, avg_energy, avg_danceability, stddev }

GET /api/mood/contexts
  → { weekday: {...}, weekend: {...}, mobile: {...}, web: {...} }

GET /api/mood/monthly
  → [{ month, avg_valence, avg_energy, avg_danceability }]
```

### Discovery & Insights
```
GET /api/discovery/timeline
  → [{ month, new_artists_count }]

GET /api/loyalty
  → [{ artist, return_probability %, half_life_days }]

GET /api/obsessions
  → [{ artist, period_share % }]

GET /api/reflect
  → { insights: [...], kpis: {...} }
```

### Milestones
```
GET /api/milestones/list
  → [{ date, type (streak|top_day|first), context }]

GET /api/milestones/flashback?date=2024-12-25
  → { date, plays: [...], top_artist, mood }
```

### Sessions & Clustering
```
GET /api/sessions/clusters
  → [{ cluster_id, name, size, centroid: {...} }]

GET /api/sessions/centroids
  → [{ cluster, valence, energy, danceability, tempo }]

GET /api/sessions/assignments?limit=100
  → [{ session_id, cluster_label, duration_min, skip_ratio, start_time }]
```

### Recommendations (⚗️)
```
GET /api/reco?top_k=20&target_mood=optional
  → [{ track, artist, score, why: { top_features: [...] } }]
```

### Simulator (⚗️)
```
GET /api/simulate/next?n=20&seed=artist_id&hour=optional
  → { sequence: [{ artist, probability }], seed_context }
```

---

## 🚀 Local Development

### Prerequisites
- Node.js 18+ (frontend)
- Python 3.10+ (backend)
- Spotify Developer credentials (Client ID/Secret)
- PostgreSQL (for persistence)

### Setup

**Frontend:**
```bash
cd apps/web
npm install
cp spotify-insights.env.example .env.local
# Add VITE_API_BASE_URL=http://localhost:8000
npm run dev           # Start dev server (Vite)
npm run build:check   # Type-check + build
npm run lint          # ESLint
```

**Backend:**
```bash
cd apps/api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp spotify-insights.env.example .env
# Add SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, DATABASE_URL
python main.py        # Start FastAPI (uvicorn)
```

### Documentation Generation

After completing a phase, auto-generate phase docs:
```bash
cd apps/web
npm run doc:phase
# Creates: documentation/<YYYYMMDD_HHMMSS>_phase_<number>_<name>.md
```

---

## ✅ Quality Gates (Per Phase)

### User Experience
- ✅ Intuitive left-drawer navigation
- ✅ Consistent card & chart styling
- ✅ Responsive layout (MUI Grid breakpoints)
- ✅ Loading skeletons & error banners

### Accessibility
- ✅ Keyboard navigation (Tab, Enter, arrow keys)
- ✅ ARIA labels for charts & controls
- ✅ Color not sole indicator (text + icons)
- ✅ Skip-to-content link
- ✅ Screen reader announcements for route changes

### Performance
- ✅ Memoized derived series (no re-renders)
- ✅ Lazy-loaded chart data
- ✅ Axios timeouts & retry (5s default)
- ✅ API pagination for top lists

### Security
- ✅ No secrets in frontend code
- ✅ Env variables for API base URL only
- ✅ CORS configured on backend
- ✅ Rate limiting (optional)
- ✅ Minimal data exposure

### Testing (Future)
- Unit tests for utilities & formatters
- Integration tests for API client
- E2E smoke tests (main flows)
- Lighthouse A11y & performance audits

---

## 🎬 Current Status

- **Latest Commit**: `7d16c08 fetch song info + spotify data of other users`
- **Git Status**: 
  - ✏️ Modified: `apps/web/spotify-insights.env.example`
  - ✏️ Modified: `apps/web/src/api/client.ts`
  - ✏️ Modified: `apps/web/vite.config.ts`
  - 📄 New: `documentation/database_schema_diagram.md`
  - 📄 New: `documentation/multi_user_data_storage_design.md`
  - 📄 New: `documentation/multi_user_summary.md`

- **Next Focus**: Continue with Phase implementation or multi-user feature expansion

---

## 📚 Documentation

Phase reports (auto-generated per CLAUDE.md):
- `documentation/<timestamp>_phase_0_foundations.md`
- `documentation/<timestamp>_phase_1_basics.md`
- `documentation/<timestamp>_phase_2_moods.md`
- ... (one per phase)

Each report contains:
- **Date & Status** (Completed/Partial/Blocked)
- **Overview** of what was added
- **Files Created/Modified**
- **Checklist** (UX, a11y, performance, security)
- **What Was Implemented** (purpose, features, flow, usage)
- **Next Steps** (concrete tasks)
- **Conclusion** (1–3 sentences)

---

## 🎓 Key Design Principles

### 1. **Personal Analytics First**
Know *your* music taste before power features. Start with overview, drill down into insights.

### 2. **Progressive Disclosure**
Basic features on main tabs, advanced (⚗️) tucked away (Recommendations, Simulator).

### 3. **Explainability**
Show "why this?" for recommendations; include context for insights.

### 4. **Performance > Perfection**
Memoize, pagination, lazy load. No over-engineering for hypothetical use cases.

### 5. **Accessibility by Default**
Keyboard nav, ARIA labels, color + text, skip links. Not an afterthought.

### 6. **Minimal Data**
Fetch only what's needed; aggregate on backend. Frontend stays lightweight.

---

## 🤝 Contributing

- Follow [CLAUDE.md](CLAUDE.md) phase prompts for structured development
- Each phase: Setup → Implementation → Docs → Checklist
- Commit frequently; keep PRs focused
- Test locally before pushing

---

## 📧 Contact

**Project Owner**: Tanmay Bhuskute (the.whitfield.222@gmail.com)

---

**Last Updated**: 2026-04-30  
**Status**: In Development (Phase 0 complete, Phase 1+ in progress)
