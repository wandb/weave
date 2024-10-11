import xml.etree.ElementTree as ET
from typing import Union

from weave.flow.scorer.base_scorer import Scorer


class XMLScorer(Scorer):
    """Score an XML string."""

    def score(self, output: Union[str, dict]) -> dict:
        if isinstance(output, dict):
            xml_string = output.get("output", "")
        else:
            xml_string = output

        try:
            ET.fromstring(xml_string)
            return {"xml_valid": True}
        except ET.ParseError:
            return {"xml_valid": False}


if __name__ == "__main__":
    scorer = XMLScorer()
    print(
        scorer.score(
            """<xml>
        <city>San Francisco</city>
        <country>USA</country>
    </xml>"""
        )
    )
