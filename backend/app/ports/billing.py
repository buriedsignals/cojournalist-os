"""Billing port interface."""
from abc import ABC, abstractmethod


class BillingPort(ABC):
    @abstractmethod
    async def validate_credits(self, user_id: str, operation: str) -> bool: ...
    @abstractmethod
    async def decrement_credit(self, user_id: str, operation: str) -> bool: ...
    @abstractmethod
    async def get_balance(self, user_id: str) -> dict: ...
