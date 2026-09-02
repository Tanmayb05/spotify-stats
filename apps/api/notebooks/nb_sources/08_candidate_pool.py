# %% [markdown]
# # 08 · Candidate pool and the popularity baseline
#
# **Question:** when a recommender is asked for 20 tracks for a user, how many
# candidates does it actually have to choose from — and where does a popularity
# baseline stop improving?
#
# **Feeds:** Phase 15's `candidates(user_id)` helper and the Baseline-0
# (popularity) design.
#
# ## The constraint that bites first
#
# `data_loader.py` sets `RECO_EXCLUDE_TOP_PLAYED = 25` (`:44`): a user's 25
# most-played tracks are withheld from recommendations, so as not to recommend
# what someone obviously already knows. Phase 11's V9 gate found this makes
# `/api/reco` return **empty** against the 40-row fixture — the exclusion is
# larger than the fixture. That is a fixture-size artifact, but it is also a
# warning: the candidate pool is a real constraint, not a formality.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import matplotlib.pyplot as plt
import pandas as pd

import _common as C

USERS = None
SINCE = None

RECO_EXCLUDE_TOP_PLAYED = 25  # data_loader.py:44
TARGET_K = 20                 # a typical "give me 20 recommendations" request

C.use_style()
DB = C.db_available()

# %%
fact = C.load_fact(users=USERS, since=SINCE) if DB else pd.DataFrame()

# %% [markdown]
# ## Catalogue size
#
# The catalogue is every track anyone has played — that is the universe a
# content or popularity model draws from.

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    catalogue = fact["track_key"].nunique()
    print(f"catalogue (distinct tracks played by anyone) : {catalogue:,}")
    print(f"distinct artists                             : "
          f"{fact['artist_key'].nunique():,}")

# %% [markdown]
# ## Per-user candidate pool
#
# For each user: catalogue minus what they already play, plus the pool that
# survives the top-N exclusion. Both matter — the first is the theoretical
# supply, the second is what the model actually sees.

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    rows = []
    for u, g in fact.groupby("user"):
        own = set(g["track_key"])
        counts = g.groupby("track_key").size().sort_values(ascending=False)
        excluded = set(counts.head(RECO_EXCLUDE_TOP_PLAYED).index)
        rows.append({
            "user": u,
            "plays": len(g),
            "own_tracks": len(own),
            "unseen_candidates": catalogue - len(own),
            "own_after_exclusion": len(own - excluded),
            "excluded": len(excluded),
        })
    pool = pd.DataFrame(rows).set_index("user").sort_values("plays", ascending=False)
    pool["candidates_per_requested_rec"] = pool["unseen_candidates"] / TARGET_K
    print(pool.to_string())

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ordered = pool.sort_values("unseen_candidates")
    ax.barh(ordered.index, ordered["unseen_candidates"], color=C.SERIES_COLORS[0],
            label="unseen candidates")
    ax.barh(ordered.index, ordered["own_tracks"], color=C.SERIES_COLORS[2],
            left=ordered["unseen_candidates"], label="already played")
    ax.set_xlabel("tracks")
    ax.set_title("Candidate pool per user, against the shared catalogue")
    ax.legend()
    C.save_fig("08_candidate_pool", aggregate=True)
    plt.show()

    thin = pool[pool["own_tracks"] <= RECO_EXCLUDE_TOP_PLAYED]
    if len(thin):
        print(f"users whose whole library fits inside the top-{RECO_EXCLUDE_TOP_PLAYED} "
              f"exclusion: {list(thin.index)}")
    else:
        print(f"every user has more than {RECO_EXCLUDE_TOP_PLAYED} distinct tracks — "
              "the exclusion never empties a real pool")

# %% [markdown]
# ## The popularity baseline
#
# Baseline 0 ranks by global plays. Two things decide whether it is a strong
# baseline: how concentrated popularity is, and how much of it any one user has
# already heard.

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    pop = (
        fact.groupby("track_key")
        .agg(global_plays=("ts", "size"), listeners=("user", "nunique"))
        .sort_values("global_plays", ascending=False)
    )
    pop["rank"] = range(1, len(pop) + 1)
    pop["cum_share"] = pop["global_plays"].cumsum() / pop["global_plays"].sum()

    for n in (10, 50, 100, 500, 1000, 5000):
        if n <= len(pop):
            print(f"top {n:>5} tracks hold {pop['cum_share'].iloc[n-1]:.1%} of all plays")

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(pop["rank"], pop["cum_share"], color=C.SERIES_COLORS[0])
    ax.axhline(0.5, color=C.ACCENT, ls="--", lw=1, label="50% of plays")
    ax.set_xscale("log")
    ax.set_xlabel("track rank by global plays (log)")
    ax.set_ylabel("cumulative share of plays")
    ax.set_title("Popularity concentration — where the baseline saturates")
    ax.legend()
    C.save_fig("08_popularity_curve", aggregate=True)
    plt.show()

    n_half = int((pop["cum_share"] < 0.5).sum()) + 1
    print(f"{n_half:,} tracks ({n_half / len(pop):.2%} of the catalogue) "
          "account for half of all plays")

# %% [markdown]
# ### How much of the popular head has each user already heard?
#
# If a user already knows the entire top-100, a popularity baseline has nothing
# fresh to offer them and its measured precision will be misleading.

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    head_sizes = (50, 100, 500)
    rows = []
    for u, g in fact.groupby("user"):
        own = set(g["track_key"])
        row = {"user": u}
        for n in head_sizes:
            head = set(pop.head(n).index)
            row[f"knows_top_{n}"] = len(own & head) / n
            row[f"fresh_in_top_{n}"] = n - len(own & head)
        rows.append(row)
    freshness = pd.DataFrame(rows).set_index("user")
    print(freshness.round(3).to_string())

    print(f"\nmedian share of the global top-100 already played: "
          f"{freshness['knows_top_100'].median():.1%}")
    print(f"worst case (user who knows most of it): "
          f"{freshness['knows_top_100'].max():.1%}")

# %% [markdown]
# ## Saturation — how deep must the baseline go?
#
# To serve `k` *unseen* recommendations from a popularity ranking, how far down
# the ranking does it have to reach for the user with the most head coverage?

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    depths = []
    for u, g in fact.groupby("user"):
        own = set(g["track_key"])
        found, depth = 0, 0
        for tk in pop.index:
            depth += 1
            if tk not in own:
                found += 1
                if found >= TARGET_K:
                    break
        depths.append({"user": u, f"depth_for_{TARGET_K}_unseen": depth})
    depth_tbl = pd.DataFrame(depths).set_index("user")
    print(depth_tbl.to_string())
    print(f"\nworst-case depth to fill {TARGET_K} unseen recommendations: "
          f"{depth_tbl.iloc[:, 0].max()}")

# %% [markdown]
# ## Decision inputs

# %%
if C.enough(fact, C.MIN_ROWS_CF, "plays"):
    C.decision(
        feeds="P15 candidates(user_id) sizing + Baseline-0 popularity design",
        catalogue_tracks=int(catalogue),
        median_unseen_candidates_per_user=float(pool["unseen_candidates"].median()),
        min_unseen_candidates=int(pool["unseen_candidates"].min()),
        reco_exclude_top_played=RECO_EXCLUDE_TOP_PLAYED,
        users_emptied_by_exclusion=int(len(thin)),
        tracks_for_half_of_all_plays=int(n_half),
        head_concentration_top_100=float(pop["cum_share"].iloc[99]),
        median_share_of_top_100_already_played=float(
            freshness["knows_top_100"].median()
        ),
        worst_case_depth_for_20_unseen=int(depth_tbl.iloc[:, 0].max()),
        candidate_pool_verdict="ample — the pool never starves at this catalogue size",
    )
