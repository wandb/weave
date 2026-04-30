import random

import pytest

from weave.shared import refs_internal
from weave.trace import refs
from weave.trace.weave_client import sanitize_object_name

quote = refs_internal.extra_value_quoter


def test_isdescended_from():
    a = refs.ObjectRef(
        entity="e", project="p", name="n", _digest="v", _extra=["attr", "x2"]
    )
    b = refs.ObjectRef(
        entity="e",
        project="p",
        name="n",
        _digest="v",
        _extra=["attr", "x2", "attr", "x4"],
    )
    assert a.is_descended_from(b) == False
    assert b.is_descended_from(a) == True


def string_with_every_char(disallowed_chars=None):
    if disallowed_chars is None:
        disallowed_chars = []
    char_codes = list(range(256))
    random.shuffle(char_codes)
    return "".join(chr(i) for i in char_codes if chr(i) not in disallowed_chars)


def test_ref_parsing_external_invalid():
    with pytest.raises(refs_internal.InvalidInternalRef):
        ref_start = refs.ObjectRef(
            entity="entity",
            project="project",
            name=string_with_every_char(),
            _digest="1234567890",
            _extra=("key", string_with_every_char()),
        )


def test_ref_parsing_external_sanitized():
    ref_start = refs.ObjectRef(
        entity="entity",
        project="project",
        name=sanitize_object_name(string_with_every_char()),
        _digest="1234567890",
        _extra=("key", string_with_every_char()),
    )

    ref_str = ref_start.uri
    exp_ref = f"{refs_internal.WEAVE_SCHEME}:///{ref_start.entity}/{ref_start.project}/object/{ref_start.name}:{ref_start.digest}/{ref_start.extra[0]}/{quote(ref_start.extra[1])}"
    assert ref_str == exp_ref

    parsed = refs.Ref.parse_uri(ref_str)
    assert parsed == ref_start


def test_ref_parsing_internal_invalid():
    with pytest.raises(refs_internal.InvalidInternalRef):
        ref_start = refs_internal.InternalObjectRef(
            project_id="project",
            name=string_with_every_char(),
            version="1234567890",
            extra=("key", string_with_every_char()),
        )


def test_ref_parsing_internal_sanitized():
    ref_start = refs_internal.InternalObjectRef(
        project_id="project",
        name=sanitize_object_name(string_with_every_char()),
        version="1234567890",
        extra=["key", string_with_every_char()],
    )

    ref_str = ref_start.uri
    exp_ref = f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///{ref_start.project_id}/object/{ref_start.name}:{ref_start.version}/{ref_start.extra[0]}/{quote(ref_start.extra[1])}"
    assert ref_str == exp_ref

    parsed = refs_internal.parse_internal_uri(ref_str)
    assert parsed == ref_start


def test_agent_turn_ref_roundtrip():
    ref_start = refs.AgentTurnRef(
        entity="entity",
        project="project",
        trace_id="0123456789abcdef0123456789abcdef",
    )
    assert (
        ref_start.uri
        == "weave:///entity/project/agent_turn/0123456789abcdef0123456789abcdef"
    )
    assert refs.Ref.parse_uri(ref_start.uri) == ref_start


def test_agent_span_ref_roundtrip():
    ref_start = refs.AgentSpanRef(
        entity="entity",
        project="project",
        span_id="0123456789abcdef",
    )
    assert ref_start.uri == "weave:///entity/project/agent_span/0123456789abcdef"
    assert refs.Ref.parse_uri(ref_start.uri) == ref_start


def test_agent_conversation_ref_roundtrip():
    ref_start = refs.AgentConversationRef(
        entity="entity",
        project="project",
        conversation_id=string_with_every_char(),
    )
    parsed = refs.Ref.parse_uri(ref_start.uri)
    assert parsed == ref_start


def test_internal_agent_turn_ref_roundtrip():
    ref_start = refs_internal.InternalAgentTurnRef(
        project_id="project",
        trace_id="0123456789abcdef0123456789abcdef",
    )
    assert (
        ref_start.uri
        == f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///project/agent_turn/0123456789abcdef0123456789abcdef"
    )
    assert refs_internal.parse_internal_uri(ref_start.uri) == ref_start


def test_internal_agent_span_ref_roundtrip():
    ref_start = refs_internal.InternalAgentSpanRef(
        project_id="project",
        span_id="0123456789abcdef",
    )
    assert (
        ref_start.uri
        == f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///project/agent_span/0123456789abcdef"
    )
    assert refs_internal.parse_internal_uri(ref_start.uri) == ref_start


def test_internal_agent_conversation_ref_roundtrip():
    raw_cid = "user/42:session ?name=hi"
    ref_start = refs_internal.InternalAgentConversationRef(
        project_id="project",
        conversation_id=raw_cid,
    )
    assert (
        ref_start.uri
        == f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///project/agent_conversation/{quote(raw_cid)}"
    )
    assert refs_internal.parse_internal_uri(ref_start.uri) == ref_start


def test_internal_agent_ref_rejects_slash():
    with pytest.raises(refs_internal.InvalidInternalRef):
        refs_internal.InternalAgentTurnRef(project_id="project", trace_id="bad/value")
    with pytest.raises(refs_internal.InvalidInternalRef):
        refs_internal.InternalAgentSpanRef(project_id="project", span_id="bad/value")


@pytest.mark.parametrize("kind", ["agent_turn", "agent_conversation", "agent_span"])
def test_agent_ref_rejects_extra_path_segments(kind):
    uri = f"weave:///entity/project/{kind}/user/42"
    with pytest.raises(ValueError, match="exactly one path segment"):
        refs.Ref.parse_uri(uri)

    internal_uri = f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///project/{kind}/user/42"
    with pytest.raises(
        refs_internal.InvalidInternalRef, match="exactly one path segment"
    ):
        refs_internal.parse_internal_uri(internal_uri)


@pytest.mark.parametrize("kind", ["agent_turn", "agent_conversation", "agent_span"])
def test_agent_ref_rejects_missing_id(kind):
    uri = f"weave:///entity/project/{kind}"
    with pytest.raises(ValueError, match="exactly one path segment"):
        refs.Ref.parse_uri(uri)

    internal_uri = f"{refs_internal.WEAVE_INTERNAL_SCHEME}:///project/{kind}"
    with pytest.raises(
        refs_internal.InvalidInternalRef, match="exactly one path segment"
    ):
        refs_internal.parse_internal_uri(internal_uri)
