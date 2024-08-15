import random

from weave.trace import refs
from weave.trace_server import refs_internal

quote = refs_internal.quote_select


def test_isdescended_from():
    a = refs.ObjectRef(entity="e", project="p", name="n", digest="v", extra=["x1"])
    b = refs.ObjectRef(
        entity="e", project="p", name="n", digest="v", extra=["x1", "x2"]
    )
    assert a.is_descended_from(b) == False
    assert b.is_descended_from(a) == True


def test_ref_parsing_external():
    def string_with_every_char():
        char_codes = list(range(256))
        random.shuffle(char_codes)
        return "".join(chr(i) for i in char_codes)

    ref_start = refs.ObjectRef(
        entity=string_with_every_char(),
        project=string_with_every_char(),
        name=string_with_every_char(),
        digest=string_with_every_char(),
        extra=(string_with_every_char(), string_with_every_char()),
    )

    ref_str = ref_start.uri()
    assert (
        ref_str
        == f"{refs_internal.WEAVE_SCHEME}:///{quote(ref_start.entity)}/{quote(ref_start.project)}/object/{quote(ref_start.name)}:{quote(ref_start.digest)}/{quote(ref_start.extra[0])}/{quote(ref_start.extra[1])}"
    )

    parsed = refs.parse_uri(ref_str)
    assert parsed == ref_start


def test_ref_parsing_internal():
    def string_with_every_char():
        char_codes = list(range(256))
        random.shuffle(char_codes)
        return "".join(chr(i) for i in char_codes)

    ref_start = refs_internal.InternalObjectRef(
        project_id=string_with_every_char(),
        name=string_with_every_char(),
        version=string_with_every_char(),
        extra=[string_with_every_char(), string_with_every_char()],
    )

    ref_str = ref_start.uri()
    assert (
        ref_str
        == f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///{quote(ref_start.project_id)}/object/{quote(ref_start.name)}:{quote(ref_start.version)}/{quote(ref_start.extra[0])}/{quote(ref_start.extra[1])}"
    )

    parsed = refs_internal.parse_internal_uri(ref_str)
    assert parsed == ref_start
