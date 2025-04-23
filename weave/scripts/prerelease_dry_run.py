# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "weave @ git+https://github.com/wandb/weave.git@master",
# ]
# ///

# Run this script with `uv run prerelease_dry_run.py`

import datetime

import weave

# This uniq id ensures that the op is not cached
uniq_id = datetime.datetime.now().timestamp()


@weave.op
def func(a: int) -> float:
    return a + uniq_id


def main() -> None:
    client = weave.init("test-project")
    res = func(42)

    client._flush()
    calls = func.calls()

    assert len(calls) == 1
    assert calls[0].output == res
    assert calls[0].inputs == {"a": 42}


if __name__ == "__main__":
    main()
    print("Dry run passed")
