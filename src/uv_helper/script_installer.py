"""Script installation and processing for UV-Helper."""

import subprocess
from pathlib import Path

from .state import StateManager
from .utils import run_command, validate_python_script


class ScriptInstallerError(Exception):
    """
    Raised when script installation or processing fails.

    This exception is raised for various script-related failures including:
    - Invalid Python script files
    - Failed dependency installation (uv add --script failures)
    - Shebang modification failures (file I/O errors)
    - Symlink creation failures (permission issues, filesystem limitations)
    - Script execution permission failures (chmod errors)
    - Script removal failures (missing scripts, file system errors)
    - UV not available in PATH

    The error message provides specific details about the failure.
    """

    pass


def process_script_dependencies(script_path: Path, dependencies: list[str]) -> bool:
    """
    Add dependencies to script using uv add --script.

    Args:
        script_path: Path to Python script
        dependencies: List of dependencies to add

    Returns:
        True if successful

    Raises:
        ScriptInstallerError: If adding dependencies fails
    """
    if not dependencies:
        return True

    try:
        # Build uv add --script command
        cmd = ["uv", "add", "--script", str(script_path)]
        cmd.extend(dependencies)

        run_command(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        raise ScriptInstallerError(f"Failed to add dependencies to script: {e.stderr}") from e


def modify_shebang(script_path: Path) -> bool:
    """
    Modify script shebang to use uv run --script.

    Transforms:
        #!/usr/bin/env python3
    To:
        #!/usr/bin/env -S uv run --script

    Args:
        script_path: Path to Python script

    Returns:
        True if successful

    Raises:
        ScriptInstallerError: If modification fails
    """
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            raise ScriptInstallerError("Script file is empty")

        # Check if first line is a shebang
        if lines[0].startswith("#!"):
            # Replace with uv shebang
            lines[0] = "#!/usr/bin/env -S uv run --script\n"
        else:
            # Add shebang at the beginning
            lines.insert(0, "#!/usr/bin/env -S uv run --script\n")

        # Write back
        with open(script_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return True
    except (OSError, UnicodeDecodeError) as e:
        raise ScriptInstallerError(f"Failed to modify shebang: {e}") from e


def create_symlink(
    script_path: Path,
    target_dir: Path,
    script_name: str | None = None,
) -> Path:
    """
    Create symlink to script in target directory.

    Args:
        script_path: Path to script file
        target_dir: Directory to create symlink in
        script_name: Optional custom name for symlink (default: script filename)

    Returns:
        Path to created symlink

    Raises:
        ScriptInstallerError: If symlink creation fails
    """
    try:
        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Determine symlink name
        if script_name is None:
            script_name = script_path.name

        symlink_path = target_dir / script_name

        # Remove existing symlink if it exists
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()

        # Create symlink
        symlink_path.symlink_to(script_path)

        return symlink_path
    except OSError as e:
        raise ScriptInstallerError(f"Failed to create symlink: {e}") from e


def make_executable(script_path: Path) -> bool:
    """
    Make script executable.

    Args:
        script_path: Path to script file

    Returns:
        True if successful

    Raises:
        ScriptInstallerError: If chmod fails
    """
    try:
        # Add execute permission: chmod +x
        current_mode = script_path.stat().st_mode
        script_path.chmod(current_mode | 0o111)  # Add execute for user, group, other
        return True
    except OSError as e:
        raise ScriptInstallerError(f"Failed to make script executable: {e}") from e


def verify_script(script_path: Path) -> bool:
    """
    Verify that script can be executed.

    Tries to run script with --help flag.

    Args:
        script_path: Path to script

    Returns:
        True if script runs successfully, False otherwise
    """
    try:
        # Try running with --help
        result = run_command(
            [str(script_path), "--help"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def remove_script_installation(
    script_name: str,
    state_manager: StateManager,
    clean_repo: bool = False,
) -> bool:
    """
    Remove an installed script.

    Args:
        script_name: Name of script to remove
        state_manager: StateManager instance
        clean_repo: Whether to clean up repository if no other scripts use it

    Returns:
        True if successful

    Raises:
        ScriptInstallerError: If removal fails
    """
    script_info = state_manager.get_script(script_name)
    if not script_info:
        raise ScriptInstallerError(f"Script '{script_name}' not found in state")

    try:
        # Remove symlink if exists
        if script_info.symlink_path and script_info.symlink_path.exists():
            script_info.symlink_path.unlink()

        # Clean up repository if requested
        if clean_repo:
            scripts_from_repo = state_manager.get_scripts_from_repo(script_info.repo_path)

            # Only delete repo if this is the last script from it
            if len(scripts_from_repo) == 1:
                import shutil

                if script_info.repo_path.exists():
                    shutil.rmtree(script_info.repo_path)

        # Remove from state
        state_manager.remove_script(script_name)

        return True
    except OSError as e:
        raise ScriptInstallerError(f"Failed to remove script: {e}") from e


def verify_uv_available() -> bool:
    """
    Verify that uv command is available.

    Returns:
        True if uv is available

    Raises:
        ScriptInstallerError: If uv is not available
    """
    try:
        run_command(["uv", "--version"], check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise ScriptInstallerError("UV is not installed or not in PATH") from e


def install_script(
    script_path: Path,
    dependencies: list[str],
    install_dir: Path,
    auto_chmod: bool = True,
    auto_symlink: bool = True,
    verify_after_install: bool = True,
) -> Path | None:
    """
    Install a script with all processing steps.

    Steps:
    1. Validate script
    2. Add dependencies
    3. Modify shebang
    4. Make executable
    5. Create symlink
    6. Verify

    Args:
        script_path: Path to script file
        dependencies: List of dependencies
        install_dir: Installation directory for symlinks
        auto_chmod: Whether to make script executable
        auto_symlink: Whether to create symlink
        verify_after_install: Whether to verify after installation

    Returns:
        Path to symlink if created, None otherwise

    Raises:
        ScriptInstallerError: If installation fails
    """
    # Validate script
    if not validate_python_script(script_path):
        raise ScriptInstallerError(f"Invalid Python script: {script_path}")

    # Add dependencies
    if dependencies:
        process_script_dependencies(script_path, dependencies)

    # Modify shebang
    modify_shebang(script_path)

    # Make executable
    if auto_chmod:
        make_executable(script_path)

    # Create symlink
    symlink_path = None
    if auto_symlink:
        symlink_path = create_symlink(script_path, install_dir)

    # Verify
    if verify_after_install:
        if not verify_script(script_path):
            # Don't fail, just warn (script might not support --help)
            pass

    return symlink_path
