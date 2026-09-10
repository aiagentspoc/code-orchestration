import importlib
from pathlib import Path
import tomllib


def test_pyproject_toml_exists() -> None:
    """Ensure pyproject.toml exists at the workspace root."""
    root = Path(__file__).resolve().parents[2]
    pyproject_path = root / "pyproject.toml"
    assert pyproject_path.is_file(), f"pyproject.toml not found at {pyproject_path}"


def test_pyproject_metadata() -> None:
    """Validate project metadata and dependency declarations in pyproject.toml."""
    root = Path(__file__).resolve().parents[2]
    pyproject_path = root / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    assert project.get("name") == "code-orchestration"
    assert project.get("version") == "0.1.0"

    dependencies = project.get("dependencies", [])
    dep_str = " ".join(dependencies)
    assert "strands-agents" in dep_str
    assert "pydantic" in dep_str
    assert "fastmcp" in dep_str
    assert "hse-easy-mock-mcp" in dep_str

    opt_deps = project.get("optional-dependencies", {})
    dev_deps = opt_deps.get("dev", [])
    dev_str = " ".join(dev_deps)
    assert "pytest" in dev_str
    assert "pytest-asyncio" in dev_str


def test_dependencies_importable() -> None:
    """Verify core dependencies can be imported in the current environment."""
    pydantic = importlib.import_module("pydantic")
    assert hasattr(pydantic, "BaseModel")

    fastmcp = importlib.import_module("fastmcp")
    assert hasattr(fastmcp, "FastMCP")

    strands = importlib.import_module("strands")
    assert hasattr(strands, "Agent")

    hse_mock = importlib.import_module("server")
    assert hasattr(hse_mock, "mcp")
