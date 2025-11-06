# Contributing to UV-Helper

Thank you for your interest in contributing to UV-Helper! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

## Development Workflow

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- [git](https://git-scm.com/) for version control

### Setting Up Development Environment

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/YOUR_USERNAME/uv-helper
   cd uv-helper
   ```

2. **Install the project with development dependencies:**

   ```bash
   uv sync
   ```

   This installs the project in editable mode with all dev dependencies.

3. **Verify installation:**

   ```bash
   uv run uv-helper --version
   ```

### Making Changes

1. **Create a new branch for your feature or bugfix:**

   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```

2. **Make your changes** following the code style guidelines below.

3. **Run code quality checks** before committing:

   ```bash
   # Run all checks in one go
   uv run ruff check --fix --unsafe-fixes && \
   uv run ruff check --select I --fix && \
   uv run ruff format && \
   uv run ty check
   ```

   Or run individually:

   ```bash
   # Linting
   uv run ruff check --fix --unsafe-fixes

   # Import sorting
   uv run ruff check --select I --fix

   # Code formatting
   uv run ruff format

   # Type checking
   uv run ty check
   ```

4. **Run tests:**

   ```bash
   uv run pytest -v
   ```

5. **Commit your changes** with a clear, descriptive message:

   ```bash
   git add .
   git commit -m "feat: add support for feature X"
   ```

   See [Commit Message Guidelines](#commit-message-guidelines) below.

## Code Style Guidelines

### General Principles

- Follow [PEP 8](https://pep8.org/) Python style guide
- Use modern Python 3.11+ features (e.g., `Type | None` instead of `Optional[Type]`)
- Write clear, self-documenting code with meaningful variable names
- Keep functions focused and small (prefer multiple small functions over large ones)
- Add docstrings to all public functions, classes, and modules

### Specific Guidelines

1. **Type Hints:**
   - Use type hints for all function signatures
   - Use modern syntax: `list[str]` instead of `List[str]`
   - Use `Path` from `pathlib` for file paths, not strings

   ```python
   # Good
   def process_script(script_path: Path, deps: list[str]) -> bool:
       """Process a script with dependencies."""
       pass

   # Bad
   def process_script(script_path, deps):
       pass
   ```

2. **Docstrings:**
   - Use Google-style docstrings
   - Include `Args`, `Returns`, and `Raises` sections
   - Be concise but complete

   ```python
   def install_script(script_path: Path, dependencies: list[str]) -> Path | None:
       """
       Install a script with dependencies.

       Args:
           script_path: Path to the script file
           dependencies: List of dependency packages

       Returns:
           Path to installed symlink, or None if not created

       Raises:
           ScriptInstallerError: If installation fails
       """
       pass
   ```

3. **Constants:**
   - Define constants in `constants.py`
   - Use UPPER_CASE for constant names
   - Group related constants together with comments

4. **Error Handling:**
   - Use custom exception classes (`GitError`, `ScriptInstallerError`)
   - Provide informative error messages
   - Don't catch generic `Exception` unless necessary

5. **Imports:**
   - Group imports: stdlib, third-party, local
   - Use absolute imports for internal modules
   - Keep imports sorted (Ruff will handle this)

### Ruff Configuration

The project uses Ruff for linting and formatting with the following configuration (see `pyproject.toml`):

- Line length: 100 characters
- Target: Python 3.13
- Enabled linters: E (pycodestyle errors), B (flake8-bugbear), Q (flake8-quotes), I (isort)

### Type Checking

We use [Ty](https://github.com/lzell/ty) for type checking. Ensure all type hints are correct:

```bash
uv run ty check
```

## Testing Requirements

### Writing Tests

1. **Test Location:**
   - Place tests in the `tests/` directory
   - Mirror the source structure: `tests/test_module.py` for `src/uv_helper/module.py`

2. **Test Structure:**
   - Use descriptive test names: `test_install_script_with_dependencies`
   - Group related tests in classes
   - Use fixtures and parametrize for common setup

3. **Testing Best Practices:**
   - Test both success and failure cases
   - Use `tmp_path` fixture for file operations
   - Mock external dependencies (Git, network calls)
   - Test edge cases and error conditions

   ```python
   def test_install_script_creates_symlink(tmp_path: Path) -> None:
       """Test that install_script creates a symlink correctly."""
       script_path = tmp_path / "script.py"
       script_path.write_text("print('hello')\n")

       install_dir = tmp_path / "bin"
       symlink = install_script(script_path, [], install_dir)

       assert symlink.exists()
       assert symlink.is_symlink()
       assert symlink.resolve() == script_path
   ```

### Running Tests

```bash
# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_cli.py -v

# Run specific test
uv run pytest tests/test_cli.py::test_cli_install -v

# Run with verbose output
uv run pytest -vv
```

### Test Requirements

- All new features must include tests
- Bug fixes should include regression tests
- Maintain or improve existing test quality

## Pull Request Process

### Before Submitting

1. **Ensure all checks pass:**
   - Code formatting (Ruff format)
   - Linting (Ruff check)
   - Type checking (Ty)
   - All tests pass

2. **Update documentation:**
   - Update README.md if adding new features
   - Update CHANGELOG.md with your changes
   - Add docstrings to new functions/classes

3. **Commit message guidelines:**

   Follow conventional commit format:

   ```
   type: subject

   body (optional)

   footer (optional)
   ```

   **Types:**
   - `feat`: New feature
   - `fix`: Bug fix
   - `docs`: Documentation changes
   - `style`: Code style changes (formatting, no logic change)
   - `refactor`: Code refactoring
   - `test`: Adding or updating tests
   - `chore`: Maintenance tasks

   **Examples:**
   ```
   feat: add support for local directory installation

   fix: prevent error when script not found in repository

   docs: update README with new installation options

   refactor: extract display functions to separate module
   ```

### Submitting a Pull Request

1. **Push your branch:**

   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create a pull request** on GitHub with:
   - Clear title describing the change
   - Description explaining what and why
   - Reference any related issues (`Fixes #123`)
   - Screenshots/examples if applicable

3. **Pull request template:**

   ```markdown
   ## Description
   Brief description of the changes.

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update

   ## Testing
   - [ ] All tests pass locally
   - [ ] Added tests for new functionality
   - [ ] Updated documentation

   ## Related Issues
   Fixes #(issue number)

   ## Additional Context
   Any additional information or context.
   ```

4. **Respond to feedback:**
   - Address review comments promptly
   - Push additional commits to the same branch
   - Request re-review when ready

### Code Review Process

- Maintainers will review your PR
- Feedback may include code style, logic, or test suggestions
- All CI checks must pass before merging
- At least one maintainer approval is required

## Reporting Issues

### Before Creating an Issue

- Search existing issues to avoid duplicates
- Check if the issue is already fixed in the latest version
- Gather relevant information (version, OS, error messages)

### Issue Template

```markdown
## Description
Clear description of the issue.

## Steps to Reproduce
1. Step one
2. Step two
3. ...

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Environment
- UV-Helper version: X.Y.Z
- Python version: 3.X.Y
- OS: Linux/macOS/Windows
- uv version: X.Y.Z

## Additional Context
Error messages, logs, screenshots, etc.
```

## Additional Resources

- [README.md](README.md) - Project overview and usage
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [Python Style Guide (PEP 8)](https://pep8.org/)
- [uv Documentation](https://github.com/astral-sh/uv)

## Getting Help

If you need help:

1. Check the [README.md](README.md) documentation
2. Search [existing issues](https://github.com/lalvarezt/uv-helper/issues)
3. Create a new issue with your question

## License

By contributing to UV-Helper, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to UV-Helper! 🎉
