import base64
from dataclasses import dataclass, field

TEST_BUCKET = "test-bucket"
_TEST_PROJECT_ID_B64 = base64.b64encode(b"shawn/test-project").decode()


@dataclass
class GCSMockState:
    """Observable + configurable state attached to the gcs fixture.

    Test-side knobs:
      `fail_paths` - inject `PreconditionFailed`-style failures by GCS path.
      `expected_concurrency` - when set, uploads block on a barrier until this
                     many are simultaneously in-flight, making `concurrent_peak`
                     deterministic instead of dependent on scheduler timing.

    Read-back:
      `blob_data`        - the in-memory backing store, keyed by full path.
      `upload_count`     - total successful uploads (skips not counted).
      `concurrent_peak`  - max in-flight uploads observed across threads.
    """

    blob_data: dict[str, bytes] = field(default_factory=dict)
    upload_count: int = 0
    concurrent_peak: int = 0
    fail_paths: set[str] = field(default_factory=set)
    expected_concurrency: int | None = None
