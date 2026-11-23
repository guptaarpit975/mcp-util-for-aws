from __future__ import annotations

import hashlib

from .contracts import HealthFinding, ResourceRecord


def evaluate_health(account_id: str, resources: list[ResourceRecord]) -> list[HealthFinding]:
    findings: list[HealthFinding] = []
    for resource in resources:
        findings.extend(_evaluate_resource(account_id, resource))
    return findings


def _evaluate_resource(account_id: str, resource: ResourceRecord) -> list[HealthFinding]:
    if resource.service == "ecs" and resource.resource_type == "service":
        desired = int(resource.metadata.get("desired_count", 0))
        running = int(resource.metadata.get("running_count", 0))
        pending = int(resource.metadata.get("pending_count", 0))
        if running < desired:
            return [
                _finding(
                    account_id,
                    resource,
                    "ECS_RUNNING_BELOW_DESIRED",
                    "critical",
                    f"{resource.name} has {running} of {desired} desired tasks running",
                    {"desired_count": desired, "running_count": running, "pending_count": pending},
                )
            ]
        if pending > 0:
            return [
                _finding(
                    account_id,
                    resource,
                    "ECS_TASKS_PENDING",
                    "warning",
                    f"{resource.name} has {pending} pending tasks",
                    {"desired_count": desired, "running_count": running, "pending_count": pending},
                )
            ]
    if resource.service == "elbv2" and resource.status != "active":
        return [
            _finding(
                account_id,
                resource,
                "ALB_NOT_ACTIVE",
                "critical",
                f"Application Load Balancer {resource.name} is {resource.status}",
                {"state": resource.status},
            )
        ]
    if resource.service == "rds" and resource.status != "available":
        severity = (
            "critical"
            if resource.status in {"failed", "inaccessible-encryption-credentials"}
            else "warning"
        )
        return [
            _finding(
                account_id,
                resource,
                "RDS_NOT_AVAILABLE",
                severity,
                f"RDS instance {resource.name} is {resource.status}",
                {"db_instance_status": resource.status},
            )
        ]
    if resource.service == "cloudfront" and resource.status == "disabled":
        return [
            _finding(
                account_id,
                resource,
                "CLOUDFRONT_DISABLED",
                "warning",
                f"CloudFront distribution {resource.name} is disabled",
                {"enabled": False},
            )
        ]
    if resource.service == "ses" and resource.status == "unverified":
        return [
            _finding(
                account_id,
                resource,
                "SES_IDENTITY_UNVERIFIED",
                "warning",
                f"SES identity {resource.name} is not verified for sending",
                {"verified_for_sending": False},
            )
        ]
    if resource.service == "cloudwatch" and resource.status in {"alarm", "insufficient_data"}:
        severity = "critical" if resource.status == "alarm" else "warning"
        return [
            _finding(
                account_id,
                resource,
                (
                    "CLOUDWATCH_ALARM_ACTIVE"
                    if resource.status == "alarm"
                    else "CLOUDWATCH_ALARM_NO_DATA"
                ),
                severity,
                f"CloudWatch alarm {resource.name} is {resource.status.replace('_', ' ')}",
                {
                    "state": resource.status,
                    "reason": resource.metadata.get("reason"),
                    "namespace": resource.metadata.get("namespace"),
                    "metric_name": resource.metadata.get("metric_name"),
                },
            )
        ]
    return []


def _finding(
    account_id: str,
    resource: ResourceRecord,
    code: str,
    severity: str,
    summary: str,
    evidence: dict,
) -> HealthFinding:
    identity = "|".join([account_id, resource.region, resource.service, resource.resource_id, code])
    return HealthFinding(
        fingerprint=hashlib.sha256(identity.encode()).hexdigest(),
        account_id=account_id,
        region=resource.region,
        service=resource.service,
        resource_type=resource.resource_type,
        resource_id=resource.resource_id,
        resource_name=resource.name,
        code=code,
        severity=severity,
        summary=summary,
        evidence=evidence,
    )
