import weave

client = weave.init("long_running_job")


@weave.op
def add_one(x: int) -> int:
    return x + 1


with client.live_status(sec=1):
    for i in range(100):
        add_one(i)
    print("done")
