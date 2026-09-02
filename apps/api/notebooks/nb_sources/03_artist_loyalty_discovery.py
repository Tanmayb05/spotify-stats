# %% [markdown]
# # 03 · Artist loyalty and discovery
#
# **Question:** how fast do people come back to an artist, how much of their
# listening is repeat versus new, and are they explorers or loyalists?
#
# **Feeds:** Phase 14's `user_artist_affinity` — the recency-weight half-life and
# the `repeat_ratio` definition — and Phase 15's explorer-vs-loyalist per-user
# experiment breakdown.
#
# ## Constants carried inline, on purpose
#
# The live app computes related numbers in
# `apps/api/app/services/data_loader.py` (`get_artist_loyalty:542`,
# `get_discovery_timeline:499`). **Phase 14 deletes that file.** These cells
# therefore re-implement the logic with the constants written out here rather
# than importing them, so the notebook stays runnable as evidence afterwards.
#
# Two constants in the current code that are easy to confuse:
#
# * `RECO_HALF_LIFE_DAYS = 180` (`data_loader.py:42`) — the recommender's
#   exponential recency weight.
# * `half_life_days` returned by `get_artist_loyalty` (`:598`) — the **median
#   inter-play gap** for an artist. Unrelated to the above despite the name.
#
# This notebook measures the second and uses it to propose a value for the first.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _common as C

USERS = None
SINCE = None

# Mirrors data_loader.get_artist_loyalty (:579): an artist needs this many plays
# before a return-gap distribution means anything.
MIN_PLAYS_PER_ARTIST = 5

C.use_style()
DB = C.db_available()

# %%
fact = C.load_fact(users=USERS, since=SINCE) if DB else pd.DataFrame()

# %% [markdown]
# ## Repeat vs discovery
#
# `repeat_ratio` is a Phase 14 daily feature, and it has a definitional choice:
# repeat *of a track* or repeat *of an artist*? Both are computed here so the
# choice is made against numbers.
#
# Note the identity convention: counts use `artist_key` (normalised) because we
# are asking "is this the same artist as before", not reproducing a legacy
# case-sensitive display count.

# %%
if C.enough(fact, C.MIN_ROWS_ARTIST, "plays"):
    f = fact.sort_values(["user", "ts"]).copy()

    # First time this user has seen this artist / track?
    f["artist_seen_before"] = f.duplicated(["user", "artist_key"])
    f["track_seen_before"] = f.duplicated(["user", "track_key"])

    per_user = f.groupby("user").agg(
        plays=("ts", "size"),
        artist_repeat_ratio=("artist_seen_before", "mean"),
        track_repeat_ratio=("track_seen_before", "mean"),
        distinct_artists=("artist_key", "nunique"),
        distinct_tracks=("track_key", "nunique"),
    )
    per_user["artists_per_1k_plays"] = (
        per_user["distinct_artists"] / per_user["plays"] * 1000
    )
    print(per_user.round(3).to_string())
    print(
        f"\nartist repeat_ratio spread : "
        f"{per_user['artist_repeat_ratio'].min():.3f} - "
        f"{per_user['artist_repeat_ratio'].max():.3f}"
    )
    print(
        f"track  repeat_ratio spread : "
        f"{per_user['track_repeat_ratio'].min():.3f} - "
        f"{per_user['track_repeat_ratio'].max():.3f}"
    )

# %% [markdown]
# ## Explorer vs loyalist
#
# Phase 15 wants to break experiment results down by listener type. The split
# has to come from a measured spread, not a vibe.

# %%
if C.enough(fact, C.MIN_ROWS_ARTIST, "plays"):
    median_apk = per_user["artists_per_1k_plays"].median()
    per_user["listener_type"] = np.where(
        per_user["artists_per_1k_plays"] >= median_apk, "explorer", "loyalist"
    )

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ordered = per_user.sort_values("artists_per_1k_plays")
    colors = [
        C.SERIES_COLORS[0] if t == "explorer" else C.SERIES_COLORS[1]
        for t in ordered["listener_type"]
    ]
    ax.barh(ordered.index, ordered["artists_per_1k_plays"], color=colors)
    ax.axvline(median_apk, color=C.ACCENT, ls="--", lw=1,
               label=f"median {median_apk:.1f}")
    ax.set_xlabel("distinct artists per 1,000 plays")
    ax.set_title("Explorer vs loyalist")
    ax.legend()
    C.save_fig("03_explorer_vs_loyalist", aggregate=True)
    plt.show()

    print(per_user[["artists_per_1k_plays", "listener_type"]]
          .sort_values("artists_per_1k_plays").round(2).to_string())

# %% [markdown]
# ## Return gaps — the half-life question
#
# For each (user, artist) with enough plays, take the gaps between consecutive
# plays in days. The current app keeps only strictly-positive gaps
# (`data_loader.py:586`), which drops same-day repeats entirely; both variants
# are computed here because that choice materially moves the median.

# %%
if C.enough(fact, C.MIN_ROWS_ARTIST, "plays"):
    f = fact.sort_values(["user", "artist_key", "ts"]).copy()
    f["gap_days"] = (
        f.groupby(["user", "artist_key"])["ts"].diff().dt.total_seconds() / 86400
    )

    counts = f.groupby(["user", "artist_key"])["ts"].transform("size")
    eligible = f[(counts >= MIN_PLAYS_PER_ARTIST) & f["gap_days"].notna()]

    all_gaps = eligible["gap_days"]
    positive_gaps = all_gaps[all_gaps > 0]

    print(f"eligible artist-pairs : {eligible.groupby(['user','artist_key']).ngroups:,}")
    print(f"gaps (all)            : n={len(all_gaps):,}  "
          f"median={all_gaps.median():.3f}d  mean={all_gaps.mean():.2f}d")
    print(f"gaps (>0 only)        : n={len(positive_gaps):,}  "
          f"median={positive_gaps.median():.3f}d  mean={positive_gaps.mean():.2f}d")
    print(f"same-day repeats      : {(all_gaps == 0).mean():.1%} of gaps")

# %%
if C.enough(fact, C.MIN_ROWS_ARTIST, "plays"):
    q = [0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    print("positive-gap quantiles (days):")
    print(positive_gaps.quantile(q).round(2).to_string())

    fig, ax = plt.subplots(figsize=(10, 4.5))
    clipped = positive_gaps[positive_gaps <= 90]
    ax.hist(clipped, bins=90, color=C.SERIES_COLORS[0])
    ax.axvline(positive_gaps.median(), color=C.ACCENT, ls="--", lw=1,
               label=f"median {positive_gaps.median():.1f}d")
    ax.set_xlabel("days between consecutive plays of the same artist (<= 90d)")
    ax.set_ylabel("count")
    ax.set_title("Artist return-gap distribution")
    ax.legend()
    C.save_fig("03_return_gaps", aggregate=True)
    plt.show()

# %% [markdown]
# ### Proposing a recency half-life
#
# The recommender weights a play by `exp(-ln2 · age_days / half_life)`. A
# sensible half-life is the age by which a listener's affinity has genuinely
# decayed — approximated here by the gap quantile beyond which return becomes
# unlikely. Compare against the current hardcoded 180 days.

# %%
RECO_HALF_LIFE_DAYS_CURRENT = 180  # data_loader.py:42

if C.enough(fact, C.MIN_ROWS_ARTIST, "plays"):
    p90 = float(positive_gaps.quantile(0.90))
    p95 = float(positive_gaps.quantile(0.95))
    print(f"current half-life  : {RECO_HALF_LIFE_DAYS_CURRENT} days")
    print(f"90th pct gap       : {p90:.1f} days")
    print(f"95th pct gap       : {p95:.1f} days")
    print(
        f"\nAt the current 180d half-life, a play {p90:.0f} days old still carries "
        f"weight {0.5 ** (p90 / RECO_HALF_LIFE_DAYS_CURRENT):.2f}."
    )

# %% [markdown]
# ## Discovery over time
#
# Discoveries = first appearance of an artist for that user. The live version
# (`get_discovery_timeline:499`) takes the first row *as encountered* rather than
# by sorted timestamp; here it is explicitly sorted, which is the correct
# reading.

# %%
if C.enough(fact, C.MIN_ROWS_ARTIST, "plays"):
    firsts = (
        fact.sort_values("ts")
        .groupby(["user", "artist_key"], as_index=False)["ts"]
        .first()
    )
    # .dt.to_period() drops tz and warns; floor to month start instead.
    firsts["month"] = firsts["ts"].dt.tz_localize(None).values.astype("datetime64[M]")
    monthly = firsts.groupby("month").size()

    plays_monthly = (
        fact.assign(
            month=fact["ts"].dt.tz_localize(None).values.astype("datetime64[M]")
        )
        .groupby("month").size()
    )
    rate = (monthly / plays_monthly).dropna()

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(monthly.index, monthly.to_numpy(), color=C.SERIES_COLORS[0],
            label="new artists")
    ax.set_ylabel("new artists / month")
    ax.set_xlabel("month")
    ax2 = ax.twinx()
    ax2.plot(rate.index, rate.to_numpy(), color=C.SERIES_COLORS[2], lw=1,
             label="discovery rate")
    ax2.set_ylabel("new artists per play")
    ax2.grid(False)
    ax.set_title("Discovery over time (all users)")
    fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.88))
    C.save_fig("03_discovery_timeline", aggregate=True)
    plt.show()

    print(f"mean discovery rate : {rate.mean():.4f} new artists per play")
    print(f"first 12 months     : {rate.head(12).mean():.4f}")
    print(f"last 12 months      : {rate.tail(12).mean():.4f}")

# %% [markdown]
# ## Decision inputs

# %%
if C.enough(fact, C.MIN_ROWS_ARTIST, "plays"):
    C.decision(
        feeds="P14 user_artist_affinity (half-life, repeat_ratio); P15 explorer/loyalist split",
        repeat_ratio_definition="artist-level: share of plays whose artist the user has played before",
        artist_repeat_ratio_median=float(per_user["artist_repeat_ratio"].median()),
        track_repeat_ratio_median=float(per_user["track_repeat_ratio"].median()),
        min_plays_per_artist=MIN_PLAYS_PER_ARTIST,
        median_positive_return_gap_days=float(positive_gaps.median()),
        p90_return_gap_days=float(positive_gaps.quantile(0.90)),
        same_day_repeat_share_of_gaps=float((all_gaps == 0).mean()),
        current_reco_half_life_days=RECO_HALF_LIFE_DAYS_CURRENT,
        explorer_loyalist_split_metric="distinct artists per 1,000 plays",
        explorer_loyalist_threshold=float(median_apk),
        mean_discovery_rate_new_artists_per_play=float(rate.mean()),
    )
