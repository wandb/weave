"""Magic values for the export module.

Operator-tunable values (bucket, region, role ARN, cluster) live in helm
values and reach the pod as env vars, not here.
"""

import re
from datetime import timedelta

MAX_EXPORT_QUERY_SECONDS = 1800

SIGNED_URL_TTL = timedelta(minutes=15)

EXPORT_OBJECT_LIFETIME = timedelta(days=7)

EXPORTS_ROW_TTL = timedelta(days=365 * 7)

STS_SESSION_DURATION = timedelta(hours=12)

MAX_CONCURRENT_EXPORTS_PER_PROJECT = 1

NAMED_COLLECTION_SWEEPER_INTERVAL = timedelta(minutes=5)

CREDENTIAL_VALUE_REGEX = re.compile(r"^[A-Za-z0-9/+=._\-]+$")

# Charset for the destination URL (`s3://bucket/env/exports/<project>/<job>/file.parquet`).
# Permits `:` and the credential charset; explicitly rejects single quote, backslash,
# whitespace, and anything CH could use to break out of a single-quoted literal.
URL_VALUE_REGEX = re.compile(r"^[A-Za-z0-9/+=._:\-]+$")

PHASE_2_PARTITION_ROW_THRESHOLD = 10_000_000

MAX_REQUEST_JSON_BYTES = 64 * 1024

# Grace window before a missing `system.query_log` row flips PENDING -> FAILED.
# Covers query submission latency + initial parse delay.
PENDING_GRACE_PERIOD = timedelta(seconds=30)

# Object-storage layout. <bucket-uri>/<env>/exports/<project_id>/<job_id>/
EXPORT_PREFIX = "exports"

EXPORT_OBJECT_NAME = "data.parquet"
EXPORT_MANIFEST_NAME = "manifest.json"

# Compression for the Parquet output. Column-level (output_format_parquet_compression_method),
# NOT the s3() function's positional outer-file compression arg.
PARQUET_COMPRESSION = "zstd"

# Named-collection name prefix. Sweeper scans `system.named_collections` for
# names beginning with this string.
NAMED_COLLECTION_PREFIX = "export_"
