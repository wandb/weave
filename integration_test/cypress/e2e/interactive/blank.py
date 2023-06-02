import weave

weave.use_fixed_server_port()
blank = weave.save(weave.panels.Board({}, []))

print(weave.show_url(blank))
