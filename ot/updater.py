"""
Update management for Obsidian Timemachine.

Provides functionality to check for updates and upgrade to the latest version.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .logger import get_logger


# GitHub repository information
GITHUB_OWNER = "StrongTechProject"
GITHUB_REPO = "Obsidian-TimeMachine"
GITHUB_API_BASE = "https://api.github.com"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"

# Request timeout in seconds
REQUEST_TIMEOUT = 15


class UpdateError(Exception):
    """Raised when update operations fail."""
    pass


@dataclass
class UpdateInfo:
    """Information about available updates.
    
    Attributes:
        current_version: Currently installed version.
        latest_version: Latest available version on GitHub.
        is_latest: True if current version is the latest.
        release_url: URL to the release page.
        release_notes: Release notes/description (if available).
        published_at: Release publication date.
    """
    current_version: str
    latest_version: str
    is_latest: bool
    release_url: str | None = None
    release_notes: str | None = None
    published_at: str | None = None


def get_current_version() -> str:
    """Get the currently installed version of obsidian-timemachine.
    
    Returns:
        Version string (e.g., "0.1.0").
        
    Raises:
        UpdateError: If version cannot be determined.
    """
    try:
        from importlib.metadata import version
        return version("obsidian-timemachine")
    except Exception:
        # Fallback: try to read from pyproject.toml
        try:
            pyproject = Path(__file__).parent.parent / "pyproject.toml"
            if pyproject.exists():
                content = pyproject.read_text()
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        except Exception:
            pass
        
        raise UpdateError("Cannot determine current version")


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a semantic version string into a tuple of integers.
    
    Handles versions like "0.1.0", "v0.1.0", "0.1.0-beta".
    
    Args:
        version_str: Version string to parse.
        
    Returns:
        Tuple of version components (major, minor, patch, ...).
    """
    # Remove 'v' prefix if present
    version_str = version_str.lstrip("v")
    
    # Remove pre-release suffix (e.g., "-beta", "-rc1")
    version_str = re.split(r"[-+]", version_str)[0]
    
    # Split and convert to integers
    parts = []
    for part in version_str.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            # Extract leading digits
            match = re.match(r"(\d+)", part)
            if match:
                parts.append(int(match.group(1)))
    
    return tuple(parts) if parts else (0,)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semantic version strings.
    
    Args:
        v1: First version string.
        v2: Second version string.
        
    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2.
    """
    parsed_v1 = parse_version(v1)
    parsed_v2 = parse_version(v2)
    
    # Pad shorter tuple with zeros
    max_len = max(len(parsed_v1), len(parsed_v2))
    padded_v1 = parsed_v1 + (0,) * (max_len - len(parsed_v1))
    padded_v2 = parsed_v2 + (0,) * (max_len - len(parsed_v2))
    
    if padded_v1 < padded_v2:
        return -1
    elif padded_v1 > padded_v2:
        return 1
    else:
        return 0


def _fetch_github_api(endpoint: str) -> dict[str, Any]:
    """Fetch data from GitHub API.
    
    Args:
        endpoint: API endpoint (e.g., "/repos/owner/repo/releases/latest").
        
    Returns:
        Parsed JSON response.
        
    Raises:
        UpdateError: If the request fails.
    """
    url = f"{GITHUB_API_BASE}{endpoint}"
    
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"obsidian-timemachine/{get_current_version()}",
        },
    )
    
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            raise UpdateError("Repository or release not found")
        elif e.code == 403:
            raise UpdateError("GitHub API rate limit exceeded. Try again later.")
        else:
            raise UpdateError(f"GitHub API error: {e.code} {e.reason}")
    except URLError as e:
        raise UpdateError(f"Network error: {e.reason}")
    except json.JSONDecodeError as e:
        raise UpdateError(f"Invalid API response: {e}")
    except TimeoutError:
        raise UpdateError("Request timed out")


def get_latest_release() -> dict[str, Any]:
    """Get the latest release information from GitHub.
    
    Returns:
        Release data dictionary.
        
    Raises:
        UpdateError: If no releases are found or request fails.
    """
    try:
        return _fetch_github_api(f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest")
    except UpdateError as e:
        if "not found" in str(e).lower():
            # Try getting the latest tag instead
            return _get_latest_tag()
        raise


def _get_latest_tag() -> dict[str, Any]:
    """Get the latest tag as a fallback when no releases exist.
    
    Returns:
        Simulated release data from tag.
        
    Raises:
        UpdateError: If no tags are found.
    """
    tags = _fetch_github_api(f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/tags")
    
    if not tags:
        raise UpdateError("No releases or tags found")
    
    latest_tag = tags[0]
    return {
        "tag_name": latest_tag["name"],
        "html_url": f"{GITHUB_REPO_URL}/releases/tag/{latest_tag['name']}",
        "body": None,
        "published_at": None,
    }


def check_for_updates() -> UpdateInfo:
    """Check if a new version is available.
    
    Returns:
        UpdateInfo with current and latest version details.
        
    Raises:
        UpdateError: If version check fails.
    """
    current = get_current_version()
    release = get_latest_release()
    
    latest = release.get("tag_name", "").lstrip("v")
    if not latest:
        raise UpdateError("Cannot determine latest version from release")
    
    is_latest = compare_versions(current, latest) >= 0
    
    return UpdateInfo(
        current_version=current,
        latest_version=latest,
        is_latest=is_latest,
        release_url=release.get("html_url"),
        release_notes=release.get("body"),
        published_at=release.get("published_at"),
    )


def perform_update(force: bool = False) -> bool:
    """Perform the update to the latest version.
    
    This uses pip to upgrade the package from the GitHub repository.
    
    Args:
        force: If True, reinstall even if already at latest version.
        
    Returns:
        True if update was successful.
        
    Raises:
        UpdateError: If update fails.
    """
    logger = get_logger()
    
    # Check if update is needed
    if not force:
        try:
            info = check_for_updates()
            if info.is_latest:
                logger.info(f"✅ Already at the latest version ({info.current_version})")
                return True
        except UpdateError:
            # Continue with update if check fails
            pass
    
    # Build pip command
    pip_url = f"git+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git"
    
    # Determine pip command
    pip_cmd = [sys.executable, "-m", "pip"]
    
    # Check if we're in a virtual environment
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    
    install_args = ["install", "--upgrade", pip_url]
    
    # Use --user if not in a virtual environment
    if not in_venv:
        install_args.insert(1, "--user")
    
    full_cmd = pip_cmd + install_args
    
    logger.info(f"📦 Running: {' '.join(full_cmd)}")
    
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for installation
        )
        
        if result.returncode == 0:
            logger.info("✅ Update completed successfully!")
            logger.info("   Please restart the application to use the new version.")
            return True
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise UpdateError(f"pip install failed: {error_msg}")
            
    except subprocess.TimeoutExpired:
        raise UpdateError("Update timed out after 5 minutes")
    except subprocess.SubprocessError as e:
        raise UpdateError(f"Failed to run pip: {e}")


def get_update_command() -> str:
    """Get the command that users can run to update manually.
    
    Returns:
        Command string for manual update.
    """
    pip_url = f"git+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git"
    return f"pip install --upgrade {pip_url}"
