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
GITHUB_RELEASES_URL = "https://github.com/genlayerlabs/genvm/releases"
GITHUB_API_RELEASES = "https://api.github.com/repos/genlayerlabs/genvm/releases"

# GenVM 0.3.0 renamed this bundle from genvm-universal.tar.xz; newest name first.
RUNNER_BUNDLE_ASSETS = ("genvm-runners-all.tar.xz", "genvm-universal.tar.xz")
GENVM_VERSION_ENV = "GENVM_VERSION"
FALLBACK_VERSION = "v0.2.16"


def get_cache_dir() -> Path:
    """Get the cache directory, creating if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def get_latest_version() -> str:
    """Newest non-prerelease GenVM release that ships a known runner bundle."""
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
        for release in releases:
            if release.get("prerelease") or release.get("draft"):
                continue
            asset_names = {asset.get("name") for asset in release.get("assets", [])}
            if asset_names.intersection(RUNNER_BUNDLE_ASSETS):
                return release["tag_name"]
    except Exception as exc:
        print(
            f"Warning: could not resolve latest GenVM version ({exc}); "
            f"falling back to {FALLBACK_VERSION}",
            file=sys.stderr,
        )
    return FALLBACK_VERSION


def _version_sort_key(version: str) -> tuple[int, ...]:
    """Numeric-component sort key so v0.2.16 ranks above v0.2.9."""
    return tuple(int(n) for n in re.findall(r"\d+", version))


def list_cached_versions() -> list[str]:
    """List all cached GenVM versions, newest first."""
    cache_dir = get_cache_dir()
    versions = []
    for f in cache_dir.glob("genvm-universal-*.tar.xz"):
        version = f.name.replace("genvm-universal-", "").replace(".tar.xz", "")
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
    """Get path to cached tarball for a version."""
    return get_cache_dir() / f"genvm-universal-{version}.tar.xz"


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


def list_available_versions() -> list[dict]:
    """Fetch all available GenVM release versions from GitHub.

    Returns a list of dicts with 'tag', 'date', and 'prerelease' keys,
    sorted newest first.
    """
    url = "https://api.github.com/repos/genlayerlabs/genvm/releases"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
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


def _get_runner_index(tarball_path: Path) -> dict[str, list[str]]:
    """Get or build a cached index of runner members in the tarball.

    First call decompresses the tarball and saves the index as JSON.
    Subsequent calls read the JSON file instantly.
    """
    index_path = tarball_path.with_suffix(tarball_path.suffix + ".index.json")
    if index_path.exists():
        return json.loads(index_path.read_text())

    index: dict[str, list[str]] = {}
    with tarfile.open(tarball_path, "r:xz") as tar:
        for m in tar.getmembers():
            if m.name.startswith("runners/") and m.name.endswith(".tar"):
                parts = m.name.split("/")
                if len(parts) >= 3:
                    runner_type = parts[1]
                    index.setdefault(runner_type, []).append(m.name)

    index_path.write_text(json.dumps(index))
    return index


def find_latest_runner(tarball_path: Path, runner_type: str) -> str | None:
    """Find the latest version hash for a runner type in the tarball.

    Uses a cached index file — no tarball decompression after first call.
    """
    index = _get_runner_index(tarball_path)
    runners = index.get(runner_type, [])

    if runners:
        latest = runners[-1]
        parts = latest.replace(f"runners/{runner_type}/", "").replace(".tar", "")
        dir_part, file_part = parts.split("/")
        return dir_part + file_part
    return None


def extract_runner(tarball_path: Path, runner_type: str, hash_val: str) -> Path:
    """Extract a specific runner from genvm-universal.tar.xz.

    Only decompresses the tarball if the runner isn't already cached on disk.
    """
    version = tarball_path.stem.replace("genvm-universal-", "")
    extract_base = get_cache_dir() / "extracted" / version
    runner_path = extract_base / runner_type / hash_val

    if runner_path.exists() and any(runner_path.iterdir()):
        return runner_path

    runner_path.mkdir(parents=True, exist_ok=True)
    tar_member_path = hash_to_tar_path(runner_type, hash_val)

    try:
        with tarfile.open(tarball_path, "r:xz") as outer_tar:
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
