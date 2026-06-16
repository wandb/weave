"""Formalized integration-tracking metadata for Weave calls.

:class:`IntegrationMetadata` is the typed builder for a call's
``attributes[INTEGRATION_ATTRIBUTE_KEY]`` provenance; :class:`IntegrationAttributes`
and :class:`IntegrationInfo` below define its shape. Op-wrapping integrations
attach it via :func:`with_integration_metadata` (which threads it through
:class:`~weave.trace.autopatch.OpSettings`); callback/tracer integrations merge
:meth:`IntegrationMetadata.as_attributes` into the attribute dict they already
build.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version
from typing import Any, TypedDict, cast

from weave.trace.autopatch import OpSettings
from weave.version import VERSION as WEAVE_VERSION

logger = logging.getLogger(__name__)

# Top-level attribute key under which integration provenance is stored.
INTEGRATION_ATTRIBUTE_KEY = "integration"

# OpenTelemetry span attributes must be scalars (or scalar sequences); values
# outside this set are stringified when flattened onto a span.
# See opentelemetry.util.types.AttributeValue.
_OTEL_SCALAR_TYPES = (str, bool, int, float)


class IntegrationInfo(TypedDict):
    """The provenance block stored at ``attributes["integration"]``."""

    name: str
    version: str
    meta: dict[str, Any]


class IntegrationAttributes(TypedDict):
    """The attribute fragment an integration merges into a call's attributes.

    The single ``integration`` key mirrors :data:`INTEGRATION_ATTRIBUTE_KEY`.
    """

    integration: IntegrationInfo


@dataclass(slots=True, frozen=True)
class IntegrationMetadata:
    """Typed builder for a call's ``attributes["integration"]`` provenance.

    Attributes:
        name: The integration identifier (e.g. ``"openai"``, ``"langchain"``).
        version: The version of the *integrating code*. For Weave's built-in
            integrations this is the Weave SDK version; an external integration
            (e.g. a Claude Code plugin) would pass its own version.
        meta: Integration-specific detail. For library integrations this carries
            the patched library's distribution name and installed version.
    """

    name: str
    version: str = WEAVE_VERSION
    meta: dict[str, Any] = field(default_factory=dict)

    def as_attributes(self) -> dict[str, Any]:
        """Render the attribute fragment to merge into a call's attributes.

        Returns a fresh dict every call so callers can mutate or merge it freely
        without aliasing this instance's ``meta``. Typed as ``dict[str, Any]``
        because every caller folds it into a call's ``attributes`` dict (the
        ``op``/``create_call`` attributes are ``dict[str, Any]``) or stamps extra
        keys onto it; :class:`IntegrationAttributes` still documents and
        type-checks the shape at construction below.
        """
        # Build via the TypedDict for field/key safety, then hand it out as a
        # plain attributes dict. `cast` is a runtime no-op, so this avoids the
        # extra copy a `{**...}` spread at each call site would incur.
        return cast(
            dict[str, Any],
            IntegrationAttributes(
                integration=IntegrationInfo(
                    name=self.name,
                    version=self.version,
                    meta=dict(self.meta),
                )
            ),
        )

    def as_otel_attributes(self) -> dict[str, Any]:
        """Render the metadata as flattened OpenTelemetry span attributes.

        OTel span attributes must be scalars, so the nested shape from
        :meth:`as_attributes` is flattened to dotted keys (``integration.name``,
        ``integration.version``, ``integration.meta.<key>``). The trace server
        reconstructs the nested dict from these keys on ingest. Used by the
        agent OTel processors that emit spans instead of calling ``create_call``.
        """
        attributes: dict[str, Any] = {
            f"{INTEGRATION_ATTRIBUTE_KEY}.name": self.name,
            f"{INTEGRATION_ATTRIBUTE_KEY}.version": self.version,
        }
        for key, value in self.meta.items():
            attributes[f"{INTEGRATION_ATTRIBUTE_KEY}.meta.{key}"] = (
                value if isinstance(value, _OTEL_SCALAR_TYPES) else str(value)
            )
        return attributes


def resolve_package_version(distribution_name: str) -> str | None:
    """Return the installed version of ``distribution_name``, or None if unknown.

    Never raises: a missing package or metadata lookup failure resolves to None
    so integration patching is never blocked by version discovery.
    """
    try:
        return _distribution_version(distribution_name)
    except PackageNotFoundError:
        return None
    except Exception:
        logger.debug(
            "Failed to resolve version for distribution %r",
            distribution_name,
            exc_info=True,
        )
        return None


def library_integration(
    name: str,
    *,
    distribution_name: str | None = None,
    **meta: Any,
) -> IntegrationMetadata:
    """Build :class:`IntegrationMetadata` for a patched third-party library.

    Fills ``meta`` with the library's distribution name and (when resolvable)
    installed version, plus any extra ``meta`` keyword pairs supplied.

    Args:
        name: The integration identifier (e.g. ``"openai"``).
        distribution_name: PyPI distribution name to resolve the version from,
            when it differs from ``name`` (e.g. ``"google-genai"``). Defaults to
            ``name``.
        **meta: Additional integration-specific metadata to record.
    """
    package_name = distribution_name or name
    resolved_meta: dict[str, Any] = {"package_name": package_name}
    if (resolved_version := resolve_package_version(package_name)) is not None:
        resolved_meta["package_version"] = resolved_version
    resolved_meta.update(meta)
    return IntegrationMetadata(name=name, meta=resolved_meta)


def apply_integration_metadata(
    attributes: dict[str, Any],
    metadata: IntegrationMetadata,
) -> None:
    """Merge ``metadata`` into ``attributes`` in place without overriding keys.

    For callback/tracer integrations that build the call's attribute dict
    directly (rather than going through ``OpSettings``). Existing keys win, so a
    user-supplied ``attributes["integration"]`` is preserved.
    """
    for key, value in metadata.as_attributes().items():
        attributes.setdefault(key, value)


def with_integration_metadata(
    op_settings: OpSettings,
    metadata: IntegrationMetadata,
) -> OpSettings:
    """Return a copy of ``op_settings`` carrying ``metadata`` as op attributes.

    Non-mutating: allocates a fresh attributes dict so the returned settings (and
    every op derived from them via ``model_copy``) do not alias the input.
    """
    merged_attributes = {**(op_settings.attributes or {}), **metadata.as_attributes()}
    return op_settings.model_copy(update={"attributes": merged_attributes})
