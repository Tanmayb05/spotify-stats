# %% [markdown]
# # 05 · Session archetypes
#
# **Question:** what does a listening session look like, and do sessions fall
# into stable archetypes worth naming?
#
# **Feeds:** Phase 14's `_cluster_sessions` port (the gap threshold and `k`) and
# Phase 13's Insights session-archetype chart.
#
# ## The constants being tested
#
# `apps/api/app/services/data_loader.py` sessionizes and clusters with these
# values, which **Phase 14 will port and Phase 14 also deletes the file**, so
# they are written out here rather than imported:
#
# | constant | value | where |
# |---|---|---|
# | session gap | 30 min | `:1349` (and a separate `SIM_GAP_MINUTES = 30` at `:68`) |
# | min tracks per session | 3 | `:1355`, `:1365` |
# | clustering features | 8 | `:1455-1464` |
# | k selection | silhouette over `2..min(8, n//10)`, default 3 | `:1473-1477` |
# | KMeans | `random_state=42, n_init=10` | `:1481`, `:1490` |
#
# The two 30-minute literals are **not linked in the code** — changing one does
# not change the other. Phase 14 should collapse them to a single constant.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

import _common as C

USERS = None
SINCE = None

SESSION_GAP_MINUTES = 30   # data_loader.py:1349
MIN_TRACKS_PER_SESSION = 3  # data_loader.py:1355
RANDOM_STATE = 42           # data_loader.py:1481

C.use_style()
DB = C.db_available()

# %%
fact = C.load_fact(users=USERS, since=SINCE) if DB else pd.DataFrame()

# %% [markdown]
# ## Is 30 minutes the right gap?
#
# The threshold is inherited, not derived. If inter-play gaps are genuinely
# bimodal — short within-session gaps, long between-session gaps — the trough
# between the modes is the principled cut point.

# %%
if C.enough(fact, C.MIN_ROWS_SESSION, "plays"):
    f = fact.sort_values(["user", "ts"]).copy()
    f["gap_min"] = f.groupby("user")["ts"].diff().dt.total_seconds() / 60
    gaps = f["gap_min"].dropna()

    print(f"inter-play gaps    : n={len(gaps):,}")
    print(f"median             : {gaps.median():.2f} min")
    for q in (0.5, 0.75, 0.9, 0.95, 0.99):
        print(f"  p{int(q*100):<3}            : {gaps.quantile(q):.1f} min")
    print(f"share <= 30 min    : {(gaps <= 30).mean():.1%}")
    print(f"share <= 60 min    : {(gaps <= 60).mean():.1%}")

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.hist(gaps[gaps <= 120], bins=120, color=C.SERIES_COLORS[0])
    ax.axvline(SESSION_GAP_MINUTES, color=C.ACCENT, ls="--", lw=1.2,
               label=f"current threshold {SESSION_GAP_MINUTES} min")
    ax.set_yscale("log")
    ax.set_xlabel("gap between consecutive plays (min, <= 120)")
    ax.set_ylabel("count (log)")
    ax.set_title("Where does one session end and the next begin?")
    ax.legend()
    C.save_fig("05_session_gap_distribution", aggregate=True)
    plt.show()

# %% [markdown]
# ## Build sessions
#
# Same rule as the app: a gap over the threshold starts a new session, and
# sessions shorter than the minimum track count are dropped.

# %%
if C.enough(fact, C.MIN_ROWS_SESSION, "plays"):
    f["new_session"] = (f["gap_min"] > SESSION_GAP_MINUTES) | f["gap_min"].isna()
    f["session_id"] = f.groupby("user")["new_session"].cumsum()

    grouped = f.groupby(["user", "session_id"])
    sessions = grouped.agg(
        start=("ts", "min"),
        end=("ts", "max"),
        track_count=("track_key", "size"),
        unique_artists=("artist_key", "nunique"),
        unique_tracks=("track_key", "nunique"),
        ms_played=("ms_played", "sum"),
        skips=("skipped", "sum"),
    ).reset_index()

    sessions = sessions[sessions["track_count"] >= MIN_TRACKS_PER_SESSION].copy()
    sessions["duration_minutes"] = (
        (sessions["end"] - sessions["start"]).dt.total_seconds() / 60
    )
    sessions["skip_ratio"] = sessions["skips"] / sessions["track_count"]
    sessions["avg_track_minutes"] = (
        sessions["ms_played"] / sessions["track_count"] / 60000
    )
    sessions["diversity"] = sessions["unique_artists"] / sessions["track_count"]
    sessions["local_hour"] = C.local_hour(sessions.rename(columns={"start": "ts"}))
    sessions["is_weekend"] = (
        C.local_iso_dow(sessions.rename(columns={"start": "ts"})) >= 6
    ).astype(int)

    print(f"sessions            : {len(sessions):,}")
    print(f"per user            : {sessions.groupby('user').size().median():.0f} (median)")
    print(f"median tracks       : {sessions['track_count'].median():.0f}")
    print(f"median duration     : {sessions['duration_minutes'].median():.1f} min")
    print(f"plays kept          : "
          f"{sessions['track_count'].sum() / len(f):.1%} of all plays")

# %% [markdown]
# ## Cluster
#
# The same 8 features and the same silhouette-driven `k` selection the app uses.

# %%
FEATURES = [
    "duration_minutes",
    "track_count",
    "unique_artists",
    "skip_ratio",
    "avg_track_minutes",
    "local_hour",
    "is_weekend",
    "diversity",
]

if C.enough(fact, C.MIN_ROWS_SESSION, "plays") and C.enough(
    sessions, 10, "sessions"
):
    X = sessions[FEATURES].to_numpy(dtype=float)
    Xs = StandardScaler().fit_transform(X)

    max_k = max(2, min(8, len(sessions) // 10))
    scores = {}
    # Silhouette on a large sample is slow and barely changes; cap it.
    sample = min(len(Xs), 10000)
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(Xs), size=sample, replace=False)

    for k in range(2, max_k + 1):
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10).fit(Xs)
        scores[k] = silhouette_score(Xs[idx], km.labels_[idx])

    best_k = max(scores, key=scores.get)
    print("silhouette by k:")
    for k, s in scores.items():
        mark = "  <-- best" if k == best_k else ""
        print(f"  k={k}: {s:.4f}{mark}")
    print(f"\napp default is k=3; silhouette picks k={best_k}")

    # A silhouette this low means the clusters are not well separated -- the
    # data is closer to one continuum (short sessions shading into long ones)
    # than to distinct archetypes. Say so rather than dressing up weak
    # structure with confident labels.
    SILHOUETTE_STRONG = 0.50
    SILHOUETTE_WEAK = 0.35
    best_score = scores[best_k]
    if best_score >= SILHOUETTE_STRONG:
        structure = "well-separated clusters"
    elif best_score >= SILHOUETTE_WEAK:
        structure = "moderate structure — usable but soft"
    else:
        structure = "weak structure — closer to a continuum than to archetypes"
    print(f"best silhouette {best_score:.3f} -> {structure}")

# %%
if C.enough(fact, C.MIN_ROWS_SESSION, "plays") and C.enough(sessions, 10, "sessions"):
    km = KMeans(n_clusters=best_k, random_state=RANDOM_STATE, n_init=10).fit(Xs)
    sessions["cluster"] = km.labels_

    centroids = pd.DataFrame(
        StandardScaler().fit(X).inverse_transform(km.cluster_centers_),
        columns=FEATURES,
    )
    centroids["sessions"] = sessions.groupby("cluster").size().to_numpy()
    centroids["share"] = centroids["sessions"] / len(sessions)
    print(centroids.round(2).to_string())

# %% [markdown]
# ### Naming the archetypes
#
# Labels are assigned from the centroid values, so they follow the data rather
# than being fixed strings that could stop matching.

# %%
if C.enough(fact, C.MIN_ROWS_SESSION, "plays") and C.enough(sessions, 10, "sessions"):
    # Labels are relative to the other centroids, so they stay meaningful
    # whatever k the silhouette picks. Only descriptors the centroids actually
    # separate on are used -- inventing a "late-night" label when no cluster is
    # distinguished by hour would be naming noise.
    def name_cluster(row: pd.Series) -> str:
        parts = []
        if row["track_count"] >= centroids["track_count"].median() * 1.5:
            parts.append("long")
        elif row["track_count"] <= centroids["track_count"].median() * 0.67:
            parts.append("short")
        if row["skip_ratio"] >= max(0.4, centroids["skip_ratio"].median() * 1.5):
            parts.append("skim-heavy")
        if row["local_hour"] < 6 or row["local_hour"] >= 22:
            parts.append("late-night")
        if row["diversity"] >= 0.85:
            parts.append("exploratory")
        return " / ".join(parts) if parts else "steady listening"

    centroids["archetype"] = centroids.apply(name_cluster, axis=1)
    print(centroids[["archetype", "sessions", "share", "track_count",
                     "duration_minutes", "skip_ratio", "local_hour",
                     "diversity"]].round(2).to_string())

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.barh(centroids["archetype"] + "  (k" + centroids.index.astype(str) + ")",
            centroids["share"], color=C.SERIES_COLORS[0])
    ax.set_xlabel("share of sessions")
    ax.set_title(f"Session archetypes (k={best_k})")
    C.save_fig("05_session_archetypes", aggregate=True)
    plt.show()

# %% [markdown]
# ## Decision inputs

# %%
if C.enough(fact, C.MIN_ROWS_SESSION, "plays") and C.enough(sessions, 10, "sessions"):
    C.decision(
        feeds="P14 _cluster_sessions port (gap, k); P13 Insights session-archetype chart",
        session_gap_minutes_current=SESSION_GAP_MINUTES,
        share_of_gaps_within_threshold=float((gaps <= SESSION_GAP_MINUTES).mean()),
        min_tracks_per_session=MIN_TRACKS_PER_SESSION,
        sessions_built=int(len(sessions)),
        plays_retained_share=float(sessions["track_count"].sum() / len(f)),
        median_session_tracks=float(sessions["track_count"].median()),
        median_session_minutes=float(sessions["duration_minutes"].median()),
        k_app_default=3,
        k_by_silhouette=int(best_k),
        best_silhouette=float(best_score),
        cluster_structure=structure,
        archetypes=", ".join(centroids["archetype"].tolist()),
        note="two unlinked 30-min literals in data_loader (:68, :1349) — collapse in P14",
    )
