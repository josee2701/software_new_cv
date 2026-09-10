"""Validation engine: runs the registered rules and computes the score (spec §9.1).

Score (DECISIONS.md, "Jefe (cierre ronda 1)"): each rule with at least one finding subtracts its
weight **once** per report — error = weight, warning = weight / 2, info = 0 — and the result is
rounded down with a minimum of 0. ``Phase.PRE`` rules always run; ``Phase.POST`` rules only when
``ctx.pdf`` is present.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from models.enums import Severity
from validator.registry import RuleSpec, registered_rules
from validator.types import Finding, Phase, Report, RuleContext

SEVERITY_ORDER: dict[Severity, int] = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
PENALTY_FACTOR: dict[Severity, float] = {
    Severity.ERROR: 1.0,
    Severity.WARNING: 0.5,
    Severity.INFO: 0,
}


def applicable_rules(ctx: RuleContext, rules: Iterable[RuleSpec] | None = None) -> list[RuleSpec]:
    """Rules that run for the context: right destination and phase (POST only with a PDF)."""
    specs = registered_rules() if rules is None else list(rules)
    return [
        spec
        for spec in specs
        if spec.runs_for(ctx.destination) and (spec.phase is Phase.PRE or ctx.pdf is not None)
    ]


def penalty(spec: RuleSpec, severity: Severity) -> float:
    return spec.weight * PENALTY_FACTOR[severity]


def compute_score(penalties: Iterable[float]) -> int:
    return max(0, math.floor(100 - sum(penalties)))


def run(ctx: RuleContext, *, rules: Iterable[RuleSpec] | None = None) -> Report:
    """Run the applicable rules (all registered ones by default) and build the report."""
    findings: list[tuple[int, int, Finding]] = []
    penalties: list[float] = []
    for index, spec in enumerate(applicable_rules(ctx, rules)):
        severity = spec.severity_for(ctx.destination)
        assert severity is not None  # guaranteed by applicable_rules
        hits = spec.fn(ctx)
        if not hits:
            continue
        penalties.append(penalty(spec, severity))
        for hit in hits:
            finding = Finding(
                rule_id=spec.id,
                severity=severity,
                message=hit.message,
                section=hit.section or spec.section,
                entity=hit.entity,
                entity_id=hit.entity_id,
                suggestion=hit.suggestion,
            )
            findings.append((SEVERITY_ORDER[severity], index, finding))
    findings.sort(key=lambda item: (item[0], item[1]))  # stable: keeps the hit order per rule
    return Report(score=compute_score(penalties), findings=tuple(f for _, _, f in findings))
