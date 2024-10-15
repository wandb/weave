import weave
import wave
import math
import tempfile

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


def test_audio_publish(client: weave.WeaveClient) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        make_audio_file(temp_file.name)
        audio = wave.open(temp_file.name, "rb")
        weave.publish(audio)

        ref = get_ref(audio)
        assert ref is not None
        gotten_audio = weave.ref(ref.uri()).get()
        assert audio.readframes(1) == gotten_audio.readframes(1)
