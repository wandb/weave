from weave.integrations.openai_realtime.encoding import pcm_to_wav


def test_pcm_to_wav_empty_produces_minimal_header():
    data = pcm_to_wav(b"")
    # RIFF header and WAVE format
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"
    # no audio frames
    assert len(data) >= 44


def test_pcm_to_wav_even_and_odd_lengths():
    pcm_even = b"\x01\x02\x03\x04"  # 4 bytes
    wav_even = pcm_to_wav(pcm_even)
    assert wav_even.startswith(b"RIFF")
    # 44-byte header + 4 bytes data
    assert len(wav_even) == 44 + 4

    pcm_odd = b"\x01\x02\x03"  # 3 bytes -> padded to 4
    wav_odd = pcm_to_wav(pcm_odd)
    assert wav_odd.startswith(b"RIFF")
    assert len(wav_odd) == 44 + 4
