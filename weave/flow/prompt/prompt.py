from collections import defaultdict
import inspect
import os
import string
import textwrap
from typing import Literal, Optional, Dict, Any

Role = Literal["system", "user", "assistant"]

PROMPTS = defaultdict(list)

class prompt(str):
    name: str
    role: Role = "system"
    defaults: Optional[Dict[str, Any]] = None
    
    def __new__(
        cls,
        fstring: str,
        name: Optional[str] = None,
        role: Role = "system",
        dedent: bool = False,
        defaults: Optional[Dict[str, Any]] = None,
    ):
        result = super().__new__(cls, textwrap.dedent(fstring) if dedent else fstring)
        result.name = name or result.default_name
        result.role = role
        result.defaults = defaults or {}

        # TODO: we might not want to do this automatically...
        # the risk would be exposing a local variable unintentionally
        frame = inspect.currentframe().f_back
        if frame:
            for k, v in frame.f_locals.items():
                if k in result.parameters() and k not in result.defaults:
                    result.defaults[k] = v
        # string = fstring.format(**result.params(caller_locals))
        PROMPTS[result.name].append(result)        
        return result
    
    @property
    def default_name(self):
        frame = inspect.currentframe().f_back        
        function_name = frame.f_code.co_name
        # TODO: do I need to call del frame?
        if "<" not in function_name:
            return function_name
        # TODO: in ipython this will be "interactiveshell"
        stack = inspect.stack()
        caller_frame = stack[1]
        return os.path.splitext(os.path.basename(caller_frame.filename))[0]
        
    def params(self, overrides: Optional[Dict[str, Any]] = None):
        params = self.defaults.copy()
        if overrides:
            params.update(overrides)
        return params
    
    def format(self, *args, **kwargs):
        # TODO: we need to return a special string object here that weave can track
        return str(self).format(*args, **self.params(kwargs))

    def parameters(self):
        formatter = string.Formatter()
        return [
            fname
            for _, fname, _, _ in formatter.parse(self)
            if fname is not None
        ]
    
    def message(self, *args, format: bool = True, **kwargs):
        # TODO: the str(...) case needs to return a special object that weave can track
        return {
            "role": self.role,
            "content": self.format(*args, **self.params(kwargs)) if format else str(self)
        }
    
    def add_image(self, image_url: str):
        # TODO: not convinced we would want this, seems rare for an image to be a
        # part of the prompt template but I could imagine a use case for it
        pass
    
    # helpers to get back to the beefier weave.Prompt object
    @property
    def object(self):
        prompt = weave.Prompt(name=self.name)
        for p in PROMPTS[self.name]:
            prompt.append(p.message(format=False))
        return prompt
