The guiding principle of this approach is to minimize the amount of code a user needs to modify.
`prompt` is a subclass of `str`, so we can use it just like a string. Parameters can be added and
the native `.format` method is used to resolve them.  I also added `dedent=True` for convenience.
In the example below `CONST` will not be captured as a variable, but `name` will.

```python
from weave import prompt as pt

name = "bob"
CONST = "helpful"
SYSTEM_PROMPT = f"""\
    You are a {CONST} assistant named {{name}}\
"""
system = pt(SYSTEM_PROMPT, dedent=True)
print(system)
print(system.format(name="cvp"))
# this is sketchy but I captured a default value of "bob" for name
print(system.format())
```
```shell
> You are a helpful assistant named {name}
> You are a helpful assistant named cvp
> You are a helpful assistant named bob
```

My prompts default to the system role, you can override it.  My thinking is the system prompt is the role
most used to guide the LLM but I could see a case for making the default user.  A part of me wonders if role is
even something we need to capture for the versioning of prompts.  It's helpful for templating but we might want
to separate those concerns, see Thought #3 below.

```python
user = pt("Think step by step", role="user")
```

We use a prompts `name` to chain together multiple prompts, the default name is the calling file name (example.py
in my case).  My argument for not requiring name would be to make it as easy as possible to start tracking prompts in
existing code.  This default naming magic could lead to confusion.  Another option could be the name of the function
we're in if it's not "<module>".  The most robust option would likely be to make users create an instance, i.e.

```python
pt = weave.Prompt("openui")
system_prompt = pt(SYSTEM_PROMPT)
```

I'm currently exposing Jamie's `weave.Prompt` object via the `object` property.  I'm not sure this is the right name
maybe `.parent` or `.chain`?

```python
eval_prompt = pt("What is the meaning of life?", name="eval")
print(user.object)
print(eval_prompt.object)
```
```shell
Prompt(name='example'):
  [{'role': 'system', 'content': 'You are a helpful assistant named {name}'},
   {'role': 'user', 'content': 'Think step by step'}]
Prompt(name='eval'):
  [{'role': 'system', 'content': 'What is the meaning of life?'}]
```

When a prompt str is passed into an op, we should automatically annotate the op with the digest of the `Prompt` object.
I also added a convenience method for openai SDK's that returns the message payload which would need to be tracked
as well.  Currently `.format` is returning a regular string, we would need to change these to be a string that refers to
the `weave.Prompt` object for this all to work and it feels a bit over my pay grade :wink:.

```python
response = client.chat.completions.create(
  model="gpt-4o-mini",
  messages=[
     {"role": "system", "content": system.format()}
  ]
)
response = client.chat.completions.create(
  model="gpt-4o-mini",
  messages=[
     system.message(name="cvp")
  ]
)
```

For quick integration someone could simply wrap the different templated parts of their prompt inline. 

```python
pt = weave.Prompt("mega")
user_input = "Un-templated user input"
response = client.chat.completions.create(
  model="gpt-4o-mini",
  messages=[
     {"role": "system", "content": pt(SYSTEM_PROMPT)},
     {"role": "user", "content": user_input},
     pt("The answer to your question is ", role="assistant").message()
  ]
)
```

In the above example we wouldn't capture the fact that user input comes before our "assistant" hint, but we could make our
playground UI's handle the case.  Alternatively a user could do something like `pt("{}", role="user").message(user_input)`
but that provides no tracing information and only helps with the template problem, see Thought #3 below.

**Thoughts**

1. We should automatically publish a prompt object the first time it's used in an op, but this might be tricky?
2. With this string centered approach, we should think about getting just the string for a sub-message of
   the bigger prompt using weave.ref()
3. I imagine having a constant image in a prompt template is pretty rare.  I could imagine wanting to setup an image as a
   variable in a prompt template.  These seem like separate concerns to me though:
   1. Keeping track of the engineering of your prompts
   2. Providing a prompt template for a playground / UI
