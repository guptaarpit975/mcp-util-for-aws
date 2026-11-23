import pytest
from aws_ops_mcp.aws import get_rds_metric_summary, search_log_reference


def test_log_search_rejects_unbounded_group_list_before_calling_aws() -> None:
    with pytest.raises(ValueError, match="between 1 and 10"):
        search_log_reference("ap-south-1", "ref-123", [])


def test_rds_metrics_reject_invalid_period_before_calling_aws() -> None:
    with pytest.raises(ValueError, match="multiple of 60"):
        get_rds_metric_summary("ap-south-1", "orders", period_seconds=61)
