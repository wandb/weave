from . import weave_server


def test_automation_protocol():
    weave_server.app.config["TESTING"] = True
    client = weave_server.app.test_client()

    # Can add commands
    response = client.post("/__weave/automate/5/add_command", json={"raw": "command1"})
    assert response.status_code == 200
    response = client.post("/__weave/automate/5/add_command", json={"raw": "command2"})
    assert response.status_code == 200

    # And get them back
    response = client.get("/__weave/automate/5/commands_after/0")
    assert response.status_code == 200
    assert response.json == {"commands": [{"raw": "command1"}, {"raw": "command2"}]}
    response = client.get("/__weave/automate/5/commands_after/1")
    assert response.status_code == 200
    assert response.json == {"commands": [{"raw": "command2"}]}

    # Before status is set, status should be running
    response = client.get("/__weave/automate/5/status")
    assert response.status_code == 200
    assert response.json == {"status": -1, "message": ""}

    # Can set status
    response = client.post(
        "/__weave/automate/5/set_status", json={"status": 0, "message": "hello"}
    )
    assert response.status_code == 200

    # And read it back
    response = client.get("/__weave/automate/5/status")
    assert response.status_code == 200
    assert response.json == {"status": 0, "message": "hello"}
