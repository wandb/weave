from weave.type_handlers.Audio import audio
from weave.type_handlers.DateTime import datetime
from weave.type_handlers.File import file
from weave.type_handlers.Image import image
from weave.type_handlers.Markdown import markdown
from weave.type_handlers.Video import video

file.register()
image.register()
audio.register()
datetime.register()
markdown.register()
video.register()
