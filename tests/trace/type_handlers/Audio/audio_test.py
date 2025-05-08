import math
import array
import wave
from pathlib import Path
from typing import Generator, Optional
import pytest

import weave
from weave.trace.weave_client import WeaveClient, get_ref

def create_sound_wave(
    num_frames: Optional[int] = None,
    duration: Optional[float] = None,
    frequency: float = 440.0,
    sample_rate: int = 44100,
    amplitude: float = 1.0,
) -> Generator[int, None, None]:
    """
    Generates a sine wave as a list of samples.

    Args:
        num_frames: The total number of frames (samples) to generate.
        frequency: The frequency of the sine wave in Hertz (Hz).
                   Defaults to 440.0 Hz (A4 note).
        sample_rate: The number of samples per second (Hz).
                     Defaults to 44100 Hz (standard CD quality).
        amplitude: The peak amplitude of the wave.
                   For 16-bit audio, this should be scaled.
                   Defaults to 1.0 (for floating point samples).
                   If dtype is 'h' (16-bit signed short), the effective amplitude
                   will be amplitude * 32767.

    Returns:
        An array.array containing the generated wave samples.
    """
    if duration:
        num_frames = num_frames or int(sample_rate * duration)
    elif not num_frames:
        raise ValueError("One of num_frames or duration must be set.")
    if frequency <= 0:
        raise ValueError("Frequency must be positive.")
    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive.")
    if not 0.0 <= amplitude <= 1.0:
        # For floating point, amplitude is typically normalized between -1.0 and 1.0.
        # For integer types, this will be scaled.
        pass # Allowing amplitude > 1 for now, but it might lead to clipping if not handled.

    # Maximum value for 16-bit signed audio
    max_amplitude_8bit = 255

    for i in range(num_frames):
        # Calculate the time for the current frame
        time_s = float(i) / sample_rate
        # Calculate the sample value for the sine wave
        # Formula: amplitude * sin(2 * pi * frequency * time)
        value = math.sin(2 * math.pi * frequency * time_s)
        scaled_value = int(amplitude * value * max_amplitude_8bit)
        # Clamp to 16-bit range to prevent overflow/underflow
        scaled_value = max(min(scaled_value, max_amplitude_8bit), max(-max_amplitude_8bit -1, 0))
        yield scaled_value

def make_wav_file_with_n_frames(tmp_path: Path, n_frames: int) -> str:
    FRAMES_PER_SECOND = 24_000
    filename = str(tmp_path / "audio.wav")
    with wave.open(filename, mode="wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(FRAMES_PER_SECOND)
        wav_file.writeframes(bytes(create_sound_wave(n_frames, sample_rate=FRAMES_PER_SECOND)))
    return filename

@pytest.fixture
def make_wav_file(tmp_path: Path) -> str:
    FRAMES_PER_SECOND = 24_000
    filename = str(tmp_path / "audio.wav")
    with wave.open(filename, mode="wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(FRAMES_PER_SECOND)
        wav_file.writeframes(bytes(create_sound_wave(duration=2.5, sample_rate=FRAMES_PER_SECOND)))
    return filename

class TestWaveObject:
    def test_audio_publish(self, client: WeaveClient, make_wav_file: str) -> None:
        client.project = "test_audio_publish"
        audio = wave.open(make_wav_file, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_audio.readframes(10)


    def test_audio_as_dataset_cell(self, client: WeaveClient, make_wav_file: str) -> None:
        client.project = "test_audio_as_dataset_cell"
        audio = wave.open(make_wav_file, "rb")
        dataset = weave.Dataset(rows=weave.Table([{"audio": audio}]))
        weave.publish(dataset)

        ref = get_ref(dataset)
        assert ref is not None

        gotten_dataset = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_dataset.rows[0]["audio"].readframes(10)



    def test_audio_as_call_io(self, client: WeaveClient, make_wav_file: str) -> None:
        @weave.op
        def audio_as_input_and_output_part(in_audio: wave.Wave_read) -> dict:
            return {"out_audio": in_audio}

        client.project = "test_audio_as_call_io"
        audio = wave.open(make_wav_file, "rb")

        exp_bytes = audio.readframes(5)
        audio.rewind()

        audio_dict = audio_as_input_and_output_part(audio)

        assert type(audio_dict["out_audio"]) is wave.Wave_read
        assert audio_dict["out_audio"].getparams() == audio.getparams()
        assert audio_dict["out_audio"].readframes(5) == exp_bytes

        input_output_part_call = audio_as_input_and_output_part.calls()[0]

        assert input_output_part_call.inputs["in_audio"].readframes(5) == exp_bytes
        assert input_output_part_call.output["out_audio"].readframes(5) == exp_bytes
