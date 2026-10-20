import logging

import httpx
import pytest
import respx

from app.clients.prowlarr import MAX_REDIRECTS, ProwlarrClient, ProwlarrError
from app.models import MagnetLink, TorrentFile

PROWLARR_URL = "http://prowlarr:9696"
SEARCH_URL = f"{PROWLARR_URL}/api/v1/search"
API_KEY = "secret-api-key"


def make_raw_release(**overrides) -> dict:
    raw = {
        "guid": "https://archive.org/details/night_of_the_living_dead",
        "title": "Night of the Living Dead (1968)",
        "indexer": "Internet Archive",
        "size": 734_003_200,
        "seeders": 12,
        "leechers": 3,
        "publishDate": "2010-05-01T00:00:00Z",
        "downloadUrl": f"{PROWLARR_URL}/1/download?apikey={API_KEY}&link=abc",
        "magnetUrl": None,
        "infoUrl": "https://archive.org/details/night_of_the_living_dead",
        "protocol": "torrent",
    }
    raw.update(overrides)
    return raw


@pytest.fixture
def client() -> ProwlarrClient:
    return ProwlarrClient(PROWLARR_URL, API_KEY)


@respx.mock
def test_search_sends_movie_query_with_api_key(client):
    route = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[]))

    client.search_movies("night of the living dead")

    request = route.calls.last.request
    assert request.url.params["query"] == "night of the living dead"
    assert request.url.params["type"] == "search"
    assert request.url.params["categories"] == "2000"
    assert request.headers["X-Api-Key"] == API_KEY


@respx.mock
def test_search_converts_releases(client):
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[make_raw_release()]))

    [release] = client.search_movies("night")

    assert release.title == "Night of the Living Dead (1968)"
    assert release.indexer == "Internet Archive"
    assert release.size == 734_003_200
    assert release.seeders == 12
    assert release.leechers == 3
    assert release.publish_date.year == 2010
    assert release.info_url == "https://archive.org/details/night_of_the_living_dead"
    assert release.download_url == f"{PROWLARR_URL}/1/download?apikey={API_KEY}&link=abc"
    assert release.magnet_url is None
    assert len(release.id) == 16


@respx.mock
def test_search_tolerates_missing_optional_fields(client):
    raw = make_raw_release(seeders=None, leechers=None, infoUrl=None)
    del raw["magnetUrl"]
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[raw]))

    [release] = client.search_movies("night")

    assert release.seeders is None
    assert release.leechers is None
    assert release.info_url is None
    assert release.magnet_url is None


@respx.mock
def test_release_id_is_stable_and_does_not_expose_guid(client):
    raw = make_raw_release()
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[raw]))

    first = client.search_movies("night")[0].id
    second = client.search_movies("night")[0].id

    assert first == second
    assert raw["guid"] not in first


@respx.mock
def test_search_drops_usenet_and_undownloadable_releases(client):
    keep = make_raw_release(guid="keep")
    magnet_only = make_raw_release(guid="magnet-only", downloadUrl=None, magnetUrl=f"{PROWLARR_URL}/1/magnet")
    usenet = make_raw_release(guid="usenet", protocol="usenet")
    no_links = make_raw_release(guid="no-links", downloadUrl=None, magnetUrl=None)
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[keep, magnet_only, usenet, no_links]))

    releases = client.search_movies("night")

    assert len(releases) == 2
    assert {release.magnet_url for release in releases} == {None, f"{PROWLARR_URL}/1/magnet"}


@respx.mock
def test_search_skips_malformed_release_without_logging_api_key(client, caplog):
    malformed = make_raw_release(guid="broken", size="not a number")
    good = make_raw_release(guid="good")
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=[malformed, "not a release", good]))

    with caplog.at_level(logging.WARNING):
        releases = client.search_movies("night")

    assert len(releases) == 1
    assert "size" in caplog.text
    assert API_KEY not in caplog.text


@pytest.mark.parametrize(
    ("response", "expected_message"),
    [
        (httpx.Response(401), "API key"),
        (httpx.Response(500), "HTTP 500"),
        (httpx.Response(200, text="<html>not json</html>"), "not valid JSON"),
        (httpx.Response(200, json={"message": "not a list"}), "expected a list"),
    ],
)
@respx.mock
def test_search_error_responses_raise_prowlarr_error(client, response, expected_message):
    respx.get(SEARCH_URL).mock(return_value=response)

    with pytest.raises(ProwlarrError, match=expected_message) as exc_info:
        client.search_movies("night")

    assert API_KEY not in str(exc_info.value)


@pytest.mark.parametrize(
    ("network_error", "expected_message"),
    [
        (httpx.ConnectError("connection refused"), "Cannot connect to Prowlarr at http://prowlarr:9696"),
        (httpx.ReadTimeout("timed out"), "timed out"),
    ],
)
@respx.mock
def test_search_network_errors_raise_prowlarr_error(client, network_error, expected_message):
    respx.get(SEARCH_URL).mock(side_effect=network_error)

    with pytest.raises(ProwlarrError, match=expected_message) as exc_info:
        client.search_movies("night")

    assert API_KEY not in str(exc_info.value)


DOWNLOAD_LINK = f"{PROWLARR_URL}/1/download?apikey={API_KEY}&link=abc"
MAGNET_URI = "magnet:?xt=urn:btih:0123456789abcdef&dn=Night"
TORRENT_BYTES = b"d8:announce...e"


@respx.mock
def test_fetch_torrent_returns_torrent_file(client):
    route = respx.get(DOWNLOAD_LINK).mock(return_value=httpx.Response(200, content=TORRENT_BYTES))

    assert client.fetch_torrent(DOWNLOAD_LINK) == TorrentFile(content=TORRENT_BYTES)
    assert route.calls.last.request.headers["X-Api-Key"] == API_KEY


@respx.mock
def test_fetch_torrent_returns_magnet_link_from_redirect(client):
    respx.get(DOWNLOAD_LINK).mock(return_value=httpx.Response(301, headers={"Location": MAGNET_URI}))

    assert client.fetch_torrent(DOWNLOAD_LINK) == MagnetLink(uri=MAGNET_URI)


@respx.mock
def test_fetch_torrent_follows_redirect_to_indexer_without_api_key_header(client):
    indexer_url = "https://indexer.example/files/night.torrent"
    respx.get(DOWNLOAD_LINK).mock(return_value=httpx.Response(302, headers={"Location": indexer_url}))
    indexer_route = respx.get(indexer_url).mock(return_value=httpx.Response(200, content=TORRENT_BYTES))

    assert client.fetch_torrent(DOWNLOAD_LINK) == TorrentFile(content=TORRENT_BYTES)
    assert "X-Api-Key" not in indexer_route.calls.last.request.headers


@respx.mock
def test_fetch_torrent_follows_redirect_chain_ending_in_magnet(client):
    indexer_url = "https://indexer.example/get/night"
    respx.get(DOWNLOAD_LINK).mock(return_value=httpx.Response(302, headers={"Location": indexer_url}))
    respx.get(indexer_url).mock(return_value=httpx.Response(302, headers={"Location": MAGNET_URI}))

    assert client.fetch_torrent(DOWNLOAD_LINK) == MagnetLink(uri=MAGNET_URI)


@respx.mock
def test_fetch_torrent_stops_after_too_many_redirects(client):
    loop_url = "https://indexer.example/loop"
    respx.get(DOWNLOAD_LINK).mock(return_value=httpx.Response(302, headers={"Location": loop_url}))
    loop_route = respx.get(loop_url).mock(return_value=httpx.Response(302, headers={"Location": loop_url}))

    with pytest.raises(ProwlarrError, match="Too many redirects"):
        client.fetch_torrent(DOWNLOAD_LINK)
    assert loop_route.call_count == MAX_REDIRECTS


@pytest.mark.parametrize(
    ("response", "expected_message"),
    [
        (httpx.Response(404), "HTTP 404"),
        (httpx.Response(200, content=b""), "empty response"),
        (httpx.Response(301), "HTTP 301"),
        (httpx.Response(302, headers={"Location": "ftp://indexer.example/night.torrent"}), "'ftp'"),
    ],
)
@respx.mock
def test_fetch_torrent_bad_responses_raise_prowlarr_error(client, response, expected_message):
    respx.get(DOWNLOAD_LINK).mock(return_value=response)

    with pytest.raises(ProwlarrError, match=expected_message) as exc_info:
        client.fetch_torrent(DOWNLOAD_LINK)

    assert API_KEY not in str(exc_info.value)


@pytest.mark.parametrize(
    ("network_error", "expected_message"),
    [
        (httpx.ConnectError("connection refused"), "Cannot connect to Prowlarr at http://prowlarr:9696"),
        (httpx.ReadTimeout("timed out"), "Timed out"),
    ],
)
@respx.mock
def test_fetch_torrent_network_errors_raise_prowlarr_error(client, network_error, expected_message):
    respx.get(DOWNLOAD_LINK).mock(side_effect=network_error)

    with pytest.raises(ProwlarrError, match=expected_message) as exc_info:
        client.fetch_torrent(DOWNLOAD_LINK)

    assert API_KEY not in str(exc_info.value)


@respx.mock
def test_fetch_torrent_names_indexer_host_when_it_is_unreachable(client):
    indexer_url = "https://indexer.example/files/night.torrent"
    respx.get(DOWNLOAD_LINK).mock(return_value=httpx.Response(302, headers={"Location": indexer_url}))
    respx.get(indexer_url).mock(side_effect=httpx.ConnectError("connection refused"))

    with pytest.raises(ProwlarrError, match="Cannot connect to indexer.example"):
        client.fetch_torrent(DOWNLOAD_LINK)
