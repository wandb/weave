import xml.etree.ElementTree as ET
from typing import Any

import weave
from weave.flow.scorer import Scorer
from weave.trace.objectify import register_object


@register_object
class ValidXMLScorer(Scorer):
    """Score an XML string."""

    @weave.op
    def score(self, *, output: str | dict, **kwargs: Any) -> dict:
        xml_string = output.get("output", "") if isinstance(output, dict) else output

        try:
            ET.fromstring(xml_string)
        except ET.ParseError:
            return {"xml_valid": False}
        else:
            return {"xml_valid": True}
