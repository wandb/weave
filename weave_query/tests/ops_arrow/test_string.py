import pytest
import pyarrow as pa
from weave_query.arrow.list_ import ArrowWeaveList
from weave_query import weave_types as types
from weave_query.ops_arrow.string import split

class TestSplitOp:

    def test_basic(self):
        arrow_data = [
            "a,b,c", 
            "a,,b,c", 
            "abc",
            "",
            None,
        ]
        pattern = ","
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = split.eager_call(awl, pattern)
        
        expected = [["a", "b", "c"], ["a", "", "b", "c"], ["abc"], [""], None]
        assert result.to_pylist_notags() == expected

    def test_split_dictionary_array(self):
        arrow_data = [
            "a,b,c", 
            "a,,b,c", 
            "abc",
            "def",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([5, 4, 5, 0, 2, 1]),
            dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        pattern = ","
        result = split.eager_call(awl, pattern)
                
        expected = [
            None,
            [""],
            None,
            ["a", "b", "c"],
            ["abc"],
            ["a", "", "b", "c"],
        ]
        assert result._arrow_data.to_pylist() == expected
