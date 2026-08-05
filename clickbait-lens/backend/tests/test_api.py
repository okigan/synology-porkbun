from __future__ import annotations

BODY = (
    "Analysts suggest the housing market may cool over the coming year. Mortgage "
    "approvals could fall further, according to two brokers surveyed by this newspaper. "
    "House prices rose 2 percent in the third quarter. Some economists argue prices will "
    "fall by 10 percent by 2026, though the range of forecasts is unusually wide. The "
    "central bank declined to comment on the outlook."
)


def analyze(client, **overrides):
    payload = {
        "url": "https://www.economist.com/finance/2024/01/01/the-crash?utm_source=twitter",
        "title": "House prices are about to crash",
        "body": BODY,
        "byline": "By Helena Marsh, Senior Correspondent",
        "outlet_name": "The Economist",
    }
    payload.update(overrides)
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_healthz(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["analyzer"] == "heuristic"


def test_analyze_returns_score_signals_claims_and_author(client):
    data = analyze(client)
    assert 0 <= data["clickbait_score"] <= 100
    assert data["verdict"] in {"clean", "low", "moderate", "high"}
    assert data["outlet_domain"] == "economist.com"
    assert data["analyzer"] == "heuristic"

    assert data["signals"], "expected at least one signal on this headline"
    assert data["claims"]

    (author,) = data["authors"]
    assert author["display_name"] == "Helena Marsh"
    assert "trust_index" in author["trust"]


def test_tracking_params_are_stripped_so_the_article_dedupes(client):
    first = analyze(client)
    second = analyze(
        client,
        url="https://www.economist.com/finance/2024/01/01/the-crash?utm_source=email&fbclid=z",
    )
    assert "utm_source" not in first["url"]
    assert first["article_id"] == second["article_id"]


def test_persist_false_leaves_no_author_behind(client):
    analyze(client, byline="By Transient Person", persist=False)
    matches = client.get("/api/v1/authors", params={"name": "Transient Person"}).json()
    assert matches == []


def test_author_detail_lists_claims_and_articles(client):
    data = analyze(client)
    author_id = data["authors"][0]["id"]
    detail = client.get(f"/api/v1/authors/{author_id}").json()
    assert detail["display_name"] == "Helena Marsh"
    assert detail["recent_articles"]
    assert detail["aliases"]


def test_alias_endpoint_merges_a_second_spelling(client):
    data = analyze(client)
    author_id = data["authors"][0]["id"]

    response = client.post(
        f"/api/v1/authors/{author_id}/aliases",
        json={"name": "H. Marsh", "outlet_domain": "economist.com"},
    )
    assert response.status_code == 200
    assert "h marsh" in response.json()["aliases"]

    same = analyze(
        client,
        url="https://www.economist.com/finance/2024/02/02/another",
        byline="By H. Marsh",
    )
    assert same["authors"][0]["id"] == author_id


def test_verify_then_resolve_updates_the_trust_index(client):
    data = analyze(client)
    author_id = data["authors"][0]["id"]
    claim_id = next(c["id"] for c in data["claims"] if c["kind"] == "prediction")

    verify = client.post(f"/api/v1/claims/{claim_id}/verify", json={"apply": False})
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    assert payload["provider"] == "fixture"
    assert payload["query"]
    assert payload["search_url"].startswith("https://duckduckgo.com/?q=")
    assert payload["applied"] is False

    before = client.get(f"/api/v1/authors/{author_id}").json()["trust"]
    assert before["resolved_claims"] == 0

    resolved = client.post(
        f"/api/v1/claims/{claim_id}/resolution",
        json={"resolution": "false", "notes": "Prices rose."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolution_method"] == "manual"

    after = client.get(f"/api/v1/authors/{author_id}").json()["trust"]
    assert after["resolved_claims"] == 1
    assert after["trust_index"] < before["trust_index"]


def test_reanalysis_preserves_existing_resolutions(client):
    data = analyze(client)
    claim_id = next(c["id"] for c in data["claims"] if c["kind"] == "prediction")
    client.post(f"/api/v1/claims/{claim_id}/resolution", json={"resolution": "true"})

    again = analyze(client)
    kept = [c for c in again["claims"] if c["id"] == claim_id]
    assert kept and kept[0]["resolution"] == "true"


def test_analyze_requires_a_title(client):
    response = client.post(
        "/api/v1/analyze", json={"url": "https://x.test/a", "title": "  ", "body": BODY}
    )
    assert response.status_code == 422


def test_missing_claim_and_author_404(client):
    assert client.get("/api/v1/authors/9999").status_code == 404
    assert client.post("/api/v1/claims/9999/verify", json={}).status_code == 404
