"""Tests for git_manager module."""

import shutil
import subprocess
from pathlib import Path

import pytest

from uv_helper.constants import GIT_SHORT_HASH_LENGTH
from uv_helper.git_manager import (
    GitRef,
    clone_or_update,
    get_current_commit_hash,
    get_default_branch,
    is_detached_head,
    parse_git_url,
)


def _run_git(repo_path: Path, *args: str) -> str:
    """Run a git command and return stripped stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _create_origin_repo_with_tag(tmp_path: Path) -> tuple[Path, str, str]:
    """Create an origin repository with a tag on commit 1 and commit 2 on main."""
    origin = tmp_path / "origin"
    origin.mkdir()

    _run_git(origin, "init", "-b", "main")
    (origin / "tool.py").write_text("print('v1')\n", encoding="utf-8")
    _run_git(origin, "add", "tool.py")
    _run_git(
        origin,
        "-c",
        "user.name=Test User",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "c1",
    )
    _run_git(origin, "tag", "v1.0.0")

    (origin / "tool.py").write_text("print('v2')\n", encoding="utf-8")
    _run_git(origin, "add", "tool.py")
    _run_git(
        origin,
        "-c",
        "user.name=Test User",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "c2",
    )

    tag_commit = _run_git(origin, "rev-parse", f"--short={GIT_SHORT_HASH_LENGTH}", "v1.0.0")
    head_commit = _run_git(origin, "rev-parse", f"--short={GIT_SHORT_HASH_LENGTH}", "HEAD")
    return origin, tag_commit, head_commit


class TestParseGitUrl:
    """Tests for parse_git_url function."""

    def test_url_without_ref(self) -> None:
        """Test URL without ref."""
        result = parse_git_url("https://github.com/user/repo")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "default"
        assert result.ref_value is None

    def test_url_with_tag(self) -> None:
        """Test URL with tag."""
        result = parse_git_url("https://github.com/user/repo@v1.0.0")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "tag"
        assert result.ref_value == "v1.0.0"

    def test_url_with_branch(self) -> None:
        """Test URL with branch."""
        result = parse_git_url("https://github.com/user/repo#dev")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "branch"
        assert result.ref_value == "dev"

    def test_url_with_git_extension(self) -> None:
        """Test URL with .git extension."""
        result = parse_git_url("https://github.com/user/repo.git")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "default"
        assert result.ref_value is None

    def test_url_with_git_extension_and_tag(self) -> None:
        """Test URL with .git extension and tag."""
        result = parse_git_url("https://github.com/user/repo.git@v1.0.0")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "tag"
        assert result.ref_value == "v1.0.0"

    def test_ssh_scheme_url_without_ref(self) -> None:
        """Test ssh:// URL without ref suffix."""
        result = parse_git_url("ssh://git@github.com/user/repo.git")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "default"
        assert result.ref_value is None

    def test_ssh_scheme_url_with_tag_ref(self) -> None:
        """Test ssh:// URL with @tag suffix."""
        result = parse_git_url("ssh://git@github.com/user/repo.git@v2.0.0")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "tag"
        assert result.ref_value == "v2.0.0"

    def test_ssh_scheme_url_with_branch_ref(self) -> None:
        """Test ssh:// URL with #branch suffix."""
        result = parse_git_url("ssh://git@github.com/user/repo.git#develop")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "branch"
        assert result.ref_value == "develop"

    def test_scp_style_ssh_url_with_tag_ref(self) -> None:
        """Test git@host:path style URL with @tag suffix."""
        result = parse_git_url("git@github.com:user/repo.git@v3.1.4")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "tag"
        assert result.ref_value == "v3.1.4"

    def test_git_protocol_url_with_commit_ref(self) -> None:
        """Test git:// URL with @commit suffix."""
        result = parse_git_url("git://github.com/user/repo.git@deadbeef")

        assert result.base_url == "https://github.com/user/repo"
        assert result.ref_type == "commit"
        assert result.ref_value == "deadbeef"


class TestGitRef:
    """Tests for GitRef dataclass."""

    def test_creates_instance(self) -> None:
        """Test creating GitRef instance."""
        ref = GitRef(
            base_url="https://github.com/user/repo",
            ref_type="tag",
            ref_value="v1.0.0",
        )

        assert ref.base_url == "https://github.com/user/repo"
        assert ref.ref_type == "tag"
        assert ref.ref_value == "v1.0.0"

    def test_with_none_ref_value(self) -> None:
        """Test GitRef with None ref_value."""
        ref = GitRef(
            base_url="https://github.com/user/repo",
            ref_type="default",
            ref_value=None,
        )

        assert ref.ref_value is None


@pytest.mark.skipif(shutil.which("git") is None, reason="git command required")
class TestCloneOrUpdateIntegration:
    """Integration tests for clone/update behavior without mocks."""

    def test_clone_or_update_tag_then_default_recovers_detached_head(self, tmp_path: Path) -> None:
        """Default updates should recover from detached HEAD after tag checkout."""
        origin, tag_commit, head_commit = _create_origin_repo_with_tag(tmp_path)
        clone_path = tmp_path / "clone"

        clone_or_update(str(origin), "v1.0.0", clone_path, ref_type="tag")
        assert get_current_commit_hash(clone_path) == tag_commit
        assert is_detached_head(clone_path) is True

        clone_or_update(str(origin), None, clone_path)
        assert get_current_commit_hash(clone_path) == head_commit
        assert is_detached_head(clone_path) is False
        assert _run_git(clone_path, "branch", "--show-current") == "main"

    def test_get_default_branch_from_detached_tag_checkout(self, tmp_path: Path) -> None:
        """Default branch resolution should work from detached tag checkouts."""
        origin, _tag_commit, _head_commit = _create_origin_repo_with_tag(tmp_path)
        clone_path = tmp_path / "clone"

        clone_or_update(str(origin), "v1.0.0", clone_path, ref_type="tag")
        assert is_detached_head(clone_path) is True

        assert get_default_branch(clone_path) == "main"
