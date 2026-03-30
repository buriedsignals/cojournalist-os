"""Scheduler port interface."""
from abc import ABC, abstractmethod


class SchedulerPort(ABC):
    @abstractmethod
    async def create_schedule(self, schedule_name: str, cron: str,
                               target_config: dict) -> str: ...
    @abstractmethod
    async def delete_schedule(self, schedule_name: str) -> None: ...
    @abstractmethod
    async def update_schedule(self, schedule_name: str, cron: str = None,
                               target_config: dict = None) -> None: ...
