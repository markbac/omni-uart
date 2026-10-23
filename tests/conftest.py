"""Pytest fixtures for OmniUART testing suite."""

from __future__ import annotations

import pytest
from omniuart.core.transfer import TransferSimulationConfig, TransferSimulator


@pytest.fixture
def transfer_simulation_config() -> TransferSimulationConfig:
    """Default configurable transfer simulation options fixture (#252)."""
    return TransferSimulationConfig()


@pytest.fixture
def transfer_simulator() -> TransferSimulator:
    """Pre-instantiated TransferSimulator fixture for deterministic integration testing (#252)."""
    return TransferSimulator()
