import importlib
from pathlib import Path
import tempfile


def test_src_package_importable() -> None:
    """Verify src package can be imported and exposes __version__."""
    src = importlib.import_module("src")
    assert hasattr(src, "__version__")
    assert src.__version__ == "0.1.0"


def test_submodules_exist() -> None:
    """Verify all pipeline modules exist and can be cleanly imported."""
    expected_modules = [
        "src.schemas",
        "src.mcp_client",
        "src.agents",
        "src.template_engine",
        "src.orchestrator",
        "src.publish",
    ]
    for mod_name in expected_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"Failed to import {mod_name}"


def test_artifact_directories_exist() -> None:
    """Verify drafts and logs directories exist and are writable."""
    root = Path(__file__).resolve().parents[2]
    drafts_dir = root / "drafts"
    logs_dir = root / "logs"

    assert drafts_dir.is_dir(), f"drafts directory not found at {drafts_dir}"
    assert logs_dir.is_dir(), f"logs directory not found at {logs_dir}"

    # Verify writability
    with tempfile.NamedTemporaryFile(dir=drafts_dir) as f:
        assert Path(f.name).exists()
    with tempfile.NamedTemporaryFile(dir=logs_dir) as f:
        assert Path(f.name).exists()
