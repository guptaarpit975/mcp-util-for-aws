from aws_ops_mcp.contracts import ResourceRecord
from aws_ops_mcp.health import evaluate_health


def test_ecs_running_below_desired_is_critical() -> None:
    resources = [
        ResourceRecord(
            service="ecs",
            resource_type="service",
            resource_id="arn:service/checkout",
            name="checkout",
            region="ap-south-1",
            status="degraded",
            metadata={"desired_count": 4, "running_count": 3, "pending_count": 1},
        )
    ]
    findings = evaluate_health("123456789012", resources)
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert findings[0].code == "ECS_RUNNING_BELOW_DESIRED"


def test_healthy_resources_do_not_create_findings() -> None:
    resources = [
        ResourceRecord(
            service="rds",
            resource_type="db_instance",
            resource_id="orders",
            name="orders",
            region="ap-south-1",
            status="available",
        )
    ]
    assert evaluate_health("123456789012", resources) == []
