from typing import Literal
import wave
import weave
from weave.trace.weave_client import WeaveClient, get_ref
from pathlib import Path
import os
import pytest

from weave.type_handlers.Audio.audio import Audio

# These paths will always resolve to the same location as this file
TEST_AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'examples')
TEST_WAV_FILE = os.path.join(TEST_AUDIO_DIR, "audio.wav")
TEST_MP3_FILE = os.path.join(TEST_AUDIO_DIR, "audio.mp3")

@pytest.fixture
def wav_bytes() -> bytes:
    return open(TEST_WAV_FILE, "rb").read()

@pytest.fixture
def mp3_bytes() -> bytes:
    return open(TEST_MP3_FILE, "rb").read()

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
    def test_audio_from_path_mp3(self, client: WeaveClient) -> None:

        client.project = "test_audio_publish"
        audio = Audio.from_path(TEST_MP3_FILE)
        weave.publish(audio)
        ref = get_ref(audio)
        print('ref')
        print(ref)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        print(gotten_audio.data)
        assert gotten_audio.endswith(gotten_audio.fmt)

    # @pytest.mark.parametrize("audio_file", [TEST_MP3_FILE, TEST_WAV_FILE])
    # def test_audio_from_path(self, client: WeaveClient, audio_file: str) -> None:
    #     client.project = "test_audio_publish"
    #     audio = Audio.from_path(audio_file)
    #
    #     weave.publish(audio)
    #     ref = get_ref(audio)
    #     print('ref')
    #     print(ref)
    #     assert ref is not None
    #     gotten_audio = weave.ref(ref.uri()).get()
    #     print(gotten_audio.data)
    #     # Ensure filetype was parsed correctly from the path
    #     assert gotten_audio.endswith(gotten_audio.fmt)
    #     # Ensure at least the first 10 bytes are the same
    #     assert open(audio_file, "rb").read(10) == gotten_audio.data[:10]

    #
    # def test_audio_as_dataset_cell(self, client: WeaveClient, wav_file: str) -> None:
    #     client.project = "test_audio_as_dataset_cell"
    #     audio = wave.open(wav_file, "rb")
    #     dataset = weave.Dataset(rows=weave.Table([{"audio": audio}]))
    #     weave.publish(dataset)
    #
    #     ref = get_ref(dataset)
    #     assert ref is not None
    #
    #     gotten_dataset = weave.ref(ref.uri()).get()
    #     assert audio.readframes(10) == gotten_dataset.rows[0]["audio"].readframes(10)
    #
    #
    # def test_audio_as_call_io(self, client: WeaveClient, wav_file: str) -> None:
    #     @weave.op
    #     def audio_as_input_and_output_part(in_audio: wave.Wave_read) -> dict:
    #         return {"out_audio": in_audio}
    #
    #     client.project = "test_audio_as_call_io"
    #     audio = wave.open(wav_file, "rb")
    #
    #     exp_bytes = audio.readframes(5)
    #     audio.rewind()
    #
    #     audio_dict = audio_as_input_and_output_part(audio)
    #
    #     assert type(audio_dict["out_audio"]) is wave.Wave_read
    #     assert audio_dict["out_audio"].getparams() == audio.getparams()
    #     assert audio_dict["out_audio"].readframes(5) == exp_bytes
    #
    #     input_output_part_call = audio_as_input_and_output_part.calls()[0]
    #
    #     assert input_output_part_call.inputs["in_audio"].readframes(5) == exp_bytes
    #     assert input_output_part_call.output["out_audio"].readframes(5) == exp_bytes
