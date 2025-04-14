# Redacting PII

:::important
This feature is only accessible via the Python SDK.
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
    weave.init("my-project", settings={"redact_pii": True, "redact_pii_fields":["CREDIT_CARD", "US_SSN"]})
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

## Redacting sensitive keys with `REDACT_KEYS`

In addition to PII redaction, the Weave SDK also supports redaction of custom keys using `REDACT_KEYS`. This is useful when you want to protect additional sensitive data that might not fall under the PII category but needs to be kept private. Examples include:

- API keys
- Authentication headers
- Tokens
- Internal IDs
- Config values

### Pre-defined `REDACT_KEYS`

Weave automatically redacts the following sensitive keys by default:

```json
[
  "api_key",
  "auth_headers",
  "authorization"
]
```

### Adding your own keys

You can extend this list with your own custom keys that you want to redact from traces:

```python
import weave

client = weave.init("my-project")

# Add custom keys to redact
weave.trace.sanitize.REDACT_KEYS.add("client_id")
weave.trace.sanitize.REDACT_KEYS.add("whatever_else")

client_id = "123"
whatever_else = "456"

@weave.op()
def test():
    a = client_id
    b = whatever_else
    return 1
```

When viewed in the Weave UI, the values of `client_id` and `whatever_else` will appear as `"REDACTED"`:

```python
client_id = "REDACTED"
whatever_else = "REDACTED"
```

## Usage information

- This feature is only available in the Python SDK.
- Enabling redaction increases processing time due to the Presidio dependency.

