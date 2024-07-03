import textwrap


def test_publish_works_for_code_with_no_source_file(client):
    code = textwrap.dedent(
        """
        import weave
        

        @weave.op()
        def add(a: int, b: float) -> str:
            return str(a + b)

        ref = weave.publish(add)
        """
    )
    captured = {}
    exec(code, globals(), captured)

    ref = captured["ref"]
    op = ref.get()
    captured_code = op.art.path_contents["obj.py"].decode()

    expected_code_capture = textwrap.dedent(
        """
        import weave

        
        @weave.op()
        def add(a: int, b: float) -> str:
            ... # Code-capture unavailable for this op
        """
    )[1:]

    assert captured_code == expected_code_capture
