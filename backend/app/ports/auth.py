"""Auth port interface."""
from abc import ABC, abstractmethod
from fastapi import Request


class AuthPort(ABC):
    @abstractmethod
    async def get_current_user(self, request: Request) -> dict: ...
    @abstractmethod
    async def get_user_email(self, user_id: str) -> str | None: ...
    @abstractmethod
    async def verify_service_key(self, key: str) -> bool: ...
