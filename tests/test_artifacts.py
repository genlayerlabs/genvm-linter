"""Unit tests for GenVM artifact version and bundle resolution."""

import importlib
import io
import json
import tarfile
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
    """get_latest_version() resolves stable and prerelease manager releases."""

    def test_skips_releases_without_a_bundle_asset(self, monkeypatch):
        monkeypatch.delenv(artifacts.GENVM_ALLOW_PRERELEASE_ENV, raising=False)
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
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases))

        assert artifacts.get_latest_version() == "v0.2.16"

    def test_accepts_renamed_runners_all_asset(self, monkeypatch):
        monkeypatch.delenv(artifacts.GENVM_ALLOW_PRERELEASE_ENV, raising=False)
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
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases))

        assert artifacts.get_latest_version() == "v0.3.0"

    def test_skips_prereleases(self, monkeypatch):
        monkeypatch.delenv(artifacts.GENVM_ALLOW_PRERELEASE_ENV, raising=False)
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
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases))

        assert artifacts.get_latest_version() == "v0.2.16"

    def test_uses_prerelease_when_repo_has_no_stable_release(self, monkeypatch):
        monkeypatch.delenv(artifacts.GENVM_ALLOW_PRERELEASE_ENV, raising=False)
        releases = [
            {
                "tag_name": "v0.6.0-rc1",
                "prerelease": True,
                "assets": [{"name": "genvm-universal.tar.xz"}],
            },
            {
                "tag_name": "v0.6.0-rc0",
                "prerelease": True,
                "assets": [{"name": "genvm-universal.tar.xz"}],
            },
        ]
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases))

        assert artifacts.get_latest_version() == "v0.6.0-rc1"

    def test_prerelease_opt_in_prefers_newer_prerelease(self, monkeypatch):
        monkeypatch.setenv(artifacts.GENVM_ALLOW_PRERELEASE_ENV, "1")
        releases = [
            {
                "tag_name": "v0.7.0-rc0",
                "prerelease": True,
                "assets": [{"name": "genvm-universal.tar.xz"}],
            },
            {
                "tag_name": "v0.6.0",
                "prerelease": False,
                "assets": [{"name": "genvm-universal.tar.xz"}],
            },
        ]
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases))

        assert artifacts.get_latest_version() == "v0.7.0-rc0"

    def test_returns_fallback_when_api_unreachable(self, monkeypatch, capsys):
        def _boom(*a, **k):
            raise OSError("network down")

        monkeypatch.setattr("urllib.request.urlopen", _boom)

        assert artifacts.get_latest_version() == artifacts.FALLBACK_VERSION
        assert "could not resolve latest GenVM version" in capsys.readouterr().err


class TestRepositoryResolution:
    """Release URLs share the manager repository source of truth."""

    def test_defaults_to_genvm_manager(self, monkeypatch):
        try:
            with monkeypatch.context() as context:
                context.delenv("GENVM_REPO", raising=False)
                reloaded = importlib.reload(artifacts)
            assert reloaded.GENVM_REPO == "genlayerlabs/genvm-manager"
            assert reloaded.GITHUB_RELEASES_URL == (
                "https://github.com/genlayerlabs/genvm-manager/releases"
            )
            assert reloaded.GITHUB_API_RELEASES == (
                "https://api.github.com/repos/genlayerlabs/genvm-manager/releases"
            )
        finally:
            importlib.reload(artifacts)

    def test_genvm_repo_environment_override(self, monkeypatch):
        try:
            with monkeypatch.context() as context:
                context.setenv("GENVM_REPO", "example/custom-genvm")
                reloaded = importlib.reload(artifacts)
            assert reloaded.GENVM_REPO == "example/custom-genvm"
            assert reloaded.GITHUB_RELEASES_URL == (
                "https://github.com/example/custom-genvm/releases"
            )
            assert reloaded.GITHUB_API_RELEASES == (
                "https://api.github.com/repos/example/custom-genvm/releases"
            )
        finally:
            importlib.reload(artifacts)


class TestListCachedVersions:
    """list_cached_versions() orders versions numerically, newest first."""

    def test_orders_versions_numerically(self, monkeypatch, tmp_path):
        monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path)
        for version in ("v0.2.9", "v0.2.16", "v0.10.0"):
            (tmp_path / f"{artifacts._cache_prefix()}{version}.tar.xz").write_bytes(b"")

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
        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResponse(releases))

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
        cached = tmp_path / f"{artifacts._cache_prefix()}v0.2.16.tar.xz"
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

        assert result == tmp_path / f"{artifacts._cache_prefix()}v0.3.0.tar.xz"
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
        assert [u.rsplit("/", 1)[-1] for u in tried] == list(artifacts.RUNNER_BUNDLE_ASSETS)

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


class TestRunnerPathLookup:
    """Runner lookup supports current and manager legacy bundle layouts."""

    def test_extract_runner_falls_back_to_legacy_prefix(self, monkeypatch, tmp_path):
        monkeypatch.setattr(artifacts, "CACHE_DIR", tmp_path / "cache")
        runner_hash = "1jb45aa8legacyhash"
        legacy_path = (
            f"executor/v0.2.17/legacy-runners/py-genlayer/{runner_hash[:2]}/{runner_hash[2:]}.tar"
        )

        inner_bytes = io.BytesIO()
        with tarfile.open(fileobj=inner_bytes, mode="w") as inner_tar:
            payload = b'{"Seq": []}'
            member = tarfile.TarInfo("runner.json")
            member.size = len(payload)
            inner_tar.addfile(member, io.BytesIO(payload))

        tarball_path = tmp_path / f"{artifacts._cache_prefix()}v0.6.0-rc1.tar.xz"
        with tarfile.open(tarball_path, mode="w:xz") as outer_tar:
            member = tarfile.TarInfo(legacy_path)
            member.size = len(inner_bytes.getvalue())
            outer_tar.addfile(member, io.BytesIO(inner_bytes.getvalue()))

        index = artifacts._get_runner_index(tarball_path)
        extracted = artifacts.extract_runner(
            tarball_path,
            "py-genlayer",
            runner_hash,
        )

        assert index["py-genlayer"] == [legacy_path]
        assert (extracted / "runner.json").read_bytes() == b'{"Seq": []}'

    def test_find_latest_runner_prefers_current_layout(self, monkeypatch, tmp_path):
        tarball_path = tmp_path / "bundle.tar.xz"
        monkeypatch.setattr(
            artifacts,
            "_get_runner_index",
            lambda _path: {
                "py-genlayer": [
                    "executor/v0.2.17/legacy-runners/py-genlayer/1j/legacy.tar",
                    "runners/py-genlayer/9b/current.tar",
                ]
            },
        )

        assert artifacts.find_latest_runner(tarball_path, "py-genlayer") == "9bcurrent"


class TestCacheRepositoryNamespacing:
    """Cached bundles must not be shared across repositories.

    Versions are not unique across repos and their contents differ, so an
    unqualified cache would let an old genvm bundle satisfy a genvm-manager
    request -- silently validating against the wrong SDK era.
    """

    def test_ignores_bundles_cached_for_another_repo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(artifacts, "get_cache_dir", lambda: tmp_path)
        # A bundle cached under a different repo's namespace.
        (tmp_path / "genvm-universal-example-other-v9.9.9.tar.xz").write_bytes(b"")
        assert artifacts.list_cached_versions() == []

    def test_ignores_legacy_unqualified_bundles(self, tmp_path, monkeypatch):
        monkeypatch.setattr(artifacts, "get_cache_dir", lambda: tmp_path)
        # Pre-split layout: exactly the bundles that must never be reused.
        (tmp_path / "genvm-universal-v0.3.0-rc3.tar.xz").write_bytes(b"")
        assert artifacts.list_cached_versions() == []

    def test_lists_bundles_for_the_current_repo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(artifacts, "get_cache_dir", lambda: tmp_path)
        prefix = artifacts._cache_prefix()
        (tmp_path / f"{prefix}v0.6.0-rc1.tar.xz").write_bytes(b"")
        assert artifacts.list_cached_versions() == ["v0.6.0-rc1"]

    def test_stale_foreign_cache_does_not_win_resolution(self, tmp_path, monkeypatch):
        """The regression this guards: an existing user's old-repo cache must
        not short-circuit resolution and defeat the repo repoint."""
        monkeypatch.setattr(artifacts, "get_cache_dir", lambda: tmp_path)
        monkeypatch.delenv(artifacts.GENVM_VERSION_ENV, raising=False)
        (tmp_path / "genvm-universal-v0.3.0-rc3.tar.xz").write_bytes(b"")
        monkeypatch.setattr(artifacts, "get_latest_version", lambda: "v0.6.0-rc1")
        assert artifacts.resolve_version() == "v0.6.0-rc1"


class TestNoBundledReleaseWarning:
    def test_warns_when_no_release_ships_a_bundle(self, monkeypatch, capsys):
        payload = [{"tag_name": "v1.0.0", "prerelease": False, "assets": []}]
        monkeypatch.setattr(
            artifacts.urllib.request,
            "urlopen",
            lambda *a, **k: _FakeResponse(payload),
        )
        assert artifacts.get_latest_version() == artifacts.FALLBACK_VERSION
        assert "ships a known runner bundle" in capsys.readouterr().err
