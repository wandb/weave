from weave.trace.pii_redaction import redact_pii


def test_redact_pii_in_dict():
    input_data = {
        "email": "test@example.com",
        "phone": "123-456-7890",
        "message": "Contact me at test@example.com or 123-456-7890.",
    }
    redacted_data = redact_pii(input_data)
    assert "test@example.com" not in redacted_data["email"]
    assert "123-456-7890" not in redacted_data["phone"]
    assert "test@example.com" not in redacted_data["message"]
    assert "123-456-7890" not in redacted_data["message"]


def test_redact_pii_nested_dict():
    input_data = {
        "user": {"email": "test@example.com", "details": {"phone": "123-456-7890"}}
    }
    redacted_data = redact_pii(input_data)
    assert "test@example.com" not in redacted_data["user"]["email"]
    assert "123-456-7890" not in redacted_data["user"]["details"]["phone"]


def test_no_pii_data_in_dict():
    input_data = {"message": "This is a normal sentence without PII."}
    redacted_data = redact_pii(input_data)
    assert input_data == redacted_data
