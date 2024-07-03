import textwrap

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
                import numpy as np
                import weave

                @weave.op()
                def softmax(x: np.ndarray) -> np.ndarray:
                    e_x = np.exp(x - np.max(x))
                    return e_x / e_x.sum()

                    
                ref = weave.publish(softmax)
                """
            ),
            textwrap.dedent(
                """
                import numpy as np
                import weave

                @weave.op()
                def softmax(x: np.ndarray) -> np.ndarray:
                    ... # Code-capture unavailable for this op
                """
            ),
        ),
        # With default values
        (
            textwrap.dedent(
                """
                """
            ),
            textwrap.dedent(
                """
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
