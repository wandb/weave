from weave.server import _handle_request


def test_playback():
    for payload in execute_payloads:
        res = _handle_request(payload, True)
        assert "err" not in res


# Paste graphs below (from DD or Network tab to test)
execute_payloads: list[dict] = []
