import base64
import os
import wave

import pytest

import weave
from weave.trace.weave_client import WeaveClient, get_ref
from weave.type_handlers.Audio.audio import Audio

# These paths will always resolve to the same location as this file
TEST_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "examples")
TEST_WAV_FILE = os.path.join(TEST_AUDIO_DIR, "audio.wav")
TEST_MP3_FILE = os.path.join(TEST_AUDIO_DIR, "audio.mp3")


class TestWaveRead:
    def test_audio_publish(self, client: WeaveClient) -> None:
        client.project = "test_audio_publish"
        audio = wave.open(TEST_WAV_FILE, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_audio.readframes(10)

    def test_audio_as_dataset_cell(self, client: WeaveClient) -> None:
        client.project = "test_audio_as_dataset_cell"
        audio = wave.open(TEST_WAV_FILE, "rb")
        dataset = weave.Dataset(rows=weave.Table([{"audio": audio}]))
        weave.publish(dataset)

        ref = get_ref(dataset)
        assert ref is not None

        gotten_dataset = weave.ref(ref.uri()).get()
        assert audio.readframes(10) == gotten_dataset.rows[0]["audio"].readframes(10)

    def test_audio_as_call_io(self, client: WeaveClient) -> None:
        @weave.op
        def audio_as_input_and_output_part(in_audio: wave.Wave_read) -> dict:
            return {"out_audio": in_audio}

        client.project = "test_audio_as_call_io"
        audio = wave.open(TEST_WAV_FILE, "rb")

        exp_bytes = audio.readframes(5)
        audio.rewind()

        audio_dict = audio_as_input_and_output_part(audio)

        assert type(audio_dict["out_audio"]) is wave.Wave_read
        assert audio_dict["out_audio"].getparams() == audio.getparams()
        assert audio_dict["out_audio"].readframes(5) == exp_bytes

        input_output_part_call = audio_as_input_and_output_part.calls()[0]

        assert input_output_part_call.inputs["in_audio"].readframes(5) == exp_bytes
        assert input_output_part_call.output["out_audio"].readframes(5) == exp_bytes


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
        assert audio_file.endswith(gotten_audio.format)
        # Ensure at least the first 10 bytes are the same
        assert open(audio_file, "rb").read(10) == gotten_audio.data[:10]

    @pytest.mark.parametrize(
        "audio_file_and_format", [(TEST_MP3_FILE, "mp3"), (TEST_WAV_FILE, "wav")]
    )
    def test_publish_audio_from_decoded_bytes(
        self, client: WeaveClient, audio_file_and_format: str
    ) -> None:
        client.project = "test_audio_publish_from_bytes"
        audio_file, format = audio_file_and_format
        audio_bytes = open(audio_file, "rb").read()
        audio = Audio.from_data(data=audio_bytes, format=format)

        ref = weave.publish(audio)
        assert ref is not None
        gotten_audio = ref.get()

        # Ensure filetype was parsed correctly from the path
        assert audio_file.endswith(gotten_audio.format)

        # Ensure at least the first 10 bytes are the same
        assert open(audio_file, "rb").read(10) == gotten_audio.data[:10]

    @pytest.mark.parametrize(
        "audio_file_and_format", [(TEST_MP3_FILE, "mp3"), (TEST_WAV_FILE, "wav")]
    )
    def test_publish_audio_from_encoded_bytes(
        self, client: WeaveClient, audio_file_and_format: str
    ) -> None:
        client.project = "test_audio_publish_from_encoded_bytes"
        audio_file, format = audio_file_and_format
        audio_bytes = open(audio_file, "rb").read()
        encoded_bytes = base64.b64encode(audio_bytes)
        audio = Audio.from_data(data=encoded_bytes, format=format)

        ref = weave.publish(audio)
        assert ref is not None
        gotten_audio = ref.get()

        # Ensure at least the first 10 bytes of the original file and decoded data are the same
        assert open(audio_file, "rb").read(10) == gotten_audio.data[:10]

    def test_audio_fails_on_unsupported_format(self, client: WeaveClient) -> None:
        client.project = "test_audio_fails_on_unsupported_format"
        assert pytest.raises(
            ValueError, lambda: Audio.from_data(data=b"example", format="invalid")
        )

    def test_audio_fails_on_empty_data(self, client: WeaveClient) -> None:
        client.project = "test_audio_fails_on_empty_data"
        assert pytest.raises(
            ValueError, lambda: Audio.from_data(data=b"", format="mp3")
        )

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

        def on_input(inputs: dict) -> dict:
            inputs["in_audiofile"] = Audio.from_path(inputs["in_audiofile"])
            return inputs

        def on_output(output: str) -> Audio:
            return Audio.from_path(output)

        @weave.op(postprocess_inputs=on_input, postprocess_output=on_output)
        def audio_as_input_and_output_part(in_audiofile: str) -> str:
            return in_audiofile

        out_file = audio_as_input_and_output_part(audio_file)

        # Make sure we didn't modify the original outputs for runtime
        assert out_file == audio_file

        input_output_part_call = audio_as_input_and_output_part.calls()[0]

        # Make sure we interpretted the postprocess correctly
        assert isinstance(input_output_part_call.inputs["in_audiofile"], Audio)
        assert isinstance(input_output_part_call.output, Audio)
