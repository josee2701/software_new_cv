"""Rule registry: the ``@rule`` decorator and the list of registered rules (spec §9.1).

A rule declares its severity per destination; ``"-"`` / ``"–"`` / missing means the rule does
not run for that destination (DECISIONS.md, "Jefe (cierre ronda 1)").
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from models.enums import Destination, Severity
from validator.types import Phase, RuleFn

_SKIP = {"-", "–", "—", "", None}


@dataclass(frozen=True)
class RuleSpec:
    id: str
    section: str
    severity: Mapping[Destination, Severity]
    weight: int
    phase: Phase
    fn: RuleFn
    description: str = ""

    def severity_for(self, destination: Destination) -> Severity | None:
        """Severity for ``destination`` or None if the rule does not run there."""
        return self.severity.get(destination)

    def runs_for(self, destination: Destination) -> bool:
        return destination in self.severity


_REGISTRY: dict[str, RuleSpec] = {}


def _parse_severity(raw: Mapping[str, str | None]) -> dict[Destination, Severity]:
    parsed: dict[Destination, Severity] = {}
    for key, value in raw.items():
        destination = Destination(key)
        if value is None or value in _SKIP:
            continue
        parsed[destination] = Severity(value)
    return parsed


def make_spec(
    *,
    id: str,
    section: str,
    severity: Mapping[str, str | None],
    weight: int,
    fn: RuleFn,
    phase: Phase = Phase.PRE,
    description: str | None = None,
) -> RuleSpec:
    """Build a :class:`RuleSpec` without registering it (used by ``@rule`` and by tests)."""
    if weight < 0:
        raise ValueError(f"{id}: el peso no puede ser negativo")
    doc = description if description is not None else (fn.__doc__ or "")
    return RuleSpec(
        id=id,
        section=section,
        severity=_parse_severity(severity),
        weight=weight,
        phase=phase,
        fn=fn,
        description=" ".join(doc.split()),
    )


def rule(
    *,
    id: str,
    section: str,
    severity: Mapping[str, str | None],
    weight: int,
    phase: Phase = Phase.PRE,
    description: str | None = None,
) -> Callable[[RuleFn], RuleFn]:
    """Register a pure rule ``(ctx: RuleContext) -> list[Hit]``.

    ``severity={"ats": "error", "mail": "warning"}``; ``"-"`` or a missing key means the rule
    does not run for that destination. ``description`` defaults to the function docstring.
    """

    def decorator(fn: RuleFn) -> RuleFn:
        current = _REGISTRY.get(id)
        if current is not None:
            if current.fn is not fn:
                raise ValueError(f"Regla duplicada: {id}")
            return fn  # module re-imported: keep the registered spec
        _REGISTRY[id] = make_spec(
            id=id,
            section=section,
            severity=severity,
            weight=weight,
            fn=fn,
            phase=phase,
            description=description,
        )
        return fn

    return decorator


def load_rules() -> None:
    """Import every module in ``validator.rules`` (modules starting with ``_`` are helpers)."""
    import validator.rules as package

    for info in pkgutil.iter_modules(package.__path__):
        if not info.name.startswith("_"):
            importlib.import_module(f"{package.__name__}.{info.name}")


def registered_rules() -> list[RuleSpec]:
    """All registered rules (discovering them first), sorted by id."""
    load_rules()
    return sorted(_REGISTRY.values(), key=lambda spec: spec.id)


def get_rule(rule_id: str) -> RuleSpec:
    load_rules()
    return _REGISTRY[rule_id]
