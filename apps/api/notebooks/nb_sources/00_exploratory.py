# %% [markdown]
# # 00 · Exploratory data analysis
#
# General look-and-see over the warehouse: trends, distributions, top
# artists/tracks, platform mix, skip behaviour, time-of-day patterns. No
# decision framing, no kill-gate verdicts, no `## Decision inputs` cell — this
# notebook exists to look at the data, not to settle a Phase 14/15/16 question.
#
# For notebooks aimed at a specific downstream decision, see `01`-`08` and
# `documentation/EDA_FINDINGS.md`. This one uses the same `_common.py` loaders,
# palette, and PII rules as the rest of the set.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import matplotlib.pyplot as plt
import pandas as pd

import _common as C

USERS = None
SINCE = None

C.use_style()
DB = C.db_available()
if not DB:
    print("no database -- every cell below will report insufficient data")

# %%
fact = C.load_fact(users=USERS, since=SINCE) if DB else pd.DataFrame()
if len(fact):
    fact["local_hour"] = C.local_hour(fact)
    fact["local_dow"] = C.local_iso_dow(fact)
    fact["local_is_weekend"] = fact["local_dow"] >= 6

C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays")

# %% [markdown]
# ## Listening over time
#
# Monthly plays and hours, all users combined.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    monthly = (
        fact.assign(month=fact["ts"].dt.tz_localize(None).values.astype("datetime64[M]"))
        .groupby("month")
        .agg(plays=("ts", "size"), hours=("ms_played", lambda s: s.sum() / 3_600_000))
    )

    fig, ax1 = plt.subplots(figsize=(11, 4.5))
    ax1.plot(monthly.index, monthly["plays"], color=C.SERIES_COLORS[0], label="plays")
    ax1.set_ylabel("plays / month")
    ax1.set_xlabel("month")
    ax2 = ax1.twinx()
    ax2.plot(monthly.index, monthly["hours"], color=C.SERIES_COLORS[2], lw=1,
              label="hours")
    ax2.set_ylabel("hours / month")
    ax2.grid(False)
    ax1.set_title("Listening volume over time (all users)")
    fig.legend(loc="upper left", bbox_to_anchor=(0.08, 0.88))
    C.save_fig("00_monthly_volume", aggregate=True)
    plt.show()

# %% [markdown]
# ## Per-user listening over time
#
# Same series, split by user, to see whether the trend is broad or driven by a
# few people.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    per_user_monthly = (
        fact.assign(month=fact["ts"].dt.tz_localize(None).values.astype("datetime64[M]"))
        .groupby(["month", "user"])
        .size()
        .unstack("user")
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(11, 5))
    per_user_monthly.plot(ax=ax, linewidth=1.2)
    ax.set_ylabel("plays / month")
    ax.set_xlabel("month")
    ax.set_title("Per-user monthly plays")
    ax.legend(loc="upper left", ncol=2, fontsize=8)
    C.save_fig("00_per_user_monthly", aggregate=False)  # per-user -> not committed
    plt.show()

# %% [markdown]
# ## Platform mix
#
# Where people listen from.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    platform = (
        fact["platform"].fillna("unknown").value_counts().head(10)
    )
    share = platform / len(fact)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(platform.index[::-1], platform.to_numpy()[::-1], color=C.SERIES_COLORS[1])
    ax.set_xlabel("plays")
    ax.set_title("Platform mix (top 10)")
    C.save_fig("00_platform_mix", aggregate=True)
    plt.show()

    print(share.head(10).round(4).to_string())

# %% [markdown]
# ## Top artists and tracks
#
# By raw play count. Uses `artist_name`/`track_name` — the case-sensitive
# display form — since this is a "what shows up on top" view, not a grouping
# analysis.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    top_artists = fact["artist_name"].value_counts().head(20)

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(top_artists.index[::-1], top_artists.to_numpy()[::-1],
            color=C.SERIES_COLORS[0])
    ax.set_xlabel("plays")
    ax.set_title("Top 20 artists by plays (all users)")
    C.save_fig("00_top_artists", aggregate=True)
    plt.show()

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    top_tracks = (
        fact.assign(label=fact["track_name"] + " — " + fact["artist_name"])
        ["label"].value_counts().head(20)
    )

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(top_tracks.index[::-1], top_tracks.to_numpy()[::-1],
            color=C.SERIES_COLORS[2])
    ax.set_xlabel("plays")
    ax.set_title("Top 20 tracks by plays (all users)")
    C.save_fig("00_top_tracks", aggregate=True)
    plt.show()

# %% [markdown]
# ## Play duration
#
# How long plays actually last, before any skip-adjustment.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    minutes = fact["ms_played"] / 60000

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.hist(minutes[minutes <= 10], bins=100, color=C.SERIES_COLORS[0])
    ax.set_xlabel("minutes played (<= 10)")
    ax.set_ylabel("count")
    ax.set_title("Play duration distribution")
    C.save_fig("00_play_duration", aggregate=True)
    plt.show()

    print(minutes.describe().round(2).to_string())

# %% [markdown]
# ## Skip behaviour
#
# Skip rate overall, per user, and by hour of day.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    overall_skip = fact["skipped"].mean()
    per_user_skip = fact.groupby("user")["skipped"].mean().sort_values(ascending=False)

    print(f"overall skip rate : {overall_skip:.1%}")
    print(per_user_skip.round(3).to_string())

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(per_user_skip.index[::-1], per_user_skip.to_numpy()[::-1],
            color=C.SERIES_COLORS[1])
    ax.axvline(overall_skip, color=C.ACCENT, ls="--", lw=1,
               label=f"overall {overall_skip:.1%}")
    ax.set_xlabel("skip rate")
    ax.set_title("Skip rate by user")
    ax.legend()
    C.save_fig("00_skip_rate_by_user", aggregate=True)
    plt.show()

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    skip_by_hour = fact.groupby("local_hour")["skipped"].mean()

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(skip_by_hour.index, skip_by_hour.to_numpy(), marker="o", ms=3,
            color=C.SERIES_COLORS[0])
    ax.set_xlabel("listener-local hour")
    ax.set_ylabel("skip rate")
    ax.set_xticks(range(0, 24, 2))
    ax.set_title("Skip rate by hour of day")
    C.save_fig("00_skip_rate_by_hour", aggregate=True)
    plt.show()

# %% [markdown]
# ## Listening heatmap
#
# Hour of day × day of week, all users, listener-local time.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    heat = (
        fact.groupby(["local_dow", "local_hour"]).size()
        .unstack("local_hour").reindex(range(1, 8), fill_value=0)
    )
    dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    fig, ax = plt.subplots(figsize=(11, 4))
    im = ax.imshow(heat.to_numpy(), aspect="auto", cmap="viridis")
    ax.set_yticks(range(7))
    ax.set_yticklabels(dow_labels)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("listener-local hour")
    ax.set_title("Listening heatmap (all users)")
    fig.colorbar(im, ax=ax, label="plays")
    C.save_fig("00_listening_heatmap", aggregate=True)
    plt.show()

# %% [markdown]
# ## Reason for starting / ending a play
#
# What triggers a play, and what ends it.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    starts = fact["reason_start"].fillna("unknown").value_counts().head(10)
    ends = fact["reason_end"].fillna("unknown").value_counts().head(10)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].barh(starts.index[::-1], starts.to_numpy()[::-1], color=C.SERIES_COLORS[0])
    axes[0].set_title("reason_start")
    axes[0].set_xlabel("plays")
    axes[1].barh(ends.index[::-1], ends.to_numpy()[::-1], color=C.SERIES_COLORS[2])
    axes[1].set_title("reason_end")
    axes[1].set_xlabel("plays")
    fig.suptitle("Why a play started / ended")
    C.save_fig("00_reason_start_end", aggregate=True)
    plt.show()

# %% [markdown]
# ## Shuffle usage
#
# Share of plays with shuffle on, per user.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    shuffle_rate = fact.groupby("user")["shuffle"].mean().sort_values(ascending=False)
    print(shuffle_rate.round(3).to_string())

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(shuffle_rate.index[::-1], shuffle_rate.to_numpy()[::-1],
            color=C.SERIES_COLORS[1])
    ax.set_xlabel("share of plays with shuffle on")
    ax.set_title("Shuffle usage by user")
    C.save_fig("00_shuffle_usage", aggregate=True)
    plt.show()

# %% [markdown]
# ## Catalogue growth
#
# Cumulative distinct tracks and artists encountered over time (all users).

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    ordered = fact.sort_values("ts")
    ordered["cum_tracks"] = (~ordered["track_key"].duplicated()).cumsum()
    ordered["cum_artists"] = (~ordered["artist_key"].duplicated()).cumsum()
    monthly_growth = (
        ordered.assign(month=ordered["ts"].dt.tz_localize(None).values.astype("datetime64[M]"))
        .groupby("month")[["cum_tracks", "cum_artists"]]
        .last()
    )

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(monthly_growth.index, monthly_growth["cum_tracks"],
            color=C.SERIES_COLORS[0], label="distinct tracks")
    ax.plot(monthly_growth.index, monthly_growth["cum_artists"],
            color=C.SERIES_COLORS[2], label="distinct artists")
    ax.set_xlabel("month")
    ax.set_ylabel("cumulative count")
    ax.set_title("Catalogue growth over time")
    ax.legend()
    C.save_fig("00_catalogue_growth", aggregate=True)
    plt.show()
