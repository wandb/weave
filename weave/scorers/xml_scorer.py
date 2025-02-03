import xml.etree.ElementTree as ET
from typing import Union

from pydantic import BaseModel, Field

import weave
from weave.scorers.base_scorer import Scorer


class ValidXMLScorerOutput(BaseModel):
    """Output type for ValidXMLScorer."""

    xml_valid: bool = Field(description="Whether the XML is valid")


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
            return ValidXMLScorerOutput(xml_valid=False)
        else:
            return ValidXMLScorerOutput(xml_valid=True)
