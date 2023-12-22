import weave

def test_weaveflow_op(user_by_api_key_in_env):
    from weave import weaveflow
    with weave.wandb_client("weaveflow_example"):
        @weave.op()
        def custom_adder(a: int, b: int) -> int:
            return a + b

        res = custom_adder(1, 2)
        print("Output", res)

