from aws_ops_mcp.server import mcp
from mcp import Client


async def test_server_exposes_only_expected_read_only_tools() -> None:
    async with Client(mcp) as client:
        result = await client.list_tools()

    names = {tool.name for tool in result.tools}
    assert names == {
        "get_caller_identity",
        "get_aws_health_summary",
        "get_rds_metrics",
        "list_application_load_balancers",
        "list_cloudfront_distributions",
        "list_cloudwatch_alarms",
        "list_cloudwatch_log_groups",
        "list_ecr_repositories",
        "list_ecs_resources",
        "list_iam_roles",
        "list_kms_keys",
        "list_parameter_metadata",
        "list_rds_instances",
        "list_s3_buckets",
        "list_ses_identities",
        "search_cloudwatch_logs",
    }
    assert not any("delete" in name or "update" in name or "create" in name for name in names)
