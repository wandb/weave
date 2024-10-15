import math
import tempfile
import wave

import weave
from weave.trace.weave_client import WeaveClient, get_ref


def make_audio_file(filename: str) -> None:
    FRAMES_PER_SECOND = 44100

    def sound_wave(frequency, num_seconds):
        for frame in range(round(num_seconds * FRAMES_PER_SECOND)):
            time = frame / FRAMES_PER_SECOND
            amplitude = math.sin(2 * math.pi * frequency * time)
            yield round((amplitude + 1) / 2 * 255)

        with wave.open(filename, mode="wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(1)
            wav_file.setframerate(FRAMES_PER_SECOND)
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
        assert audio.readframes(1) == gotten_audio.readframes(1)


def test_audio_as_property(client: WeaveClient) -> None:
    client.project = "test_audio_as_property"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        make_audio_file(temp_file.name)
        audio = wave.open(temp_file.name, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        assert audio.readframes(1) == gotten_audio.readframes(1)


def test_audio_as_dataset_cell(client: WeaveClient) -> None:
    client.project = "test_audio_as_dataset_cell"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        make_audio_file(temp_file.name)
        audio = wave.open(temp_file.name, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None


@weave.op
def audio_as_solo_output(publish_first: bool) -> wave.Wave_read:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        make_audio_file(temp_file.name)
        audio = wave.open(temp_file.name, "rb")
        if publish_first:
            weave.publish(audio)
        return audio


@weave.op
def audio_as_input_and_output_part(in_audio: wave.Wave_read) -> dict:
    return {"out_audio": in_audio}


def test_audio_as_call_io(client: WeaveClient) -> None:
    client.project = "test_audio_as_call_io"
    non_published_audio = audio_as_solo_output(publish_first=False)
    audio_dict = audio_as_input_and_output_part(non_published_audio)

    exp_bytes = non_published_audio.readframes(1)
    assert audio_dict["out_audio"].readframes(1) == exp_bytes
