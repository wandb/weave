import asyncio
import dataclasses

import weave


@dataclasses.dataclass(frozen=True)
class MyDataclass:
    a_string: str
    an_int: int
    a_list: list[int]


class MyModel(weave.Model):
    @weave.op()
    async def invoke(
        self,
        str_value: str,
        int_value: int,
        list_value: list[int],
    ) -> dict:
        my_dataclass = MyDataclass(
            a_string=str_value, an_int=int_value, a_list=list_value
        )

        print(f"model: str_value is a {type(str_value)}")
        print(f"model: int_value is a {type(int_value)}")
        print(f"model: list_value is a {type(list_value)}")
        print(f"model: an element in list_value is a {type(list_value[0])}")

        return {
            "my_dataclass": my_dataclass,
        }


class MyScorer(weave.Scorer):
    @weave.op()
    async def score(
        self, str_value: str, int_value: int, list_value: list[int], model_output: dict
    ) -> dict:
        my_dataclass = model_output["my_dataclass"]

        print(f"score: str_value is a {type(str_value)}")
        print(f"score: int_value is a {type(int_value)}")
        print(f"score: list_value is a {type(list_value)}")
        print(f"score: an element in list_value is a {type(list_value[0])}")
        print(f"score: my_dataclass is a {type(my_dataclass)}")

        return {
            "score_output": my_dataclass,
        }

    @weave.op()
    def summarize(self, score_rows: list[dict]) -> dict:
        print(f"summarize: score_rows is a {type(score_rows)}")
        print(f"summarize: an element in score_rows is a {type(score_rows[0])}")
        print(f"summarize: score_output is a {type(score_rows[0]['score_output'])}")

        assert isinstance(
            score_rows[0]["score_output"], MyDataclass
        ), "Dataclass not boxed str"

        return {
            "some_metric": 1.0,
        }


def test_evaluation_type_consistency(client):
    model = MyModel()
    scorer = MyScorer()
    ds = [
        {"str_value": "hello", "int_value": 2, "list_value": [1, 2, 3]},
    ]

    evaluation = weave.Evaluation(
        dataset=ds,
        scorers=[scorer],
        trials=1,
    )
    asyncio.run(evaluation.evaluate(model))
