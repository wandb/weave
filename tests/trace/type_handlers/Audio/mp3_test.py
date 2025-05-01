import numpy as np
from pydub import AudioSegment
from typing import Optional
from pathlib import Path
import wave

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
    tone = amplitude * np.sin(2*np.pi*frequency*t)
    audio_data = tone.astype(np.int16)
    return AudioSegment(
        audio_data.tobytes(), 
        frame_rate=sample_rate,
        sample_width=audio_data.dtype.itemsize,
        channels=1
    )

def make_audio_file(filename: str, duration: Optional[int] = None) -> None:
    audio_segment = make_audio(duration)
    ext = filename.split(".")[-1][1:]
    audio_segment.export(filename, format=ext)

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
    gotten_audio: AudioSegment = weave.ref(ref.uri()).get()
    assert gotten_audio.duration_seconds == 1
