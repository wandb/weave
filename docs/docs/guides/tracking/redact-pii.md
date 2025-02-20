# Redact PII from Traces

:::important
This feature is only available for Enterprise users, and is only accessible via the Python SDK.
:::

Some organizations process Personally Identifiable Information (PII) such as names, phone numbers, and email addresses in their Large Language Model (LLM) workflows. Storing this data in Weights & Biases (W&B) Weave poses compliance and security risks.

The _Sensitive Data Protection_ feature allows you to automatically redact Personally Identifiable Information (PII) from a [trace](../tracking/index.md) before it is sent to Weave servers. This feature integrates [Microsoft Presidio](https://microsoft.github.io/presidio/) into the Weave Python SDK, which means that you can control redaction settings at the SDK level.

The Sensitive Data Protection feature introduces the following functionality to the Python SDK:

- A `redact_pii` setting, which can be toggled on or off in the `weave.init` call to enable PII redaction.
- Automatic redaction of [common entities](#entities-redacted-by-default) when `redact_pii = True`.
- Customizable redaction fields using the configurable `redact_pii_fields` setting.

## Enable PII redaction

To get started with the Sensitive Data Protection feature in Weave, complete the following steps:

1. Install the required dependencies:

    ```bash
    pip install presidio-analyzer presidio-anonymizer
    ```

2. Modify your `weave.init` call to enable redaction. When `redact_pii=True`, [common entities are redacted by default](#entities-redacted-by-default):

    ```python
    import weave

    weave.init("my-project", settings={"redact_pii": True})
    ```

3. (Optional) Customize redaction fields using the `redact_pii_fields` parameter:

    ```python
    weave.init("my-project", settings={"redact_pii": True, "redact_pii_fields"=["CREDIT_CARD", "US_SSN"]})
    ```

    For a full list of the entities that can be detected and redacted, see [PII entities supported by Presidio](https://microsoft.github.io/presidio/supported_entities/).

## Entities redacted by default

The following entities are automatically redacted when PII redaction is enabled:

- `CREDIT_CARD`
- `CRYPTO`
- `EMAIL_ADDRESS`
- `ES_NIF`
- `FI_PERSONAL_IDENTITY_CODE`
- `IBAN_CODE`
- `IN_AADHAAR`
- `IN_PAN`
- `IP_ADDRESS`
- `LOCATION`
- `PERSON`
- `PHONE_NUMBER`
- `UK_NHS`
- `UK_NINO`
- `US_BANK_NUMBER`
- `US_DRIVER_LICENSE`
- `US_PASSPORT`
- `US_SSN`

## Usage information 

- This feature is only available in the Python SDK.
- Enabling redaction increases processing time due to the Presidio dependency.
