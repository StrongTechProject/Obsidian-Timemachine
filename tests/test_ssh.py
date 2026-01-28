"""Tests for SSH key management module."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ot.ssh import (
    SSHKey,
    find_ssh_keys,
    check_key_permissions,
    generate_ssh_key,
)


class TestSSHKey:
    """Tests for SSHKey dataclass."""
    
    def test_key_creation(self, tmp_path: Path) -> None:
        """Test creating an SSHKey object."""
        private = tmp_path / "id_test"
        public = tmp_path / "id_test.pub"
        
        key = SSHKey(
            private_key_path=private,
            public_key_path=public,
            key_type="ed25519",
        )
        
        assert key.private_key_path == private
        assert key.public_key_path == public
        assert key.key_type == "ed25519"
    
    def test_key_exists_false(self, tmp_path: Path) -> None:
        """Test exists property when keys don't exist."""
        key = SSHKey(
            private_key_path=tmp_path / "missing",
            public_key_path=tmp_path / "missing.pub",
        )
        
        assert not key.exists
    
    def test_key_exists_true(self, tmp_path: Path) -> None:
        """Test exists property when keys exist."""
        private = tmp_path / "id_test"
        public = tmp_path / "id_test.pub"
        private.write_text("private key content")
        public.write_text("public key content")
        
        key = SSHKey(
            private_key_path=private,
            public_key_path=public,
        )
        
        assert key.exists
    
    def test_get_public_key_content(self, tmp_path: Path) -> None:
        """Test reading public key content."""
        public = tmp_path / "id_test.pub"
        public.write_text("ssh-ed25519 AAAA... user@host\n")
        
        key = SSHKey(
            private_key_path=tmp_path / "id_test",
            public_key_path=public,
        )
        
        content = key.get_public_key_content()
        assert content == "ssh-ed25519 AAAA... user@host"


class TestFindSSHKeys:
    """Tests for find_ssh_keys function."""
    
    def test_find_keys_empty_dir(self, tmp_path: Path) -> None:
        """Test finding keys in empty directory."""
        keys = find_ssh_keys(tmp_path)
        assert keys == []
    
    def test_find_keys_with_ed25519(self, tmp_path: Path) -> None:
        """Test finding ed25519 keys."""
        private = tmp_path / "id_ed25519"
        public = tmp_path / "id_ed25519.pub"
        private.write_text("private")
        public.write_text("public")
        
        keys = find_ssh_keys(tmp_path)
        
        assert len(keys) == 1
        assert keys[0].private_key_path == private
        assert keys[0].key_type == "ed25519"
    
    def test_find_keys_with_rsa(self, tmp_path: Path) -> None:
        """Test finding rsa keys."""
        private = tmp_path / "id_rsa"
        public = tmp_path / "id_rsa.pub"
        private.write_text("private")
        public.write_text("public")
        
        keys = find_ssh_keys(tmp_path)
        
        assert len(keys) == 1
        assert keys[0].key_type == "rsa"
    
    def test_find_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test with nonexistent directory."""
        keys = find_ssh_keys(tmp_path / "nonexistent")
        assert keys == []


class TestCheckKeyPermissions:
    """Tests for check_key_permissions function."""
    
    def test_check_missing_file(self, tmp_path: Path) -> None:
        """Test checking permissions on missing file."""
        is_valid, mode = check_key_permissions(tmp_path / "missing")
        
        assert not is_valid
        assert mode == "file not found"
    
    def test_check_correct_permissions(self, tmp_path: Path) -> None:
        """Test checking correct permissions (600)."""
        key_file = tmp_path / "id_test"
        key_file.write_text("private key")
        key_file.chmod(0o600)
        
        is_valid, mode = check_key_permissions(key_file)
        
        assert is_valid
        assert mode == "600"


class TestGenerateSSHKey:
    """Tests for generate_ssh_key function."""
    
    @patch("ot.ssh.subprocess.run")
    def test_generate_key_success(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test successful key generation."""
        key_path = tmp_path / "id_new"
        
        # Create the key files to simulate ssh-keygen success
        def create_keys(*args, **kwargs):
            key_path.write_text("private")
            Path(str(key_path) + ".pub").write_text("public")
            return MagicMock(returncode=0)
        
        mock_run.side_effect = create_keys
        
        result = generate_ssh_key(
            email="test@example.com",
            key_path=key_path,
        )
        
        assert result is not None
        assert result.private_key_path == key_path
    
    def test_generate_key_already_exists(self, tmp_path: Path) -> None:
        """Test generating when key already exists."""
        key_path = tmp_path / "id_existing"
        key_path.write_text("existing key")
        Path(str(key_path) + ".pub").write_text("public")
        
        result = generate_ssh_key(
            email="test@example.com",
            key_path=key_path,
            overwrite=False,
        )
        
        assert result is not None
        assert result.private_key_path == key_path
