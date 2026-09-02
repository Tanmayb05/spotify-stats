"""Pandera schema for a raw Spotify streaming-history export row.

Applied PRE-landing to the parsed list-of-dicts (via a pandas DataFrame). Real
exports carry 23 keys, the test fixture 17 -- so `strict=False` and never a
check on the column SET. `coerce=False`: we validate the raw types, normalization
happens later in normalize.py.

Rule vocabulary (written verbatim to bronze.quarantine.rule):

  ts_missing            ts absent / empty                       blocking
  ts_unparseable        to_utc(ts) is None                      blocking
  ms_played_range       < 0 or > 86_400_000                     blocking
  music_row_track_name  spotify_track_uri present, track null   blocking (df-level)
  platform_type         platform present and not a str          blocking
  row_not_a_dict        array element is not a JSON object      blocking (pre-Pandera)
  reason_start_enum     not one of the 10 observed              warn -> land
  reason_end_enum       not one of the 11 observed              warn -> land
"""

from __future__ import annotations

import pandas as pd
from pandera.pandas import Check, Column, DataFrameSchema

from app.ingest.normalize import to_utc

MS_PER_DAY = 86_400_000

# Observed enum values across all 10 users (warn-only -- Owner Decision 7).
REASON_START_VALUES = frozenset({
    "trackdone", "fwdbtn", "clickrow", "appload", "playbtn", "backbtn",
    "remote", "trackerror", "unknown", "switched-to-audio",
})
REASON_END_VALUES = frozenset({
    "trackdone", "fwdbtn", "endplay", "logout", "unexpected-exit-while-paused",
    "backbtn", "remote", "unknown", "trackerror", "unexpected-exit",
    "switched-to-video",
})


def _ts_parseable(series):
    """Element-wise: ts is present and to_utc() can parse it. A null/empty ts
    fails here too -- validate.py splits ts_missing vs ts_unparseable from the
    failure_case value."""
    return series.map(
        lambda v: v is not None and not _is_nan(v) and str(v).strip() != "" and to_utc(v) is not None
    )


def _is_nan(v) -> bool:
    """True for a float NaN (how pandas represents a missing cell). Non-floats
    are never NaN."""
    return isinstance(v, float) and pd.isna(v)


def _ms_in_range(series):
    def ok(v):
        if v is None or _is_nan(v):
            return True  # missing ms_played is coerced to 0 later, not a reject
        try:
            n = float(v)
        except (TypeError, ValueError):
            return False
        return 0 <= n <= MS_PER_DAY
    return series.map(ok)


def _is_str_or_null(series):
    return series.map(lambda v: v is None or _is_nan(v) or isinstance(v, str))


def _music_row_has_track_name(df):
    """DataFrame-level: every row with a spotify_track_uri must have a
    non-blank master_metadata_track_name. Returns a boolean Series aligned to
    df.index (True = ok)."""
    uri = df.get("spotify_track_uri")
    name = df.get("master_metadata_track_name")
    if uri is None:
        return df.index.to_series().map(lambda _: True)

    def ok(i):
        u = uri.get(i)
        if u is None or _is_nan(u) or str(u).strip() == "":
            return True
        n = None if name is None else name.get(i)
        return n is not None and not _is_nan(n) and str(n).strip() != ""

    return df.index.to_series().map(ok)


# strict=False: real exports have keys the fixture lacks; never reject on column set.
# Only `ts` is required to be present as a column at all.
RAW_ROW_SCHEMA = DataFrameSchema(
    columns={
        # nullable=False so a null ts raises the implicit not_nullable check
        # (mapped to ts_missing in validate.py); _ts_parseable catches the
        # present-but-garbage case (ts_unparseable). A missing "ts" key entirely
        # is filled with NaN by the DataFrame constructor and also trips
        # not_nullable, which is the behaviour we want.
        "ts": Column(
            object,
            checks=Check(_ts_parseable, element_wise=False, name="ts_parseable"),
            required=True,
            nullable=False,
        ),
        "ms_played": Column(
            object,
            checks=Check(_ms_in_range, element_wise=False, name="ms_played_range"),
            required=False,
            nullable=True,
        ),
        "platform": Column(
            object,
            checks=Check(_is_str_or_null, element_wise=False, name="platform_type"),
            required=False,
            nullable=True,
        ),
    },
    checks=[
        Check(_music_row_has_track_name, name="music_row_track_name"),
    ],
    strict=False,
    coerce=False,
    name="raw_streaming_history_row",
)
