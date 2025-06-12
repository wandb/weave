from typing import Any, Callable, Optional

from weave.integrations.patcher import NoOpPatcher, Patcher
from weave.integrations.verdict.tracer import VerdictTracer
from weave.trace.autopatch import IntegrationSettings


def get_verdict_module() -> Optional[Any]:
    """Get the verdict module if it's available."""
    try:
        import verdict
    except ImportError:
        return None
    else:
        return verdict


class VerdictPatcher(Patcher):
    def __init__(self) -> None:
        self._patched = False
        self._orig_pipeline_init: Optional[Callable[..., None]] = None
        self._tracer = VerdictTracer()

    def attempt_patch(self) -> bool:
        if self._patched:
            return True
        verdict = get_verdict_module()
        if verdict is None:
            return False

            # Patch Pipeline.__init__
        Pipeline = verdict.core.pipeline.Pipeline
        self._orig_pipeline_init = Pipeline.__init__
        default_tracer = self._tracer
        orig_pipeline_init = self._orig_pipeline_init

        # Defensive check - if we couldn't get the original init, don't patch
        if orig_pipeline_init is None:
            return False

        def pipeline_init(
            self: Any, name: str = "Pipeline", tracer: Optional[Any] = None
        ) -> None:
            orig_pipeline_init(
                self, name, tracer if tracer is not None else default_tracer
            )

        Pipeline.__init__ = pipeline_init

        self._patched = True
        return True

    def undo_patch(self) -> bool:
        if not self._patched:
            return False
        verdict = get_verdict_module()
        if verdict is None:
            return False
        verdict.core.pipeline.Pipeline.__init__ = self._orig_pipeline_init
        self._patched = False
        return True


def get_verdict_patcher(settings: Optional[IntegrationSettings] = None) -> Patcher:
    if settings is None:
        settings = IntegrationSettings()
    if not settings.enabled:
        return NoOpPatcher()
    return VerdictPatcher()
