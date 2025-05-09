import base64
import os
from pathlib import Path

import pytest

import weave
from weave.trace.weave_client import WeaveClient, get_ref
from weave.type_handlers.Audio.audio import Audio

# These paths will always resolve to the same location as this file
TEST_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "examples")
TEST_WAV_FILE = os.path.join(TEST_AUDIO_DIR, "audio.wav")
TEST_MP3_FILE = os.path.join(TEST_AUDIO_DIR, "audio.mp3")


# Copy the file to a temporary location
@pytest.fixture
def wav_file(tmp_path: Path, wav_bytes: bytes) -> str:
    filename = str(tmp_path / "audio.wav")
    with open(filename, "wb") as f:
        f.write(wav_bytes)
    return filename


# Copy the file to a temporary location
@pytest.fixture
def mp3_file(tmp_path: Path, mp3_bytes: bytes) -> str:
    filename = str(tmp_path / "audio.mp3")
    with open(filename, "wb") as f:
        f.write(mp3_bytes)
    return filename


# class TestWaveRead:
#     def test_audio_publish(self, client: WeaveClient, wav_file: str) -> None:
#         client.project = "test_audio_publish"
#         audio = wave.open(wav_file, "rb")
#         weave.publish(audio)
#
#         ref = get_ref(audio)
#         assert ref is not None
#         gotten_audio = weave.ref(ref.uri()).get()
#         assert audio.readframes(10) == gotten_audio.readframes(10)
#
#
#     def test_audio_as_dataset_cell(self, client: WeaveClient, wav_file: str) -> None:
#         client.project = "test_audio_as_dataset_cell"
#         audio = wave.open(wav_file, "rb")
#         dataset = weave.Dataset(rows=weave.Table([{"audio": audio}]))
#         weave.publish(dataset)
#
#         ref = get_ref(dataset)
#         assert ref is not None
#
#         gotten_dataset = weave.ref(ref.uri()).get()
#         assert audio.readframes(10) == gotten_dataset.rows[0]["audio"].readframes(10)
#
#
#     def test_audio_as_call_io(self, client: WeaveClient, wav_file: str) -> None:
#         @weave.op
#         def audio_as_input_and_output_part(in_audio: wave.Wave_read) -> dict:
#             return {"out_audio": in_audio}
#
#         client.project = "test_audio_as_call_io"
#         audio = wave.open(wav_file, "rb")
#
#         exp_bytes = audio.readframes(5)
#         audio.rewind()
#
#         audio_dict = audio_as_input_and_output_part(audio)
#
#         assert type(audio_dict["out_audio"]) is wave.Wave_read
#         assert audio_dict["out_audio"].getparams() == audio.getparams()
#         assert audio_dict["out_audio"].readframes(5) == exp_bytes
#
#         input_output_part_call = audio_as_input_and_output_part.calls()[0]
#
#         assert input_output_part_call.inputs["in_audio"].readframes(5) == exp_bytes
#         assert input_output_part_call.output["out_audio"].readframes(5) == exp_bytes


class TestWeaveAudio:
    @pytest.mark.parametrize("audio_file", [TEST_MP3_FILE, TEST_WAV_FILE])
    def test_publish_audio_from_path(
        self, client: WeaveClient, audio_file: str
    ) -> None:
        client.project = "test_audio_publish_from_path"
        audio = Audio.from_path(audio_file)
        ref = weave.publish(audio)
        assert ref is not None
        gotten_audio = ref.get()
        # Ensure filetype was parsed correctly from the path
        assert audio_file.endswith(gotten_audio.fmt)
        # Ensure at least the first 10 bytes are the same
        assert open(audio_file, "rb").read(10) == gotten_audio.data[:10]

    @pytest.mark.parametrize(
        "audio_file_and_fmt", [(TEST_MP3_FILE, "mp3"), (TEST_WAV_FILE, "wav")]
    )
    def test_publish_audio_from_decoded_bytes(
        self, client: WeaveClient, audio_file_and_fmt: str
    ) -> None:
        client.project = "test_audio_publish_from_bytes"
        audio_file, fmt = audio_file_and_fmt
        audio_bytes = open(audio_file, "rb").read()
        if fmt == "wav":
            audio = Audio(data=audio_bytes, fmt="wav")
        else:
            audio = Audio(data=audio_bytes, fmt="mp3")

        ref = weave.publish(audio)
        assert ref is not None
        gotten_audio = ref.get()

        # Ensure filetype was parsed correctly from the path
        assert audio_file.endswith(gotten_audio.fmt)

        # Ensure at least the first 10 bytes are the same
        assert open(audio_file, "rb").read(10) == gotten_audio.data[:10]

    @pytest.mark.parametrize(
        "audio_file_and_fmt", [(TEST_MP3_FILE, "mp3"), (TEST_WAV_FILE, "wav")]
    )
    def test_publish_audio_from_encoded_bytes(
        self, client: WeaveClient, audio_file_and_fmt: str
    ) -> None:
        client.project = "test_audio_publish_from_bytes"
        audio_file, fmt = audio_file_and_fmt
        audio_bytes = open(audio_file, "rb").read()
        encoded_bytes = base64.b64encode(audio_bytes)

        if fmt == "wav":
            audio = Audio(data=encoded_bytes, fmt="wav")
        else:
            audio = Audio(data=encoded_bytes, fmt="mp3")

        ref = weave.publish(audio)
        assert ref is not None
        gotten_audio = ref.get()

        # Ensure at least the first 10 bytes of the original file and decoded data are the same
        assert open(audio_file, "rb").read(10) == gotten_audio.data[:10]

    @pytest.mark.parametrize("audio_file", [TEST_MP3_FILE, TEST_WAV_FILE])
    def test_audio_as_dataset_cell(self, client: WeaveClient, audio_file: str) -> None:
        client.project = "test_audio_as_dataset_cell"
        audio = Audio.from_path(audio_file)
        ref = weave.publish(audio)
        assert ref is not None
        dataset = weave.Dataset(rows=weave.Table([{"audio": audio}]))
        ref = weave.publish(dataset)

        ref = get_ref(dataset)
        assert ref is not None

        gotten_dataset = ref.get()
        assert audio.data[:10] == gotten_dataset.rows[0]["audio"].data[:10]

    @pytest.mark.parametrize("audio_file", [TEST_MP3_FILE, TEST_WAV_FILE])
    def test_audio_as_call_io(self, client: WeaveClient, audio_file: str) -> None:
        client.project = "test_audio_as_call_io"

        def postprocess_inputs(inputs: dict) -> dict:
            inputs["in_audiofile"] = Audio.from_path(inputs["in_audiofile"])
            return inputs

        def postprocess_output(output: dict) -> dict:
            output["out_audiofile"] = Audio.from_path(output["out_audiofile"])
            return output

        @weave.op(
            postprocess_inputs=postprocess_inputs, postprocess_output=postprocess_output
        )
        def audio_as_input_and_output_part(in_audiofile: str) -> dict:
            return {"out_audiofile": in_audiofile}

        audio_dict = audio_as_input_and_output_part(audio_file)

        # Make sure we didn't modify the original outputs for runtime
        # assert type(audio_dict["out_audiofile"]) is str

        input_output_part_call = audio_as_input_and_output_part.calls()[0]

        # Make sure we interpretted the postprocess correctly
        assert isinstance(input_output_part_call.inputs["in_audiofile"], Audio)
        assert isinstance(input_output_part_call.output["out_audiofile"], Audio)
