from weave.type_handlers.Audio import audio
from weave.type_handlers.DateTime import datetime
from weave.type_handlers.Image import image
from weave.type_handlers.Markdown import markdown

image.register()
audio.register()
datetime.register()
markdown.register()
