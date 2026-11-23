from __future__ import annotations

import os

from mcp.server import MCPServer

from .aws import (
    caller_identity,
    collect_service,
    configured_profile,
    get_rds_metric_summary,
    list_log_groups,
    search_log_reference,
)
from .contracts import EvidenceEnvelope
from .health import evaluate_health

mcp = MCPServer(
    "OpsLens AWS Read-Only Tools",
    instructions=(
        "Read-only AWS inspection tools. The AWS profile is selected by the host and is not "
        "accepted as a model-controlled tool argument."
    ),
)


def _service_evidence(tool: str, service: str, region: str | None = None) -> EvidenceEnvelope:
    profile = configured_profile()
    page_limit = int(os.getenv("OPSLENS_INVENTORY_PAGE_LIMIT", "10"))
    result = collect_service(
        service,
        region,
        profile=profile,
        page_limit=page_limit,
    )
    return EvidenceEnvelope(
        tool=tool,
        account_id=result.account_id,
        profile=result.profile,
        status="partial" if result.warnings else "ok",
        facts={"resource_count": len(result.resources), "service": service, "region": region},
        resources=result.resources,
        warnings=result.warnings,
    )


@mcp.tool()
def get_caller_identity() -> EvidenceEnvelope:
    """Return the AWS account and principal selected by the local host."""
    identity = caller_identity()
    return EvidenceEnvelope(
        tool="get_caller_identity",
        account_id=identity["account_id"],
        profile=identity["profile"],
        facts={"arn": identity["arn"], "user_id": identity["user_id"]},
    )


@mcp.tool()
def list_cloudfront_distributions() -> EvidenceEnvelope:
    """List CloudFront distributions and their basic read-only posture."""
    return _service_evidence("list_cloudfront_distributions", "cloudfront")


@mcp.tool()
def list_application_load_balancers(region: str) -> EvidenceEnvelope:
    """List Application Load Balancers in one AWS region."""
    return _service_evidence("list_application_load_balancers", "elbv2", region)


@mcp.tool()
def list_s3_buckets() -> EvidenceEnvelope:
    """List S3 buckets without reading object contents."""
    return _service_evidence("list_s3_buckets", "s3")


@mcp.tool()
def list_ecs_resources(region: str) -> EvidenceEnvelope:
    """List ECS clusters and services, including desired and running task counts."""
    return _service_evidence("list_ecs_resources", "ecs", region)


@mcp.tool()
def list_rds_instances(region: str) -> EvidenceEnvelope:
    """List RDS instances and non-secret configuration in one AWS region."""
    return _service_evidence("list_rds_instances", "rds", region)


@mcp.tool()
def list_kms_keys(region: str) -> EvidenceEnvelope:
    """List KMS key identifiers without performing cryptographic operations."""
    return _service_evidence("list_kms_keys", "kms", region)


@mcp.tool()
def list_ses_identities(region: str) -> EvidenceEnvelope:
    """List SES email identities and verification state without sending email."""
    return _service_evidence("list_ses_identities", "ses", region)


@mcp.tool()
def list_parameter_metadata(region: str) -> EvidenceEnvelope:
    """List Parameter Store metadata without retrieving parameter values."""
    return _service_evidence("list_parameter_metadata", "ssm", region)


@mcp.tool()
def list_cloudwatch_alarms(region: str) -> EvidenceEnvelope:
    """List CloudWatch metric alarms and their current state."""
    return _service_evidence("list_cloudwatch_alarms", "cloudwatch", region)


@mcp.tool()
def list_cloudwatch_log_groups(region: str) -> EvidenceEnvelope:
    """List CloudWatch log groups and retention metadata without reading log events."""
    result = list_log_groups(
        region,
        profile=configured_profile(),
        page_limit=int(os.getenv("OPSLENS_INVENTORY_PAGE_LIMIT", "10")),
    )
    return EvidenceEnvelope(
        tool="list_cloudwatch_log_groups",
        account_id=result["account_id"],
        profile=result["profile"],
        status="partial" if result["truncated"] else "ok",
        facts={
            "region": region,
            "log_group_count": len(result["log_groups"]),
            "log_groups": result["log_groups"],
            "truncated": result["truncated"],
        },
        warnings=["Log group enumeration reached the configured page limit."]
        if result["truncated"]
        else [],
    )


@mcp.tool()
def search_cloudwatch_logs(
    region: str,
    reference_id: str,
    log_group_names: list[str],
    lookback_minutes: int = 60,
    limit: int = 100,
) -> EvidenceEnvelope:
    """Find a reference ID in up to ten named log groups within a bounded time window."""
    result = search_log_reference(
        region,
        reference_id,
        log_group_names,
        lookback_minutes=lookback_minutes,
        limit=limit,
        profile=configured_profile(),
    )
    return EvidenceEnvelope(
        tool="search_cloudwatch_logs",
        account_id=result["account_id"],
        profile=result["profile"],
        status="partial" if result["warnings"] else "ok",
        facts={
            "region": region,
            "reference_id": reference_id,
            "start_time": result["start_time"],
            "end_time": result["end_time"],
            "searched_log_groups": result["searched_log_groups"],
            "event_count": len(result["events"]),
            "events": result["events"],
        },
        warnings=result["warnings"],
    )


@mcp.tool()
def get_rds_metrics(
    region: str,
    db_instance_identifier: str,
    lookback_minutes: int = 60,
    period_seconds: int = 300,
) -> EvidenceEnvelope:
    """Read bounded CloudWatch CPU, connection, memory, storage, and IOPS metrics for RDS."""
    result = get_rds_metric_summary(
        region,
        db_instance_identifier,
        lookback_minutes=lookback_minutes,
        period_seconds=period_seconds,
        profile=configured_profile(),
    )
    return EvidenceEnvelope(
        tool="get_rds_metrics",
        account_id=result["account_id"],
        profile=result["profile"],
        status="partial" if result["warnings"] else "ok",
        facts={
            "region": region,
            "db_instance_identifier": db_instance_identifier,
            "start_time": result["start_time"],
            "end_time": result["end_time"],
            "period_seconds": result["period_seconds"],
            "metrics": result["metrics"],
        },
        warnings=result["warnings"],
    )


@mcp.tool()
def list_ecr_repositories(region: str) -> EvidenceEnvelope:
    """List ECR repositories without pulling, pushing, or deleting images."""
    return _service_evidence("list_ecr_repositories", "ecr", region)


@mcp.tool()
def list_iam_roles() -> EvidenceEnvelope:
    """List IAM roles and basic metadata without modifying IAM."""
    return _service_evidence("list_iam_roles", "iam")


@mcp.tool()
def get_aws_health_summary(regions: list[str]) -> EvidenceEnvelope:
    """Evaluate deterministic health findings across configured AWS services and regions."""
    from .aws import collect_inventory

    profile = configured_profile()
    page_limit = int(os.getenv("OPSLENS_INVENTORY_PAGE_LIMIT", "10"))
    result = collect_inventory(profile, regions, page_limit=page_limit)
    findings = evaluate_health(result.account_id, result.resources)
    severity_counts = {
        severity: sum(1 for finding in findings if finding.severity == severity)
        for severity in ("critical", "warning", "info")
    }
    return EvidenceEnvelope(
        tool="get_aws_health_summary",
        account_id=result.account_id,
        profile=result.profile,
        status="partial" if result.warnings else "ok",
        facts={
            "resource_count": len(result.resources),
            "finding_count": len(findings),
            "severity_counts": severity_counts,
            "findings": [finding.model_dump(mode="json") for finding in findings],
        },
        warnings=result.warnings,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
