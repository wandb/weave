import random

from weave.trace import refs
from weave.trace_server import refs_internal

quote = refs_internal.ref_part_quoter


def test_isdescended_from():
    a = refs.ObjectRef(entity="e", project="p", name="n", digest="v", extra=["x1"])
    b = refs.ObjectRef(
        entity="e", project="p", name="n", digest="v", extra=["x1", "x2"]
    )
    assert a.is_descended_from(b) == False
    assert b.is_descended_from(a) == True


def string_with_every_char(disallowed_chars=[]):
    char_codes = list(range(256))
    random.shuffle(char_codes)
    return "".join(chr(i) for i in char_codes if chr(i) not in disallowed_chars)


def test_ref_parsing_external():
    ref_start = refs.ObjectRef(
        entity=string_with_every_char(["/", ":"]),
        project=string_with_every_char(["/", ":"]),
        name=string_with_every_char(),
        digest="1234567890",
        extra=("key", string_with_every_char()),
    )

    ref_str = ref_start.uri()
    exp_ref = f"{refs_internal.WEAVE_SCHEME}:///{quote(ref_start.entity)}/{quote(ref_start.project)}/object/{quote(ref_start.name)}:{ref_start.digest}/{ref_start.extra[0]}/{quote(ref_start.extra[1])}"
    assert ref_str == exp_ref

    parsed = refs.parse_uri(ref_str)
    assert parsed == ref_start


def test_ref_parsing_internal():
    ref_start = refs_internal.InternalObjectRef(
        project_id="1234567890",
        name=string_with_every_char(),
        version="1234567890",
        extra=["key", string_with_every_char()],
    )

    ref_str = ref_start.uri()
    exp_ref = f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///{ref_start.project_id}/object/{quote(ref_start.name)}:{ref_start.version}/{ref_start.extra[0]}/{quote(ref_start.extra[1])}"
    assert ref_str == exp_ref

    parsed = refs_internal.parse_internal_uri(ref_str)
    assert parsed == ref_start
