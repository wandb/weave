import weave
from weave.show import show_url

weave.use_fixed_server_port()
obj = [
    1,
    2,
    3,
]  # weave.legacy.panels.Board({}, [weave.legacy.panels.BoardPanel(weave.legacy.panels.Table([1, 2, 3]))])
blank = weave.save(obj)

print(show_url(obj))
