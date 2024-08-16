from pydantic import BeforeValidator
from typing_extensions import Annotated

from weave.trace_server.refs_internal import quote_select


def quote_string(v: str) -> str:
    return quote_select(v)


QuotedString = Annotated[str, BeforeValidator(quote_string)]
