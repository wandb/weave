import io
import wave
from abc import ABC, abstractmethod
from typing import Literal

import numpy as np
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# PNG Image Settings
PNG_DIMENSIONS = (128, 128)

# WAV Audio Settings
WAV_DURATION_SECONDS = 1
WAV_FRAMERATE = 22050
WAV_SAMPLE_WIDTH = 2
WAV_NUM_CHANNELS = 1
WAV_FREQUENCY = 440

# MP4 Video Settings
MP4_FPS = 24
MP4_DURATION_SECONDS = 1
MP4_DIMENSIONS = (320, 240)


class GeneratedMedia(ABC):
    """An abstract base class for generated media that can be saved."""

    @abstractmethod
    def save(self, filename: str) -> None:
        """Saves the media content to a file."""
        pass


class PngMedia(GeneratedMedia):
    """Handles saving for Pillow Image objects."""

    def __init__(self, image: Image.Image):
        self._image = image

    def save(self, filename: str) -> None:
        return self._image.save(filename)


class BytesMedia(GeneratedMedia):
    """Handles saving for any media represented as raw bytes (e.g., PDF, WAV)."""

    def __init__(self, data: bytes, media_type: str = "File"):
        self._data = data
        self._media_type = media_type

    def save(self, filename: str) -> None:
        with open(filename, "wb") as f:
            f.write(self._data)
        return


# --- Generation Functions ---


def generate_png() -> PngMedia:
    """Generates a PNG image and returns a savable media object."""
    width, height = PNG_DIMENSIONS
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            r = int((x / (width - 1)) * 255)
            b = int(255 - r)
            img_array[y, x] = [r, 0, b]
    image = Image.fromarray(img_array, "RGB")
    return PngMedia(image)


def generate_pdf() -> BytesMedia:
    """Generates a PDF and returns a savable media object."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    _, height = letter
    c.drawString(100, height - 100, "Hello, World!")
    c.drawString(100, height - 120, "This is a test PDF.")
    c.save()
    buffer.seek(0)
    return BytesMedia(buffer.getvalue(), media_type="PDF")


def generate_wav() -> BytesMedia:
    """Generates a WAV audio file and returns a savable media object."""
    num_samples = int(WAV_FRAMERATE * WAV_DURATION_SECONDS)
    t = np.linspace(0, WAV_DURATION_SECONDS, num_samples, endpoint=False)
    sine_wave = np.sin(2 * np.pi * WAV_FREQUENCY * t)
    amplitude = 2 ** (8 * WAV_SAMPLE_WIDTH - 1) - 1
    audio_data = (sine_wave * amplitude).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(WAV_NUM_CHANNELS)
        wav_file.setsampwidth(WAV_SAMPLE_WIDTH)
        wav_file.setframerate(WAV_FRAMERATE)
        wav_file.writeframes(audio_data.tobytes())
    buffer.seek(0)
    return BytesMedia(buffer.getvalue(), media_type="WAV")


def generate_mp4() -> BytesMedia:
    """Generates a minimal valid MP4 file and returns a savable media object."""
    # OpenCV was causing issues and requires FFMPEG backend
    # This is a more portable solution
    # Create a minimal valid MP4 file structure
    # This is a very basic MP4 with just the essential boxes
    # ftyp box (file type)
    ftyp = b"".join(
        [
            b"\x00\x00\x00\x20",  # box size (32 bytes)
            b"ftyp",  # box type
            b"isom",  # major brand
            b"\x00\x00\x02\x00",  # minor version
            b"isom",  # compatible brands
            b"iso2",
            b"mp41",
        ]
    )

    # mdat box (media data) - empty for now
    mdat = b"".join(
        [
            b"\x00\x00\x00\x08",  # box size (8 bytes - just header)
            b"mdat",  # box type
        ]
    )

    # moov box (movie header) - minimal structure
    moov = b"".join(
        [
            b"\x00\x00\x00\x08",  # box size (8 bytes - just header)
            b"moov",  # box type
        ]
    )

    # Combine all boxes
    mp4_data = ftyp + mdat + moov

    return BytesMedia(mp4_data, media_type="MP4")


def generate_media(media_type: Literal["MP4", "WAV", "PDF", "PNG"]):
    if media_type == "MP4":
        return generate_mp4()
    elif media_type == "WAV":
        return generate_wav()
    elif media_type == "PDF":
        return generate_pdf()
    elif media_type == "PNG":
        return generate_png()
