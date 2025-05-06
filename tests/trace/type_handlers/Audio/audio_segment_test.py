from pathlib import Path
from typing import Optional

import numpy as np
import pytest
from pydub import AudioSegment

import weave
from weave.trace.weave_client import WeaveClient, get_ref

"""When testing types, it is important to test:
Objects:
1. Publishing Directly
2. Publishing as a property
3. Using as a cell in a table
Calls:
4. Using as inputs, output, and output component (raw)
5. Using as inputs, output, and output component (refs)
"""


@pytest.fixture
def make_audio_segment(duration: Optional[int] = None) -> AudioSegment:
    sample_rate = 44100  # Standard audio sample rate
    duration = 1
    frequency = 440  # Hz (A4 note)

    t = np.linspace(0, duration, int(sample_rate * duration), False)
    amplitude = np.iinfo(np.int16).max
    tone = amplitude * np.sin(2 * np.pi * frequency * t)
    audio_data = tone.astype(np.int16)

    return AudioSegment(
        audio_data.tobytes(), frame_rate=sample_rate, channels=1, sample_width=2
    )


@pytest.fixture
def make_mp3_file(tmp_path: Path, make_audio_segment: AudioSegment) -> str:
    filename = str(tmp_path / "audio.mp3")
    ext = filename.split(".")[-1]
    make_audio_segment.export(out_f=filename, format=ext)
    return filename


def test_weave_audio_publish(client: WeaveClient, make_mp3_file: str) -> None:
    client.project = "test_audio_publish"

    # Goes in as wrapper around path
    audio = weave.Audio(make_mp3_file)
    weave.publish(audio)
    ref = get_ref(audio)
    assert ref is not None
    # Comes out as an AudioSegment object
    gotten_audio: AudioSegment = ref.get()
    assert gotten_audio.duration_seconds == 1


def test_audio_segment_publish(
    client: WeaveClient, make_audio_segment: AudioSegment
) -> None:
    client.project = "test_audio_publish"
    # Goes in as AudioSegement object
    weave.publish(make_audio_segment)
    ref = get_ref(make_audio_segment)
    assert ref is not None
    # Comes out as an AudioSegment object
    gotten_audio = ref.get()
    assert isinstance(gotten_audio, AudioSegment)


def test_weave_audio_mp3_as_call_io(client: WeaveClient, make_mp3_file) -> None:
    client.project = "test_weave_audio_mp3_as_call_io"

    @weave.op
    def weave_audio_as_input_and_output_part(in_audio: weave.Audio) -> dict:
        return {"out_audio": in_audio}

    # Create a temporary audio file
    weave_audio = weave.Audio(make_mp3_file)

    # Load the file into audio segement
    source_audio = AudioSegment.from_mp3(make_mp3_file)

    weave_audio_as_input_and_output_part(weave_audio)
    # Load op returns an AudioSegment, so we don't need to .from_mp3 them
    input_output_part_call = weave_audio_as_input_and_output_part.calls()[0]

    input_audio = input_output_part_call.inputs["in_audio"]
    output_audio = input_output_part_call.output["out_audio"]

    source_frames = source_audio[:5]
    in_frames = input_audio[:5]
    out_frames = output_audio[:5]

    # Here the file should be copied directly so it is never re-encoded
    # Thus, source audio should match input and output
    for i in range(5):
        assert in_frames[i] == source_frames[i]
        assert out_frames[i] == source_frames[i]


def test_audio_segment_mp3_as_call_io(client: WeaveClient, make_mp3_file) -> None:
    @weave.op
    def audio_segment_as_input_and_output_part(in_audio: AudioSegment) -> dict:
        return {"out_audio": in_audio}

    client.project = "test_audio_as_call_io"
    # Load the file into audio segement
    source_audio = AudioSegment.from_mp3(make_mp3_file)
    audio_segment_as_input_and_output_part(source_audio)
    calls = audio_segment_as_input_and_output_part.calls()

    assert len(calls) == 1

    input_output_part_call = calls[0]

    input_audio = input_output_part_call.inputs["in_audio"]
    output_audio = input_output_part_call.output["out_audio"]

    in_frames = input_audio.get_array_of_samples()[:5]
    out_frames = output_audio.get_array_of_samples()[:5]

    # Here we pass an audio secgment object, so it is re-encoded
    # Thus, source audio WILL NOT match input and output
    # However, the input and output should match
    for i in range(5):
        assert in_frames[i] == out_frames[i]
