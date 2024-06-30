import textwrap


def test_publish_works_for_code_with_no_source_file(client):
    code = textwrap.dedent(
        """
        import weave
        
        @weave.op()
        def add(a: int, b: int) -> int:
            return a + b

        ref = weave.publish(add)
        """
    )
    exec(code)
