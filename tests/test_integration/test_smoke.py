import asyncio
import pytest


def test_test_runner_smoke() -> None:
    """Basic sanity check verifying pytest execution harness."""
    assert 1 + 1 == 2


@pytest.mark.asyncio
async def test_asyncio_support() -> None:
    """Verify asyncio test support via pytest-asyncio."""
    await asyncio.sleep(0.01)
    assert True
