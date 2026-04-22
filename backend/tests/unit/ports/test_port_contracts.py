"""Verify port ABCs cannot be instantiated directly."""
import pytest

from app.ports.storage import (
    ScoutStoragePort, ExecutionStoragePort, RunStoragePort,
    UnitStoragePort, UserStoragePort,
)
from app.ports.scheduler import SchedulerPort
from app.ports.auth import AuthPort
from app.ports.billing import BillingPort


@pytest.mark.parametrize("port_cls", [
    ScoutStoragePort, ExecutionStoragePort, RunStoragePort,
    UnitStoragePort, UserStoragePort,
    SchedulerPort, AuthPort, BillingPort,
])
def test_port_cannot_be_instantiated(port_cls):
    with pytest.raises(TypeError):
        port_cls()
