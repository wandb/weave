from typing import Any, Optional
from weave.integrations.patcher import Patcher, NoOpPatcher
from weave.trace.autopatch import IntegrationSettings
from weave.integrations.verdict.tracer import VerdictTracer


def get_verdict_module():
    """Get the verdict module if it's available."""
    try:
        import verdict
    except ImportError:
        return None
    else:
        return verdict


class VerdictPatcher(Patcher):
    def __init__(self):
        self._patched = False
        self._orig_pipeline_init = None
        self._orig_unit_init = None
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

        def pipeline_init(self, name="Pipeline", tracer=None):
            orig_pipeline_init(
                self, name, tracer if tracer is not None else default_tracer
            )

        Pipeline.__init__ = pipeline_init

        # Patch Unit.__init__
        Unit = verdict.core.primitive.Unit
        self._orig_unit_init = Unit.__init__
        orig_unit_init = self._orig_unit_init

        def unit_init(self, *args, tracer=None, **kwargs):
            orig_unit_init(
                self,
                *args,
                tracer=tracer if tracer is not None else default_tracer,
                **kwargs,
            )

        Unit.__init__ = unit_init

        self._patched = True
        return True

    def undo_patch(self) -> bool:
        if not self._patched:
            return False
        verdict = get_verdict_module()
        if verdict is None:
            return False
        verdict.core.pipeline.Pipeline.__init__ = self._orig_pipeline_init
        verdict.core.primitive.Unit.__init__ = self._orig_unit_init
        self._patched = False
        return True


def get_verdict_patcher(settings: Optional[IntegrationSettings] = None) -> Patcher:
    if settings is None:
        settings = IntegrationSettings()
    if not settings.enabled:
        return NoOpPatcher()
    return VerdictPatcher()
