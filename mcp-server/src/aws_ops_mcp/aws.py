from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .contracts import InventoryResult, ResourceRecord

Collector = Callable[[boto3.Session, str, int], list[ResourceRecord]]

REGIONAL_COLLECTORS: dict[str, Collector] = {}
GLOBAL_COLLECTORS: dict[str, Collector] = {}


def _register(registry: dict[str, Collector], name: str):
    def decorator(function: Collector) -> Collector:
        registry[name] = function
        return function

    return decorator


def configured_profile(explicit_profile: str | None = None) -> str:
    return explicit_profile or os.getenv("OPSLENS_AWS_PROFILE", "")


def new_session(profile: str | None = None, region: str | None = None) -> boto3.Session:
    selected_profile = configured_profile(profile)
    kwargs: dict[str, str] = {}
    if selected_profile:
        kwargs["profile_name"] = selected_profile
    if region:
        kwargs["region_name"] = region
    return boto3.Session(**kwargs)


def caller_identity(profile: str | None = None) -> dict[str, str]:
    selected_profile = configured_profile(profile)
    session = new_session(selected_profile)
    result = session.client("sts").get_caller_identity()
    return {
        "account_id": result["Account"],
        "arn": result["Arn"],
        "user_id": result["UserId"],
        "profile": selected_profile or "default",
    }


def _pages(client: Any, operation: str, result_key: str, page_limit: int) -> Iterable[Any]:
    if client.can_paginate(operation):
        paginator = client.get_paginator(operation)
        for index, page in enumerate(paginator.paginate()):
            if index >= page_limit:
                break
            yield from page.get(result_key, [])
        return
    response = getattr(client, operation)()
    yield from response.get(result_key, [])


@_register(GLOBAL_COLLECTORS, "cloudfront")
def collect_cloudfront(session: boto3.Session, _: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("cloudfront")
    resources: list[ResourceRecord] = []
    marker: str | None = None
    for _index in range(page_limit):
        kwargs = {"Marker": marker} if marker else {}
        response = client.list_distributions(**kwargs)
        distribution_list = response.get("DistributionList", {})
        for item in distribution_list.get("Items", []):
            resources.append(
                ResourceRecord(
                    service="cloudfront",
                    resource_type="distribution",
                    resource_id=item["Id"],
                    name=item.get("Comment") or item.get("DomainName") or item["Id"],
                    arn=item.get("ARN"),
                    region="global",
                    status="enabled" if item.get("Enabled") else "disabled",
                    metadata={
                        "domain_name": item.get("DomainName"),
                        "aliases": item.get("Aliases", {}).get("Items", []),
                        "price_class": item.get("PriceClass"),
                        "http_version": item.get("HttpVersion"),
                    },
                )
            )
        if not distribution_list.get("IsTruncated"):
            break
        marker = distribution_list.get("NextMarker")
    return resources


@_register(GLOBAL_COLLECTORS, "s3")
def collect_s3(session: boto3.Session, _: str, _page_limit: int) -> list[ResourceRecord]:
    response = session.client("s3").list_buckets()
    return [
        ResourceRecord(
            service="s3",
            resource_type="bucket",
            resource_id=item["Name"],
            name=item["Name"],
            arn=f"arn:aws:s3:::{item['Name']}",
            region="global",
            status="available",
            metadata={"creation_date": item.get("CreationDate")},
        )
        for item in response.get("Buckets", [])
    ]


@_register(GLOBAL_COLLECTORS, "iam")
def collect_iam(session: boto3.Session, _: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("iam")
    resources: list[ResourceRecord] = []
    for role in _pages(client, "list_roles", "Roles", page_limit):
        resources.append(
            ResourceRecord(
                service="iam",
                resource_type="role",
                resource_id=role["RoleName"],
                name=role["RoleName"],
                arn=role.get("Arn"),
                region="global",
                status="active",
                metadata={
                    "path": role.get("Path"),
                    "created_at": role.get("CreateDate"),
                    "max_session_duration": role.get("MaxSessionDuration"),
                },
            )
        )
    return resources


@_register(REGIONAL_COLLECTORS, "elbv2")
def collect_elbv2(session: boto3.Session, region: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("elbv2", region_name=region)
    resources: list[ResourceRecord] = []
    for item in _pages(client, "describe_load_balancers", "LoadBalancers", page_limit):
        if item.get("Type") != "application":
            continue
        resources.append(
            ResourceRecord(
                service="elbv2",
                resource_type="application_load_balancer",
                resource_id=item["LoadBalancerArn"],
                name=item["LoadBalancerName"],
                arn=item["LoadBalancerArn"],
                region=region,
                status=item.get("State", {}).get("Code", "unknown"),
                metadata={
                    "dns_name": item.get("DNSName"),
                    "scheme": item.get("Scheme"),
                    "vpc_id": item.get("VpcId"),
                },
            )
        )
    return resources


@_register(REGIONAL_COLLECTORS, "ecs")
def collect_ecs(session: boto3.Session, region: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("ecs", region_name=region)
    cluster_arns = list(_pages(client, "list_clusters", "clusterArns", page_limit))
    resources: list[ResourceRecord] = [
        ResourceRecord(
            service="ecs",
            resource_type="cluster",
            resource_id=arn,
            name=arn.rsplit("/", 1)[-1],
            arn=arn,
            region=region,
            status="active",
        )
        for arn in cluster_arns
    ]
    for cluster_arn in cluster_arns:
        service_arns: list[str] = []
        next_token: str | None = None
        for _index in range(page_limit):
            kwargs: dict[str, str] = {"cluster": cluster_arn}
            if next_token:
                kwargs["nextToken"] = next_token
            response = client.list_services(**kwargs)
            service_arns.extend(response.get("serviceArns", []))
            next_token = response.get("nextToken")
            if not next_token:
                break
        for offset in range(0, len(service_arns), 10):
            descriptions = client.describe_services(
                cluster=cluster_arn,
                services=service_arns[offset : offset + 10],
            ).get("services", [])
            for item in descriptions:
                running = item.get("runningCount", 0)
                desired = item.get("desiredCount", 0)
                resources.append(
                    ResourceRecord(
                        service="ecs",
                        resource_type="service",
                        resource_id=item["serviceArn"],
                        name=item["serviceName"],
                        arn=item["serviceArn"],
                        region=region,
                        status="healthy" if running >= desired else "degraded",
                        metadata={
                            "cluster_arn": cluster_arn,
                            "launch_type": item.get("launchType"),
                            "desired_count": desired,
                            "running_count": running,
                            "pending_count": item.get("pendingCount", 0),
                            "task_definition": item.get("taskDefinition"),
                        },
                    )
                )
    return resources


@_register(REGIONAL_COLLECTORS, "rds")
def collect_rds(session: boto3.Session, region: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("rds", region_name=region)
    resources: list[ResourceRecord] = []
    for item in _pages(client, "describe_db_instances", "DBInstances", page_limit):
        resources.append(
            ResourceRecord(
                service="rds",
                resource_type="db_instance",
                resource_id=item["DBInstanceIdentifier"],
                name=item["DBInstanceIdentifier"],
                arn=item.get("DBInstanceArn"),
                region=region,
                status=item.get("DBInstanceStatus", "unknown"),
                metadata={
                    "engine": item.get("Engine"),
                    "engine_version": item.get("EngineVersion"),
                    "instance_class": item.get("DBInstanceClass"),
                    "multi_az": item.get("MultiAZ"),
                    "publicly_accessible": item.get("PubliclyAccessible"),
                    "endpoint": item.get("Endpoint", {}).get("Address"),
                },
            )
        )
    return resources


@_register(REGIONAL_COLLECTORS, "kms")
def collect_kms(session: boto3.Session, region: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("kms", region_name=region)
    return [
        ResourceRecord(
            service="kms",
            resource_type="key",
            resource_id=item["KeyId"],
            name=item["KeyId"],
            arn=item.get("KeyArn"),
            region=region,
            status="unknown",
        )
        for item in _pages(client, "list_keys", "Keys", page_limit)
    ]


@_register(REGIONAL_COLLECTORS, "ses")
def collect_ses(session: boto3.Session, region: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("sesv2", region_name=region)
    resources: list[ResourceRecord] = []
    for item in _pages(client, "list_email_identities", "EmailIdentities", page_limit):
        resources.append(
            ResourceRecord(
                service="ses",
                resource_type="email_identity",
                resource_id=item["IdentityName"],
                name=item["IdentityName"],
                region=region,
                status="verified" if item.get("VerifiedForSendingStatus") else "unverified",
                metadata={"identity_type": item.get("IdentityType")},
            )
        )
    return resources


@_register(REGIONAL_COLLECTORS, "ssm")
def collect_ssm(session: boto3.Session, region: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("ssm", region_name=region)
    return [
        ResourceRecord(
            service="ssm",
            resource_type="parameter",
            resource_id=item["Name"],
            name=item["Name"],
            region=region,
            status="available",
            metadata={
                "type": item.get("Type"),
                "version": item.get("Version"),
                "tier": item.get("Tier"),
                "last_modified": item.get("LastModifiedDate"),
            },
        )
        for item in _pages(client, "describe_parameters", "Parameters", page_limit)
    ]


@_register(REGIONAL_COLLECTORS, "cloudwatch")
def collect_cloudwatch(
    session: boto3.Session,
    region: str,
    page_limit: int,
) -> list[ResourceRecord]:
    client = session.client("cloudwatch", region_name=region)
    return [
        ResourceRecord(
            service="cloudwatch",
            resource_type="alarm",
            resource_id=item["AlarmName"],
            name=item["AlarmName"],
            arn=item.get("AlarmArn"),
            region=region,
            status=item.get("StateValue", "unknown").lower(),
            metadata={
                "namespace": item.get("Namespace"),
                "metric_name": item.get("MetricName"),
                "reason": item.get("StateReason"),
            },
        )
        for item in _pages(client, "describe_alarms", "MetricAlarms", page_limit)
    ]


@_register(REGIONAL_COLLECTORS, "ecr")
def collect_ecr(session: boto3.Session, region: str, page_limit: int) -> list[ResourceRecord]:
    client = session.client("ecr", region_name=region)
    return [
        ResourceRecord(
            service="ecr",
            resource_type="repository",
            resource_id=item["repositoryName"],
            name=item["repositoryName"],
            arn=item.get("repositoryArn"),
            region=region,
            status="available",
            metadata={
                "repository_uri": item.get("repositoryUri"),
                "tag_mutability": item.get("imageTagMutability"),
                "scan_on_push": item.get("imageScanningConfiguration", {}).get("scanOnPush"),
                "encryption_type": item.get("encryptionConfiguration", {}).get("encryptionType"),
            },
        )
        for item in _pages(client, "describe_repositories", "repositories", page_limit)
    ]


def collect_inventory(
    profile: str | None,
    regions: list[str],
    *,
    services: list[str] | None = None,
    page_limit: int = 10,
) -> InventoryResult:
    identity = caller_identity(profile)
    selected_profile = identity["profile"]
    session = new_session(profile)
    selected_services = set(services or [*GLOBAL_COLLECTORS, *REGIONAL_COLLECTORS])
    result = InventoryResult(account_id=identity["account_id"], profile=selected_profile)

    for service, collector in GLOBAL_COLLECTORS.items():
        if service not in selected_services:
            continue
        try:
            result.resources.extend(collector(session, "global", page_limit))
        except (BotoCoreError, ClientError) as error:
            result.warnings.append(_safe_error(service, "global", error))

    for region in regions:
        for service, collector in REGIONAL_COLLECTORS.items():
            if service not in selected_services:
                continue
            try:
                result.resources.extend(collector(session, region, page_limit))
            except (BotoCoreError, ClientError) as error:
                result.warnings.append(_safe_error(service, region, error))
    return result


def collect_service(
    service: str,
    region: str | None = None,
    *,
    profile: str | None = None,
    page_limit: int = 10,
) -> InventoryResult:
    regions = [region] if region else []
    if service in REGIONAL_COLLECTORS and not regions:
        raise ValueError(f"region is required for {service}")
    return collect_inventory(profile, regions, services=[service], page_limit=page_limit)


def list_log_groups(
    region: str,
    *,
    profile: str | None = None,
    page_limit: int = 10,
) -> dict[str, Any]:
    identity = caller_identity(profile)
    client = new_session(profile, region).client("logs", region_name=region)
    groups: list[dict[str, Any]] = []
    next_token: str | None = None
    for _index in range(page_limit):
        arguments = {"nextToken": next_token} if next_token else {}
        response = client.describe_log_groups(**arguments)
        groups.extend(
            {
                "log_group_name": item["logGroupName"],
                "arn": item.get("arn"),
                "retention_days": item.get("retentionInDays"),
                "stored_bytes": item.get("storedBytes"),
                "log_group_class": item.get("logGroupClass"),
            }
            for item in response.get("logGroups", [])
        )
        next_token = response.get("nextToken")
        if not next_token:
            break
    return {
        "account_id": identity["account_id"],
        "profile": identity["profile"],
        "region": region,
        "log_groups": groups,
        "truncated": bool(next_token),
    }


def search_log_reference(
    region: str,
    reference_id: str,
    log_group_names: list[str],
    *,
    lookback_minutes: int = 60,
    limit: int = 100,
    profile: str | None = None,
) -> dict[str, Any]:
    if not reference_id.strip():
        raise ValueError("reference_id must not be empty")
    if not 1 <= len(log_group_names) <= 10:
        raise ValueError("log_group_names must contain between 1 and 10 groups")
    if not 1 <= lookback_minutes <= 10_080:
        raise ValueError("lookback_minutes must be between 1 and 10080")
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    identity = caller_identity(profile)
    client = new_session(profile, region).client("logs", region_name=region)
    now = datetime.now(UTC)
    start = now - timedelta(minutes=lookback_minutes)
    escaped_reference = reference_id.replace("\\", "\\\\").replace('"', '\\"')
    events: list[dict[str, Any]] = []
    warnings: list[str] = []
    for log_group_name in log_group_names:
        if len(events) >= limit:
            break
        try:
            response = client.filter_log_events(
                logGroupName=log_group_name,
                startTime=int(start.timestamp() * 1000),
                endTime=int(now.timestamp() * 1000),
                filterPattern=f'"{escaped_reference}"',
                limit=limit - len(events),
            )
            events.extend(
                {
                    "log_group_name": log_group_name,
                    "log_stream_name": item.get("logStreamName"),
                    "timestamp": item.get("timestamp"),
                    "ingestion_time": item.get("ingestionTime"),
                    "message": item.get("message", "")[:5_000],
                    "event_id": item.get("eventId"),
                }
                for item in response.get("events", [])
            )
        except (BotoCoreError, ClientError) as error:
            warnings.append(_safe_error("cloudwatch-logs", region, error))
    events.sort(key=lambda item: item.get("timestamp") or 0)
    return {
        "account_id": identity["account_id"],
        "profile": identity["profile"],
        "region": region,
        "reference_id": reference_id,
        "start_time": start,
        "end_time": now,
        "searched_log_groups": log_group_names,
        "events": events[:limit],
        "warnings": warnings,
    }


def get_rds_metric_summary(
    region: str,
    db_instance_identifier: str,
    *,
    lookback_minutes: int = 60,
    period_seconds: int = 300,
    profile: str | None = None,
) -> dict[str, Any]:
    if not db_instance_identifier.strip():
        raise ValueError("db_instance_identifier must not be empty")
    if not 5 <= lookback_minutes <= 10_080:
        raise ValueError("lookback_minutes must be between 5 and 10080")
    if period_seconds < 60 or period_seconds % 60:
        raise ValueError("period_seconds must be a multiple of 60")

    identity = caller_identity(profile)
    client = new_session(profile, region).client("cloudwatch", region_name=region)
    end = datetime.now(UTC)
    start = end - timedelta(minutes=lookback_minutes)
    metric_names = [
        "CPUUtilization",
        "DatabaseConnections",
        "FreeableMemory",
        "FreeStorageSpace",
        "ReadIOPS",
        "WriteIOPS",
    ]
    response = client.get_metric_data(
        MetricDataQueries=[
            {
                "Id": f"metric{index}",
                "Label": name,
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/RDS",
                        "MetricName": name,
                        "Dimensions": [
                            {
                                "Name": "DBInstanceIdentifier",
                                "Value": db_instance_identifier,
                            }
                        ],
                    },
                    "Period": period_seconds,
                    "Stat": "Average",
                },
                "ReturnData": True,
            }
            for index, name in enumerate(metric_names)
        ],
        StartTime=start,
        EndTime=end,
        ScanBy="TimestampAscending",
    )
    metrics: dict[str, Any] = {}
    warnings: list[str] = []
    for item in response.get("MetricDataResults", []):
        values = item.get("Values", [])
        timestamps = item.get("Timestamps", [])
        label = item.get("Label") or item.get("Id")
        metrics[label] = {
            "status": item.get("StatusCode"),
            "sample_count": len(values),
            "latest": values[-1] if values else None,
            "average": sum(values) / len(values) if values else None,
            "maximum": max(values) if values else None,
            "series": [
                {"timestamp": timestamp, "value": value}
                for timestamp, value in zip(timestamps, values, strict=False)
            ],
        }
        if item.get("StatusCode") not in {None, "Complete"}:
            warnings.append(f"{label}: CloudWatch status {item.get('StatusCode')}")
        warnings.extend(
            f"{label}: {message.get('Code')} - {message.get('Value')}"
            for message in item.get("Messages", [])
        )
    return {
        "account_id": identity["account_id"],
        "profile": identity["profile"],
        "region": region,
        "db_instance_identifier": db_instance_identifier,
        "start_time": start,
        "end_time": end,
        "period_seconds": period_seconds,
        "metrics": metrics,
        "warnings": warnings,
    }


def _safe_error(service: str, region: str, error: Exception) -> str:
    if isinstance(error, ClientError):
        details = error.response.get("Error", {})
        code = details.get("Code", "ClientError")
        message = details.get("Message", "AWS request failed")
        return f"{service} ({region}): {code} - {message}"
    return f"{service} ({region}): {type(error).__name__}"
