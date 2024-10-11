import xml.etree.ElementTree as ET
from typing import Union

from weave.flow.scorer.base_scorer import Scorer


class XMLScorer(Scorer):
    """Score an XML string."""

    def score(self, output: Union[str, dict]) -> dict:  # type: ignore
        if isinstance(output, dict):
            xml_string = output.get("output", "")
        else:
            xml_string = output

        try:
            ET.fromstring(xml_string)
            return {"xml_valid": True}
        except ET.ParseError:
            return {"xml_valid": False}
