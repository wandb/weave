import weave
from weave_query.weave_query.show import show_url

weave.use_fixed_server_port()
obj = [
    1,
    2,
    3,
]  # weave_query.weave_query.panels.Board({}, [weave_query.weave_query.panels.BoardPanel(weave_query.weave_query.panels.Table([1, 2, 3]))])
blank = weave.save(obj)

print(show_url(obj))
