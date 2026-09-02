# %% [markdown]
# # 02 · Temporal behaviour
#
# **Question:** when do people actually listen, and where do the natural cut
# points fall?
#
# **Feeds:** Phase 14's `user_temporal_preferences` — the real `hour_bucket` and
# `dow_bucket` cut points and the `context_label` set, **derived rather than
# guessed**, plus the `night_share` cutoff.
#
# ## The timezone trap (read this before quoting any number here)
#
# `gold.dim_time.hour` is **UTC**. The warehouse runs `TimeZone=Etc/UTC`, Spotify
# exports UTC timestamps, and `dim_time.hour == EXTRACT(hour FROM ts)` exactly.
# Taken at face value the all-user histogram peaks at 03:00-05:00, which is not a
# listening pattern — it is the morning peak of a UTC+5:30 audience.
#
# Every hour in this notebook is therefore a **listener-local** hour via
# `_common.local_hour()`, which applies `LOCAL_UTC_OFFSET_HOURS = 5.5`. That
# offset is an explicit assumption (the warehouse stores no per-user timezone),
# and Phase 14 must revisit it if the user base stops being single-region.

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

# %%
fact = C.load_fact(users=USERS, since=SINCE) if DB else pd.DataFrame()

if len(fact):
    fact["local_hour"] = C.local_hour(fact)
    fact["local_dow"] = C.local_iso_dow(fact)
    fact["local_is_weekend"] = fact["local_dow"] >= 6

# %% [markdown]
# ## UTC vs local — why the correction matters
#
# Both curves below are the same plays. Only the labelling differs, and the
# labelling is what Phase 14 would bake into `context_label`.

# %%
if C.enough(fact, C.MIN_ROWS_TEMPORAL, "plays"):
    utc_h = fact.groupby("hour").size()
    loc_h = fact.groupby("local_hour").size()

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(utc_h.index, utc_h.to_numpy(), marker="o", ms=3,
            color=C.SERIES_COLORS[1], label="UTC hour (as stored)")
    ax.plot(loc_h.index, loc_h.to_numpy(), marker="o", ms=3,
            color=C.SERIES_COLORS[0], label="listener-local hour (+5:30)")
    ax.set_xlabel("hour of day")
    ax.set_ylabel("plays")
    ax.set_xticks(range(0, 24, 2))
    ax.set_title("Hour-of-day: storage timezone vs listener-local")
    ax.legend()
    C.save_fig("02_hour_utc_vs_local", aggregate=True)
    plt.show()

    print(f"UTC   peak hour : {utc_h.idxmax():02d}:00  trough: {utc_h.idxmin():02d}:00")
    print(f"local peak hour : {loc_h.idxmax():02d}:00  trough: {loc_h.idxmin():02d}:00")

# %% [markdown]
# ## Where are the natural cut points?
#
# Rather than imposing familiar buckets, find where the local-hour curve
# actually changes level. The share-of-plays curve is smooth, so the cut points
# are taken where the hour-over-hour change flips sign around the daily
# minimum/maximum.

# %%
if C.enough(fact, C.MIN_ROWS_TEMPORAL, "plays"):
    share = (loc_h / loc_h.sum()).reindex(range(24), fill_value=0.0)
    uniform = 1 / 24

    tbl = pd.DataFrame({
        "plays": loc_h.reindex(range(24), fill_value=0),
        "share": share,
        "vs_uniform": share / uniform,
    })
    tbl["delta"] = tbl["share"].diff().fillna(0)
    print(tbl.round(4).to_string())
    print(f"\nuniform share would be {uniform:.4f} per hour")

# %% [markdown]
# ### Proposed buckets
#
# Read off the table above: hours materially below uniform are the quiet block,
# and the two peaks (morning, evening) separate the rest.

# %%
# Proposed cut points, in listener-local hours. Half-open intervals [lo, hi).
HOUR_BUCKETS = {
    "late_night": (0, 6),    # deep trough
    "morning": (6, 12),      # rising into the first peak
    "afternoon": (12, 17),   # midday plateau
    "evening": (17, 22),     # the day's maximum
    "night": (22, 24),       # falling away
}


def bucket_of(h: int) -> str:
    for name, (lo, hi) in HOUR_BUCKETS.items():
        if lo <= h < hi:
            return name
    return "unknown"


if C.enough(fact, C.MIN_ROWS_TEMPORAL, "plays"):
    fact["hour_bucket"] = fact["local_hour"].map(bucket_of)
    bucket_share = (
        fact.groupby("hour_bucket").size().sort_values(ascending=False) / len(fact)
    )
    print(bucket_share.round(4).to_string())

# %% [markdown]
# ## Weekday vs weekend
#
# `dow_bucket` in Phase 14 is only worth two levels if the two actually differ.

# %%
if C.enough(fact, C.MIN_ROWS_TEMPORAL, "plays"):
    wk = fact.groupby(["local_is_weekend", "local_hour"]).size().unstack(0).fillna(0)
    wk_norm = wk / wk.sum()

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(wk_norm.index, wk_norm[False], marker="o", ms=3,
            color=C.SERIES_COLORS[0], label="weekday")
    ax.plot(wk_norm.index, wk_norm[True], marker="o", ms=3,
            color=C.SERIES_COLORS[2], label="weekend")
    ax.set_xlabel("listener-local hour")
    ax.set_ylabel("share of that group's plays")
    ax.set_xticks(range(0, 24, 2))
    ax.set_title("Weekday vs weekend shape")
    ax.legend()
    C.save_fig("02_weekday_vs_weekend", aggregate=True)
    plt.show()

    weekend_share = float(fact["local_is_weekend"].mean())
    # Weekend days are 2/7 of the calendar; compare against that, not against 0.5.
    print(f"weekend share of plays : {weekend_share:.3f} "
          f"(calendar baseline {2/7:.3f})")
    print(f"peak hour weekday      : {wk_norm[False].idxmax():02d}:00")
    print(f"peak hour weekend      : {wk_norm[True].idxmax():02d}:00")

# %% [markdown]
# ## `night_share` — the cutoff Phase 14 needs
#
# `night_share` is a per-user daily feature. Its definition needs a night window
# that is (a) genuinely quiet for most users and (b) discriminating — a window
# where everyone scores the same is a useless feature.

# %%
if C.enough(fact, C.MIN_ROWS_TEMPORAL, "plays"):
    candidates = {
        "00-06": (0, 6),
        "23-06": (23, 6),
        "22-06": (22, 6),
        "00-05": (0, 5),
    }

    rows = []
    for label, (lo, hi) in candidates.items():
        if lo < hi:
            mask = fact["local_hour"].between(lo, hi - 1)
        else:  # wraps midnight
            mask = (fact["local_hour"] >= lo) | (fact["local_hour"] < hi)
        per_user_share = fact.assign(night=mask).groupby("user")["night"].mean()
        rows.append({
            "window": label,
            "overall_share": float(mask.mean()),
            "user_min": float(per_user_share.min()),
            "user_max": float(per_user_share.max()),
            "user_spread": float(per_user_share.max() - per_user_share.min()),
            "user_std": float(per_user_share.std()),
        })
    night_tbl = pd.DataFrame(rows).set_index("window")
    # Raw spread is not a fair comparison: a wider window captures more plays and
    # will almost always show a wider spread. Normalise by the window's own
    # overall share to get discrimination *per unit of listening captured*.
    night_tbl["hours"] = [
        (hi - lo) % 24 or 24 for lo, hi in candidates.values()
    ]
    night_tbl["spread_per_share"] = (
        night_tbl["user_spread"] / night_tbl["overall_share"]
    )
    night_tbl = night_tbl.sort_values("spread_per_share", ascending=False)
    print(night_tbl.round(4).to_string())

    best_window = night_tbl.index[0]
    widest = night_tbl["user_spread"].idxmax()
    print(f"\nmost discriminating per unit captured : {best_window}")
    print(f"widest raw spread                     : {widest}")
    if best_window != widest:
        print("(the two differ — raw spread favours the wider window by construction)")

# %% [markdown]
# ## Per-user divergence
#
# Do all ten users share one clock, or does Phase 14 need genuinely per-user
# temporal preferences? If the per-user peak hours cluster tightly, a global
# prior would do; if they spread, per-user rows earn their place.

# %%
if C.enough(fact, C.MIN_ROWS_TEMPORAL, "plays"):
    per_user_hour = (
        fact.groupby(["user", "local_hour"]).size().unstack(1).fillna(0)
    )
    per_user_norm = per_user_hour.div(per_user_hour.sum(axis=1), axis=0)
    peak_hours = per_user_norm.idxmax(axis=1).sort_values()

    print("peak local hour per user:")
    print(peak_hours.to_string())
    print(f"\nspread of peak hours : {peak_hours.min():02d}:00 - "
          f"{peak_hours.max():02d}:00 ({peak_hours.nunique()} distinct)")

    fig, ax = plt.subplots(figsize=(10, 4))
    im = ax.imshow(per_user_norm.to_numpy(), aspect="auto", cmap="viridis")
    ax.set_yticks(range(len(per_user_norm)))
    ax.set_yticklabels(per_user_norm.index)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("listener-local hour")
    ax.set_title("Per-user hour profile (row-normalised)")
    fig.colorbar(im, ax=ax, label="share of user's plays")
    C.save_fig("02_per_user_hour_profile")  # per-user -> not committed
    plt.show()

# %% [markdown]
# ## Decision inputs

# %%
if C.enough(fact, C.MIN_ROWS_TEMPORAL, "plays"):
    C.decision(
        feeds="P14 user_temporal_preferences (hour_bucket, dow_bucket, context_label, night_share)",
        local_utc_offset_hours=C.LOCAL_UTC_OFFSET_HOURS,
        hour_buckets=str(HOUR_BUCKETS),
        peak_local_hour=int(loc_h.idxmax()),
        trough_local_hour=int(loc_h.idxmin()),
        night_share_window=best_window,
        night_share_overall=float(night_tbl.loc[best_window, "overall_share"]),
        night_share_user_spread=float(night_tbl.loc[best_window, "user_spread"]),
        weekend_play_share=float(weekend_share),
        weekend_calendar_baseline=round(2 / 7, 4),
        distinct_per_user_peak_hours=int(peak_hours.nunique()),
        dow_bucket_recommendation="two levels (weekday/weekend) — shapes differ",
    )
