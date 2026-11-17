"""Shared ``limit`` / ``offset`` query parameters.

Every list endpoint accepts ``limit`` (1-100) and ``offset`` (0-100000). Use as a dependency::

    async def list_things(page: PageParams): ...   # page.limit, page.offset
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

MAX_LIMIT = 100
MAX_OFFSET = 100_000  # deep offsets make PostgreSQL scan and discard rows


@dataclass(frozen=True, slots=True)
class Pagination:
    limit: int
    offset: int


def pagination(default_limit: int = 50):  # noqa: ANN201 - returns a FastAPI dependency
    """Dependency factory with a per-endpoint default page size."""

    def dependency(
        limit: Annotated[
            int, Query(ge=1, le=MAX_LIMIT, description=f"Page size (1-{MAX_LIMIT}).")
        ] = default_limit,
        offset: Annotated[int, Query(ge=0, le=MAX_OFFSET, description="Number of items to skip.")] = 0,
    ) -> Pagination:
        return Pagination(limit=limit, offset=offset)

    return dependency


PageParams = Annotated[Pagination, Depends(pagination())]
#: People lists default to a larger page.
PeoplePageParams = Annotated[Pagination, Depends(pagination(100))]
