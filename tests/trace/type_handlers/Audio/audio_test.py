import math
import tempfile
import wave
from typing import Optional

import weave
from weave.trace.weave_client import WeaveClient, get_ref


def make_audio_file(filename: str, nframes: Optional[int] = None) -> None:
    FRAMES_PER_SECOND = 24_000

    def sound_wave(frequency, num_seconds):
        for frame in range(round(num_seconds * FRAMES_PER_SECOND)):
            time = frame / FRAMES_PER_SECOND
            amplitude = math.sin(2 * math.pi * frequency * time)
            yield round((amplitude + 1) / 2 * 255)

    with wave.open(filename, mode="wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(FRAMES_PER_SECOND)
        if nframes is not None:
            wav_file.setnframes(nframes)
        wav_file.writeframes(bytes(sound_wave(440, 2.5)))


def test_audio_publish(client: WeaveClient) -> None:
    client.project = "test_audio_publish"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        make_audio_file(temp_file.name)
        audio = wave.open(temp_file.name, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_audio.readframes(10)


def test_audio_as_property(client: WeaveClient) -> None:
    client.project = "test_audio_as_property"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        make_audio_file(temp_file.name)
        audio = wave.open(temp_file.name, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_audio.readframes(10)


def test_audio_as_dataset_cell(client: WeaveClient) -> None:
    client.project = "test_audio_as_dataset_cell"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        make_audio_file(temp_file.name)
        audio = wave.open(temp_file.name, "rb")
        dataset = weave.Dataset(rows=[{"audio": audio}])
        weave.publish(dataset)

        ref = get_ref(dataset)
        assert ref is not None

        gotten_dataset = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_dataset.rows[0]["audio"].readframes(10)


@weave.op
def audio_as_input_and_output_part(in_audio: wave.Wave_read) -> dict:
    return {"out_audio": in_audio}


def test_audio_as_call_io(client: WeaveClient) -> None:
    client.project = "test_audio_as_call_io"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        make_audio_file(temp_file.name)
        audio = wave.open(temp_file.name, "rb")

        exp_bytes = audio.readframes(5)
        audio.rewind()

        audio_dict = audio_as_input_and_output_part(audio)

        assert type(audio_dict["out_audio"]) is wave.Wave_read
        assert audio_dict["out_audio"].getparams() == audio.getparams()
        assert audio_dict["out_audio"].readframes(5) == exp_bytes

        input_output_part_call = audio_as_input_and_output_part.calls()[0]

        assert input_output_part_call.inputs["in_audio"].readframes(5) == exp_bytes
        assert input_output_part_call.output["out_audio"].readframes(5) == exp_bytes


def test_audio_with_max_nframes(client: WeaveClient) -> None:
    client.project = "test_audio_with_max_nframes"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        two_gb_nframes = (1 * 1024 * 1024 * 1024) - 1
        make_audio_file(temp_file.name, nframes=two_gb_nframes)
        audio = wave.open(temp_file.name, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_audio.readframes(10)

        # now with 0 nframes
        make_audio_file(temp_file.name, nframes=0)
        audio = wave.open(temp_file.name, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_audio.readframes(10)
