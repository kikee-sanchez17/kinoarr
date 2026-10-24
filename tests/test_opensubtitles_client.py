import json

import httpx
import pytest
import respx

from app.clients.opensubtitles import OpenSubtitlesClient, OpenSubtitlesError, QuotaExceededError

API = "https://api.opensubtitles.com/api/v1"
API_KEY = "secret-api-key"
PASSWORD = "secret-password"
TOKEN = "secret-token"
FILE_LINK = "https://www.opensubtitles.com/download/abc/subfile/Movie.srt"


def make_result(file_id: int = 1, **attribute_overrides) -> dict:
    attributes = {
        "language": "en",
        "download_count": 100,
        "hearing_impaired": False,
        "foreign_parts_only": False,
        "ai_translated": False,
        "machine_translated": False,
        "moviehash_match": False,
        "files": [{"file_id": file_id, "cd_number": 1, "file_name": f"Movie {file_id}"}],
    }
    attributes.update(attribute_overrides)
    return {"id": str(file_id), "type": "subtitle", "attributes": attributes}


def anonymous_client() -> OpenSubtitlesClient:
    return OpenSubtitlesClient(API_KEY, "", "", user_agent="Kinoarr v0.1.0")


def logged_in_client() -> OpenSubtitlesClient:
    return OpenSubtitlesClient(API_KEY, "user", PASSWORD, user_agent="Kinoarr v0.1.0")


def mock_login(base_url: str = "api.opensubtitles.com") -> respx.Route:
    return respx.post(f"{API}/login").mock(
        return_value=httpx.Response(200, json={"token": TOKEN, "base_url": base_url, "status": 200})
    )


def mock_download(remaining: int = 19) -> None:
    respx.post(f"{API}/download").mock(
        return_value=httpx.Response(200, json={"link": FILE_LINK, "file_name": "Movie.srt", "remaining": remaining})
    )
    respx.get(FILE_LINK).mock(return_value=httpx.Response(200, content=b"1\n00:00:01,000 --> 00:00:02,000\nHi\n"))


@respx.mock
def test_search_sends_sorted_lowercase_params_and_identifying_headers():
    route = respx.get(f"{API}/subtitles").mock(return_value=httpx.Response(200, json={"data": []}))

    anonymous_client().search_english(query="Night Of The Living Dead")

    request = route.calls.last.request
    assert str(request.url) == (
        f"{API}/subtitles?foreign_parts_only=exclude&hearing_impaired=exclude"
        "&languages=en&query=night+of+the+living+dead&type=movie"
    )
    assert request.headers["Api-Key"] == API_KEY
    assert request.headers["User-Agent"] == "Kinoarr v0.1.0"
    assert "Authorization" not in request.headers


@respx.mock
def test_search_by_hash_converts_and_filters_results():
    results = [
        make_result(1, moviehash_match=True),
        make_result(2, hearing_impaired=True),
        make_result(3, foreign_parts_only=True),
        make_result(4, ai_translated=True),
        make_result(5, machine_translated=True),
        make_result(6, language="es"),
        make_result(7, files=[{"file_id": 7}, {"file_id": 8}]),
    ]
    route = respx.get(f"{API}/subtitles").mock(return_value=httpx.Response(200, json={"data": results}))

    [candidate] = anonymous_client().search_english(movie_hash="0123456789abcdef")

    assert route.calls.last.request.url.params["moviehash"] == "0123456789abcdef"
    assert candidate.file_id == 1
    assert candidate.hash_match
    assert candidate.download_count == 100


@respx.mock
def test_anonymous_download_returns_file_content():
    mock_download()

    assert anonymous_client().download(1).startswith(b"1\n00:00:01,000")


@respx.mock
def test_logged_in_client_logs_in_once_and_sends_token():
    login = mock_login()
    mock_download()
    client = logged_in_client()

    client.download(1)
    client.download(2)

    assert login.call_count == 1
    assert json.loads(login.calls.last.request.content) == {"username": "user", "password": PASSWORD}
    download_request = respx.calls[-2].request
    assert download_request.headers["Authorization"] == f"Bearer {TOKEN}"


@respx.mock
def test_login_base_url_is_used_for_later_requests():
    mock_login(base_url="vip-api.opensubtitles.com")
    vip_search = respx.get("https://vip-api.opensubtitles.com/api/v1/subtitles").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    logged_in_client().search_english(query="movie")

    assert vip_search.called


@respx.mock
def test_expired_token_triggers_one_new_login():
    login = mock_login()
    respx.post(f"{API}/download").mock(
        side_effect=[
            httpx.Response(401),
            httpx.Response(200, json={"link": FILE_LINK}),
        ]
    )
    respx.get(FILE_LINK).mock(return_value=httpx.Response(200, content=b"subtitle"))

    assert logged_in_client().download(1) == b"subtitle"
    assert login.call_count == 2


@respx.mock
def test_quota_exceeded_raises_with_reset_time():
    respx.post(f"{API}/download").mock(
        return_value=httpx.Response(406, json={"message": "quota", "reset_time_utc": "2026-10-20T23:59:59.999Z"})
    )

    with pytest.raises(QuotaExceededError, match="resets at 2026-10-20 23:59 UTC") as exc_info:
        anonymous_client().download(1)

    assert exc_info.value.reset_at.isoformat().startswith("2026-10-20T23:59:59")


@pytest.mark.parametrize(
    ("response", "expected_message"),
    [
        (httpx.Response(401), "rejected the credentials"),
        (httpx.Response(403), "rejected the credentials"),
        (httpx.Response(429), "rate limit"),
        (httpx.Response(500), "HTTP 500"),
        (httpx.Response(200, text="not json"), "Unexpected"),
        (httpx.Response(200, json={"data": [{"attributes": {"language": "en", "files": [{}]}}]}), "Unexpected"),
    ],
)
@respx.mock
def test_search_errors_raise_without_secrets(response, expected_message):
    respx.get(f"{API}/subtitles").mock(return_value=response)

    with pytest.raises(OpenSubtitlesError, match=expected_message) as exc_info:
        anonymous_client().search_english(query="movie")

    assert API_KEY not in str(exc_info.value)


@pytest.mark.parametrize(
    ("network_error", "expected_message"),
    [(httpx.ConnectError("refused"), "Cannot connect"), (httpx.ReadTimeout("slow"), "timed out")],
)
@respx.mock
def test_network_errors_raise_opensubtitles_error(network_error, expected_message):
    respx.get(f"{API}/subtitles").mock(side_effect=network_error)

    with pytest.raises(OpenSubtitlesError, match=expected_message):
        anonymous_client().search_english(query="movie")


@respx.mock
def test_rejected_login_does_not_leak_password_or_key():
    respx.post(f"{API}/login").mock(return_value=httpx.Response(401))

    with pytest.raises(OpenSubtitlesError) as exc_info:
        logged_in_client().download(1)

    assert PASSWORD not in str(exc_info.value)
    assert API_KEY not in str(exc_info.value)


@respx.mock
def test_failed_file_download_raises():
    respx.post(f"{API}/download").mock(return_value=httpx.Response(200, json={"link": FILE_LINK}))
    respx.get(FILE_LINK).mock(return_value=httpx.Response(404))

    with pytest.raises(OpenSubtitlesError, match="HTTP 404"):
        anonymous_client().download(1)


@respx.mock
def test_search_results_carry_the_movie_they_belong_to():
    with_movie = make_result(
        1, feature_details={"title": "The Exorcism of Emily Rose", "year": 2005, "imdb_id": 404032}
    )
    without_movie = make_result(2)
    respx.get(f"{API}/subtitles").mock(return_value=httpx.Response(200, json={"data": [with_movie, without_movie]}))

    first, second = anonymous_client().search_english(query="the exorcism of emily rose")

    assert (first.movie_title, first.movie_year) == ("The Exorcism of Emily Rose", 2005)
    assert (second.movie_title, second.movie_year) == (None, None)


@respx.mock
def test_search_results_carry_the_release_they_were_timed_for():
    with_release = make_result(1, release="Lady.Bird.2017.720p.BluRay.x264.DTS-HDC", fps=23.976)
    unknown_release = make_result(2, release="", fps=0.0)
    respx.get(f"{API}/subtitles").mock(return_value=httpx.Response(200, json={"data": [with_release, unknown_release]}))

    first, second = anonymous_client().search_english(query="lady bird 2017")

    assert (first.release_name, first.frame_rate) == ("Lady.Bird.2017.720p.BluRay.x264.DTS-HDC", 23.976)
    assert (second.release_name, second.frame_rate) == (None, None)
