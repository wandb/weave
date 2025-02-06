# Redact PII from Traces

Some organizations process Personally Identifiable Information (PII) such as names, phone numbers, and email addresses in their Large Language Model (LLM) workflows. Storing this data in Weights & Biases (W&B) Weave poses compliance and security risks.

The  _Sensitive Data Protection_ feature allows you to automatically redact Personally Identifiable Information (PII) from a [trace](../tracking/index.md) before it is sent to Weave servers. This feature integrates [Microsoft Presidio](https://microsoft.github.io/presidio/) into the Weave Python SDK, which means that you can control redaction settings at the SDK level.

:::important
This feature is only available for enterprise customers, and only available in the Python SDK.
:::

The Sensitive Data Protection feature introduces the following functionality to the Python SDK:

- A `redact_pii` setting, which can be toggled on or off in the `weave.init` call to enable PII redaction.
- Automatic redaction of `PERSON`, `PHONE_NUMBER`, and `EMAIL_ADDRESS` when `redact_pii = True`.
-  Customizable redaction fields using the configurable `redact_pii_fields` setting.

## Enable PII redaction

To get started with the Sensitive Data Protection feature in Weave, complete the following steps:

1. Install the required dependencies:

    ```bash
    pip install presidio-analyzer presidio-anonymizer
    ```

2. Modify your `weave.init` call to enable redaction. By default, `PERSON`, `PHONE_NUMBER` and `EMAIL_ADDRESS` are redacted when `redact_pii=True`:

    ```python
    import weave

    weave.init("my-project", redact_pii=True)
    ```

3. (Optional) Customize redaction fields using the `redact_pii_fields` parameter:

    ```python
    weave.init("my-project", redact_pii=True, redact_pii_fields=["CREDIT_CARD", "SSN"])
    ```

## Usage information 

- Enabling redaction increases processing time due to the Presidio dependency.
- If you don't have an enterprise subscription, you will receive an error if you try to enable this feature.
