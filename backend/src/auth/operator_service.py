"""OperatorService — business logic for operator lifecycle.

Handles create/revoke/rotate/list for operators.
"""

from __future__ import annotations

import secrets as _secrets_mod
from typing import TYPE_CHECKING, List, Optional, Tuple

from ..core.repositories import IOperatorRepository
from .operators import (
    DEFAULT_TOKEN_TTL_DAYS,
    Operator,
    _operator_to_safe_dict,
)

if TYPE_CHECKING:
    from ..core.repositories_sqlalchemy import SqlAlchemyAsyncOperatorRepository


class OperatorService:
    def __init__(self, repo: IOperatorRepository) -> None:
        self._repo = repo

    def create_operator(
        self,
        name: str,
        role: str,
        tenant_id: str,
        ttl_days: int = DEFAULT_TOKEN_TTL_DAYS,
        token: Optional[str] = None,
    ) -> Tuple[Operator, str]:
        raw_token = token if token is not None else _secrets_mod.token_urlsafe(32)
        return self._repo.create(name, role, raw_token, tenant_id, ttl_days)

    def revoke_operator(self, operator_id: str) -> bool:
        return self._repo.revoke(operator_id)

    def rotate_token(
        self,
        operator_id: str,
        ttl_days: int = DEFAULT_TOKEN_TTL_DAYS,
    ) -> Optional[str]:
        return self._repo.rotate_token(operator_id, ttl_days)

    def get_operator_safe(self, operator_id: str) -> Optional[dict]:
        op = self._repo.get_any(operator_id)
        if op is None:
            return None
        return _operator_to_safe_dict(op)

    def list_operators_for_admin(self) -> List[dict]:
        operators = self._repo.list()
        return [_operator_to_safe_dict(op) for op in operators]

    def bootstrap(self) -> None:
        self._repo.bootstrap_if_needed()


class AsyncOperatorService:
    """Async version of OperatorService — uses AsyncSession-based async repository."""

    def __init__(self, repo: "SqlAlchemyAsyncOperatorRepository") -> None:
        self._repo = repo

    async def create_operator(
        self,
        name: str,
        role: str,
        tenant_id: str,
        ttl_days: int = DEFAULT_TOKEN_TTL_DAYS,
        token: Optional[str] = None,
    ) -> "Tuple[Operator, str]":
        raw_token = token if token is not None else _secrets_mod.token_urlsafe(32)
        return await self._repo.create(name, role, raw_token, tenant_id, ttl_days)

    async def revoke_operator(self, operator_id: str) -> bool:
        return await self._repo.revoke(operator_id)

    async def rotate_token(
        self,
        operator_id: str,
        ttl_days: int = DEFAULT_TOKEN_TTL_DAYS,
    ) -> Optional[str]:
        return await self._repo.rotate_token(operator_id, ttl_days)

    async def get_operator_safe(self, operator_id: str) -> Optional[dict]:
        op = await self._repo.get_any(operator_id)
        if op is None:
            return None
        return _operator_to_safe_dict(op)

    async def list_operators_for_admin(self) -> "List[dict]":
        operators = await self._repo.list()
        return [_operator_to_safe_dict(op) for op in operators]
