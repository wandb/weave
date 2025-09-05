import base64

from weave.integrations.openai_realtime.audio_buffer import AudioBufferManager


def test_audio_buffer_extend_and_slice_and_clear():
    buf = AudioBufferManager(sample_rate_hz=1000, bits_per_sample=16, channels=1)
    # 1 kHz, 2 bytes per sample -> 2 bytes per ms
    payload = bytes(range(20))  # 20 bytes -> 10 ms
    b64 = base64.b64encode(payload).decode()
    buf.extend_base64(b64)

    # Slice 0..5ms -> first 10 bytes
    seg = buf.get_segment_ms(0, 5)
    assert seg == payload[:10]

    # Slice beyond range clamps
    seg2 = buf.get_segment_ms(-100, 1000)
    assert seg2 == payload

    buf.clear()
    assert len(buf.buffer) == 0


def test_audio_buffer_invalid_base64_is_ignored(caplog):
    buf = AudioBufferManager()
    before = len(buf.buffer)
    buf.extend_base64("<not-base64>")
    # No exception and buffer unchanged
    assert len(buf.buffer) == before
