# %% [markdown]
# # 04 · Genre coverage — the Phase 14 kill gate
#
# **Question:** is genre metadata complete enough to build
# `gold.user_genre_affinity` on?
#
# **Feeds:** the Phase 14 **genre-affinity kill gate**. The roadmap's rule: build
# the feature if tagged artists cover **≥ 80% of plays**; otherwise ship it empty
# and documented, or skip it.
#
# ## Why this notebook is not a formality
#
# Phase 11 measured **78.2%** play-coverage after an opt-in MusicBrainz backfill
# and recorded the verdict **KEEP**. That measurement was taken when
# `gold.dim_artist` held ~4,536 artists — the primary user's artists. Phase 12
# then ingested all ten users, and the dimension grew to ~12,700 artists while
# the backfill still only ever tagged 682 of them.
#
# This notebook re-measures coverage on the **current** warehouse. If it has
# fallen below the gate, the Phase 11 verdict no longer holds and Phase 14 must
# either re-run `scripts/backfill_artist_tags.py` over the full dimension or
# treat the feature as cut.

# %%
import sys

sys.path.insert(0, "..") if ".." not in sys.path else None

import matplotlib.pyplot as plt

import _common as C

USERS = None
SINCE = None

# The roadmap's gate: tagged artists must cover this share of plays.
KILL_GATE_PLAY_COVERAGE = 0.80
# Phase 11's recorded measurement, for comparison.
PHASE_11_RECORDED_COVERAGE = 0.782

C.use_style()
DB = C.db_available()

# %% [markdown]
# ## Two coverage numbers, and only one of them matters
#
# *Artist coverage* — what share of rows in `dim_artist` carry a genre — is the
# number that looks bad and means little: the dimension's tail is full of
# artists played once. *Play coverage* — what share of actual plays resolve to a
# tagged artist — is what the feature would experience, and it is the gate.

# %%
artist_cov = None
HAVE_ARTISTS = False

if DB:
    artist_cov = C.query(
        """
        SELECT
            count(*)                                                       AS artists,
            count(*) FILTER (WHERE cardinality(coalesce(genres, '{}')) > 0) AS with_spotify,
            count(*) FILTER (WHERE cardinality(coalesce(genres_enriched, '{}')) > 0) AS with_enriched,
            count(*) FILTER (WHERE cardinality(coalesce(genres_enriched, genres, '{}')) > 0) AS with_any
        FROM gold.dim_artist
        """
    ).iloc[0]
    HAVE_ARTISTS = C.enough(int(artist_cov["artists"]), 1, "artists in dim_artist")

if HAVE_ARTISTS:
    print(f"dim_artist rows          : {artist_cov['artists']:,}")
    print(f"  with Spotify genres    : {artist_cov['with_spotify']:,}")
    print(f"  with enriched genres   : {artist_cov['with_enriched']:,}")
    print(f"  with any genre         : {artist_cov['with_any']:,} "
          f"({artist_cov['with_any'] / artist_cov['artists']:.1%})")

# %%
HAVE_PLAYS = False

if HAVE_ARTISTS:
    play_cov = C.query(
        """
        SELECT
            count(*) AS plays,
            count(a.artist_key) AS plays_with_artist_row,
            sum(CASE WHEN cardinality(coalesce(a.genres_enriched, a.genres, '{}')) > 0
                     THEN 1 ELSE 0 END) AS plays_tagged,
            sum(CASE WHEN cardinality(coalesce(a.genres, '{}')) > 0
                     THEN 1 ELSE 0 END) AS plays_tagged_spotify_only
        FROM gold.fact_streams f
        LEFT JOIN gold.dim_artist a USING (artist_key)
        WHERE f.is_music
        """
    ).iloc[0]

    HAVE_PLAYS = C.enough(int(play_cov["plays"]), C.MIN_ROWS_OVERVIEW, "music plays")

if HAVE_PLAYS:
    coverage = play_cov["plays_tagged"] / play_cov["plays"]
    fk_rate = play_cov["plays_with_artist_row"] / play_cov["plays"]

    print(f"music plays              : {play_cov['plays']:,}")
    print(f"  resolve to a dim_artist: {fk_rate:.1%}")
    print(f"  land on a tagged artist: {coverage:.1%}   <-- the gate number")
    print(f"  (Spotify genres alone) : "
          f"{play_cov['plays_tagged_spotify_only'] / play_cov['plays']:.1%}")

# %% [markdown]
# ## Verdict against the gate

# %%
if HAVE_PLAYS:
    passed = coverage >= KILL_GATE_PLAY_COVERAGE
    drift = coverage - PHASE_11_RECORDED_COVERAGE

    print(f"gate threshold           : {KILL_GATE_PLAY_COVERAGE:.0%}")
    print(f"measured now             : {coverage:.1%}")
    print(f"Phase 11 recorded        : {PHASE_11_RECORDED_COVERAGE:.1%}")
    print(f"drift since Phase 11     : {drift:+.1%}")
    print()
    print(f"VERDICT: {'KEEP' if passed else 'DOES NOT PASS'} "
          f"— {'at or above' if passed else 'below'} the {KILL_GATE_PLAY_COVERAGE:.0%} gate")
    if not passed:
        print(
            "\nThe Phase 11 KEEP verdict was measured on a smaller dim_artist\n"
            "(primary user only). Phase 12 ingested all ten users; the backfill\n"
            "never ran over the artists that arrived with them.\n"
            "Phase 14 options:\n"
            "  1. re-run scripts/backfill_artist_tags.py over the full dimension,\n"
            "     then re-measure here before building the feature;\n"
            "  2. ship gold.user_genre_affinity empty + documented;\n"
            "  3. cut the feature."
        )

# %% [markdown]
# ## Where is the untagged mass?
#
# If untagged plays concentrate in a manageable number of artists, a targeted
# backfill closes the gap cheaply. That is the actionable question behind the
# verdict.

# %%
untagged = None

if HAVE_PLAYS:
    untagged = C.query(
        """
        SELECT a.artist_name, count(*) AS plays
        FROM gold.fact_streams f
        JOIN gold.dim_artist a USING (artist_key)
        WHERE f.is_music
          AND cardinality(coalesce(a.genres_enriched, a.genres, '{}')) = 0
        GROUP BY 1
        ORDER BY plays DESC
        LIMIT 2000
        """
    )

    if len(untagged):
        total_untagged = int(play_cov["plays"] - play_cov["plays_tagged"])
        cum = untagged["plays"].cumsum()
        for n in (50, 100, 500, 1000, 2000):
            if n <= len(untagged):
                print(f"top {n:>4} untagged artists cover "
                      f"{cum.iloc[n-1] / total_untagged:.1%} of untagged plays "
                      f"({cum.iloc[n-1]:,} of {total_untagged:,})")

# %%
if HAVE_PLAYS and untagged is not None and len(untagged):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    frac = untagged["plays"].cumsum() / total_untagged
    ax.plot(range(1, len(frac) + 1), frac, color=C.SERIES_COLORS[0])
    ax.axhline(0.8, color=C.ACCENT, ls="--", lw=1, label="80% of untagged plays")
    ax.set_xlabel("untagged artists, ranked by plays")
    ax.set_ylabel("cumulative share of untagged plays")
    ax.set_title("How concentrated is the untagged mass?")
    ax.legend()
    C.save_fig("04_untagged_concentration", aggregate=True)
    plt.show()

    need_80 = int((frac < 0.8).sum()) + 1
    print(f"backfilling ~{need_80:,} artists would recover 80% of untagged plays")
    projected = coverage + 0.8 * (1 - coverage)
    print(f"projected coverage after that backfill: {projected:.1%}")

# %% [markdown]
# ## What the tagged vocabulary looks like
#
# If the feature survives, these are the labels it would be built from.

# %%
genres = None

if HAVE_PLAYS:
    genres = C.query(
        """
        SELECT lower(g) AS genre, count(*) AS plays
        FROM gold.fact_streams f
        JOIN gold.dim_artist a USING (artist_key)
        CROSS JOIN LATERAL unnest(coalesce(a.genres_enriched, a.genres, '{}')) AS g
        WHERE f.is_music
        GROUP BY 1
        ORDER BY plays DESC
        """
    )
    if C.enough(genres, 5, "distinct genres"):
        print(f"distinct genre labels : {len(genres):,}")
        print("top 15 by plays:")
        print(genres.head(15).to_string(index=False))

        head_share = genres["plays"].head(20).sum() / genres["plays"].sum()
        print(f"\ntop-20 labels hold {head_share:.1%} of tagged plays")

# %% [markdown]
# ## Decision inputs

# %%
if HAVE_PLAYS:
    C.decision(
        feeds="P14 genre-affinity kill gate (gold.user_genre_affinity: build / empty / cut)",
        gate_threshold_play_coverage=KILL_GATE_PLAY_COVERAGE,
        measured_play_coverage=float(coverage),
        phase_11_recorded_coverage=PHASE_11_RECORDED_COVERAGE,
        drift_since_phase_11=float(drift),
        verdict="KEEP" if passed else "DOES NOT PASS — re-backfill or cut",
        artist_row_coverage=float(artist_cov["with_any"] / artist_cov["artists"]),
        artist_fk_match_rate=float(fk_rate),
        dim_artist_rows=int(artist_cov["artists"]),
        artists_ever_tagged=int(artist_cov["with_any"]),
        artists_to_backfill_for_80pct_of_untagged=(
            int(need_80) if untagged is not None and len(untagged) else 0
        ),
        projected_coverage_after_backfill=(
            float(projected) if untagged is not None and len(untagged) else float(coverage)
        ),
        distinct_genre_labels=int(len(genres)) if genres is not None else 0,
    )
