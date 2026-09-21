"""Publishing through the Git Data API, against a fake session that records calls."""

import json

import pytest

from gridpulse.charts.site import GitHub, publish


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self.content = b"x" if body is not None else b""
        self._body = body

    def json(self):
        return self._body


class FakeSession:
    """Answers the calls publish() makes; tree shas come from the blob shas."""

    def __init__(self, head_tree=None, branch_exists=True, existing=()):
        self.headers = {}
        self.calls = []
        self.head_tree = head_tree
        self.branch_exists = branch_exists
        self.existing = existing  # paths already on the branch

    def request(self, method, url, timeout, json=None, params=None):
        path = url.split("/repos/o/r")[1]
        self.calls.append((method, path, json))
        if method == "GET" and path.startswith("/git/ref/"):
            if not self.branch_exists:
                return FakeResponse(404, {"message": "Not Found"})
            return FakeResponse(200, {"object": {"sha": "headsha"}})
        if method == "GET" and path.startswith("/git/commits/"):
            return FakeResponse(
                200, {"sha": "headsha", "tree": {"sha": self.head_tree}}
            )
        if method == "GET" and path.startswith("/git/trees/"):
            entries = [{"path": p, "type": "blob"} for p in self.existing]
            return FakeResponse(200, {"tree": entries})
        if path == "/git/blobs":
            return FakeResponse(201, {"sha": "blob-" + json["content"][:6]})
        if path == "/git/trees":
            shas = ",".join(str(e["sha"]) for e in json["tree"])
            return FakeResponse(201, {"sha": f"tree:{shas}"})
        if path == "/git/commits":
            return FakeResponse(201, {"sha": "newcommit"})
        if path.startswith("/git/refs"):
            return FakeResponse(200 if method == "PATCH" else 201, {"ref": "ok"})
        raise AssertionError(f"unexpected call {method} {path}")


FILES = {"index.html": b"<html>", "a.png": b"\x89PNG"}
EXPECTED_TREE = "tree:blob-iVBORw,blob-PGh0bW"  # a.png then index.html, sorted by path


def test_changed_site_is_committed_and_the_branch_moved():
    session = FakeSession(head_tree="older")
    sha = publish(FILES, GitHub("o/r", "tok", session), "main", "msg")
    assert sha == "newcommit"
    methods = [(m, p) for m, p, _ in session.calls]
    assert ("POST", "/git/commits") in methods
    assert ("PATCH", "/git/refs/heads/main") in methods
    commit = next(j for m, p, j in session.calls if p == "/git/commits")
    assert commit["parents"] == ["headsha"]
    assert commit["tree"] == EXPECTED_TREE
    tree = next(j for m, p, j in session.calls if p == "/git/trees")
    assert tree["base_tree"] == "older"  # files the publisher does not own survive


def test_dropped_chart_is_removed_and_unmanaged_files_kept():
    session = FakeSession(
        head_tree="older",
        existing=("README.md", "CNAME", "logo.png", "charts/old.png", "charts/a.png"),
    )
    files = {"index.html": b"<html>", "charts/a.png": b"\x89PNG"}
    publish(files, GitHub("o/r", "tok", session), "main", "msg")
    tree = next(j for m, p, j in session.calls if p == "/git/trees")
    deleted = [e["path"] for e in tree["tree"] if e["sha"] is None]
    assert deleted == ["charts/old.png"]


def test_unchanged_site_makes_no_commit():
    session = FakeSession(head_tree=EXPECTED_TREE)
    assert publish(FILES, GitHub("o/r", "tok", session), "main", "msg") is None
    assert not any(
        p in ("/git/commits", "/git/refs/heads/main") for _, p, _ in session.calls
    )


def test_missing_branch_is_created_with_a_root_commit():
    session = FakeSession(branch_exists=False)
    sha = publish(FILES, GitHub("o/r", "tok", session), "main", "msg")
    assert sha == "newcommit"
    commit = next(j for m, p, j in session.calls if p == "/git/commits")
    assert commit["parents"] == []
    assert ("POST", "/git/refs") in [(m, p) for m, p, _ in session.calls]
    tree = next(j for m, p, j in session.calls if p == "/git/trees")
    assert "base_tree" not in tree


def test_token_goes_in_the_header_and_never_in_errors():
    session = FakeSession()
    github = GitHub("o/r", "secret-token", session)
    assert session.headers["Authorization"] == "Bearer secret-token"

    def failing(method, url, timeout, json=None):
        return FakeResponse(500, {"message": "boom secret-token"})

    session.request = failing
    with pytest.raises(RuntimeError) as err:
        github.head("main")
    assert "secret-token" not in str(err.value)
    assert "500" in str(err.value)


def test_blob_content_is_base64(monkeypatch):
    session = FakeSession()
    GitHub("o/r", "tok", session).blob(b"\x89PNG")
    _, _, body = session.calls[-1]
    assert body == {"content": "iVBORw==", "encoding": "base64"}
    json.dumps(body)  # serialisable as sent
