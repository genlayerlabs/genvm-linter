"""Unit tests for GenVM artifact version and bundle resolution."""

import json
import urllib.error

from genvm_linter.validate import artifacts


class _FakeResponse:
    """Minimal context-manager stand-in for urllib's HTTP response."""

    headers = {}

    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *_args):
        return json.dumps(self._payload).encode("utf-8")


class TestResolveVersion:
    """resolve_version() precedence: env var > cache > latest release."""

    def test_env_var_takes_precedence(self, monkeypatch):
        monkeypatch.setenv(artifacts.GENVM_VERSION_ENV, "v1.2.3")
        monkeypatch.setattr(artifacts, "list_cached_versions", lambda: ["v0.2.16"])
        monkeypatch.setattr(artifacts, "get_latest_version", lambda: "v0.9.9")

        assert artifacts.resolve_version() == "v1.2.3"

    def test_falls_back_to_newest_cached_version(self, monkeypatch):
        monkeypatch.delenv(artifacts.GENVM_VERSION_ENV, raising=False)
        monkeypatch.setattr(artifacts, "list_cached_versions", lambda: ["v0.2.16"])
        monkeypatch.setattr(artifacts, "get_latest_version", lambda: "v0.9.9")

        assert artifacts.resolve_version() == "v0.2.16"

    def test_falls_back_to_latest_when_no_cache(self, monkeypatch):
        monkeypatch.delenv(artifacts.GENVM_VERSION_ENV, raising=False)
        monkeypatch.setattr(artifacts, "list_cached_versions", lambda: [])
        monkeypatch.setattr(artifacts, "get_latest_version", lambda: "v0.9.9")

        assert artifacts.resolve_version() == "v0.9.9"


class TestGetLatestVersion:
    """get_latest_version() skips pre-releases and assetless releases."""

    def test_skips_releases_without_a_bundle_asset(self, monkeypatch):
        releases = [
            {
                "tag_name": "v0.9.9",
                "prerelease": False,
                "assets": [{"name": "genvm-linux-amd64.tar.xz"}],
            },
            {
                "tag_name": "v0.2.16",
                "prerelease": False,
                "assets": [{"name": "genvm-universal.tar.xz"}],
            },
        ]
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases)
        )

        assert artifacts.get_latest_version() == "v0.2.16"

    def test_accepts_renamed_runners_all_asset(self, monkeypatch):
        releases = [
            {
                "tag_name": "v0.3.0",
                "prerelease": False,
                "assets": [{"name": "genvm-runners-all.tar.xz"}],
            },
            {
                "tag_name": "v0.2.16",
                "prerelease": False,
                "assets": [{"name": "genvm-universal.tar.xz"}],
            },
        ]
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases)
        )

        assert artifacts.get_latest_version() == "v0.3.0"

    def test_skips_prereleases(self, monkeypatch):
        releases = [
            {
                "tag_name": "v0.3.0-rc0",
                "prerelease": True,
                "assets": [{"name": "genvm-runners-all.tar.xz"}],
            },
            {
                "tag_name": "v0.2.16",
                "prerelease": False,
                "assets": [{"name": "genvm-universal.tar.xz"}],
            },
        ]
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases)
        )

        assert artifacts.get_latest_version() == "v0.2.16"

    def test_returns_fallback_when_api_unreachable(self, monkeypatch, capsys):
        def _boom(*a, **k):
            raise OSError("network down")

        monkeypatch.setattr("urllib.request.urlopen", _boom)

        assert artifacts.get_latest_version() == artifacts.FALLBACK_VERSION
        assert "could not resolve latest GenVM version" in capsys.readouterr().err


class TestListCachedVersions:
    """list_cached_versions() orders versions numerically, newest first."""

    def test_orders_versions_numerically(self, monkeypatch, tmp_path):
        monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path)
        for version in ("v0.2.9", "v0.2.16", "v0.10.0"):
            (tmp_path / f"genvm-universal-{version}.tar.xz").write_bytes(b"")

        assert artifacts.list_cached_versions() == ["v0.10.0", "v0.2.16", "v0.2.9"]


class TestListAvailableVersions:
    """list_available_versions() accepts both supported bundle asset names."""

    def test_includes_releases_with_any_supported_bundle_asset(self, monkeypatch):
        releases = [
            {
                "tag_name": "v0.3.0",
                "published_at": "2026-01-02T00:00:00Z",
                "prerelease": False,
                "assets": [{"name": "genvm-runners-all.tar.xz"}],
            },
            {
                "tag_name": "v0.2.16",
                "published_at": "2026-01-01T00:00:00Z",
                "prerelease": False,
                "assets": [{"name": "genvm-universal.tar.xz"}],
            },
            {
                "tag_name": "v0.1.0",
                "published_at": "2025-01-01T00:00:00Z",
                "prerelease": False,
                "assets": [{"name": "genvm-linux-amd64.tar.xz"}],
            },
        ]
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases)
        )

        assert [release["tag"] for release in artifacts.list_available_versions()] == [
            "v0.3.0",
            "v0.2.16",
        ]


class TestDownloadArtifacts:
    """download_artifacts() resolves whichever bundle asset a release ships."""

    @staticmethod
    def _http_404(url):
        return urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    def test_returns_cached_tarball_without_downloading(self, monkeypatch, tmp_path):
        monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path)
        cached = tmp_path / "genvm-universal-v0.2.16.tar.xz"
        cached.write_bytes(b"cached")

        def _fail(*a, **k):
            raise AssertionError("should not download a cached tarball")

        monkeypatch.setattr(artifacts, "_download_to", _fail)

        assert artifacts.download_artifacts("v0.2.16") == cached

    def test_uses_first_available_asset(self, monkeypatch, tmp_path):
        monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path)
        tried = []

        def _download(url, dest, progress_callback=None):
            tried.append(url)
            dest.write_bytes(b"bundle")

        monkeypatch.setattr(artifacts, "_download_to", _download)

        result = artifacts.download_artifacts("v0.3.0")

        assert result == tmp_path / "genvm-universal-v0.3.0.tar.xz"
        assert result.read_bytes() == b"bundle"
        assert tried == [
            f"{artifacts.GITHUB_RELEASES_URL}/download/v0.3.0/genvm-runners-all.tar.xz"
        ]

    def test_falls_back_to_old_asset_on_404(self, monkeypatch, tmp_path):
        monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path)
        tried = []

        def _download(url, dest, progress_callback=None):
            tried.append(url)
            if url.endswith("genvm-runners-all.tar.xz"):
                raise self._http_404(url)
            dest.write_bytes(b"bundle")

        monkeypatch.setattr(artifacts, "_download_to", _download)

        result = artifacts.download_artifacts("v0.2.16")

        assert result.read_bytes() == b"bundle"
        assert [u.rsplit("/", 1)[-1] for u in tried] == list(
            artifacts.RUNNER_BUNDLE_ASSETS
        )

    def test_raises_when_no_asset_found(self, monkeypatch, tmp_path):
        monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path)

        def _download(url, dest, progress_callback=None):
            raise self._http_404(url)

        monkeypatch.setattr(artifacts, "_download_to", _download)

        try:
            artifacts.download_artifacts("v9.9.9")
        except FileNotFoundError as e:
            assert "v9.9.9" in str(e)
        else:
            raise AssertionError("expected FileNotFoundError")
