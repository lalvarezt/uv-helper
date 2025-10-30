"""Tests for git_manager module."""

from uv_helper.git_manager import GitRef, parse_git_url


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
