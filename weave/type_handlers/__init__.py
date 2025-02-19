from weave.type_handlers.Audio import audio
from weave.type_handlers.DateTime import datetime
from weave.type_handlers.Image import image

image.register()
audio.register()
datetime.register()
