from pathlib import Path
from typing import Optional

import numpy as np
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


def make_audio(duration: Optional[int] = None) -> AudioSegment:
    sample_rate = 44100  # Standard audio sample rate
    duration = duration or 2  # seconds
    frequency = 440  # Hz (A4 note)

    t = np.linspace(0, duration, int(sample_rate * duration), False)
    amplitude = np.iinfo(np.int16).max
    tone = amplitude * np.sin(2 * np.pi * frequency * t)
    audio_data = tone.astype(np.int16)

    return AudioSegment(
        audio_data.tobytes(), frame_rate=sample_rate, channels=1, sample_width=2
    )


def make_audio_file(filename: str, duration: Optional[int] = None) -> None:
    audio_segment = make_audio(duration)
    ext = filename.split(".")[-1]
    audio_segment.export(out_f=filename, format=ext)


def test_weave_audio_publish(client: WeaveClient, tmp_path: Path) -> None:
    client.project = "test_audio_publish"
    filename = str(tmp_path / "audio.mp3")
    duration = 1
    make_audio_file(filename, duration)

    # Goes in as wrapper around path
    audio = weave.Audio(filename)
    weave.publish(audio)
    ref = get_ref(audio)
    assert ref is not None
    weave.ref(ref.uri()).get()
    # Comes out as an AudioSegment object
    gotten_audio: AudioSegment = weave.ref(ref.uri()).get()
    assert gotten_audio.duration_seconds == 1


def test_audio_segment_publish(client: WeaveClient) -> None:
    client.project = "test_audio_publish"
    duration = 1
    audio = make_audio(duration)

    # Goes in as AudioSegement object
    weave.publish(audio)
    ref = get_ref(audio)
    assert ref is not None

    # Comes out as an AudioSegment object
    gotten_audio = weave.ref(ref.uri()).get()
    assert gotten_audio.duration_seconds == 1


@weave.op
def weave_audio_as_input_and_output_part(in_audio: weave.Audio) -> dict:
    return {"out_audio": in_audio}


def test_weave_audio_mp3_as_call_io(client: WeaveClient, tmp_path: Path) -> None:
    client.project = "test_audio_as_call_io"
    temp_file = str(tmp_path / "audio.mp3")
    # Create a temporary audio file
    make_audio_file(temp_file)

    # Load the file into audio segement
    audio = AudioSegment.from_mp3(temp_file)
    source_test_frames = [audio.get_frame(i) for i in range(5)]

    input_output_part_call = weave_audio_as_input_and_output_part.calls()[0]

    input_audio = input_output_part_call.inputs["in_audio"]
    input_test_frames = [input_audio.get_frame(i) for i in range(5)]
    assert input_test_frames == source_test_frames

    output_audio = input_output_part_call.output["out_audio"]
    output_test_frames = [output_audio.get_frame(i) for i in range(5)]
    assert output_test_frames == source_test_frames
