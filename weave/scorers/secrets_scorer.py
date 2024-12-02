import hashlib
import os
import tempfile
import warnings
from enum import Enum
from typing import Any

import weave
from weave.scorers.base_scorer import Scorer
from weave.scorers.secrets_plugins import ALL_PLUGINS

try:
    from detect_secrets import SecretsCollection
    from detect_secrets.settings import transient_settings
except ImportError:
    raise ImportError(
        "The detect-secrets package is required for the SecretsScorer. "
        "Please install it by running `pip install detect-secrets`."
    )


class REDACTION(str, Enum):
    REDACT_PARTIAL = "REDACT_PARTIAL"
    REDACT_ALL = "REDACT_ALL"
    REDACT_HASH = "REDACT_HASH"


class SecretsScorer(Scorer):
    """Validate whether a string contains a secret."""

    _detect_secrets_config: dict[str, Any] = ALL_PLUGINS
    redact_mode: REDACTION = REDACTION.REDACT_ALL

    @staticmethod
    def redact_value(value: str, mode: str) -> str:
        if mode == REDACTION.REDACT_PARTIAL:
            redacted_value = f"{value[:2]}..{value[-2:]}"
        elif mode == REDACTION.REDACT_HASH:
            redacted_value = hashlib.md5(value.encode()).hexdigest()
        elif mode == REDACTION.REDACT_ALL:
            redacted_value = "******"
        else:
            raise ValueError(f"redact mode wasn't recognized {mode}")

        return redacted_value

    def get_unique_secrets(self, value: str) -> tuple[dict[str, Any], list[str]]:
        """Get unique secrets from the value."""
        secrets = SecretsCollection()
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(value.encode("utf-8"))
        temp_file.close()

        with transient_settings(self._detect_secrets_config):
            secrets.scan_file(str(temp_file.name))

        unique_secrets = {}
        for file in secrets.files:
            for found_secret in secrets[file]:
                if found_secret.secret_value is None:
                    continue

                actual_secret = found_secret.secret_value
                line_number = found_secret.line_number
                if actual_secret not in unique_secrets:
                    unique_secrets[actual_secret] = [line_number]
                else:
                    if line_number not in unique_secrets[actual_secret]:
                        unique_secrets[actual_secret].append(line_number)

        os.remove(temp_file.name)
        lines = value.splitlines()
        return unique_secrets, lines

    def get_modified_value(
        self, unique_secrets: dict[str, Any], lines: list[str]
    ) -> str:
        """Replace the secrets on the lines with asterisks."""
        for secret, line_numbers in unique_secrets.items():
            for line_number in line_numbers:
                lines[line_number - 1] = lines[line_number - 1].replace(
                    secret, self.redact_value(secret, self.redact_mode)
                )

        modified_value = "\n".join(lines)
        return modified_value

    def scan(self, prompt: str) -> tuple[str, bool, float]:
        if prompt.strip() == "":
            return prompt, True, -1.0

        unique_secrets, lines = self.get_unique_secrets(prompt)
        if unique_secrets:
            modified_value = self.get_modified_value(unique_secrets, lines)
            return modified_value, False, 1.0

        return prompt, True, -1.0

    @weave.op
    async def score(self, input: str, output: str) -> dict:
        result = {
            "input_secrets": {},
            "output_secrets": {},
            "total_secrets": 0,
            "input_has_secrets": False,
            "output_has_secrets": False,
        }

        for text, key in [(input, "input_secrets"), (output, "output_secrets")]:
            if "\n" not in text:
                warnings.warn(
                    "The DetectSecrets validator works best with multiline code snippets."
                )
                text += "\n"

            redacted_text, no_secrets, risk_score = self.scan(text)
            if not no_secrets:
                result[key] = {
                    "detected_secrets": ["detected"],
                    "modified_value": redacted_text,
                }
                if result["total_secrets"] is None:
                    result["total_secrets"] = 1
                else:
                    if isinstance(result["total_secrets"], int):
                        result["total_secrets"] += 1
                    else:
                        result["total_secrets"] = 1
                if key == "input_secrets":
                    result["input_has_secrets"] = True
                else:
                    result["output_has_secrets"] = True
            else:
                result[key] = {"detected_secrets": [], "modified_value": text}

        return result
