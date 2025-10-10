import base64
import binascii
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AudioBufferManager:
    """Maintains a single, continuous PCM audio buffer for a conversation and
    provides helpers to slice out segments by millisecond offsets.

    Default format: 16-bit PCM, mono, 24kHz (extensible).
    """

    sample_rate_hz: int = 24000
    bits_per_sample: int = 16
    channels: int = 1
    buffer: bytearray = field(default_factory=bytearray)

    def bytes_per_sample(self) -> int:
        return (self.bits_per_sample // 8) * self.channels

    def extend_base64(self, b64: str) -> None:
        """Decode base64 audio and extend buffer. Ignores invalid payloads gracefully."""
        try:
            self.buffer.extend(base64.b64decode(b64))
        except binascii.Error as e:
            # Some fixtures use placeholder strings like "<audio bytes>".
            # Skip invalid base64 without failing the pipeline, but log for visibility.
            logger.warning(
                "AudioBufferManager.extend_base64: invalid base64; ignoring. error=%s preview=%r",
                e,
                b64[:20],
            )

    def clear(self) -> None:
        self.buffer.clear()

    def _ms_to_byte_range(self, start_ms: int, end_ms: int) -> tuple[int, int]:
        bps = self.bytes_per_sample()
        start_samples = int((start_ms / 1000.0) * self.sample_rate_hz)
        end_samples = int((end_ms / 1000.0) * self.sample_rate_hz)
        return start_samples * bps, end_samples * bps

    def get_segment_ms(self, start_ms: int, end_ms: int) -> bytes:
        start_b, end_b = self._ms_to_byte_range(start_ms, end_ms)
        start_b = max(0, start_b)
        end_b = min(len(self.buffer), max(start_b, end_b))
        return bytes(self.buffer[start_b:end_b])
