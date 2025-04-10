from weave_query.ops_primitives.boolean import boolean_all, boolean_any


class TestBooleanAllOp:
    def test_all_true(self):
        values = [True, True, True]
        result = boolean_all.eager_call(values)
        assert result == True

    def test_all_false(self):
        values = [False, False, False]
        result = boolean_all.eager_call(values)
        assert result == False

    def test_mixed(self):
        values = [True, False, True]
        result = boolean_all.eager_call(values)
        assert result == False

    def test_none(self):
        values = [None, None, None]
        result = boolean_all.eager_call(values)
        assert result == True

    def test_none_and_false(self):
        values = [None, False, None]
        result = boolean_all.eager_call(values)
        assert result == False

    def test_none_and_true(self):
        values = [None, True, None]
        result = boolean_all.eager_call(values)
        assert result == True


class TestBooleanAnyOp:
    def test_any_true(self):
        values = [True, False, True]
        result = boolean_any.eager_call(values)
        assert result == True

    def test_any_false(self):
        values = [False, False, False]
        result = boolean_any.eager_call(values)
        assert result == False

    def test_none(self):
        values = [None, None, None]
        result = boolean_any.eager_call(values)
        assert result == False

    def test_none_and_true(self):
        values = [None, True, None]
        result = boolean_any.eager_call(values)
        assert result == True

    def test_none_and_false(self):
        values = [None, False, None]
        result = boolean_any.eager_call(values)
        assert result == False
