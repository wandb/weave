import xml.etree.ElementTree as ET
from typing import TypedDict, Union

import weave
from weave.flow.scorer import Scorer


class ValidXMLScorerOutput(TypedDict):
    """Output type for ValidXMLScorer."""

    xml_valid: bool


class ValidXMLScorer(Scorer):
    """Score an XML string."""

    @weave.op
    def score(self, output: Union[str, dict]) -> ValidXMLScorerOutput:
        if isinstance(output, dict):
            xml_string = output.get("output", "")
        else:
            xml_string = output

        try:
            ET.fromstring(xml_string)
        except ET.ParseError:
            return {"xml_valid": False}
        else:
            return {"xml_valid": True}
