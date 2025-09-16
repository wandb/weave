from weave.type_handlers import Video
from weave.type_handlers.Audio import audio
from weave.type_handlers.Content import content
from weave.type_handlers.DateTime import datetime
from weave.type_handlers.File import file
from weave.type_handlers.Image import image
from weave.type_handlers.Markdown import markdown

file.register()
content.register()
image.register()
audio.register()
datetime.register()
markdown.register()

Video.install_hook()
