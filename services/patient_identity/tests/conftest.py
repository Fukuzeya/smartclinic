"""Top-level conftest — marks integration tests and sets asyncio mode."""
import pytest


def pytest_collection_modifyitems(items: list) -> None:
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
