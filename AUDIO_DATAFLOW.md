# Weave Audio Media Data Flow

**Audience:** Security reviewers evaluating how audio data is handled by Weights & Biases Weave.

**Scope:** Describes how audio bytes (mp3 / wav / flac / ogg / m4a) travel from a user's application to server-side storage and back, when **external bucket storage (S3 / GCS / Azure Blob) is enabled**.

---

## 1. Example

The flows below are driven by this minimal user program, adapted from the [Weave media docs](https://docs.wandb.ai/weave/guides/core-types/media#log-audio):

```python
import weave
from weave import Content
import wave
import numpy as np
from typing import Annotated

weave.init("your-team-name/your-project-name")

# Create a 1-second, 440 Hz sine-wave .wav on disk
frames = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))
audio_data = (frames * 32767 * 0.3).astype(np.int16)
with wave.open("beep.wav", "wb") as f:
    f.setnchannels(1); f.setsampwidth(2); f.setframerate(44100)
    f.writeframes(audio_data.tobytes())

@weave.op
def load_audio(path: Annotated[str, Content]) -> Annotated[bytes, Content]:
    with open(path, "rb") as f:
        return f.read()

result = load_audio("beep.wav")
```

The `Content` annotation tells Weave that the parameter is a binary media object, so it is stored as a referenced file rather than embedded in the op-call record.

---

## 2. Architecture

```mermaid
---
config:
  layout: elk
---
flowchart LR
    User["User Process<br/>(Python SDK)"]
    Svc["Weave Service"]
    DB[("Database<br/>(op calls + file metadata)")]
    Blob[("Cloud Blob Storage<br/>S3 / GCS / Azure")]

    User <-- "HTTPS (TLS 1.2+)" --> Svc
    Svc <--> DB
    Svc <--> Blob
```

- **User Process** — the customer's application running the Weave Python SDK.
- **Weave Service** — authenticated HTTPS API; authorizes every request against project-level ACLs.
- **Database** — stores op-call records and file metadata (project, content digest, location).
- **Cloud Blob Storage** — stores the raw audio bytes when bucket storage is enabled.

---

## 3. Write Path

```mermaid
---
config:
  layout: elk
---
sequenceDiagram
    autonumber
    participant U as User Process<br/>(Python SDK)
    participant S as Weave Service
    participant B as Cloud Blob<br/>Storage
    participant D as Database

    Note over U: @weave.op intercepts the call.<br/>SDK wraps payload as Content —<br/>detects MIME, computes SHA-256 digest,<br/>separates audio bytes from op-call metadata.

    rect rgba(140,180,120,0.08)
    Note over U,D: Upload audio bytes (one round-trip per file)
    U->>S: HTTPS: audio bytes + expected digest
    S->>S: Authenticate and authorize project access
    S->>S: Re-compute digest and verify<br/>it matches the client's digest
    alt bucket storage enabled
        S->>B: Write audio bytes to project-scoped key
        B-->>S: Ack
        S->>D: Record file metadata<br/>(project, digest, blob location)
    else bucket storage not enabled
        S->>D: Write audio bytes inline + metadata
    end
    D-->>S: Ack
    S-->>U: HTTPS response (digest)
    end

    rect rgba(140,180,120,0.08)
    Note over U,D: Send op-call metadata (references audio by digest)
    U->>S: HTTPS: op-call metadata
    S->>S: Authenticate and authorize project access
    S->>D: Record op-call row
    D-->>S: Ack
    S-->>U: HTTPS response
    end
```

**Key points:**

- Audio bytes and op-call metadata are transmitted in **separate HTTPS requests**. Raw audio is never embedded in the op-call JSON.
- The SDK computes a **SHA-256 digest** of each audio file client-side; the service re-computes it on receipt and rejects the upload on mismatch, detecting corruption in transit.
- The digest is also used as the **content-addressed storage key**, scoped by project. Identical audio uploaded twice to the same project is stored once; different projects are isolated.
- The service writes to cloud blob storage at a deterministic, project-scoped path. The database only records the **location** (and size) — no audio bytes live in the database on this path.

---

## 4. Read Path

```mermaid
---
config:
  layout: elk
---
sequenceDiagram
    autonumber
    participant U as Weave UI / SDK
    participant S as Weave Service
    participant D as Database
    participant B as Cloud Blob<br/>Storage

    U->>S: HTTPS: request audio by (project, digest)
    S->>S: Authenticate and authorize project access
    S->>D: Look up file metadata
    D-->>S: Location (blob URI or inline bytes)
    alt audio stored in blob
        S->>B: Read audio bytes
        B-->>S: Audio bytes
    else audio stored inline
        Note over S: Use inline bytes from metadata
    end
    S-->>U: HTTPS response (audio bytes)
```

All reads are proxied through the authenticated Weave service. Blob objects are **not** exposed via direct public URLs or signed URLs; project-level ACLs are enforced on every request.

---

## 5. Configuration Controls

Bucket storage is enabled by the W&B operator via service configuration:

- A master setting specifies the **storage URI** (`s3://…`, `gs://…`, or `az://…`) and the cloud-provider credentials.
- An **allow list** (or a percentage-based ramp keyed on project ID) determines which projects route new uploads to blob storage. Projects not enabled continue to store files inline in the database.
- Provider-specific settings include region, optional KMS key (AWS), and service-account credentials (GCP/Azure).

Existing files are unaffected by flipping the switch: each file is read from whichever location it was originally written to.
