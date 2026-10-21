from datetime import UTC, datetime

from app.models import Release
from app.services.release_store import ReleaseStore


def make_release(release_id: str) -> Release:
    return Release(
        id=release_id,
        title=f"Movie {release_id}",
        indexer="Internet Archive",
        size=1_000,
        seeders=1,
        leechers=0,
        publish_date=datetime(2020, 1, 1, tzinfo=UTC),
        info_url=None,
        download_url=f"http://prowlarr:9696/1/download?link={release_id}",
        magnet_url=None,
    )


def test_get_returns_added_release():
    store = ReleaseStore()
    release = make_release("a")

    store.add([release])

    assert store.get("a") == release


def test_get_unknown_id_returns_none():
    assert ReleaseStore().get("missing") is None


def test_oldest_releases_are_evicted_past_the_limit():
    store = ReleaseStore(max_releases=2)

    store.add([make_release("a"), make_release("b")])
    store.add([make_release("c")])

    assert store.get("a") is None
    assert store.get("b") is not None
    assert store.get("c") is not None


def test_adding_a_release_again_makes_it_the_newest():
    store = ReleaseStore(max_releases=2)

    store.add([make_release("a"), make_release("b")])
    store.add([make_release("a"), make_release("c")])

    assert store.get("a") is not None
    assert store.get("b") is None
