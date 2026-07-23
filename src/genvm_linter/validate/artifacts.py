"""Download and cache GenVM release artifacts."""

import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "genvm-linter"
GENVM_REPO = os.environ.get("GENVM_REPO", "genlayerlabs/genvm-manager")
GITHUB_RELEASES_URL = f"https://github.com/{GENVM_REPO}/releases"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{GENVM_REPO}/releases"

# GenVM 0.3.0 renamed this bundle from genvm-universal.tar.xz; newest name first.
RUNNER_BUNDLE_ASSETS = ("genvm-runners-all.tar.xz", "genvm-universal.tar.xz")
GENVM_VERSION_ENV = "GENVM_VERSION"
GENVM_ALLOW_PRERELEASE_ENV = "GENVM_ALLOW_PRERELEASE"
GENVM_SOURCE_MODE_ENV = "GENVM_SOURCE_MODE"
GENVM_PREBUILT_DIR_ENV = "GENVM_PREBUILT_DIR"
GENVMROOT_ENV = "GENVMROOT"
FALLBACK_VERSION = "v0.6.0-rc1"
RUNNER_INDEX_VERSION = 2


def get_cache_dir() -> Path:
    """Get the cache directory, creating if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def get_latest_version() -> str:
    """Resolve the newest suitable GenVM release that ships a known runner bundle.

    Stable releases are preferred by default. If none exist, the newest prerelease
    is used so the prerelease-only genvm-manager repository works out of the box.
    GENVM_ALLOW_PRERELEASE=1 opts into prereleases even when a stable release exists.
    """
    try:
        req = urllib.request.Request(
            f"{GITHUB_API_RELEASES}?per_page=100",
            headers={
                "User-Agent": "genvm-linter",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            releases = json.loads(response.read().decode("utf-8"))
        prerelease_candidate: str | None = None
        allow_prerelease = os.environ.get(GENVM_ALLOW_PRERELEASE_ENV) == "1"
        for release in releases:
            if release.get("draft"):
                continue
            asset_names = {asset.get("name") for asset in release.get("assets", [])}
            if not asset_names.intersection(RUNNER_BUNDLE_ASSETS):
                continue
            if release.get("prerelease"):
                if allow_prerelease:
                    return release["tag_name"]
                if prerelease_candidate is None:
                    prerelease_candidate = release["tag_name"]
                continue
            return release["tag_name"]
        if prerelease_candidate is not None:
            return prerelease_candidate
        print(
            f"Warning: no release in {GENVM_REPO} ships a known runner bundle "
            f"({', '.join(RUNNER_BUNDLE_ASSETS)}); falling back to "
            f"{FALLBACK_VERSION}, which may not exist in that repository",
            file=sys.stderr,
        )
    except Exception as exc:
        print(
            f"Warning: could not resolve latest GenVM version from {GENVM_REPO} "
            f"({exc}); falling back to {FALLBACK_VERSION}",
            file=sys.stderr,
        )
    return FALLBACK_VERSION


def _version_sort_key(version: str) -> tuple[int, ...]:
    """Numeric-component sort key so v0.2.16 ranks above v0.2.9."""
    return tuple(int(n) for n in re.findall(r"\d+", version))


def _cache_repo_slug() -> str:
    """Filesystem-safe form of GENVM_REPO, used to namespace cached bundles."""
    return GENVM_REPO.replace("/", "-")


def _cache_prefix() -> str:
    return f"genvm-universal-{_cache_repo_slug()}-"


def list_cached_versions() -> list[str]:
    """List cached GenVM versions for the CURRENT repo, newest first.

    Bundles are namespaced by repository. Versions are not unique across
    repositories, and their contents differ (runner sets, SDK layout), so an
    unqualified cache would let a bundle downloaded from one repo satisfy a
    request aimed at another. Legacy unqualified files are deliberately
    ignored: they predate the genvm -> genvm-manager split and are exactly
    the bundles that must not be reused.
    """
    cache_dir = get_cache_dir()
    prefix = _cache_prefix()
    versions = []
    for f in cache_dir.glob(f"{prefix}*.tar.xz"):
        version = f.name[len(prefix) :].replace(".tar.xz", "")
        versions.append(version)
    return sorted(versions, key=_version_sort_key, reverse=True)


def resolve_version() -> str:
    """GenVM version to use: GENVM_VERSION env var > newest cached > latest release."""
    pinned = os.environ.get(GENVM_VERSION_ENV)
    if pinned:
        return pinned
    cached = list_cached_versions()
    if cached:
        return cached[0]
    return get_latest_version()


def get_tarball_path(version: str) -> Path:
    """Get path to cached tarball for a version of the current repo."""
    return get_cache_dir() / f"{_cache_prefix()}{version}.tar.xz"


def _download_to(url: str, dest: Path, progress_callback=None) -> None:
    """Stream url to dest, replacing it atomically on success."""
    req = urllib.request.Request(url, headers={"User-Agent": "genvm-linter"})
    tmp_path = None
    downloaded = 0

    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            total = int(response.headers.get("Content-Length", 0))
            with tempfile.NamedTemporaryFile(delete=False, dir=dest.parent) as tmp:
                tmp_path = Path(tmp.name)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
        os.replace(tmp_path, dest)
    except Exception:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
        raise


def download_artifacts(version: str | None = None, progress_callback=None) -> Path:
    """
    Download genvm-universal.tar.xz from GitHub releases.

    Args:
        version: GenVM version (e.g., "v0.2.12"). If None, uses latest.
        progress_callback: Optional callback(downloaded_bytes, total_bytes)

    Returns:
        Path to the downloaded tarball.
    """
    if version is None:
        version = resolve_version()

    tarball_path = get_tarball_path(version)

    if tarball_path.exists():
        return tarball_path

    last_error: Exception | None = None
    for asset in RUNNER_BUNDLE_ASSETS:
        url = f"{GITHUB_RELEASES_URL}/download/{version}/{asset}"
        try:
            _download_to(url, tarball_path, progress_callback)
            return tarball_path
        except urllib.error.HTTPError as e:
            if e.code == 404:
                last_error = e
                continue
            raise

    raise FileNotFoundError(
        f"No GenVM runner bundle for {version}; tried {', '.join(RUNNER_BUNDLE_ASSETS)}"
    ) from last_error


def _configured_prebuilt_root() -> tuple[str, Path] | None:
    """Return the configured prebuilt root and the env var that selected it."""
    for env_var in (GENVM_PREBUILT_DIR_ENV, GENVMROOT_ENV):
        value = os.environ.get(env_var)
        if value:
            return env_var, Path(value).expanduser()
    return None


def _prebuilt_root_error(root: Path) -> str | None:
    """Describe why a path is not a usable GenVM tree."""
    if not root.is_dir():
        return "the path is not a directory"

    missing = []
    if not (root / "bin" / "genvm-modules").is_file():
        missing.append("bin/genvm-modules")
    if not (root / "runners").is_dir():
        missing.append("runners/")
    if missing:
        return f"missing {', '.join(missing)}"
    return None


def resolve_artifact_source(
    version: str | None = None,
    progress_callback=None,
) -> Path:
    """Resolve a prebuilt GenVM tree or a downloaded release bundle.

    GENVM_SOURCE_MODE=prebuilt requires a usable tree and never downloads.
    GENVM_SOURCE_MODE=release always uses the release bundle. With no explicit
    mode, a usable configured tree wins and an absent or unusable tree falls
    back to the existing release behavior.
    """
    mode = os.environ.get(GENVM_SOURCE_MODE_ENV, "").strip()
    if mode not in {"", "prebuilt", "release"}:
        raise ValueError(
            f"Invalid {GENVM_SOURCE_MODE_ENV}={mode!r}; expected 'prebuilt', "
            "'release', or an empty value for auto mode"
        )

    configured = _configured_prebuilt_root()
    if mode != "release" and configured is not None:
        env_var, root = configured
        error = _prebuilt_root_error(root)
        if error is None:
            return root
        if mode == "prebuilt":
            raise RuntimeError(
                f"{GENVM_SOURCE_MODE_ENV}=prebuilt selected {env_var}={str(root)!r}, "
                f"but that GenVM tree is unusable: {error}. Build GenVM first or "
                f"point {GENVM_PREBUILT_DIR_ENV} at a tree containing "
                "bin/genvm-modules and runners/."
            )

    if mode == "prebuilt":
        raise RuntimeError(
            f"{GENVM_SOURCE_MODE_ENV}=prebuilt requires {GENVM_PREBUILT_DIR_ENV} "
            f"(preferred) or {GENVMROOT_ENV} to point at a GenVM tree containing "
            "bin/genvm-modules and runners/."
        )

    return download_artifacts(version, progress_callback=progress_callback)


def list_available_versions() -> list[dict]:
    """Fetch all available GenVM release versions from GitHub.

    Returns a list of dicts with 'tag', 'date', and 'prerelease' keys,
    sorted newest first.
    """
    req = urllib.request.Request(
        GITHUB_API_RELEASES,
        headers={"Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as response:
        releases = json.loads(response.read().decode("utf-8"))

    return [
        {
            "tag": r["tag_name"],
            "date": r["published_at"][:10],
            "prerelease": r.get("prerelease", False),
        }
        for r in releases
        if {a.get("name") for a in r.get("assets", [])}.intersection(RUNNER_BUNDLE_ASSETS)
    ]


def hash_to_tar_path(runner_type: str, hash_val: str) -> str:
    """
    Convert a dependency hash to the path inside genvm-universal.tar.xz.

    Example:
      py-lib-genlayer-std, 0asq35p8mzlzwgxcrx5v51srnsqyj72cq7993way1vqddwxcvkq4
      -> runners/py-lib-genlayer-std/0a/sq35p8mzlzwgxcrx5v51srnsqyj72cq7993way1vqddwxcvkq4.tar
    """
    dir_prefix = hash_val[:2]
    file_suffix = hash_val[2:]
    return f"runners/{runner_type}/{dir_prefix}/{file_suffix}.tar"


def _get_bundle_runner_index(tarball_path: Path) -> dict[str, list[str]]:
    """Get or build a cached index of runner members in the tarball.

    First call decompresses the tarball and saves the index as JSON.
    Subsequent calls read the JSON file instantly.
    """
    index_path = tarball_path.with_suffix(
        tarball_path.suffix + f".index-v{RUNNER_INDEX_VERSION}.json"
    )
    if index_path.exists():
        return json.loads(index_path.read_text())

    index: dict[str, list[str]] = {}
    with tarfile.open(tarball_path, "r:xz") as tar:
        for m in tar.getmembers():
            if m.name.startswith("runners/") and m.name.endswith(".tar"):
                parts = m.name.split("/")
                if len(parts) >= 4:
                    runner_type = parts[1]
                    index.setdefault(runner_type, []).append(m.name)
            elif m.name.startswith("executor/") and m.name.endswith(".tar"):
                parts = m.name.split("/")
                if len(parts) >= 6 and parts[2] == "legacy-runners":
                    runner_type = parts[3]
                    index.setdefault(runner_type, []).append(m.name)

    index_path.write_text(json.dumps(index))
    return index


def _get_prebuilt_runner_index(root: Path) -> dict[str, list[str]]:
    """Index runner tarballs directly from a prebuilt GenVM tree."""
    index: dict[str, list[str]] = {}

    current_root = root / "runners"
    for runner_path in sorted(current_root.glob("*/*/*.tar")):
        relative_path = runner_path.relative_to(root).as_posix()
        runner_type = relative_path.split("/")[1]
        index.setdefault(runner_type, []).append(relative_path)

    executor_root = root / "executor"
    for runner_path in sorted(executor_root.glob("*/legacy-runners/*/*/*.tar")):
        relative_path = runner_path.relative_to(root).as_posix()
        runner_type = relative_path.split("/")[3]
        index.setdefault(runner_type, []).append(relative_path)

    return index


def _get_runner_index(artifact_path: Path) -> dict[str, list[str]]:
    """Get the runner index for either a release bundle or prebuilt tree."""
    if artifact_path.is_dir():
        return _get_prebuilt_runner_index(artifact_path)
    return _get_bundle_runner_index(artifact_path)


def _runner_hash_from_tar_path(tar_member_path: str) -> str:
    """Recover a runner hash from either supported bundle member layout."""
    parts = tar_member_path.split("/")
    return parts[-2] + parts[-1].removesuffix(".tar")


def _select_runner_tar_path(
    runner_paths: list[str],
    runner_type: str,
    hash_val: str,
) -> str:
    """Select a runner path, preferring the current layout over legacy."""
    current_path = hash_to_tar_path(runner_type, hash_val)
    if current_path in runner_paths:
        return current_path

    legacy_suffix = f"/legacy-runners/{runner_type}/{hash_val[:2]}/{hash_val[2:]}.tar"
    for runner_path in runner_paths:
        if runner_path.startswith("executor/") and runner_path.endswith(legacy_suffix):
            return runner_path
    return current_path


def _find_runner_tar_path(
    artifact_path: Path,
    runner_type: str,
    hash_val: str,
) -> str:
    """Find a runner in either source, preferring current layout over legacy."""
    runners = _get_runner_index(artifact_path).get(runner_type, [])
    return _select_runner_tar_path(runners, runner_type, hash_val)


def find_latest_runner(artifact_path: Path, runner_type: str) -> str | None:
    """Find the latest version hash for a runner type in the artifact source.

    Release bundles use a cached index file, avoiding repeat decompression.
    """
    index = _get_runner_index(artifact_path)
    runners = index.get(runner_type, [])

    if runners:
        current_runners = [path for path in runners if path.startswith("runners/")]
        latest = (current_runners or runners)[-1]
        return _runner_hash_from_tar_path(latest)
    return None


def extract_runner(artifact_path: Path, runner_type: str, hash_val: str) -> Path:
    """Extract a specific runner from a bundle or prebuilt GenVM tree.

    Only extracts the runner if it is not already cached on disk.
    """
    if artifact_path.is_dir():
        source_namespace = "prebuilt"
    else:
        source_namespace = artifact_path.stem.replace("genvm-universal-", "")
    extract_base = get_cache_dir() / "extracted" / source_namespace
    runner_path = extract_base / runner_type / hash_val

    if runner_path.exists() and any(runner_path.iterdir()):
        return runner_path

    runner_path.mkdir(parents=True, exist_ok=True)

    try:
        tar_member_path = _find_runner_tar_path(artifact_path, runner_type, hash_val)
        if artifact_path.is_dir():
            with tarfile.open(artifact_path / tar_member_path, mode="r:") as inner_tar:
                inner_tar.extractall(runner_path, filter="data")
        else:
            with tarfile.open(artifact_path, "r:xz") as outer_tar:
                inner_tar_member = outer_tar.getmember(tar_member_path)
                inner_tar_file = outer_tar.extractfile(inner_tar_member)

                if inner_tar_file is None:
                    raise RuntimeError(f"Could not extract {tar_member_path}")

                with tarfile.open(fileobj=inner_tar_file, mode="r:") as inner_tar:
                    inner_tar.extractall(runner_path, filter="data")

        return runner_path
    except Exception:
        if runner_path.exists():
            import shutil

            shutil.rmtree(runner_path)
        raise


def parse_runner_manifest(runner_path: Path) -> dict[str, str]:
    """Parse runner.json to get dependency versions."""
    runner_json = runner_path / "runner.json"
    if not runner_json.exists():
        return {}

    content = json.loads(runner_json.read_text())
    deps = {}
    for item in content.get("Seq", []):
        if "Depends" in item:
            dep = item["Depends"]
            name, hash_val = dep.rsplit(":", 1)
            deps[name] = hash_val
    return deps


def clean_cache(
    keep_versions: list[str] | None = None,
    keep_latest: bool = True,
) -> tuple[int, int]:
    """
    Clean cached GenVM artifacts.

    Args:
        keep_versions: List of versions to keep (e.g., ["v0.2.12"])
        keep_latest: If True, always keep the latest version

    Returns:
        Tuple of (files_deleted, bytes_freed)
    """
    import shutil

    keep = set(keep_versions or [])
    if keep_latest:
        try:
            latest = get_latest_version()
            keep.add(latest)
        except Exception:
            pass  # Network error, skip

    files_deleted = 0
    bytes_freed = 0

    # Clean tarballs
    for f in get_cache_dir().glob("genvm-universal-*.tar.xz"):
        version = f.name.replace("genvm-universal-", "").replace(".tar.xz", "")
        if version not in keep:
            bytes_freed += f.stat().st_size
            f.unlink()
            files_deleted += 1

    # Clean extracted directories
    extracted_dir = get_cache_dir() / "extracted"
    if extracted_dir.exists():
        for d in extracted_dir.iterdir():
            if d.is_dir() and d.name not in keep:
                for f in d.rglob("*"):
                    if f.is_file():
                        bytes_freed += f.stat().st_size
                        files_deleted += 1
                shutil.rmtree(d)

    # Clean stubs
    stubs_dir = get_cache_dir() / "stubs"
    if stubs_dir.exists():
        for d in stubs_dir.iterdir():
            if d.is_dir() and d.name not in keep:
                for f in d.rglob("*"):
                    if f.is_file():
                        bytes_freed += f.stat().st_size
                        files_deleted += 1
                shutil.rmtree(d)

    return files_deleted, bytes_freed
