import pyarrow as pa

from weave_query import weave_types as types
from weave_query.arrow.list_ import ArrowWeaveList
from weave_query.ops_arrow.boolean import boolean_all, boolean_any


class TestBooleanAllOp:
    def test_all_true(self):
        values = [True, True, True]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_all.eager_call(awl)
        assert result == True

    def test_all_false(self):
        values = [False, False, False]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_all.eager_call(awl)
        assert result == False

    def test_mixed(self):
        values = [True, False, True]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_all.eager_call(awl)
        assert result == False

    def test_empty(self):
        values = []
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_all.eager_call(awl)
        assert result == True

    def test_none(self):
        values = [None, None, None]
        awl = ArrowWeaveList(pa.array(values, type=pa.bool_()), types.Boolean())
        result = boolean_all.eager_call(awl)
        assert result == True

    def test_none_and_false(self):
        values = [None, False, None]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_all.eager_call(awl)
        assert result == False

    def test_none_and_true(self):
        values = [None, True, None]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_all.eager_call(awl)
        assert result == True


class TestBooleanAnyOp:
    def test_any_true(self):
        values = [True, False, True]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_any.eager_call(awl)
        assert result == True

    def test_any_false(self):
        values = [False, False, False]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_any.eager_call(awl)
        assert result == False

    def test_none(self):
        values = [None, None, None]
        awl = ArrowWeaveList(pa.array(values, type=pa.bool_()), types.Boolean())
        result = boolean_any.eager_call(awl)
        assert result == False

    def test_none_and_true(self):
        values = [None, True, None]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_any.eager_call(awl)
        assert result == True

    def test_none_and_false(self):
        values = [None, False, None]
        awl = ArrowWeaveList(pa.array(values), types.Boolean())
        result = boolean_any.eager_call(awl)
        assert result == False
