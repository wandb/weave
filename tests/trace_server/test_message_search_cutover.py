from datetime import timedelta

import pytest

from tests.trace_server.test_indexed_message_search import START, _insert
from weave.shared.errors import InvalidRequest
from weave.trace_server.agents.types import AgentSearchReq

pytestmark = pytest.mark.trace_server


@pytest.mark.parametrize("project_id", ["p", "another-project"])
def test_unconditional_cutover_response(ch_server, project_id):
    _insert(ch_server, project=project_id, span="old")
    _insert(
        ch_server, project=project_id, span="new", started=START + timedelta(seconds=1)
    )
    request = AgentSearchReq(project_id=project_id, query="guitar acoustic")
    response = ch_server.agent_search(request)
    digest = ch_server.ch_client.query(
        "SELECT lower(hex(murmurHash3_128('acoustic guitar')))"
    ).first_row[0]
    timestamp = response.results[0].last_activity
    assert timestamp.replace(tzinfo=None) == START.replace(tzinfo=None) + timedelta(
        seconds=1
    )
    assert response.model_dump() == {
        "results": [
            {
                "conversation_id": "conv",
                "conversation_name": "",
                "agent_name": "agent",
                "matched_messages": [
                    {
                        "span_id": "new",
                        "trace_id": "trace",
                        "role": "user",
                        "content_preview": "acoustic guitar",
                        "content_digest": digest,
                        "started_at": timestamp,
                    }
                ],
                "last_activity": timestamp,
            }
        ],
        "total_conversations": 1,
    }
    with pytest.raises(InvalidRequest, match="Close the quoted phrase"):
        ch_server.agent_search(request.model_copy(update={"query": '"unfinished'}))
    structured = ch_server.agent_search(
        request.model_copy(
            update={"query": "", "trace_id": "trace", "truncate_content": False}
        )
    )
    assert [m.span_id for m in structured.results[0].matched_messages] == ["new", "old"]
