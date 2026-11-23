from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aws_ops_mcp.contracts import InventoryResult, ResourceRecord
from opslens.repositories import InventoryRepository


@pytest.mark.asyncio
async def test_inventory_metadata_is_json_normalized_before_insert() -> None:
    created_at = datetime(2026, 11, 24, 10, 15, tzinfo=UTC)
    inventory = InventoryResult(
        account_id="123456789012",
        profile="test",
        resources=[
            ResourceRecord(
                service="s3",
                resource_type="bucket",
                resource_id="example",
                name="example",
                region="global",
                metadata={"creation_date": created_at, "nested": {"seen_at": created_at}},
            )
        ],
    )
    session = AsyncMock()

    await InventoryRepository(session).replace_inventory(inventory)

    insert_statement = session.execute.await_args_list[1].args[0]
    parameters = insert_statement.compile().params
    assert parameters["metadata_json"] == {
        "creation_date": "2026-11-24T10:15:00Z",
        "nested": {"seen_at": "2026-11-24T10:15:00Z"},
    }
