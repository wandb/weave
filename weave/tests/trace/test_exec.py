import textwrap
import typing
from typing import Union

import numpy as np
import pytest


@pytest.mark.parametrize(
    "code, expected_captured_code",
    [
        # Basic
        (
            textwrap.dedent(
                """
                import weave
                

                @weave.op()
                def add(a: int, b: float) -> str:
                    return str(a + b)


                ref = weave.publish(add)
                """
            ),
            textwrap.dedent(
                """
                import weave

                
                @weave.op()
                def add(a: int, b: float) -> str:
                    ... # Code-capture unavailable for this op
                """
            ),
        ),
        # With import renaming
        (
            textwrap.dedent(
                """
                import weave
                import numpy as np

                @weave.op()
                def softmax(x: np.ndarray) -> np.ndarray:
                    e_x = np.exp(x - np.max(x))
                    return e_x / e_x.sum()

                    
                ref = weave.publish(softmax)
                """
            ),
            textwrap.dedent(
                """
                import weave
                import numpy as np

                @weave.op()
                def softmax(x: np.ndarray) -> np.ndarray:
                    ... # Code-capture unavailable for this op
                """
            ),
        ),
        # default values, complex types
        (
            textwrap.dedent(
                """
                import weave
                import numpy as np
                import typing

                @weave.op()
                def func(x: np.ndarray, y: int, greeting: str = "Hello friend!") -> dict[str, typing.Union[np.float64, str]]:
                    return {"mean": mean(x + y), "greeting": greeting}

                    
                ref = weave.publish(func)
                """
            ),
            textwrap.dedent(
                """
                import weave
                import numpy as np
                import typing

                @weave.op()
                def func(x: np.ndarray, y: int, greeting: str = "Hello friend!") -> dict[str, typing.Union[np.float64, str]]:
                    ... # Code-capture unavailable for this op
                """
            ),
        ),
    ],
)
def test_publish_works_for_code_with_no_source_file(
    client, code, expected_captured_code
):
    captured = {}
    exec(code, globals(), captured)

    ref = captured["ref"]
    op = ref.get()
    actual_captured_code = op.art.path_contents["obj.py"].decode()
    expected_captured_code = expected_captured_code[1:]  # ignore first newline

    assert actual_captured_code == expected_captured_code
