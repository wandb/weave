# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "packaging>=21.0",
#     "tomli>=2.0.1; python_version < '3.11'",
# ]
# ///
"""Detect when a Weave integration's upstream library has a newer release.

This is the deterministic "sensor" half of the integration-updater workflow
(see .claude/skills/integration-updater/SKILL.md). It answers three questions
for one or more integrations, and makes no judgement calls and no edits:

1. Which version of the upstream library do we currently support? Parsed from
   the integration's entry in pyproject.toml [project.optional-dependencies].
2. What is the latest release on PyPI, and is it newer than / outside the range
   we support -- in particular, does it cross a major-version boundary or exceed
   an intentional upper cap?
3. Do our monkey-patch targets (the SymbolPatcher dotted paths) still resolve
   against the installed library? A silently-unresolved target means tracing has
   quietly stopped for that call -- the exact failure a library upgrade causes.

The upstream distribution name is read from the integration's
`library_integration(name, distribution_name=...)` call, so aliases like
mistral -> mistralai are handled without a hardcoded table.

Usage:
    # Version + static-symbol check for one integration (no upstream lib needed):
    uv run scripts/check_integration_updates.py openai

    # All integrations, JSON for the skill / automation to parse:
    uv run scripts/check_integration_updates.py --json

    # Also live-resolve patch targets against a specific upstream version:
    uv run --with 'openai==1.109.1' scripts/check_integration_updates.py openai

Exit code is 0 on a successful scan (even when updates are found) and non-zero
only on an unexpected error, so automation can distinguish "ran fine, here are
the findings" from "the tool broke". Pass --fail-on-findings to exit 2 when any
integration has an actionable finding.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.metadata
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 lacks the stdlib TOML parser.
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEGRATIONS_DIR = REPO_ROOT / "weave" / "integrations"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

PYPI_JSON_URL = "https://pypi.org/pypi/{distribution}/json"
DEFAULT_TIMEOUT_SECONDS = 15.0
USER_AGENT = "weave-integration-updater"

# SymbolPatcher(get_base_symbol, attribute_name, make_new_value): we only read
# the first two args. These names let us also read them if ever passed by keyword.
SYMBOL_PATCHER_CALL = "SymbolPatcher"
SYMBOL_PATCHER_BASE_KW = "get_base_symbol"
SYMBOL_PATCHER_ATTR_KW = "attribute_name"

# library_integration(name, *, distribution_name=..., **meta): the PyPI/import
# distribution the integration resolves its version from.
LIBRARY_INTEGRATION_CALL = "library_integration"
DISTRIBUTION_NAME_KW = "distribution_name"

# Operators that establish the lower bound (floor) and upper bound (cap) of a
# version specifier, used to classify how far behind the latest release we are.
FLOOR_OPERATORS = frozenset({">=", ">", "==", "~="})
CAP_OPERATORS = frozenset({"<=", "<", "=="})

# Statuses (highest-signal first) that a scheduled/CI caller should act on.
ACTIONABLE_STATUSES = frozenset({"broken_symbols", "major_update", "capped"})

STATUS_LABELS = {
    "up_to_date": "up to date",
    "minor_update": "newer release available",
    "capped": "latest exceeds pinned cap",
    "major_update": "MAJOR update available",
    "broken_symbols": "PATCH TARGETS BROKEN against installed library",
    "unknown": "could not determine (PyPI fetch failed)",
    "error": "error",
}


@dataclass(frozen=True)
class SymbolTarget:
    """A single SymbolPatcher patch target extracted from integration source."""

    module: str | None  # None unless the base symbol is import_module("<literal>")
    attribute: str | None  # None unless attribute_name is a string literal
    file: str
    lineno: int
    base_source: str  # ast.unparse of the base-symbol expression (dynamic cases)
    attribute_source: str

    @property
    def is_static(self) -> bool:
        return self.module is not None and self.attribute is not None


@dataclass
class SymbolResolution:
    module: str
    attribute: str
    resolved: bool
    reason: str | None = None


@dataclass
class SymbolReport:
    library_installed: bool
    installed_version: str | None
    total: int
    static: int
    resolved: int
    checked_live: bool
    broken: list[SymbolResolution] = field(default_factory=list)
    dynamic: list[dict[str, str]] = field(default_factory=list)


@dataclass
class IntegrationReport:
    integration: str
    status: str = "unknown"
    distribution: str | None = None
    pyproject_extra_found: bool = False
    extra_requirements: list[str] = field(default_factory=list)
    current_specifier: str | None = None
    current_floor: str | None = None
    current_cap: str | None = None
    latest_version: str | None = None
    latest_is_prerelease: bool = False
    newer_available: bool = False
    crosses_major: bool = False
    exceeds_cap: bool = False
    within_current_range: bool = False
    symbols: SymbolReport | None = None
    notes: list[str] = field(default_factory=list)
    error: str | None = None


# --------------------------------------------------------------------------- #
# AST extraction: patch targets and distribution name (no imports required)
# --------------------------------------------------------------------------- #


def _python_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def _string_literal(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _import_module_literal(node: ast.AST | None) -> str | None:
    """Return X from `lambda: importlib.import_module("X")`, else None."""
    if not isinstance(node, ast.Lambda) or not isinstance(node.body, ast.Call):
        return None
    call = node.body
    if _call_name(call.func) != "import_module" or not call.args:
        return None
    return _string_literal(call.args[0])


def _symbol_patcher_args(node: ast.Call) -> tuple[ast.AST | None, ast.AST | None]:
    base = node.args[0] if len(node.args) >= 1 else None
    attr = node.args[1] if len(node.args) >= 2 else None
    for keyword in node.keywords:
        if keyword.arg == SYMBOL_PATCHER_BASE_KW:
            base = keyword.value
        elif keyword.arg == SYMBOL_PATCHER_ATTR_KW:
            attr = keyword.value
    return base, attr


def _iter_calls(directory: Path, call_name: str) -> list[tuple[Path, ast.Call]]:
    calls: list[tuple[Path, ast.Call]] = []
    for path in _python_files(directory):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node.func) == call_name:
                calls.append((path, node))
    return calls


def extract_symbol_targets(directory: Path) -> list[SymbolTarget]:
    """Extract every SymbolPatcher patch target under ``directory``."""
    targets: list[SymbolTarget] = []
    for path, node in _iter_calls(directory, SYMBOL_PATCHER_CALL):
        base_node, attr_node = _symbol_patcher_args(node)
        if base_node is None or attr_node is None:
            continue
        targets.append(
            SymbolTarget(
                module=_import_module_literal(base_node),
                attribute=_string_literal(attr_node),
                file=str(path.relative_to(REPO_ROOT)),
                lineno=node.lineno,
                base_source=ast.unparse(base_node),
                attribute_source=ast.unparse(attr_node),
            )
        )
    return targets


def extract_distribution_name(directory: Path) -> str | None:
    """Read the distribution name from the integration's library_integration call.

    Prefers an explicit ``distribution_name=`` keyword; otherwise falls back to
    the positional integration name the call was built with; None if no call.
    """
    fallback: str | None = None
    for _path, node in _iter_calls(directory, LIBRARY_INTEGRATION_CALL):
        for keyword in node.keywords:
            if keyword.arg == DISTRIBUTION_NAME_KW:
                distribution = _string_literal(keyword.value)
                if distribution is not None:
                    return distribution
        name = _string_literal(node.args[0]) if node.args else None
        if name is not None and fallback is None:
            fallback = name
    return fallback


# --------------------------------------------------------------------------- #
# pyproject + PyPI
# --------------------------------------------------------------------------- #


def load_optional_dependencies() -> dict[str, list[str]]:
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return data.get("project", {}).get("optional-dependencies", {})


def find_requirement(
    requirement_strings: list[str], distribution: str
) -> Requirement | None:
    target = canonicalize_name(distribution)
    for raw in requirement_strings:
        try:
            requirement = Requirement(raw)
        except InvalidRequirement:
            continue
        if canonicalize_name(requirement.name) == target:
            return requirement
    return None


def specifier_bounds(specifier: SpecifierSet) -> tuple[Version | None, Version | None]:
    """Return (floor, cap): the effective lower and upper version bounds."""
    floors: list[Version] = []
    caps: list[Version] = []
    for spec in specifier:
        try:
            version = Version(spec.version)
        except InvalidVersion:
            continue  # e.g. `==1.2.*` wildcard specifiers
        if spec.operator in FLOOR_OPERATORS:
            floors.append(version)
        if spec.operator in CAP_OPERATORS:
            caps.append(version)
    return (max(floors) if floors else None), (min(caps) if caps else None)


def fetch_latest_version(
    distribution: str, *, include_prereleases: bool, timeout: float
) -> tuple[Version | None, str | None]:
    """Return (latest_version, error). Never raises for network/HTTP issues."""
    url = PYPI_JSON_URL.format(distribution=distribution)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # URL is a fixed https PyPI endpoint
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        return None, f"PyPI returned HTTP {exc.code} for {distribution!r}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return None, f"could not reach PyPI for {distribution!r}: {exc}"
    except (ValueError, OSError) as exc:
        return None, f"failed to read PyPI response for {distribution!r}: {exc}"

    candidates: list[Version] = []
    for raw_version, files in payload.get("releases", {}).items():
        if not files or all(file.get("yanked") for file in files):
            continue  # no artifacts, or the whole release was yanked
        try:
            version = Version(raw_version)
        except InvalidVersion:
            continue
        if version.is_prerelease and not include_prereleases:
            continue
        candidates.append(version)
    if candidates:
        return max(candidates), None

    info_version = payload.get("info", {}).get("version")
    if info_version:
        try:
            return Version(info_version), None
        except InvalidVersion:
            return None, f"PyPI reported an unparseable version {info_version!r}"
    return None, f"no suitable releases found on PyPI for {distribution!r}"


# --------------------------------------------------------------------------- #
# Live symbol resolution (imports the upstream library when available)
# --------------------------------------------------------------------------- #


def _dynamic_entries(targets: list[SymbolTarget]) -> list[dict[str, str]]:
    return [
        {
            "file": target.file,
            "lineno": str(target.lineno),
            "base": target.base_source,
            "attribute": target.attribute_source,
        }
        for target in targets
        if not target.is_static
    ]


def _resolve_single(module: str, attribute: str) -> SymbolResolution:
    try:
        base = importlib.import_module(module)
    except Exception as exc:  # importing external code; classify the failure below
        top = module.split(".", maxsplit=1)[0]
        try:
            importlib.import_module(top)
            reason = f"module {module!r} not found (moved or removed?): {type(exc).__name__}"
        except Exception:  # probing whether the top-level package exists
            reason = f"library {top!r} not installed"
        return SymbolResolution(module, attribute, resolved=False, reason=reason)

    obj: object = base
    resolved_path = module
    for part in attribute.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            return SymbolResolution(
                module,
                attribute,
                resolved=False,
                reason=f"{resolved_path!r} has no attribute {part!r}",
            )
        resolved_path = f"{resolved_path}.{part}"
    return SymbolResolution(module, attribute, resolved=True)


def build_symbol_report(
    targets: list[SymbolTarget], distribution: str | None, *, check_live: bool
) -> SymbolReport:
    static_targets = [t for t in targets if t.is_static]
    report = SymbolReport(
        library_installed=False,
        installed_version=None,
        total=len(targets),
        static=len(static_targets),
        resolved=0,
        checked_live=False,
        dynamic=_dynamic_entries(targets),
    )
    if not check_live or not static_targets:
        return report

    # Is any upstream top-level package importable in this interpreter?
    top_levels = {t.module.split(".", maxsplit=1)[0] for t in static_targets if t.module}
    for top in top_levels:
        try:
            importlib.import_module(top)
            report.library_installed = True
            break
        except Exception:  # probing whether the package is present
            continue
    if distribution is not None:
        try:
            report.installed_version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            report.installed_version = None
    if not report.library_installed:
        return report

    report.checked_live = True
    for target in static_targets:
        # is_static guarantees module/attribute are non-None here.
        resolution = _resolve_single(target.module, target.attribute)  # type: ignore[arg-type]
        if resolution.resolved:
            report.resolved += 1
        else:
            report.broken.append(resolution)
    return report


# --------------------------------------------------------------------------- #
# Per-integration analysis
# --------------------------------------------------------------------------- #


def _status(report: IntegrationReport) -> str:
    if report.error:
        return "error"
    if report.symbols and report.symbols.checked_live and report.symbols.broken:
        return "broken_symbols"
    if report.latest_version is None:
        return "unknown"
    if report.crosses_major:
        return "major_update"
    if report.exceeds_cap:
        return "capped"
    if report.newer_available:
        return "minor_update"
    return "up_to_date"


def analyze_integration(
    integration: str,
    *,
    include_prereleases: bool,
    timeout: float,
    check_symbols: bool,
) -> IntegrationReport:
    report = IntegrationReport(integration=integration)
    directory = INTEGRATIONS_DIR / integration
    if not directory.is_dir():
        report.error = f"no integration directory at weave/integrations/{integration}"
        report.status = "error"
        return report

    distribution = extract_distribution_name(directory) or integration
    report.distribution = distribution

    extras = load_optional_dependencies()
    requirement: Requirement | None = None
    if integration in extras:
        report.pyproject_extra_found = True
        report.extra_requirements = list(extras[integration])
        requirement = find_requirement(report.extra_requirements, distribution)
        if requirement is None:
            report.notes.append(
                f"distribution {distribution!r} is not pinned in the {integration!r} extra"
            )
    else:
        report.notes.append(f"no [project.optional-dependencies] entry named {integration!r}")

    floor = cap = None
    if requirement is not None:
        report.current_specifier = str(requirement.specifier) or None
        floor, cap = specifier_bounds(requirement.specifier)
        report.current_floor = str(floor) if floor is not None else None
        report.current_cap = str(cap) if cap is not None else None

    latest, fetch_error = fetch_latest_version(
        distribution, include_prereleases=include_prereleases, timeout=timeout
    )
    if fetch_error is not None:
        report.notes.append(fetch_error)
    if latest is not None:
        report.latest_version = str(latest)
        report.latest_is_prerelease = latest.is_prerelease
        if requirement is not None and requirement.specifier:
            report.within_current_range = requirement.specifier.contains(
                latest, prereleases=include_prereleases
            )
        else:
            report.within_current_range = True
        if floor is not None:
            report.newer_available = latest > floor
            report.crosses_major = latest.major > floor.major
        if cap is not None:
            report.exceeds_cap = latest > cap

    targets = extract_symbol_targets(directory)
    report.symbols = build_symbol_report(targets, distribution, check_live=check_symbols)

    report.status = _status(report)
    return report


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #


def discover_integrations() -> list[str]:
    return sorted(
        path.name
        for path in INTEGRATIONS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith(("_", "."))
    )


def format_human(reports: list[IntegrationReport]) -> str:
    lines: list[str] = []
    for report in reports:
        label = STATUS_LABELS.get(report.status, "")
        lines.append(f"{report.integration}  [{report.status}] {label}".rstrip())
        if report.error:
            lines.append(f"    error: {report.error}")
            lines.append("")
            continue

        bounds = []
        if report.current_floor:
            bounds.append(f"floor {report.current_floor}")
        if report.current_cap:
            bounds.append(f"cap {report.current_cap}")
        bound_str = f"  ({', '.join(bounds)})" if bounds else ""
        lines.append(f"    distribution:   {report.distribution}")
        lines.append(f"    supported:      {report.current_specifier or '(unpinned)'}{bound_str}")
        pre = " (pre-release)" if report.latest_is_prerelease else ""
        lines.append(f"    latest on PyPI: {report.latest_version or 'unknown'}{pre}")

        flags = [
            name
            for name, on in (
                ("newer_available", report.newer_available),
                ("crosses_major", report.crosses_major),
                ("exceeds_cap", report.exceeds_cap),
                ("within_current_range", report.within_current_range),
            )
            if on
        ]
        if flags:
            lines.append(f"    flags:          {', '.join(flags)}")

        symbols = report.symbols
        if symbols is not None:
            if symbols.checked_live:
                summary = (
                    f"{symbols.total} target(s), {symbols.resolved}/{symbols.static} static "
                    f"resolved against installed {symbols.installed_version or '?'}"
                )
            else:
                summary = (
                    f"{symbols.total} target(s), {symbols.static} static; live check skipped "
                    f"({report.distribution} not importable here)"
                )
            lines.append(f"    patch targets:  {summary}")
            for broken in symbols.broken:
                lines.append(
                    f"        BROKEN  {broken.module} :: {broken.attribute}  -- {broken.reason}"
                )
            if symbols.dynamic:
                lines.append(
                    f"        {len(symbols.dynamic)} dynamic target(s) not statically checkable:"
                )
                for entry in symbols.dynamic:
                    lines.append(
                        f"          {entry['file']}:{entry['lineno']}  "
                        f"base={entry['base']}  attr={entry['attribute']}"
                    )
        for note in report.notes:
            lines.append(f"    note: {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect when a Weave integration's upstream library has a newer release.",
    )
    parser.add_argument(
        "integrations",
        nargs="*",
        help="Integration name(s) (default: all under weave/integrations/)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Emit machine-readable JSON"
    )
    parser.add_argument(
        "--include-prereleases",
        action="store_true",
        help="Consider pre-release versions on PyPI",
    )
    parser.add_argument(
        "--no-symbol-check",
        action="store_true",
        help="Skip importing the library to live-resolve patch targets",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="PyPI request timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--list", action="store_true", help="List known integrations and exit"
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit 2 when any integration has an actionable finding",
    )
    args = parser.parse_args()

    if args.list:
        for name in discover_integrations():
            print(name)
        return 0

    names = args.integrations or discover_integrations()
    reports = [
        analyze_integration(
            name,
            include_prereleases=args.include_prereleases,
            timeout=args.timeout,
            check_symbols=not args.no_symbol_check,
        )
        for name in names
    ]

    if args.as_json:
        print(json.dumps({"integrations": [asdict(report) for report in reports]}, indent=2))
    else:
        print(format_human(reports), end="")

    if args.fail_on_findings and any(r.status in ACTIONABLE_STATUSES for r in reports):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
