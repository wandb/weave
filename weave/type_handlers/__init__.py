from weave.type_handlers.Audio import audio
from weave.type_handlers.Content import content
from weave.type_handlers.DateTime import datetime
from weave.type_handlers.File import file
from weave.type_handlers.Image import image
from weave.type_handlers.Markdown import markdown
from weave.type_handlers.Video import video
from weave.type_handlers.Video.lazy_import import install_hook

file.register()
content.register()
image.register()
audio.register()
datetime.register()
markdown.register()

# Install the lazy import hook for MoviePy instead of registering immediately
install_hook()
