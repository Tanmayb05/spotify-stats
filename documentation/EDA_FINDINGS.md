# EDA findings

Digest of the eight Phase 13.5 notebooks in [`apps/api/notebooks/`](../apps/api/notebooks/).
One section per notebook: the question asked, what the chart shows, and **the
number a later phase should quote**. This is the fast path when you do not want
to boot Jupyter.

**Measured:** 2026-09-02, against the full local warehouse — 336,936 music plays
across 10 users, 2018-10-29 → 2025-10-28. The data-quality run backing these
numbers was `warn` (31 checks, 29 passed, 0 blocking failures).

**Scope.** This document holds *distributions and behavioural findings*. It does
not restate schema semantics or the D1–D4 decisions — those live in
[`DATA_MODEL.md`](DATA_MODEL.md) — nor the check definitions and thresholds,
which live in [`DATA_QUALITY.md`](DATA_QUALITY.md). Where a number here also
appears there, it is a **check against** the recorded value, so the documents
cannot silently drift.

---

## Two findings that change planned work

Both were discovered by these notebooks and are not recorded anywhere else.

### 1. The genre kill gate no longer passes — 67.1%, not 78.2%

Phase 11 measured 78.2% genre play-coverage and recorded the verdict **KEEP** for
`gold.user_genre_affinity`. That measurement was taken when `gold.dim_artist`
held ~4,536 artists (the primary user's). Phase 12 then ingested all ten users;
the dimension grew to **12,748 artists** while the opt-in backfill had only ever
tagged **682** of them.

Re-measured on the current warehouse: **67.1%** of plays land on a tagged
artist — **11.1 points below the Phase 11 figure and 12.9 below the ≥80% gate.**
The artist FK match rate is 100%, so this is missing metadata, not a join
problem.

**It is cheaply fixable.** The untagged mass is concentrated: backfilling the top
**~941** untagged artists recovers 80% of untagged plays, projecting coverage to
**93.4%**. Phase 14 should re-run `scripts/backfill_artist_tags.py` over the full
dimension and re-run notebook 04 before deciding — not inherit the stale KEEP.

### 2. The app's hour-of-day logic runs on UTC

`gold.dim_time.hour` is UTC. Read raw, the all-user histogram peaks at
**03:00–05:00**, which is not a listening pattern — it is a UTC+5:30 audience's
morning. Corrected to listener-local time the curve becomes an ordinary one:
**peak 18:00, trough 04:00**, with a secondary 09:00–10:00 bump.

`data_loader._calculate_mood_metrics` applies hour-band logic ("+0.15 valence if
10:00–20:00") directly to UTC timestamps, so **every band is shifted by 5.5
hours** for this audience. Phase 14 must convert before bucketing; deriving
`context_label` from raw UTC hours would mislabel every bucket.

---

## 01 · Dataset overview

**Question:** what is in this warehouse, how much per person, and is it
trustworthy enough to build on?

| | |
|---|---|
| Music plays | **336,936** |
| Users | **10** |
| Listening hours | **13,024** |
| Span | 2018-10-29 → 2025-10-28 (**7.0 years**) |
| Distinct tracks / artists | 46,128 / 12,576 |
| Non-music rows (video, podcast) | 1,334 (0.39%) |
| DQ status at measurement | `warn` — 31 checks, 29 passed, **0 blocking** |

**The panel is lopsided, and that is the headline caveat for Phase 16.** The
largest user holds **20.9%** of all plays, the top three hold **53.0%**, and the
Gini across users is **0.370**. The smallest user has **131** plays against the
largest's 70,518 — a 538× range.

**Coverage floor:** at a proposed 1,000-play threshold, **9 of 10 users** can be
modelled and evaluated individually. `user_05` (131 plays) cannot and should be
excluded from per-user metrics or reported separately.

> **Quote in P16:** n=10, but effectively n=9 for per-user evaluation; aggregate
> metrics are weighted heavily toward three people.

📊 `documentation/assets/eda/01_plays_per_user.png`

---

## 02 · Temporal behaviour

**Question:** when do people listen, and where do the natural cut points fall?

All hours below are **listener-local** (UTC+5:30). See finding 2 above.

**Derived hour buckets** — read off where the share-of-plays curve changes level
against the 0.0417 uniform share:

| Bucket | Local hours | Share of plays |
|---|---|---|
| `evening` | 17–22 | **28.2%** |
| `morning` | 6–12 | **26.1%** |
| `afternoon` | 12–17 | **20.8%** |
| `late_night` | 0–6 | **15.9%** |
| `night` | 22–24 | **9.0%** |

**`night_share` window:** four candidates were compared. Raw per-user spread
favours the widest window by construction, so windows were ranked by spread per
unit of listening captured. **`00–06`** wins on that basis (spread 0.389 over
15.9% of plays); `22–06` has the widest raw spread (0.473) but captures 24.8%.
Either is defensible — `00–06` is the tighter definition.

**`dow_bucket` earns its two levels.** Weekend plays are **26.4%** against a
28.6% calendar baseline, so weekends are slightly *under*-represented in volume —
but the shape differs sharply: weekday peak **09:00**, weekend peak **19:00**.

**Per-user temporal preferences are justified**, not a global prior: the ten
users' peak hours span 00:00–22:00 across **7 distinct** peak hours.

> **Quote in P14:** the bucket table above; `night_share` = share of plays in
> local 00:00–06:00; two `dow_bucket` levels.

📊 `02_hour_utc_vs_local.png`, `02_weekday_vs_weekend.png`

---

## 03 · Artist loyalty and discovery

**Question:** how fast do people return to an artist, and how much listening is
repeat versus new?

**`repeat_ratio` — recommend the artist-level definition.** Median artist-level
repeat ratio is **0.940**; track-level is **0.806**. The artist-level measure
spans 0.802–0.977 across users, so it discriminates while staying interpretable
("94% of plays are of an artist this person has heard before").

**Return gaps** (6,432 eligible user-artist pairs, ≥5 plays each):

| Quantile | Days |
|---|---|
| p50 | **0.51** |
| p75 | 6.72 |
| p90 | **39.8** |
| p95 | 106.9 |
| p99 | 456.9 |

Same-day repeats are only **0.54%** of gaps, so the app's
keep-only-positive-gaps rule (`data_loader.py:586`) barely changes the
distribution — it is safe to keep or drop.

**The 180-day recency half-life looks too slow.** At `RECO_HALF_LIFE_DAYS = 180`,
a play 40 days old (the p90 return gap) still carries weight **0.86** — the
model treats a listener as still-engaged well past the point where 90% of real
returns have happened. A half-life nearer the **40–107 day** p90–p95 band would
track actual behaviour. Phase 14 should test this rather than inherit 180.

**Explorer vs loyalist:** split on distinct artists per 1,000 plays, threshold =
median **59.6**. Five users each side; the metric ranges 23.5 → 198.5.

**Discovery decays sharply.** Mean rate **0.089** new artists per play, but
**0.281** in the first 12 months against **0.042** in the last 12 — a 6.7×
decline. Any discovery-rate feature must be windowed, not lifetime.

📊 `03_explorer_vs_loyalist.png`, `03_return_gaps.png`, `03_discovery_timeline.png`

---

## 04 · Genre coverage — the Phase 14 kill gate

**Question:** is genre metadata complete enough to build
`gold.user_genre_affinity`?

**Verdict: DOES NOT PASS.** See finding 1 above for the full story.

| | |
|---|---|
| Gate threshold | ≥ 80% of plays |
| **Measured now** | **67.1%** |
| Phase 11 recorded | 78.2% |
| Drift | **−11.1 points** |
| `dim_artist` rows | 12,748 |
| Artists ever tagged | 2,875 (22.6%) |
| Artist FK match rate | 100% |
| Artists to backfill for 80% of untagged plays | **~941** |
| **Projected coverage after that backfill** | **93.4%** |

Artist-row coverage (22.6%) looks alarming but means little — the dimension's
tail is full of once-played artists. Play coverage is the gate.

The tagged vocabulary is usable if the feature survives: **1,324** distinct
labels, top-20 holding 40.3% of tagged plays, led by `hindi pop`, `pop`,
`bollywood`, `desi`.

> **Phase 14 must choose:** (1) re-run the backfill and re-measure — the
> recommended path, given 93.4% projected; (2) ship the table empty and
> documented; (3) cut the feature.

📊 `04_untagged_concentration.png`

---

## 05 · Session archetypes

**Question:** what does a session look like, and are there real archetypes?

**The 30-minute gap threshold is well-chosen.** **90.0%** of inter-play gaps fall
within it, and the gap distribution's p90 is 30.4 min — the threshold sits
almost exactly at the knee. Median gap is 3.2 min. No change recommended.

**Sessions:** 22,901 built, retaining **95.9%** of plays. Median 9 tracks,
median 29.0 minutes.

**Honest finding: the archetypes are weak.** Silhouette selects **k=2**
(score **0.287**), not the app's hardcoded k=3 (0.210). A score below ~0.35
means the clusters are not well separated — this data is closer to **one
continuum** (short sessions shading into long) than to distinct archetypes. The
two clusters are simply *short* (83%, ~9 tracks, 28 min) and *long* (17%, ~38
tracks, 97 min).

> **Quote in P14:** keep gap=30; use k=2, not 3; and label the result "session
> length", not "archetype". Phase 13's Insights chart should not imply richer
> structure than 0.287 supports.

**Code note for the P14 port:** `data_loader.py` has **two unlinked 30-minute
literals** — `SIM_GAP_MINUTES` (`:68`) and a bare `30` in `_build_sessions`
(`:1349`). Changing one does not change the other. Collapse them.

📊 `05_session_gap_distribution.png`, `05_session_archetypes.png`

---

## 06 · Mood proxy validation

**Question:** what do the app's "valence / energy / danceability" figures
actually measure?

**Answer: the clock, the play duration, and the skip flag. No audio.**

- **0 of 46,146** tracks carry a stored `mood_proxy_*` value. Decision D1
  confirmed: Spotify deprecated `/audio-features` in November 2024 and no such
  data exists here. (808 tracks have `audio_source='enriched'` — that is artist
  metadata, not audio features.)
- The displayed numbers come from `_calculate_mood_metrics`, a step function
  taking **5, 4 and 6 distinct values** for valence, energy and danceability
  respectively. A real audio feature is continuous.
- Correlations against its own inputs confirm there is nothing else in there:
  danceability ↔ minutes played **0.855**, danceability ↔ skipped **−0.731**,
  valence ↔ weekend **0.562**, valence ↔ hour **0.417**. Energy correlates with
  nothing but hour, weakly (0.028), because its bands nearly cancel.

**Wording Phase 16 can lift directly:**

> This project reports no audio-derived mood. Spotify's `/audio-features`
> endpoint was deprecated in November 2024 and no such data exists in this
> dataset. The "valence", "energy" and "danceability" figures shown in the app
> are a deterministic step function of the play's hour, its duration and its
> skip flag, taking 5, 4 and 6 distinct values respectively. They are
> behavioural context features and must not be described as, or compared
> against, Spotify audio features.

> **Quote in P14:** rename these to `context_*` or `behavior_*`. Never
> `valence`/`energy`/`danceability` — the current names invite exactly the
> comparison that cannot be supported.

📊 `06_mood_proxy_by_hour.png`

---

## 07 · Collaborative filtering feasibility at n=10

**Question:** can CF work with ten users, and how much weight should the hybrid
give user similarity?

**Verdict: usable on shared items, but users are only weakly alike. Keep β at
the roadmap default of 0.15.**

| | |
|---|---|
| Users × distinct tracks | 10 × 46,128 |
| Non-zero cells | 69,821 |
| Tracks with ≥2 listeners | **11,381 (24.7%)** |
| **Plays on multi-listener tracks** | **69.7%** |
| Cold-start play mass | **30.3%** |
| Mean pairwise Jaccard | **0.075** |
| Max pairwise Jaccard | 0.209 (`user_03`↔`user_04`) |

**Read the two numbers together.** Only a quarter of *tracks* have more than one
listener, but those tracks carry **70% of plays** — so CF has real signal to work
with on the head of the catalogue. Against that, mean pairwise Jaccard of 0.075
says no two users are strongly alike; the strongest pair (0.209) is a mild
affinity, and `user_05`/`user_09` are near-disjoint from everyone.

Ignore the 15.1% matrix "density" — with only 10 rows a matrix looks dense while
carrying almost no collaborative signal. Item overlap is the number that matters.

> **Quote in P15:** β = 0.15 (unchanged). Expect Model 2 to underperform content
> on the 30.3% cold-start mass. **Still build it** — E2 asks "does CF help at
> n=10?" and this notebook sets the expectation, it does not answer the
> experiment.

📊 `07_item_overlap.png`, `07_user_similarity.png`

---

## 08 · Candidate pool and the popularity baseline

**Question:** how many candidates does a recommender actually have, and where
does a popularity baseline saturate?

**The candidate pool never starves.** Every user sees at least **32,314** unseen
candidates against a 46,128-track catalogue; the median is 39,148. That is
~1,600–2,300 candidates per requested recommendation at k=20.

**`RECO_EXCLUDE_TOP_PLAYED = 25` is harmless on real data.** No user's library is
small enough for the exclusion to empty their pool — even `user_05` (56 distinct
tracks) retains 31. Phase 11's V9 finding that `/api/reco` returns empty was a
**40-row fixture artifact**, not a production constraint.

**Popularity is diffuse, which weakens the baseline.** The top 100 tracks hold
only **7.3%** of plays; it takes **2,377 tracks (5.15% of the catalogue)** to
reach half. There is no small popular head to recommend from.

**And users already know that head.** Median user has played **86.5%** of the
global top-100; one user has played **100%** of it. To serve 20 *unseen*
popularity-ranked tracks, the baseline must reach **281 ranks deep** in the worst
case.

> **Quote in P15:** `candidates(user_id)` needs no special handling for pool
> size. Baseline-0 must exclude already-played tracks and page at least ~300
> deep. Expect its precision to be weak — not because popularity is a bad
> signal, but because it is diffuse here and largely already consumed.

📊 `08_candidate_pool.png`, `08_popularity_curve.png`

---

## Consolidated hand-off

| Phase | Decision | Number to quote | Notebook |
|---|---|---|---|
| P14 | `hour_bucket` cut points | 5 buckets, local hours (table above) | 02 |
| P14 | `night_share` window | local 00:00–06:00 (15.9% of plays) | 02 |
| P14 | `dow_bucket` | 2 levels; weekday peak 09:00, weekend 19:00 | 02 |
| P14 | Convert UTC→local before bucketing | +5:30; UTC peak 03–05 is an artifact | 02, 06 |
| P14 | `repeat_ratio` definition | artist-level; median 0.940 | 03 |
| P14 | Affinity half-life | test 40–107d; **not** the inherited 180d | 03 |
| P14 | Genre affinity | **gate fails at 67.1%**; backfill ~941 artists → 93.4% | 04 |
| P14 | Session gap / k | keep 30 min; **k=2**, weak structure (0.287) | 05 |
| P14 | Collapse duplicate 30-min literals | `data_loader.py:68` and `:1349` | 05 |
| P14 | `mood_proxy_*` naming | rename `context_*`; 0/46,146 populated | 06 |
| P15 | Explorer/loyalist split | ≥59.6 distinct artists per 1k plays | 03 |
| P15 | Hybrid β | 0.15 (unchanged); 69.7% shared mass, Jaccard 0.075 | 07 |
| P15 | Baseline-0 depth | page ≥300 deep; users know 86.5% of top-100 | 08 |
| P16 | n=10 caveat | 9 modellable users; top-3 hold 53% of plays | 01 |
| P16 | Mood limitation wording | lift the paragraph in §06 verbatim | 06 |
