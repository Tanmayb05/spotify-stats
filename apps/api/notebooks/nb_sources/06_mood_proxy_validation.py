# %% [markdown]
# # 06 · Mood proxy validation
#
# **Question:** the app shows "valence / energy / danceability" — what do those
# numbers actually measure?
#
# **Feeds:** Phase 14's `mood_proxy_*` columns, and Phase 16's honesty statement
# about what this project can and cannot claim.
#
# ## The short answer, stated up front
#
# **There is no audio-features data in this repository.** Spotify deprecated the
# `/audio-features` endpoint in November 2024, before this project needed it.
# `gold.dim_track.mood_proxy_valence` / `_energy` / `_danceability` exist as
# columns and are **unpopulated by design** (Decision D1 in
# `documentation/DATA_MODEL.md`); `audio_source` is `'none'` for essentially
# every track.
#
# What the app displays instead is a **deterministic arithmetic function of the
# timestamp and play duration**, computed in
# `data_loader.py:_calculate_mood_metrics` (`:256-320`). It contains no audio
# information whatsoever. This notebook proves the columns are empty, ports the
# heuristic, and shows exactly what it does and does not track — so that Phase 14
# names it honestly and Phase 16 does not overclaim.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import _common as C

USERS = None
SINCE = None

C.use_style()
DB = C.db_available()

# %% [markdown]
# ## Step 1 — the database columns really are empty

# %%
audio = None
HAVE_TRACKS = False
total = populated = 0

if DB:
    audio = C.query(
        """
        SELECT audio_source,
               count(*) AS tracks,
               count(mood_proxy_valence)      AS has_valence,
               count(mood_proxy_energy)       AS has_energy,
               count(mood_proxy_danceability) AS has_danceability
        FROM gold.dim_track
        GROUP BY 1 ORDER BY tracks DESC
        """
    )
    total = int(audio["tracks"].sum())
    populated = int(audio["has_valence"].sum())
    HAVE_TRACKS = C.enough(total, 1, "tracks in dim_track")

if HAVE_TRACKS:
    print(audio.to_string(index=False))
    print(f"\ntracks with a stored valence: {populated:,} of {total:,} "
          f"({populated / total:.2%})")
    print("Decision D1 confirmed — the stored mood columns carry no data.")

# %% [markdown]
# ## Step 2 — port the heuristic
#
# Transcribed from `data_loader.py:256-320`. Note it reads only `ts`,
# `ms_played` and `skipped`.
#
# **Weekday numbering:** the source uses `datetime.weekday()` (0=Mon..6=Sun) and
# calls `>= 5` the weekend. `dim_time.iso_dow` is 1=Mon..7=Sun with `>= 6` as the
# weekend — the *same set of days*, different numbers. Getting this wrong silently
# shifts every value, so the port below derives the weekend flag from the
# timestamp directly.

# %%
MS_LONG_PLAY = 180_000   # >= 3 min
MS_MEDIUM_PLAY = 60_000  # >= 1 min


def mood_metrics(ts: pd.Series, ms_played: pd.Series, skipped: pd.Series) -> pd.DataFrame:
    """Vectorised port of data_loader._calculate_mood_metrics (:256-320)."""
    hour = ts.dt.hour
    is_weekend = ts.dt.weekday >= 5  # source convention, 0=Mon

    valence = pd.Series(0.5, index=ts.index)
    valence += np.where(is_weekend, 0.15, 0.0)
    valence += np.select(
        [hour.between(10, 20), hour.between(6, 9) | hour.between(21, 22)],
        [0.15, 0.05],
        default=0.0,
    )
    valence += np.where((hour >= 23) | (hour < 6), -0.10, 0.0)

    energy = pd.Series(0.5, index=ts.index)
    energy += np.select(
        [hour.between(6, 11), hour.between(12, 17), hour.between(18, 21)],
        [0.25, 0.15, 0.05],
        default=-0.15,
    )

    dance = pd.Series(0.5, index=ts.index)
    dance += np.select(
        [ms_played >= MS_LONG_PLAY, ms_played >= MS_MEDIUM_PLAY],
        [0.25, 0.10],
        default=-0.15,
    )
    dance += np.where(skipped, -0.20, 0.0)

    out = pd.DataFrame({
        "valence": valence.clip(0, 1).round(3),
        "energy": energy.clip(0, 1).round(3),
        "danceability": dance.clip(0, 1).round(3),
    })
    return out


# %% [markdown]
# ## Step 3 — apply it
#
# The heuristic is defined on *local* time in spirit (its hour bands describe a
# person's day), but the app applies it to whatever timestamp it holds, which is
# UTC. Both are computed here: the difference is the size of the bug the app
# currently carries.

# %%
fact = C.load_fact(users=USERS, since=SINCE) if DB else pd.DataFrame()

if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    utc_mood = mood_metrics(fact["ts"], fact["ms_played"], fact["skipped"])
    local_ts = fact["ts"] + pd.Timedelta(hours=C.LOCAL_UTC_OFFSET_HOURS)
    local_mood = mood_metrics(local_ts, fact["ms_played"], fact["skipped"])

    comp = pd.DataFrame({
        "as applied (UTC)": utc_mood.mean(),
        "on local time": local_mood.mean(),
    })
    comp["difference"] = comp["on local time"] - comp["as applied (UTC)"]
    print(comp.round(4).to_string())
    print("\nThe app applies hour-band logic to UTC timestamps; on this")
    print("UTC+5:30 audience that shifts every band by 5.5 hours.")

# %% [markdown]
# ## Step 4 — what does the proxy actually track?
#
# If these three numbers are a deterministic function of hour, duration and the
# skip flag, they must correlate perfectly with those inputs and carry no
# information beyond them. Showing that is the point.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    probe = pd.DataFrame({
        "valence": local_mood["valence"],
        "energy": local_mood["energy"],
        "danceability": local_mood["danceability"],
        "local_hour": C.local_hour(fact),
        "minutes_played": fact["ms_played"] / 60000,
        "skipped": fact["skipped"].astype(int),
        "is_weekend": (C.local_iso_dow(fact) >= 6).astype(int),
    })
    corr = probe.corr(numeric_only=True).loc[
        ["valence", "energy", "danceability"],
        ["local_hour", "minutes_played", "skipped", "is_weekend"],
    ]
    print("correlation with the heuristic's own inputs:")
    print(corr.round(3).to_string())

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), sharey=True)
    by_hour = probe.groupby("local_hour")[["valence", "energy", "danceability"]].mean()
    for ax, col, color in zip(axes, by_hour.columns, C.SERIES_COLORS):
        ax.plot(by_hour.index, by_hour[col], marker="o", ms=3, color=color)
        ax.set_title(col)
        ax.set_xlabel("listener-local hour")
        ax.set_xticks(range(0, 24, 6))
    axes[0].set_ylabel("mean proxy value")
    fig.suptitle("The 'mood' proxies are step functions of the clock", y=1.02)
    C.save_fig("06_mood_proxy_by_hour", aggregate=True)
    plt.show()

# %% [markdown]
# ### How many distinct values can each proxy take?
#
# A real audio feature is continuous. A step function over a handful of
# conditions is not — and the count of distinct values makes that concrete.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    for col in ("valence", "energy", "danceability"):
        vals = sorted(local_mood[col].unique())
        print(f"{col:<14}: {len(vals)} distinct values -> {vals}")

# %% [markdown]
# ## Step 5 — the honest statement
#
# Wording Phase 16 can lift directly.

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    n_val = local_mood["valence"].nunique()
    n_ene = local_mood["energy"].nunique()
    n_dan = local_mood["danceability"].nunique()
    print(
        "This project reports no audio-derived mood. Spotify's /audio-features\n"
        "endpoint was deprecated in November 2024 and no such data exists in this\n"
        f"dataset ({populated:,} of {total:,} tracks carry a stored value). The\n"
        "'valence', 'energy' and 'danceability' figures shown in the app are a\n"
        "deterministic step function of the play's hour, its duration and its skip\n"
        f"flag, taking {n_val}, {n_ene} and {n_dan} distinct values respectively.\n"
        "They are behavioural context features and must not be described as, or\n"
        "compared against, Spotify audio features."
    )

# %% [markdown]
# ## Decision inputs

# %%
if C.enough(fact, C.MIN_ROWS_OVERVIEW, "plays"):
    C.decision(
        feeds="P14 mood_proxy_* naming/definition; P16 limitations section",
        stored_mood_values_populated=int(populated),
        dim_track_rows=int(total),
        audio_source_enriched_tracks=int(
            audio.loc[audio["audio_source"] == "enriched", "tracks"].sum()
        ),
        distinct_valence_values=int(n_val),
        distinct_energy_values=int(n_ene),
        distinct_danceability_values=int(n_dan),
        heuristic_inputs="hour of play, ms_played, skipped flag — no audio",
        applied_on_utc_bug="hour bands applied to UTC; shifts by 5.5h for this audience",
        recommended_naming="context_* or behavior_* — never valence/energy/danceability",
    )
