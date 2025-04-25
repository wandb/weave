from weave.flow.prompt.prompt import MessagesPrompt, StringPrompt


def test_stringprompt_format():
    prompt = StringPrompt("You are a pirate. Tell us your thoughts on {topic}.")
    assert (
        prompt.format(topic="airplanes")
        == "You are a pirate. Tell us your thoughts on airplanes."
    )


def test_messagesprompt_format():
    prompt = MessagesPrompt(
        [
            {"role": "system", "content": "You are a pirate."},
            {"role": "user", "content": "Tell us your thoughts on {topic}."},
        ]
    )
    assert prompt.format(topic="airplanes") == [
        {"role": "system", "content": "You are a pirate."},
        {"role": "user", "content": "Tell us your thoughts on airplanes."},
    ]
