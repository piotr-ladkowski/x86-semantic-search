import re


def test_health_and_ready(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    body = client.get("/readyz").json()
    assert body == {"status": "ready", "instructions": 3, "articles": 1}


def test_home_and_listings(client):
    assert client.get("/").status_code == 200
    r = client.get("/instructions")
    assert r.status_code == 200 and "POPCNT" in r.text and "3 of 4 planned" in r.text
    assert "About registers" in client.get("/articles").text


def test_search_page_renders_results(client):
    r = client.get("/search", params={"q": "count set bits"})
    assert r.status_code == 200
    assert 'href="/instructions/popcnt"' in r.text
    assert "About registers" in r.text  # related articles section


def test_empty_search_redirects_home(client):
    r = client.get("/search", params={"q": "  "}, follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "/")


def test_search_page_escapes_query(client):
    r = client.get("/search", params={"q": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in r.text


def test_instruction_page(client):
    r = client.get("/instructions/popcnt")
    assert r.status_code == 200
    for needle in ("POPCNT r64, r/m64", "Gotchas", "draft", "test-rev"):
        assert needle in r.text


def test_alias_and_case_redirect_to_canonical_url(client):
    for name in ("sal", "SAL", "SHL"):
        r = client.get(f"/instructions/{name}", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (301, "/instructions/shl")


def test_planned_related_instruction_is_not_linked(client):
    # shl lists `rol` as related, which is in the roster but has no page yet.
    assert "/instructions/rol" not in client.get("/instructions/shl").text


def test_article_page(client):
    r = client.get("/articles/regs")
    assert r.status_code == 200 and "Registers hold values" in r.text
    assert 'href="/instructions/popcnt"' in r.text


def test_404_html_vs_json(client):
    html = client.get("/instructions/nope")
    assert html.status_code == 404 and "text/html" in html.headers["content-type"]
    assert client.get("/articles/nope").status_code == 404
    api = client.get("/api/instructions/nope")
    assert api.status_code == 404 and api.json()["detail"].startswith("No documented")


def test_api_search(client):
    r = client.get(
        "/api/search", params={"q": "population count", "kind": "instruction", "limit": 2}
    )
    data = r.json()
    assert r.status_code == 200 and len(data["results"]) == 2
    first = data["results"][0]
    assert first["slug"] == "popcnt" and first["url"] == "/instructions/popcnt"
    assert {"mnemonic", "title", "summary", "category", "status", "score", "match"} <= set(first)


def test_api_search_validation(client):
    assert client.get("/api/search").status_code == 422
    assert client.get("/api/search", params={"q": ""}).status_code == 422
    assert client.get("/api/search", params={"q": "x" * 201}).status_code == 422
    assert client.get("/api/search", params={"q": "x", "limit": 0}).status_code == 422
    assert client.get("/api/search", params={"q": "x", "kind": "bogus"}).status_code == 422


def test_api_instruction_by_alias(client):
    data = client.get("/api/instructions/sal").json()
    assert data["slug"] == "shl" and "body_html" not in data and "Gotchas" in data["sections"]
    assert len(client.get("/api/instructions").json()["results"]) == 3


def test_about_page_explains_the_search_with_live_numbers(client):
    r = client.get("/about")
    assert r.status_code == 200
    for needle in (
        "How search works",
        "384 numbers",
        "cosine",
        "3 of 4 planned instruction pages",  # computed from the roster and the pages, not typed in
        "A real search, run just now",
        'href="/instructions/popcnt"',  # the live example links to real pages
    ):
        assert needle in r.text, needle
    assert re.search(
        r"\d+ pins</strong>\s+covering\s+3\s+instruction\s+pages\s+and\s+1\s+article\b", r.text
    )


def test_about_is_reachable_from_the_navigation(client):
    assert 'href="/about"' in client.get("/").text
    assert 'href="/about"' in client.get("/instructions/popcnt").text
