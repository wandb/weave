from weave_query import box
from weave_query.ops_primitives.number import is_integer


class TestIsIntegralOp:
    def test_integer(self):
        number = 1
        result = is_integer.eager_call(number)
        assert result == True

        number = -1
        result = is_integer.eager_call(number)
        assert result == True

        number = 0
        result = is_integer.eager_call(number)
        assert result == True

    def test_float(self):
        number = 1.0
        result = is_integer.eager_call(number)
        assert result == True

        number = -1.0
        result = is_integer.eager_call(number)
        assert result == True

        number = 0.0
        result = is_integer.eager_call(number)
        assert result == True

        number = 1.5
        result = is_integer.eager_call(number)
        assert result == False

        number = -1.5
        result = is_integer.eager_call(number)
        assert result == False

    def test_null(self):
        number = None
        result = is_integer.eager_call(number)
        assert result == False

    def test_with_boxed_values(self):
        number = box.box(1)
        result = is_integer.eager_call(number)
        assert result == True

        number = box.box(-1)
        result = is_integer.eager_call(number)
        assert result == True

        number = box.box(0)
        result = is_integer.eager_call(number)
        assert result == True

        number = box.box(1.0)
        result = is_integer.eager_call(number)
        assert result == True

        number = box.box(1.5)
        result = is_integer.eager_call(number)
        assert result == False

        number = box.box(-1.5)
        result = is_integer.eager_call(number)
        assert result == False

        number = box.box(None)
        result = is_integer.eager_call(number)
        assert result == False
