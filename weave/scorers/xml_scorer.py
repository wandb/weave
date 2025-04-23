import xml.etree.ElementTree as ET
from typing import Union

import weave


class ValidXMLScorer(weave.Scorer):
    """Score an XML string."""

    @weave.op
    def score(self, output: Union[str, dict]) -> dict:
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
