"""Download and cache GenVM release artifacts."""

import json
import tarfile
import urllib.request
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "genvm-linter"
GITHUB_RELEASES_URL = "https://github.com/genlayerlabs/genvm/releases"


def get_cache_dir() -> Path:
    """Get the cache directory, creating if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def get_latest_version() -> str:
    """Fetch the latest GenVM release version from GitHub."""
    url = f"{GITHUB_RELEASES_URL}/latest"
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req) as response:
        # GitHub redirects to /releases/tag/vX.Y.Z
        final_url = response.geturl()
        version = final_url.split("/")[-1]
        return version


def get_tarball_path(version: str) -> Path:
    """Get path to cached tarball for a version."""
    return get_cache_dir() / f"genvm-universal-{version}.tar.xz"


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
        version = get_latest_version()

    tarball_path = get_tarball_path(version)

    if tarball_path.exists():
        return tarball_path

    url = f"{GITHUB_RELEASES_URL}/download/{version}/genvm-universal.tar.xz"

    def report_progress(block_num, block_size, total_size):
        if progress_callback:
            downloaded = block_num * block_size
            progress_callback(downloaded, total_size)

    try:
        urllib.request.urlretrieve(url, tarball_path, report_progress)
        return tarball_path
    except Exception:
        if tarball_path.exists():
            tarball_path.unlink()
        raise


def list_cached_versions() -> list[str]:
    """List all cached GenVM versions."""
    cache_dir = get_cache_dir()
    versions = []
    for f in cache_dir.glob("genvm-universal-*.tar.xz"):
        # Remove "genvm-universal-" prefix and ".tar" from stem (since .tar.xz has double extension)
        version = f.name.replace("genvm-universal-", "").replace(".tar.xz", "")
        versions.append(version)
    return sorted(versions)


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


def extract_runner(tarball_path: Path, runner_type: str, hash_val: str) -> Path:
    """
    Extract a specific runner from genvm-universal.tar.xz.

    Returns:
        Path to extracted runner directory.
    """
    version = tarball_path.stem.replace("genvm-universal-", "")
    extract_base = get_cache_dir() / "extracted" / version
    runner_path = extract_base / runner_type / hash_val

    if runner_path.exists():
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


def find_latest_runner(tarball_path: Path, runner_type: str) -> str | None:
    """Find the latest version hash for a runner type in the tarball."""
    with tarfile.open(tarball_path, "r:xz") as tar:
        runners = [
            m.name
            for m in tar.getmembers()
            if m.name.startswith(f"runners/{runner_type}/") and m.name.endswith(".tar")
        ]

        if runners:
            latest = runners[-1]
            parts = latest.replace(f"runners/{runner_type}/", "").replace(".tar", "")
            dir_part, file_part = parts.split("/")
            return dir_part + file_part
    return None


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


def clean_cache(keep_versions: list[str] | None = None, keep_latest: bool = True) -> tuple[int, int]:
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
