Perfect—let’s lock in a **phase-by-phase plan** where:

* **Before each phase**: we run a **Phase Setup** that adds any missing skeleton files, routes, types, envs, and doc tooling.
* **After each phase**: the webapp is **fully functional** (incrementally richer).
* **Each phase auto-generates a Markdown report** in `documentation/` named
  `YYYYMMDD_HHMMSS_phase_<number>_<name>.md`.
* We consistently apply your **UX, performance, security, and accessibility principles**.

Below are ready-to-paste **claude code prompts** for each phase. Use them one-by-one; each includes: setup → implementation → doc writing → checklists & tests. Tech stack matches your request: **React + MUI + MUI X Charts** (frontend) and the backend you already have (or stubs, where noted).

* **colour pallete for webapp**: - Tailwind

{ 'dark_purple': { DEFAULT: '#1c0b19', 100: '#060205', 200: '#0c050a', 300: '#120710', 400: '#180915', 500: '#1c0b19', 600: '#612656', 700: '#a54092', 800: '#ca78bb', 900: '#e5bbdd' }, 'federal_blue': { DEFAULT: '#140d4f', 100: '#040310', 200: '#080520', 300: '#0c082f', 400: '#100a3f', 500: '#140d4f', 600: '#251997', 700: '#3927dc', 800: '#7b6fe8', 900: '#bdb7f3' }, 'keppel': { DEFAULT: '#4ea699', 100: '#10211f', 200: '#1f433d', 300: '#2f645c', 400: '#3f857b', 500: '#4ea699', 600: '#6fbbb0', 700: '#93ccc3', 800: '#b7ddd7', 900: '#dbeeeb' }, 'emerald': { DEFAULT: '#2dd881', 100: '#082c19', 200: '#105833', 300: '#18844c', 400: '#20b066', 500: '#2dd881', 600: '#56e099', 700: '#80e8b2', 800: '#abf0cc', 900: '#d5f7e5' }, 'aquamarine': { DEFAULT: '#6fedb7', 100: '#083e26', 200: '#0f7b4d', 300: '#17b973', 400: '#30e597', 500: '#6fedb7', 600: '#8bf1c5', 700: '#a8f4d3', 800: '#c5f8e2', 900: '#e2fbf0' } }

- CSV

1c0b19,140d4f,4ea699,2dd881,6fedb7

- With #

#1c0b19, #140d4f, #4ea699, #2dd881, #6fedb7

- Array

["1c0b19","140d4f","4ea699","2dd881","6fedb7"]

- Object

{"Dark purple":"1c0b19","Federal blue":"140d4f","Keppel":"4ea699","Emerald":"2dd881","Aquamarine":"6fedb7"}

- Extended Array

[{"name":"Dark purple","hex":"1c0b19","rgb":[28,11,25],"cmyk":[0,61,11,89],"hsb":[311,61,11],"hsl":[311,44,8],"lab":[5,10,-5]},{"name":"Federal blue","hex":"140d4f","rgb":[20,13,79],"cmyk":[75,84,0,69],"hsb":[246,84,31],"hsl":[246,72,18],"lab":[9,27,-39]},{"name":"Keppel","hex":"4ea699","rgb":[78,166,153],"cmyk":[53,0,8,35],"hsb":[171,53,65],"hsl":[171,36,48],"lab":[63,-30,-1]},{"name":"Emerald","hex":"2dd881","rgb":[45,216,129],"cmyk":[79,0,40,15],"hsb":[149,79,85],"hsl":[149,69,51],"lab":[77,-61,31]},{"name":"Aquamarine","hex":"6fedb7","rgb":[111,237,183],"cmyk":[53,0,23,7],"hsb":[154,53,93],"hsl":[154,78,68],"lab":[86,-48,16]}]

- XML

<palette>
  <color name="Dark purple" hex="1c0b19" r="28" g="11" b="25" />
  <color name="Federal blue" hex="140d4f" r="20" g="13" b="79" />
  <color name="Keppel" hex="4ea699" r="78" g="166" b="153" />
  <color name="Emerald" hex="2dd881" r="45" g="216" b="129" />
  <color name="Aquamarine" hex="6fedb7" r="111" g="237" b="183" />
</palette>


* **font style**: Web use
If you're making a web page, you can use the following HTML and CSS:

<!-- HTML in your document's head -->
<link rel="preconnect" href="https://rsms.me/">
<link rel="stylesheet" href="https://rsms.me/inter/inter.css">

/* CSS */
:root {
  font-family: Inter, sans-serif;
  font-feature-settings: 'liga' 1, 'calt' 1; /* fix for Chrome */
}
@supports (font-variation-settings: normal) {
  :root { font-family: InterVariable, sans-serif; }
}

---

# Phase 0 — Project Skeleton & Doc Tooling (Foundations)

**Goal**: Create baseline structure, MUI theme, nav, routing, envs, and a doc-writer utility so every phase can emit a Markdown report automatically.

### ✅ Phase Setup (skeleton)

**Paste to claude code:**

```
You are a senior full-stack engineer. In repo root, ensure this structure exists:

- /frontend (Vite + React + TS)
- /backend (FastAPI Python)  // keep minimal health endpoint if backend exists, else stub it
- /documentation             // markdown reports per phase

FRONTEND (Material UI + MUI X Charts):
1) Install deps:
   npm i @mui/material @emotion/react @emotion/styled @mui/icons-material @mui/x-charts axios zustand
2) Add files:
   src/theme/AppThemeProvider.tsx
   src/layout/AppLayout.tsx
   src/components/StatCard.tsx
   src/components/ErrorBanner.tsx
   src/api/client.ts
   src/store/app.ts
   src/pages/Overview.tsx
   src/pages/Moods.tsx
   src/pages/Discovery.tsx
   src/pages/Milestones.tsx
   src/pages/Sessions.tsx
   src/pages/Recommendations.tsx
   src/pages/Simulator.tsx
   src/pages/NotFound.tsx
   src/utils/format.ts
   src/main.tsx
   src/App.tsx
- Dark theme by default; responsive typography; consistent spacing with sx.
- Left Drawer nav: Overview, Moods, Discovery, Milestones, Sessions, Recommendations (⚗️), Simulator (⚗️).
- AppBar with title and a (stub) theme toggle.
- Routes wired with react-router v6 and <AppLayout />.

DOCS TOOLING:
- Add /frontend/scripts/writePhaseDoc.ts (Node script) that writes a file:
  documentation/<YYYYMMDD_HHMMSS>_phase_<number>_<name>.md
  with sections: date; phase; status; overview; time to complete; files created; files modified; checklist; what was implemented (purpose, features, implementation, flow, usage); next steps; conclusion.
- Add an npm script: "doc:phase": "ts-node scripts/writePhaseDoc.ts"
  (set up ts-node config if needed).

ACCESSIBILITY & SECURITY BASELINE:
- Global skip-to-content link.
- <CssBaseline />; prefers-reduced-motion check for animations (no blocking).
- Announce route changes to screen readers.
- Axios with baseURL from VITE_API_BASE_URL, sane timeouts, error interceptor.
- Don’t store secrets in frontend; rely on env.

Definition of Done:
- App builds and runs.
- Drawer navigation works; blank pages render.
- "Phase 0" doc created to /documentation.
Provide all new/changed files in full.
```

### 📄 Documentation to create

* `documentation/<timestamp>_phase_0_foundations.md` (created by the script).

---

# Phase 1 — Basics: Data Exploration & Overview Dashboard

**Goal**: Ship a functional **Overview** with stat cards + time & platform charts + top artists/tracks. This uses **MUI X Charts**.

### ✅ Phase Setup

**Paste to claude code:**

```
Phase 1 Setup:
- Ensure backend endpoints exist (or stub) with example JSON:
  GET /api/stats/overview
  GET /api/top/artists?limit=10
  GET /api/top/tracks?limit=10
  GET /api/time/monthly
  GET /api/platforms
- In frontend, add typed API functions to src/api/client.ts for these.
- Add skeleton loaders (MUI Skeleton) to Overview page.
- Add simple error banner wiring via Zustand.

Definition of Done (setup):
- Frontend compiles with typed stubs.
- Calling endpoints returns mock data if real backend is not wiring yet.
Output code.
```

### 🧩 Phase Implementation

**Paste to claude code:**

```
Phase 1 Implementation (Overview):
- Implement Overview with:
  - Stat cards: total_streams, total_hours, unique_artists, unique_tracks, unique_albums.
  - Line chart: monthly streams or hours.
  - Pie: platform share.
  - Bar charts: top artists, top tracks.
- Responsive Grid layout; keyboard-accessible cards/charts.
- Number formatting utilities for large counts and hours.

Definition of Done (impl):
- Overview fully functional against the provided endpoints.
- Loading and error states present.
- Lighthouse pass: no major a11y violations.

Write documentation:
- Use writePhaseDoc.ts to create documentation/<timestamp>_phase_1_basics.md
- Fill all sections (date; phase; status; overview; time to complete; files created; files modified; checklist; what was implemented: purpose, features, implementation, flow, usage; next steps; conclusion).
Return the updated files and the doc content your script would write.
```

---

# Phase 2 — Moods & Time-based Discovery (Spotify audio features)

**Goal**: Pull **valence, energy, danceability** (from Spotify), visualize timelines and context comparisons.

### ✅ Phase Setup

**Paste to claude code:**

```
Phase 2 Setup:
- Backend job: /backend/jobs/enrich_audio_features.py to fetch and cache audio features for known tracks (valence, energy, danceability, tempo, key, mode, loudness).
- Add endpoints:
  GET /api/mood/summary?window=7d|30d|90d
  GET /api/mood/contexts (weekday vs weekend, platform vs platform)
  GET /api/mood/monthly
- Env: SPOTIFY_CLIENT_ID/SECRET documented in backend README.
- Frontend: typed API wrappers and Moods page skeleton (selectors for window).

Definition of Done (setup):
- Mock or real responses available.
- Frontend compiles with hooks and controls in place.
Provide code.
```

### 🧩 Phase Implementation

**Paste to claude code:**

```
Phase 2 Implementation (Moods):
- Row 1: LineChart with valence, energy, danceability; window selector (7/30/90d).
- Row 2: Bar comparisons: weekday vs weekend, mobile vs desktop (if provided).
- Row 3: Simple “mood ring” using circular progress for the latest window averages.
- A11y: charts labeled; controls announced; color not sole indicator.

Definition of Done:
- Functional Moods page with real (or mock) data.
- Loading/error handled; responsive layout.

Write documentation to documentation/<timestamp>_phase_2_moods.md
Return updated files and doc content your script would write.
```

---

# Phase 3 — Artist Discovery & Reflective Insights

**Goal**: Discovery timeline, loyalty/half-life, obsessions, and short reflective cards.

### ✅ Phase Setup

**Paste to claude code:**

```
Phase 3 Setup:
- Backend endpoints:
  GET /api/discovery/timeline
  GET /api/loyalty
  GET /api/obsessions
  GET /api/reflect
- Frontend: add typed calls; Discovery page scaffolding; basic table component.

Definition of Done (setup):
- Mock/real endpoints respond.
- Discovery page skeleton renders.
Provide code.
```

### 🧩 Phase Implementation

**Paste to claude code:**

```
Phase 3 Implementation (Discovery):
- LineChart: discoveries per month.
- Table: loyalty with columns (artist, return_prob %, half_life_days).
- BarChart: obsessions (period share).
- Reflective MUI Cards with short insights and KPIs.
- Performance: memoize derived series, avoid re-renders.

Definition of Done:
- Page functional and accessible; keyboard navigation across table/cards.

Write documentation to documentation/<timestamp>_phase_3_discovery.md
Return updated files and doc content your script would write.
```

---

# Phase 4 — Milestones

**Goal**: Streaks, top days, firsts, and a “flashback” widget.

### ✅ Phase Setup

**Paste to claude code:**

```
Phase 4 Setup:
- Backend:
  GET /api/milestones/list
  GET /api/milestones/flashback?date=YYYY-MM-DD
- Frontend: Milestones page skeleton, date picker (MUI), list UI.

Definition of Done (setup):
- Endpoints callable (mock ok).
- Page compiles with skeleton components.
Provide code.
```

### 🧩 Phase Implementation

**Paste to claude code:**

```
Phase 4 Implementation (Milestones):
- Grouped list by year with type badges.
- Flashback: date input -> card with details.
- Export: small “Copy summary” button.

Definition of Done:
- Fully functional; accessible list semantics.

Write documentation to documentation/<timestamp>_phase_4_milestones.md
Return updated files and doc content your script would write.
```

---

# Phase 5 — Session Segmentation (Clustering)

**Goal**: Sessionize with a 30-min gap; compute features; k-means/GMM clusters; show profiles and recent assignments.

### ✅ Phase Setup

**Paste to claude code:**

```
Phase 5 Setup:
- Backend:
  GET /api/sessions/clusters
  GET /api/sessions/centroids
  GET /api/sessions/assignments?limit=100
- Implement sessionizer job with gap=30min and feature builder.
- Persist cluster labels; select k via silhouette.

Frontend:
- Sessions page skeleton; chips for labels; small multi-chart slots.

Definition of Done (setup):
- Endpoints respond with mock/real data; types added.

Provide code.
```

### 🧩 Phase Implementation

**Paste to claude code:**

```
Phase 5 Implementation (Sessions):
- Cards: each cluster's centroid features (render as small bar groups).
- Table: recent sessions with label chip, duration, skip ratio, start time.
- Optional: tiny stacked line showing cluster share over time if available.

Definition of Done:
- Page functional; keyboard and screen reader friendly.

Write documentation to documentation/<timestamp>_phase_5_sessions.md
Return updated files and doc content your script would write.
```

---

# Phase 6 — ML Recommender (⚗️)

**Goal**: Content-based (audio features + your preference vector), with “why this” tooltips and CSV export.

### ✅ Phase Setup

**Paste to claude code:**

```
Phase 6 Setup:
- Backend:
  GET /api/reco?top_k=20&target_mood=optional
- Implement content-based scorer (cosine on normalized features), recency weighting, and MMR diversification.
- Add minimal evaluation notebook (offline) saved under /backend/notebooks (optional).

Frontend:
- Recommendations page skeleton with filters.

Definition of Done (setup):
- Endpoint returns stable shape with why.top_features.

Provide code.
```

### 🧩 Phase Implementation

**Paste to claude code:**

```
Phase 6 Implementation (Recommendations):
- Grid of recommendation cards: title, artist, score chip, "why this" caption.
- Filter: target mood select (happy/energetic/chill).
- Button: export to CSV.
- Performance: virtualize list if long.

Definition of Done:
- Fully functional against endpoint; a11y labels for buttons and chips.

Write documentation to documentation/<timestamp>_phase_6_recommendations.md
Return updated files and doc content your script would write.
```

---

# Phase 7 — Predictive Simulator (⚗️)

**Goal**: Artist-level Markov chain; optional HMM mood states; “Simulate next N plays.”

### ✅ Phase Setup

**Paste to claude code:**

```
Phase 7 Setup:
- Backend:
  GET /api/simulate/next?n=20&seed=artist_id&hour=optional
- Build Markov transition matrices by hour-of-day bucket; smoothing for unseen states.
- Optional: HMM over mood states.
Frontend:
- Simulator page skeleton with controls: seed artist autocomplete, N slider, hour select.

Definition of Done (setup):
- Endpoint returns sequence object with probabilities.

Provide code.
```

### 🧩 Phase Implementation

**Paste to claude code:**

```
Phase 7 Implementation (Simulator):
- Controls + results list with probability bars.
- Button: Export sequence (CSV).
- A11y: announce results update; keyboard-accessible sliders and selects.

Definition of Done:
- Fully functional simulation; graceful handling of unknown seed.

Write documentation to documentation/<timestamp>_phase_7_simulator.md
Return updated files and doc content your script would write.
```

---

## Documentation schema (what each Markdown must contain)

Each phase’s doc must follow this exact outline (your script will fill it):

```
# <Phase Name> — Phase <number>
**Date:** <YYYY-MM-DD HH:MM:SS>  
**Status:** <Completed/Partial/Blocked>  
**Time to complete:** <e.g., 2h 35m>

## Overview
Short, human-readable description of what this phase adds.

## Files Created
- path/one.tsx
- ...

## Files Modified
- path/two.ts
- ...

## Checklist
- [x] Intuitive navigation
- [x] Consistent design
- [x] Responsive layout
- [x] A11y labels/roles
- [x] Error handling & feedback
- [x] Performance sanity checks
- [x] Security baseline (no secrets, safe fetch, minimal data)
- [x] Docs generated

## What Was Implemented
### Purpose
### Features
### Implementation
### Flow
### Usage

## Next Steps
Bulleted, concrete tasks for next phase.

## Conclusion
1–3 sentences assessing impact and stability.
```

---

## Principles baked into every phase

* **User Experience & Interface**

  * Know your users: personal analytics first, power toggles second.
  * **Intuitive nav** via left Drawer; **consistency** of cards and charts.
  * **Visual hierarchy**: stat cards → key charts → secondary tables.
  * **Feedback**: skeletons while loading, error banners on failures.
  * **Progressive disclosure**: advanced tabs (⚗️) tucked away.
  * **Responsive**: MUI Grid breakpoints (`xs=12`, `md=6`, `lg=4`).

* **Performance & Technical**

  * Memoize derived series, avoid expensive re-renders.
  * Axios timeouts & retry (idempotent GETs).
  * API pagination for top lists.
  * Separation: `/frontend` vs `/backend`; typed API client.
  * Data minimization in responses.

* **Security & Trust**

  * No secrets in frontend; use env variables only for base URLs.
  * Sensible CORS; rate limit on backend if exposed.
  * Meaningful consent: if you later collect anything, show a clear notice.

* **Inclusivity & Accessibility**

  * Keyboard navigation, focus outlines intact.
  * Labels/aria for charts and controls.
  * Color is not the only cue; tooltips and legends included.
  * Check contrast via MUI theme palette.

---
