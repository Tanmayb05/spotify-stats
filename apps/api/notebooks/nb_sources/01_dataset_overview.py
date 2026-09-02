# %% [markdown]
# # 01 · Dataset overview
#
# **Question:** what is actually in this warehouse, how much of it is there per
# person, and is it trustworthy enough to build features on?
#
# **Feeds:** Phase 16's write-up (the "research question / n=10 caveats" section)
# and the per-user coverage floor every later model has to respect.
#
# This notebook deliberately does **not** restate what
# `documentation/DATA_MODEL.md` already records (column semantics, decisions
# D1-D4) or what `documentation/DATA_QUALITY.md` records (the 21 checks and
# their thresholds). Where a number here overlaps one of those, it is framed as
# a **check against** the recorded value, so the two cannot silently drift.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import pandas as pd

import _common as C

# Parameters
USERS = None  # None = all users; or e.g. ["user_01", "user_02"]
SINCE = None  # ISO date string, or None

C.use_style()
DB = C.db_available()
if not DB:
    print("no database -- every cell below will report insufficient data")

# %% [markdown]
# ## Data-quality status
#
# Phase 13 gates the pipeline with 21 checks. Reading the latest run here means
# a reader knows whether everything below was computed on a gate-clean
# warehouse, rather than having to go and look.

# %%
dq = C.latest_dq_run() if DB else None
if dq is None:
    print("no completed data-quality run found (migration 013 applied?)")
else:
    print(f"latest DQ run   : {dq['run_at']:%Y-%m-%d %H:%M} UTC")
    print(f"status          : {dq['status']}")
    print(
        f"checks          : {dq['checks_total']} total | "
        f"{dq['passed']} passed | {dq['failed']} failed | "
        f"{dq['warned']} warned | {dq['skipped']} skipped"
    )
    if dq["failed"]:
        print("\nWARNING: blocking checks failed -- treat the numbers below with care.")

# %% [markdown]
# ## Scale and shape

# %%
fact = C.load_fact(users=USERS, since=SINCE) if DB else pd.DataFrame()

if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    n_plays = len(fact)
    n_users = fact["user"].nunique()
    hours = fact["ms_played"].sum() / 3_600_000
    span = (fact["ts"].max() - fact["ts"].min()).days / 365.25

    print(f"music plays      : {n_plays:,}")
    print(f"users            : {n_users}")
    print(f"listening hours  : {hours:,.0f}")
    print(f"span             : {fact['ts'].min():%Y-%m-%d} -> "
          f"{fact['ts'].max():%Y-%m-%d}  ({span:.1f} years)")
    print(f"distinct tracks  : {fact['track_key'].nunique():,}")
    print(f"distinct artists : {fact['artist_key'].nunique():,}")

# %% [markdown]
# ## Per-user coverage
#
# This is the table every later phase has to respect: a model cannot be
# evaluated per-user on someone with a few hundred plays the way it can on
# someone with seventy thousand.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    per_user = (
        fact.groupby("user")
        .agg(
            plays=("ts", "size"),
            hours=("ms_played", lambda s: s.sum() / 3_600_000),
            tracks=("track_key", "nunique"),
            artists=("artist_key", "nunique"),
            first=("ts", "min"),
            last=("ts", "max"),
            skip_rate=("skipped", "mean"),
        )
        .sort_values("plays", ascending=False)
    )
    per_user["days_active"] = (per_user["last"] - per_user["first"]).dt.days
    per_user["plays_per_day"] = per_user["plays"] / per_user["days_active"].clip(lower=1)

    display_cols = ["plays", "hours", "tracks", "artists", "days_active",
                    "plays_per_day", "skip_rate"]
    print(per_user[display_cols].round(2).to_string())

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ordered = per_user.sort_values("plays")
    ax.barh(ordered.index, ordered["plays"], color=C.SERIES_COLORS[0])
    ax.set_xlabel("music plays")
    ax.set_ylabel("")
    ax.set_title("Plays per user — the n=10 reality")
    for y, v in enumerate(ordered["plays"]):
        ax.text(v, y, f" {v:,}", va="center", fontsize=8)
    C.save_fig("01_plays_per_user", aggregate=True)
    plt.show()

# %% [markdown]
# ## How lopsided is the panel?
#
# The headline caveat for Phase 16: this is not ten comparable users. If the top
# user holds a large share of all plays, aggregate metrics are really that one
# person's metrics, and every per-user mean needs a spread alongside it.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    share = per_user["plays"] / per_user["plays"].sum()
    top1 = share.iloc[0]
    top3 = share.iloc[:3].sum()
    # Gini over per-user play counts: 0 = everyone equal, 1 = one user has all.
    x = per_user["plays"].sort_values().to_numpy(dtype=float)
    n = len(x)
    gini = (2 * (x * range(1, n + 1)).sum() / (n * x.sum())) - (n + 1) / n

    print(f"top user share   : {top1:.1%}")
    print(f"top-3 share      : {top3:.1%}")
    print(f"Gini (plays)     : {gini:.3f}")
    print(f"smallest user    : {per_user['plays'].min():,} plays")
    print(f"median user      : {per_user['plays'].median():,.0f} plays")

# %% [markdown]
# ## Coverage floor
#
# Which users have enough data to be modelled and evaluated individually? The
# floor below is a starting proposal for Phase 15's per-user evaluation, not a
# law -- it is set where the per-user curve breaks.

# %%
MODELLING_FLOOR = 1000  # plays; revisit against the distribution printed above

if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    ok = per_user[per_user["plays"] >= MODELLING_FLOOR]
    thin = per_user[per_user["plays"] < MODELLING_FLOOR]
    print(f"users at or above {MODELLING_FLOOR:,} plays : {len(ok)}")
    if len(thin):
        print(f"below the floor  : {list(thin.index)} "
              f"({', '.join(f'{v:,}' for v in thin['plays'])} plays)")

# %% [markdown]
# ## Non-music rows
#
# `is_music = false` marks video and podcast rows. Every loader in `_common.py`
# filters them by default; the count is worth knowing because leaving them in
# inflates artist and track counts.

# %%
if DB:
    nonmusic = C.query(
        "SELECT count(*) FILTER (WHERE NOT is_music) AS non_music, "
        "count(*) AS total FROM gold.fact_streams"
    ).iloc[0]
    print(f"non-music rows : {nonmusic['non_music']:,} "
          f"({nonmusic['non_music'] / nonmusic['total']:.2%} of the fact table)")

# %% [markdown]
# ## Decision inputs

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    C.decision(
        feeds="P16 write-up (n=10 caveats); per-user coverage floor for every model",
        total_music_plays=int(len(fact)),
        users_total=int(fact["user"].nunique()),
        users_above_modelling_floor=int((per_user["plays"] >= MODELLING_FLOOR).sum()),
        modelling_floor_plays=MODELLING_FLOOR,
        top_user_share_of_plays=float(top1),
        gini_plays_across_users=float(gini),
        smallest_user_plays=int(per_user["plays"].min()),
        span_years=float(span),
        dq_status=(dq or {}).get("status", "unknown"),
    )
