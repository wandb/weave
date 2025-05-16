from .audio import Audio

AUDIO_ALIASES = [
    "weave.type_handlers.Audio.audio.Audio",
    "weave.trace.type_wrappers.audio.Audio",
    "weave.trace.type_wrappers.Audio",
    "weave.Audio",
]

# Special object informing doc generation tooling which symbols
# to document & to associate with this module.
__docspec__ = [Audio, AUDIO_ALIASES]
