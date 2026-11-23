from datetime import UTC, datetime

from aws_ops_mcp.contracts import InventoryResult, ResourceRecord


def test_inventory_contract_is_structured() -> None:
    result = InventoryResult(
        account_id="123456789012",
        profile="test",
        collected_at=datetime.now(UTC),
        resources=[
            ResourceRecord(
                service="s3",
                resource_type="bucket",
                resource_id="example",
                name="example",
                region="global",
                status="available",
            )
        ],
    )
    payload = result.model_dump(mode="json")
    assert payload["resources"][0]["service"] == "s3"
    assert payload["account_id"] == "123456789012"
