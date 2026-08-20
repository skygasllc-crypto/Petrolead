"""Shared test helpers."""

from __future__ import annotations


def discover_and_save(client, payload: dict):
    """Run a discover search and save every previewed result — mimics a
    user reviewing results then clicking "Save All". Returns
    (discover_response, save_response)."""
    discover_response = client.post("/api/discover", json=payload)
    assert discover_response.status_code == 200, discover_response.text
    companies = discover_response.json()["companies"]
    save_response = client.post("/api/companies/save-bulk", json={"companies": companies})
    assert save_response.status_code == 200, save_response.text
    return discover_response, save_response


def discover_url_and_save(client, url: str):
    """Run the paste-a-link preview and save it. Returns (preview_response, saved_company)."""
    preview_response = client.post("/api/discover-url", json={"url": url})
    assert preview_response.status_code == 200, preview_response.text
    save_response = client.post("/api/companies/save", json=preview_response.json())
    assert save_response.status_code == 200, save_response.text
    return preview_response, save_response.json()
