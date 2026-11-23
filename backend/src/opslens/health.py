from __future__ import annotations

from datetime import UTC, datetime

from aws_ops_mcp.contracts import InventoryResult
from aws_ops_mcp.health import evaluate_health
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Finding, HealthSnapshot, ResourceInventory
from .schemas import HealthSummaryResponse


class HealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reconcile(self, inventory: InventoryResult) -> list[Finding]:
        now = datetime.now(UTC)
        evaluated = evaluate_health(inventory.account_id, inventory.resources)
        findings_by_resource: dict[str, list] = {}
        for finding in evaluated:
            findings_by_resource.setdefault(finding.resource_id, []).append(finding)

        await self.session.execute(
            delete(HealthSnapshot).where(HealthSnapshot.account_id == inventory.account_id)
        )
        for resource in inventory.resources:
            resource_findings = findings_by_resource.get(resource.resource_id, [])
            self.session.add(
                HealthSnapshot(
                    account_id=inventory.account_id,
                    region=resource.region,
                    service=resource.service,
                    resource_type=resource.resource_type,
                    resource_id=resource.resource_id,
                    resource_name=resource.name,
                    status="attention" if resource_findings else "healthy",
                    evidence_json={
                        "resource_status": resource.status,
                        "finding_codes": [item.code for item in resource_findings],
                    },
                    evaluated_at=now,
                )
            )

        existing = {
            item.fingerprint: item
            for item in (
                await self.session.scalars(
                    select(Finding).where(Finding.account_id == inventory.account_id)
                )
            ).all()
        }
        active_fingerprints: set[str] = set()
        for value in evaluated:
            active_fingerprints.add(value.fingerprint)
            record = existing.get(value.fingerprint)
            if record is None:
                record = Finding(
                    fingerprint=value.fingerprint,
                    account_id=value.account_id,
                    region=value.region,
                    service=value.service,
                    resource_type=value.resource_type,
                    resource_id=value.resource_id,
                    resource_name=value.resource_name,
                    code=value.code,
                    severity=value.severity,
                    summary=value.summary,
                    evidence_json=value.evidence,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                self.session.add(record)
            else:
                record.region = value.region
                record.service = value.service
                record.resource_name = value.resource_name
                record.severity = value.severity
                record.summary = value.summary
                record.evidence_json = value.evidence
                record.last_seen_at = now
                if record.status == "resolved":
                    record.status = "open"
                    record.resolved_at = None

        for fingerprint, record in existing.items():
            if fingerprint not in active_fingerprints and record.status != "resolved":
                record.status = "resolved"
                record.resolved_at = now

        await self.session.flush()
        return list(
            (
                await self.session.scalars(
                    select(Finding)
                    .where(
                        Finding.account_id == inventory.account_id,
                        Finding.status.in_(["open", "acknowledged"]),
                    )
                    .order_by(Finding.severity, Finding.last_seen_at.desc())
                )
            ).all()
        )

    async def list_findings(self, status: str | None = None) -> tuple[list[Finding], int]:
        filters = []
        if status and status != "all":
            filters.append(Finding.status == status)
        query = (
            select(Finding)
            .where(*filters)
            .order_by(
                Finding.status,
                Finding.severity,
                Finding.last_seen_at.desc(),
            )
        )
        count_query = select(func.count()).select_from(Finding).where(*filters)
        items = list((await self.session.scalars(query)).all())
        total = int((await self.session.scalar(count_query)) or 0)
        return items, total

    async def acknowledge(self, finding_id: str) -> Finding | None:
        record = await self.session.get(Finding, finding_id)
        if record and record.status == "open":
            record.status = "acknowledged"
            record.acknowledged_at = datetime.now(UTC)
            await self.session.flush()
        return record

    async def evaluate_stored_inventory(self) -> list[Finding]:
        resources = list((await self.session.scalars(select(ResourceInventory))).all())
        if not resources:
            return []
        grouped: dict[str, list[ResourceInventory]] = {}
        for resource in resources:
            grouped.setdefault(resource.account_id, []).append(resource)
        findings: list[Finding] = []
        from aws_ops_mcp.contracts import ResourceRecord

        for account_id, rows in grouped.items():
            inventory = InventoryResult(
                account_id=account_id,
                profile="stored-inventory",
                resources=[
                    ResourceRecord(
                        service=row.service,
                        resource_type=row.resource_type,
                        resource_id=row.resource_id,
                        name=row.name,
                        region=row.region,
                        arn=row.arn,
                        status=row.status,
                        metadata=row.metadata_json,
                    )
                    for row in rows
                ],
            )
            findings.extend(await self.reconcile(inventory))
        return findings

    async def summary(self) -> HealthSummaryResponse:
        total_resources = int(
            (await self.session.scalar(select(func.count()).select_from(HealthSnapshot))) or 0
        )
        healthy_resources = int(
            (
                await self.session.scalar(
                    select(func.count())
                    .select_from(HealthSnapshot)
                    .where(HealthSnapshot.status == "healthy")
                )
            )
            or 0
        )
        open_filter = Finding.status.in_(["open", "acknowledged"])
        open_findings = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(Finding).where(open_filter)
                )
            )
            or 0
        )
        critical = int(
            (
                await self.session.scalar(
                    select(func.count())
                    .select_from(Finding)
                    .where(open_filter, Finding.severity == "critical")
                )
            )
            or 0
        )
        warning = int(
            (
                await self.session.scalar(
                    select(func.count())
                    .select_from(Finding)
                    .where(open_filter, Finding.severity == "warning")
                )
            )
            or 0
        )
        last_evaluated = await self.session.scalar(select(func.max(HealthSnapshot.evaluated_at)))
        return HealthSummaryResponse(
            total_resources=total_resources,
            healthy_resources=healthy_resources,
            open_findings=open_findings,
            critical_findings=critical,
            warning_findings=warning,
            last_evaluated_at=last_evaluated,
        )
