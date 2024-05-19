import dataclasses
import typing
import weave
from .. import panel

ModeOption = typing.Literal["plaintext", "markdown", "diff"]


@weave.type()
class PanelStringConfig:
    mode: typing.Optional[ModeOption] = None


@weave.type()
class PanelString(panel.Panel):
    id = "string"
    config: typing.Optional[PanelStringConfig] = dataclasses.field(
        default_factory=lambda: None
    )

    def __init__(self, input_node, vars=None, config=None, **options):
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = PanelStringConfig()
        if "mode" in options:
            self.config.mode = options["mode"]
