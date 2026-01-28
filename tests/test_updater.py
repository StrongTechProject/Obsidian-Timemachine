"""
Tests for the updater module.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ot.updater import (
    UpdateError,
    UpdateInfo,
    compare_versions,
    parse_version,
    get_current_version,
    check_for_updates,
    perform_update,
    get_update_command,
    _fetch_github_api,
)


class TestParseVersion:
    """Tests for parse_version function."""
    
    def test_simple_version(self):
        """Test parsing simple semantic version."""
        assert parse_version("1.2.3") == (1, 2, 3)
    
    def test_version_with_v_prefix(self):
        """Test parsing version with 'v' prefix."""
        assert parse_version("v1.2.3") == (1, 2, 3)
    
    def test_version_with_prerelease(self):
        """Test parsing version with pre-release suffix."""
        assert parse_version("1.2.3-beta") == (1, 2, 3)
        assert parse_version("1.2.3-rc1") == (1, 2, 3)
    
    def test_version_with_build_metadata(self):
        """Test parsing version with build metadata."""
        assert parse_version("1.2.3+build.123") == (1, 2, 3)
    
    def test_two_part_version(self):
        """Test parsing two-part version."""
        assert parse_version("1.2") == (1, 2)
    
    def test_single_part_version(self):
        """Test parsing single-part version."""
        assert parse_version("1") == (1,)
    
    def test_zero_version(self):
        """Test parsing zero version."""
        assert parse_version("0.0.0") == (0, 0, 0)


class TestCompareVersions:
    """Tests for compare_versions function."""
    
    def test_equal_versions(self):
        """Test comparing equal versions."""
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("v1.0.0", "1.0.0") == 0
    
    def test_first_version_smaller(self):
        """Test when first version is smaller."""
        assert compare_versions("1.0.0", "1.0.1") == -1
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.0.0", "2.0.0") == -1
    
    def test_first_version_larger(self):
        """Test when first version is larger."""
        assert compare_versions("1.0.1", "1.0.0") == 1
        assert compare_versions("1.1.0", "1.0.0") == 1
        assert compare_versions("2.0.0", "1.0.0") == 1
    
    def test_different_length_versions(self):
        """Test comparing versions with different lengths."""
        assert compare_versions("1.0", "1.0.0") == 0
        assert compare_versions("1.0.0", "1.0") == 0
        assert compare_versions("1.0", "1.0.1") == -1
        assert compare_versions("1.0.1", "1.0") == 1
    
    def test_with_v_prefix(self):
        """Test comparing versions with 'v' prefix."""
        assert compare_versions("v1.0.0", "v1.0.1") == -1
        assert compare_versions("v1.0.1", "1.0.0") == 1


class TestUpdateInfo:
    """Tests for UpdateInfo dataclass."""
    
    def test_create_update_info(self):
        """Test creating UpdateInfo instance."""
        info = UpdateInfo(
            current_version="0.1.0",
            latest_version="0.2.0",
            is_latest=False,
            release_url="https://github.com/example/repo/releases/tag/v0.2.0",
            release_notes="Bug fixes and improvements",
        )
        
        assert info.current_version == "0.1.0"
        assert info.latest_version == "0.2.0"
        assert info.is_latest is False
        assert info.release_url is not None
    
    def test_is_latest_true(self):
        """Test UpdateInfo when already at latest."""
        info = UpdateInfo(
            current_version="0.2.0",
            latest_version="0.2.0",
            is_latest=True,
        )
        
        assert info.is_latest is True


class TestGetCurrentVersion:
    """Tests for get_current_version function."""
    
    @patch("importlib.metadata.version")
    def test_get_version_from_metadata(self, mock_version):
        """Test getting version from importlib.metadata."""
        mock_version.return_value = "0.1.0"
        
        result = get_current_version()
        assert result == "0.1.0"
        mock_version.assert_called_with("obsidian-timemachine")


class TestFetchGitHubAPI:
    """Tests for _fetch_github_api function."""
    
    @patch("ot.updater.urlopen")
    def test_successful_fetch(self, mock_urlopen):
        """Test successful API fetch."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"tag_name": "v0.2.0"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        
        result = _fetch_github_api("/repos/test/repo/releases/latest")
        
        assert result["tag_name"] == "v0.2.0"
    
    @patch("ot.updater.urlopen")
    def test_404_error(self, mock_urlopen):
        """Test handling 404 error."""
        from urllib.error import HTTPError
        
        mock_urlopen.side_effect = HTTPError(
            url="https://api.github.com/test",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )
        
        with pytest.raises(UpdateError, match="not found"):
            _fetch_github_api("/repos/test/repo/releases/latest")
    
    @patch("ot.updater.urlopen")
    def test_rate_limit_error(self, mock_urlopen):
        """Test handling rate limit error."""
        from urllib.error import HTTPError
        
        mock_urlopen.side_effect = HTTPError(
            url="https://api.github.com/test",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None,
        )
        
        with pytest.raises(UpdateError, match="rate limit"):
            _fetch_github_api("/repos/test/repo/releases/latest")
    
    @patch("ot.updater.urlopen")
    def test_network_error(self, mock_urlopen):
        """Test handling network error."""
        from urllib.error import URLError
        
        mock_urlopen.side_effect = URLError("Connection refused")
        
        with pytest.raises(UpdateError, match="Network error"):
            _fetch_github_api("/repos/test/repo/releases/latest")


class TestCheckForUpdates:
    """Tests for check_for_updates function."""
    
    @patch("ot.updater.get_latest_release")
    @patch("ot.updater.get_current_version")
    def test_update_available(self, mock_current, mock_release):
        """Test when an update is available."""
        mock_current.return_value = "0.1.0"
        mock_release.return_value = {
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/test/repo/releases/tag/v0.2.0",
            "body": "New features",
            "published_at": "2024-01-01T00:00:00Z",
        }
        
        info = check_for_updates()
        
        assert info.current_version == "0.1.0"
        assert info.latest_version == "0.2.0"
        assert info.is_latest is False
    
    @patch("ot.updater.get_latest_release")
    @patch("ot.updater.get_current_version")
    def test_already_latest(self, mock_current, mock_release):
        """Test when already at latest version."""
        mock_current.return_value = "0.2.0"
        mock_release.return_value = {
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/test/repo/releases/tag/v0.2.0",
            "body": None,
            "published_at": None,
        }
        
        info = check_for_updates()
        
        assert info.is_latest is True
    
    @patch("ot.updater.get_latest_release")
    @patch("ot.updater.get_current_version")
    def test_current_newer_than_release(self, mock_current, mock_release):
        """Test when current version is newer (dev build)."""
        mock_current.return_value = "0.3.0"
        mock_release.return_value = {
            "tag_name": "v0.2.0",
            "html_url": None,
            "body": None,
            "published_at": None,
        }
        
        info = check_for_updates()
        
        assert info.is_latest is True


class TestPerformUpdate:
    """Tests for perform_update function."""
    
    @patch("ot.updater.subprocess.run")
    @patch("ot.updater.check_for_updates")
    @patch("ot.updater.get_logger")
    def test_skip_when_latest(self, mock_logger, mock_check, mock_run):
        """Test that update is skipped when already at latest."""
        mock_logger.return_value = MagicMock()
        mock_check.return_value = UpdateInfo(
            current_version="0.2.0",
            latest_version="0.2.0",
            is_latest=True,
        )
        
        result = perform_update(force=False)
        
        assert result is True
        mock_run.assert_not_called()
    
    @patch("ot.updater.subprocess.run")
    @patch("ot.updater.check_for_updates")
    @patch("ot.updater.get_logger")
    def test_force_update_when_latest(self, mock_logger, mock_check, mock_run):
        """Test force update even when at latest."""
        mock_logger.return_value = MagicMock()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        result = perform_update(force=True)
        
        assert result is True
        mock_run.assert_called_once()
    
    @patch("ot.updater.subprocess.run")
    @patch("ot.updater.check_for_updates")
    @patch("ot.updater.get_logger")
    def test_update_failure(self, mock_logger, mock_check, mock_run):
        """Test handling update failure."""
        mock_logger.return_value = MagicMock()
        mock_check.return_value = UpdateInfo(
            current_version="0.1.0",
            latest_version="0.2.0",
            is_latest=False,
        )
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Permission denied",
        )
        
        with pytest.raises(UpdateError, match="pip install failed"):
            perform_update()


class TestGetUpdateCommand:
    """Tests for get_update_command function."""
    
    def test_returns_pip_command(self):
        """Test that get_update_command returns valid pip command."""
        cmd = get_update_command()
        
        assert "pip install" in cmd
        assert "--upgrade" in cmd
        assert "github.com" in cmd
        assert "StrongTechProject" in cmd
        assert "Obsidian-TimeMachine" in cmd
