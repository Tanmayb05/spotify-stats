"""Unit tests for app/ingest/discover.py -- filesystem only, no DB/network.

Builds a throwaway data/ tree in tmp_path so the assertions do not depend on
the repo's actual export files.
"""

from pathlib import Path

from app.ingest.discover import (
    ALL_SLUGS,
    PRIMARY_SLUG,
    USER_SLUGS,
    discover_files,
    file_sha256,
)


def _touch(path: Path, content: str = "[]") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_tree(root: Path) -> None:
    _touch(root / "streaming_2018-2020_0.json", '[{"a":1}]')
    _touch(root / "streaming_2020-2022_1.json", '[{"a":2}]')
    _touch(root / "streaming_video_2018-2025.json", '[{"v":1}]')       # excluded: video
    _touch(root / "Spotify Account Data" / "Identifiers.json", "{}")   # excluded: account dump
    _touch(root / "other users" / "amit" / "Streaming_History_Audio_2019.json", '[{"b":1}]')
    _touch(root / "other users" / "amit" / "Streaming_History_Video_2019.json", '[{"v":1}]')  # excluded
    _touch(root / "other users" / "sam" / "Streaming_History_Audio_2020.json", '[{"c":1}]')


def test_discover_excludes_video_and_account_data(tmp_path):
    _make_tree(tmp_path)
    files = discover_files(root=tmp_path)
    rels = [f.rel_path for f in files]
    assert not any("video" in r.lower() for r in rels)
    assert not any("account data" in r.lower() for r in rels)


def test_discover_finds_primary_and_others(tmp_path):
    _make_tree(tmp_path)
    files = discover_files(root=tmp_path)
    by_slug = {}
    for f in files:
        by_slug.setdefault(f.slug, []).append(f)
    assert set(by_slug) == {PRIMARY_SLUG, "amit", "sam"}
    assert len(by_slug[PRIMARY_SLUG]) == 2
    assert by_slug[PRIMARY_SLUG][0].is_primary is True
    assert by_slug["amit"][0].is_primary is False


def test_discover_deterministic_sort(tmp_path):
    _make_tree(tmp_path)
    a = [(f.slug, f.rel_path) for f in discover_files(root=tmp_path)]
    b = [(f.slug, f.rel_path) for f in discover_files(root=tmp_path)]
    assert a == b == sorted(a)


def test_discover_only_filter(tmp_path):
    _make_tree(tmp_path)
    files = discover_files(root=tmp_path, only=["amit"])
    assert {f.slug for f in files} == {"amit"}


def test_discover_hash_is_content_addressed(tmp_path):
    _make_tree(tmp_path)
    p = tmp_path / "streaming_2018-2020_0.json"
    h1 = file_sha256(p)
    assert len(h1) == 64
    p.write_text('[{"a":999}]', encoding="utf-8")
    assert file_sha256(p) != h1


def test_all_slugs_is_primary_plus_nine_sorted():
    assert ALL_SLUGS[0] == PRIMARY_SLUG
    assert ALL_SLUGS[1:] == sorted(USER_SLUGS)
    assert len(ALL_SLUGS) == 10
