import weave

from weave_query.weave_query.show import show_url

weave.use_fixed_server_port()
obj = [
    1,
    2,
    3,
]  # weave.legacy.weave.panels.Board({}, [weave.legacy.weave.panels.BoardPanel(weave.legacy.weave.panels.Table([1, 2, 3]))])
blank = weave.save(obj)

print(show_url(obj))
