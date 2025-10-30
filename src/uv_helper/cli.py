"""CLI interface for UV-Helper."""

import os
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__
from .config import load_config
from .deps import resolve_dependencies
from .git_manager import (
    GitError,
    clone_or_update,
    get_current_commit_hash,
    get_default_branch,
    parse_git_url,
    verify_git_available,
)
from .script_installer import (
    ScriptInstallerError,
    install_script,
    remove_script_installation,
    verify_uv_available,
)
from .state import ScriptInfo, StateManager
from .utils import ensure_dir, get_repo_name_from_url, is_git_url, prompt_confirm

console = Console()


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Custom config file path",
)
@click.pass_context
def cli(ctx: click.Context, config: Path | None) -> None:
    """UV-Helper: Install and manage Python scripts from Git repositories."""
    ctx.ensure_object(dict)

    # Load configuration
    try:
        ctx.obj["config"] = load_config(config)
    except (FileNotFoundError, ValueError, OSError, PermissionError) as e:
        console.print(f"[red]Error:[/red] Configuration: {e}")
        sys.exit(1)

    # Verify required tools
    try:
        verify_git_available()
        verify_uv_available()
    except (GitError, ScriptInstallerError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("git-url")
@click.option(
    "--script",
    "-s",
    multiple=True,
    required=True,
    help="Script names to install (can be specified multiple times)",
)
@click.option(
    "--with",
    "-w",
    "with_deps",
    help="Dependencies: requirements.txt path or comma-separated libs",
)
@click.option(
    "--force", "-f", is_flag=True, help="Force overwrite existing scripts without confirmation"
)
@click.option("--no-symlink", is_flag=True, help="Skip creating symlinks in bin directory")
@click.option(
    "--install-dir",
    type=click.Path(path_type=Path),
    help="Custom installation directory (overrides config)",
)
@click.option("-v", "--verbose", is_flag=True, help="Show dependency resolution details")
@click.pass_context
def install(
    ctx: click.Context,
    git_url: str,
    script: tuple[str, ...],
    with_deps: str | None,
    force: bool,
    no_symlink: bool,
    install_dir: Path | None,
    verbose: bool,
) -> None:
    """
    Install Python scripts from a Git repository.

    Downloads the specified repository, processes the requested scripts,
    adds dependencies, modifies shebangs to use 'uv run --script', and
    creates symlinks in the bin directory for easy execution.

    Examples:

        \b
        # Install a single script
        uv-helper install https://github.com/user/repo --script myscript.py

        \b
        # Install multiple scripts
        uv-helper install https://github.com/user/repo --script script1.py --script script2.py

        \b
        # Install with dependencies from requirements.txt
        uv-helper install https://github.com/user/repo --script app.py --with requirements.txt

        \b
        # Install with inline dependencies
        uv-helper install https://github.com/user/repo --script app.py --with "requests,click>=8.0"

        \b
        # Install from a specific branch or tag
        uv-helper install https://github.com/user/repo#dev --script app.py
        uv-helper install https://github.com/user/repo@v1.0.0 --script app.py
    """
    config = ctx.obj["config"]

    # Validate Git URL
    if not is_git_url(git_url):
        console.print(f"[red]Error:[/red] Invalid Git URL: {git_url}")
        sys.exit(1)

    # Parse Git URL
    git_ref = parse_git_url(git_url)

    # Initialize state manager
    state_manager = StateManager(config.state_file)

    # Check for existing installations
    existing_scripts = []
    for script_name in script:
        if state_manager.get_script(script_name):
            existing_scripts.append(script_name)

    if existing_scripts and not force:
        console.print(
            f"[yellow]Warning:[/yellow] Scripts already installed: {', '.join(existing_scripts)}"
        )
        if not prompt_confirm("Overwrite existing installations?", default=False):
            console.print("Installation cancelled.")
            return

    # Determine repo directory
    repo_name = get_repo_name_from_url(git_ref.base_url)
    repo_path = config.repo_dir / repo_name

    # Clone or update repository
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Cloning/updating repository...", total=None)

        try:
            clone_or_update(
                git_ref.base_url,
                git_ref.ref_value,
                repo_path,
                depth=config.clone_depth,
            )
            progress.update(task, completed=True)
        except GitError as e:
            console.print(f"[red]Error:[/red] Git: {e}")
            sys.exit(1)

    # Get current commit hash and actual branch
    try:
        commit_hash = get_current_commit_hash(repo_path)
        # If no specific ref was provided, get the actual default branch
        actual_ref = git_ref.ref_value or get_default_branch(repo_path)
    except GitError as e:
        console.print(f"[red]Error:[/red] Git: Failed to get commit hash: {e}")
        sys.exit(1)

    # Resolve dependencies
    try:
        dependencies = resolve_dependencies(with_deps, repo_path)
        if verbose and dependencies:
            console.print(f"Dependencies: {', '.join(dependencies)}")
    except (FileNotFoundError, OSError) as e:
        console.print(f"[red]Error:[/red] Dependencies: {e}")
        sys.exit(1)

    # Determine bin directory
    install_directory = install_dir if install_dir else config.install_dir
    ensure_dir(install_directory)

    # Install scripts
    results = []
    for script_name in script:
        script_path = repo_path / script_name

        # Check if script exists
        if not script_path.exists():
            console.print(f"[red]Error:[/red] Script '{script_name}' not found at: {script_path}")
            results.append((script_name, False, "Not found"))
            continue

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Installing {script_name}...", total=None)

                symlink_path = install_script(
                    script_path,
                    dependencies,
                    install_directory,
                    auto_chmod=config.auto_chmod,
                    auto_symlink=not no_symlink and config.auto_symlink,
                    verify_after_install=config.verify_after_install,
                )

                progress.update(task, completed=True)

            # Save to state
            script_info = ScriptInfo(
                name=script_name,
                source_url=git_ref.base_url,
                ref=actual_ref,
                installed_at=datetime.now(),
                repo_path=repo_path,
                symlink_path=symlink_path,
                dependencies=dependencies,
                commit_hash=commit_hash,
            )
            state_manager.add_script(script_info)

            results.append((script_name, True, symlink_path))

        except ScriptInstallerError as e:
            console.print(f"[red]Error:[/red] Installing '{script_name}': {e}")
            results.append((script_name, False, str(e)))

    # Display results
    _display_install_results(results, install_directory)


@cli.command("list")
@click.option(
    "--format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format: table (default) or json",
)
@click.option("-v", "--verbose", is_flag=True, help="Show commit hash and dependencies")
@click.pass_context
def list_scripts(ctx: click.Context, format: str, verbose: bool) -> None:
    """
    List all installed scripts with their details.

    Displays information about installed scripts including name, source URL,
    installation date, current commit hash, and symlink location.

    Examples:

        \b
        # List all scripts in table format (default)
        uv-helper list

        \b
        # List with verbose output showing commit hash and dependencies
        uv-helper list -v

        \b
        # Output as JSON for scripting
        uv-helper list --format json
    """
    config = ctx.obj["config"]
    state_manager = StateManager(config.state_file)

    scripts = state_manager.list_scripts()

    if not scripts:
        console.print("No scripts installed.")
        return

    if format == "json":
        import json

        # Use Pydantic's model_dump with mode='json' for JSON-compatible output
        output = [script.model_dump(mode="json") for script in scripts]
        print(json.dumps(output, indent=2, default=str))
    else:
        _display_scripts_table(scripts, verbose)


@cli.command()
@click.argument("script-name")
@click.option(
    "--clean-repo", "-c", is_flag=True, help="Remove repository if no other scripts use it"
)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def remove(
    ctx: click.Context,
    script_name: str,
    clean_repo: bool,
    force: bool,
) -> None:
    """
    Remove an installed script and optionally clean up its repository.

    Removes the script's symlink from the bin directory and updates the
    installation state. If --clean-repo is specified and no other scripts
    from the same repository are installed, removes the repository as well.

    Examples:

        \b
        # Remove a script (keeps repository for other scripts)
        uv-helper remove myscript

        \b
        # Remove script and clean up repository if unused
        uv-helper remove myscript --clean-repo

        \b
        # Skip confirmation prompt
        uv-helper remove myscript --force
    """
    config = ctx.obj["config"]
    state_manager = StateManager(config.state_file)

    # Check if script exists
    script_info = state_manager.get_script(script_name)
    if not script_info:
        console.print(f"[red]Error:[/red] Script '{script_name}' not found.")
        sys.exit(1)

    assert script_info is not None  # Type narrowing for type checker

    # Confirm removal
    if not force:
        console.print(f"Removing script: [cyan]{script_name}[/cyan]")
        console.print(f"  Source: {script_info.source_url}")
        console.print(f"  Symlink: {script_info.symlink_path}")
        if clean_repo:
            console.print(f"  Repository: {script_info.repo_path} (will be removed)")

        if not prompt_confirm("Proceed with removal?", default=False):
            console.print("Removal cancelled.")
            return

    # Remove script
    try:
        remove_script_installation(script_name, state_manager, clean_repo=clean_repo)
        console.print(f"[green]✓[/green] Successfully removed {script_name}")
    except ScriptInstallerError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("script-name")
@click.option("--force", "-f", is_flag=True, help="Force reinstall even if up-to-date")
@click.pass_context
def update(ctx: click.Context, script_name: str, force: bool) -> None:
    """
    Update an installed script to the latest version from its repository.

    Fetches the latest changes from the script's Git repository and checks
    if the commit hash has changed. If an update is available (or --force
    is specified), reinstalls the script with the new version.

    Examples:

        \b
        # Update a script if newer version available
        uv-helper update myscript

        \b
        # Force reinstall even if already up-to-date
        uv-helper update myscript --force
    """
    config = ctx.obj["config"]
    state_manager = StateManager(config.state_file)

    # Check if script exists
    script_info = state_manager.get_script(script_name)
    if not script_info:
        console.print(f"[red]Error:[/red] Script '{script_name}' not found.")
        sys.exit(1)

    assert script_info is not None  # Type narrowing for type checker

    # Update repository
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Updating repository...", total=None)

            clone_or_update(
                script_info.source_url,
                script_info.ref,
                script_info.repo_path,
                depth=config.clone_depth,
            )

            progress.update(task, completed=True)

        # Check if there are updates
        new_commit_hash = get_current_commit_hash(script_info.repo_path)

        # Get the actual current branch (in case we fell back from a non-existent branch)
        try:
            actual_branch = get_default_branch(script_info.repo_path)
        except GitError:
            actual_branch = script_info.ref

        if new_commit_hash == script_info.commit_hash and not force:
            # Still update the ref in state if it changed
            if actual_branch != script_info.ref:
                script_info.ref = actual_branch
                state_manager.add_script(script_info)
            result = [(script_name, "up-to-date")]
            _display_update_results(result)
            return

        # Reinstall script
        script_path = script_info.repo_path / script_name
        symlink_path = install_script(
            script_path,
            script_info.dependencies,
            config.install_dir,
            auto_chmod=config.auto_chmod,
            auto_symlink=config.auto_symlink,
            verify_after_install=config.verify_after_install,
        )

        # Update state with new commit hash and actual branch
        script_info.commit_hash = new_commit_hash
        script_info.ref = actual_branch
        script_info.installed_at = datetime.now()
        script_info.symlink_path = symlink_path
        state_manager.add_script(script_info)

        result = [(script_name, "updated")]
        _display_update_results(result)

    except (GitError, ScriptInstallerError) as e:
        result = [(script_name, f"Error: {e}")]
        _display_update_results(result)
        sys.exit(1)


@cli.command("update-all")
@click.option("--force", "-f", is_flag=True, help="Force reinstall all scripts")
@click.pass_context
def update_all(ctx: click.Context, force: bool) -> None:
    """
    Update all installed scripts to their latest versions.

    Iterates through all installed scripts and updates each one by fetching
    the latest changes from their respective Git repositories. Displays a
    summary table showing which scripts were updated and their status.

    Examples:

        \b
        # Update all scripts if newer versions are available
        uv-helper update-all

        \b
        # Force reinstall all scripts
        uv-helper update-all --force
    """
    config = ctx.obj["config"]
    state_manager = StateManager(config.state_file)

    scripts = state_manager.list_scripts()

    if not scripts:
        console.print("No scripts installed.")
        return

    console.print(f"Updating {len(scripts)} script(s)...")

    results = []
    for script_info in scripts:
        try:
            # Update repository
            clone_or_update(
                script_info.source_url,
                script_info.ref,
                script_info.repo_path,
                depth=config.clone_depth,
            )

            # Check for updates
            new_commit_hash = get_current_commit_hash(script_info.repo_path)

            # Get the actual current branch (in case we fell back from a non-existent branch)
            try:
                actual_branch = get_default_branch(script_info.repo_path)
            except GitError:
                actual_branch = script_info.ref

            if new_commit_hash == script_info.commit_hash and not force:
                # Still update the ref in state if it changed
                if actual_branch != script_info.ref:
                    script_info.ref = actual_branch
                    state_manager.add_script(script_info)
                results.append((script_info.name, "up-to-date"))
                continue

            # Reinstall
            script_path = script_info.repo_path / script_info.name
            symlink_path = install_script(
                script_path,
                script_info.dependencies,
                config.install_dir,
                auto_chmod=config.auto_chmod,
                auto_symlink=config.auto_symlink,
                verify_after_install=config.verify_after_install,
            )

            # Update state with new commit hash and actual branch
            script_info.commit_hash = new_commit_hash
            script_info.ref = actual_branch
            script_info.installed_at = datetime.now()
            script_info.symlink_path = symlink_path
            state_manager.add_script(script_info)

            results.append((script_info.name, "updated"))

        except (GitError, ScriptInstallerError) as e:
            results.append((script_info.name, f"Error: {e}"))

    # Display results
    _display_update_results(results)


def _display_install_results(
    results: list[tuple[str, bool, Path | None | str]],
    install_dir: Path,
) -> None:
    """Display installation results."""
    table = Table(title="Installation Results")
    table.add_column("Script", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Location")

    for script_name, success, location in results:
        if success:
            status = "✓ Installed"
            loc = str(location) if location else "N/A"
        else:
            status = "✗ Failed"
            loc = str(location)

        table.add_row(script_name, status, loc)

    console.print(table)

    # Check if install_dir is in PATH
    if str(install_dir) not in os.environ.get("PATH", ""):
        console.print(
            Panel(
                f"[yellow]Warning:[/yellow] {install_dir} is not in your PATH.\n"
                f"Add it to your shell configuration:\n"
                f'  export PATH="{install_dir}:$PATH"',
                title="PATH Warning",
                border_style="yellow",
            )
        )


def _display_scripts_table(scripts: list[ScriptInfo], verbose: bool) -> None:
    """Display scripts in a table."""
    table = Table(title="Installed Scripts")
    table.add_column("Script", style="cyan")
    table.add_column("Source", style="magenta")
    table.add_column("Ref", style="green")
    table.add_column("Installed", style="yellow")

    if verbose:
        table.add_column("Commit", style="blue")
        table.add_column("Dependencies")

    for script in scripts:
        row = [
            script.name,
            script.source_url.split("/")[-2:][0] + "/" + script.source_url.split("/")[-1],
            script.ref,
            script.installed_at.strftime("%Y-%m-%d %H:%M"),
        ]

        if verbose:
            row.append(script.commit_hash)
            row.append(", ".join(script.dependencies) if script.dependencies else "None")

        table.add_row(*row)

    console.print(table)


def _display_update_results(results: list[tuple[str, str]]) -> None:
    """Display update results."""
    table = Table(title="Update Results")
    table.add_column("Script", style="cyan")
    table.add_column("Status", style="green")

    for script_name, status in results:
        if status == "updated":
            status_text = "[green]✓ Updated[/green]"
        elif status == "up-to-date":
            status_text = "[blue]✓ Up-to-date[/blue]"
        else:
            status_text = f"[red]✗ {status}[/red]"

        table.add_row(script_name, status_text)

    console.print(table)


if __name__ == "__main__":
    cli()
