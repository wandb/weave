import io
import wave


def pcm_to_wav(
    pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Convert raw PCM audio data to WAV format.

    Args:
        pcm_data: Raw PCM audio bytes (little-endian 16-bit PCM)
        sample_rate: Sample rate in Hz (default 24000 for OpenAI Realtime)
        channels: Number of channels (default 1 for mono)
        sample_width: Sample width in bytes (default 2 for 16-bit)

    Returns:
        WAV formatted audio bytes
    """
    # Ensure we have valid PCM data
    if not pcm_data or len(pcm_data) == 0:
        # Return minimal valid WAV file with no audio data
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"")
        wav_buffer.seek(0)
        return wav_buffer.getvalue()

    # Ensure the PCM data length is even (for 16-bit samples)
    if len(pcm_data) % 2 != 0:
        # Pad with a zero byte if odd length
        pcm_data = pcm_data + b"\x00"

    # Create WAV file in memory using wave module for correct formatting
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        # Set WAV parameters
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)

        # Write the PCM data as frames
        wav_file.writeframes(pcm_data)

    # Get the WAV data
    wav_buffer.seek(0)
    return wav_buffer.getvalue()
