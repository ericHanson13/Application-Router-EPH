"""Tests for the local web page's server. Uses the fake Claude from test_review."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from permit_review.web import make_server
from tests.test_review import OVERVIEW, FakeClient, write_pdf


@pytest.fixture
def server():
    srv = make_server(0, FakeClient(OVERVIEW))  # port 0: pick any free port
    port = srv.server_address[1]
    srv.RequestHandlerClass.port = port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://localhost:{port}"
    srv.shutdown()


def post_pdf(base, data, origin):
    req = urllib.request.Request(f"{base}/api/review?name=sub%2Fpermit.pdf", data=data, method="POST",
                                 headers={"Content-Type": "application/pdf", "Origin": origin})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def test_serves_the_page(server):
    with urllib.request.urlopen(server + "/") as resp:
        assert b"Choose folder" in resp.read()
    with urllib.request.urlopen(server + "/api/status") as resp:
        assert json.loads(resp.read()) == {"api_key_set": True}


def test_reviews_an_uploaded_pdf(server, tmp_path):
    write_pdf(tmp_path / "permit.pdf", pages=3)

    result = post_pdf(server, (tmp_path / "permit.pdf").read_bytes(), origin=server)

    assert result["file"] == "sub/permit.pdf"
    assert result["page_count"] == 3
    assert result["result"] == "FAIL"
    assert result["missing_attachments"] == ["Construction drawings"]


def test_rejects_requests_from_other_websites(server, tmp_path):
    write_pdf(tmp_path / "permit.pdf")
    with pytest.raises(urllib.error.HTTPError) as err:
        post_pdf(server, (tmp_path / "permit.pdf").read_bytes(), origin="https://evil.example")
    assert err.value.code == 403
