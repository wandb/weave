from weave.flow.prompt.prompt import MessagesPrompt, StringPrompt


def test_stringprompt_format():
    class MyPrompt(StringPrompt):
        def format(self, **kwargs) -> str:
            return "Imagine a lot of complicated logic build this string."

    prompt = MyPrompt()
    assert prompt.format() == "Imagine a lot of complicated logic build this string."


def test_messagesprompt_format():
    class MyPrompt(MessagesPrompt):
        def format(self, **kwargs) -> list:
            return [
                {"role": "user", "content": "What's 23 * 42"},
            ]

    prompt = MyPrompt()
    assert prompt.format() == [
        {"role": "user", "content": "What's 23 * 42"},
    ]
