import weave
from weave import Model


class YourModel(Model):
    attribute1: str
    attribute2: int

    @weave.op()
    def predict(self, input_data: str) -> dict:
        # Model logic goes here
        prediction = self.attribute1 + " " + input_data
        return {"pred": prediction}


import weave

weave.init("intro-example")

model = YourModel(attribute1="hello", attribute2=5)
model.predict("world")

import weave

weave.init("intro-example")

model = YourModel(attribute1="howdy", attribute2=10)
model.predict("world")


with weave.attributes({"env": "production"}):
    model.predict("world")
