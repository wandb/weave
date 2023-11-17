import weave

weave.use_fixed_server_port()
obj = [
    1,
    2,
    3,
]  # weave.panels.Board({}, [weave.panels.BoardPanel(weave.panels.Table([1, 2, 3]))])
blank = weave.save(obj)

print(weave.show_url(obj))
