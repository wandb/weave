from weave.content_types.content import (
    Audio,
    Content,
    Csv,
    Image,
    JavaScript,
    Json,
    Markdown,
    Pdf,
    PlainText,
    Python,
    TypeScript,
    Video,
    Yaml,
)


def test_name():
    print(__name__)


__docspec__ = [
    Content,
    Audio,
    Video,
    Image,
    Pdf,
    Json,
    Yaml,
    Csv,
    Markdown,
    PlainText,
    Python,
    JavaScript,
    TypeScript,
]
