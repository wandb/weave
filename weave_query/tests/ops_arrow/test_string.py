import pyarrow as pa
import pytest

from weave_query import weave_types as types
from weave_query.arrow.list_ import ArrowWeaveList
from weave_query.ops_arrow.string import (
    __eq__,
    __ne__,
    _concatenate_strings,
    append,
    arrowweavelist_len,
    endswith,
    isalnum,
    isalpha,
    isnumeric,
    join_to_str,
    lower,
    lstrip,
    partition,
    prepend,
    replace,
    rstrip,
    slice,
    split,
    startswith,
    string_add,
    strip,
    to_number,
    upper,
)


class TestEqualOp:
    def test_other_is_string(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = __eq__.eager_call(awl, "hello")
        expected = [True, False, False]
        assert result.to_pylist_notags() == expected

    def test_other_is_awl(self):
        arrow_data = ["hello", "world", None, None, "foo"]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        other = ArrowWeaveList(
            pa.array(["hello", "world", None, "foo", None]), types.String()
        )
        result = __eq__.eager_call(awl, other)
        expected = [True, True, True, False, False]
        assert result.to_pylist_notags() == expected

    def test_other_is_awl_of_different_length_raises_exception(self):
        arrow_data = ["hello", "world", "foo", "bar"]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        other = ArrowWeaveList(pa.array(["hello", "world"]), types.String())
        with pytest.raises(pa.lib.ArrowInvalid):
            __eq__.eager_call(awl, other)

    def test_dictionary_array(self):
        arrow_data = ["hello", "world", None]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = __eq__.eager_call(awl, "hello")
        expected = [False, False, True, False]
        assert result._arrow_data.to_pylist() == expected


class TestNotEqualOp:
    def test_other_is_string(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = __ne__.eager_call(awl, "hello")
        expected = [False, True, True]
        assert result.to_pylist_notags() == expected

    def test_other_is_awl(self):
        arrow_data = ["hello", "earth", None, None, "foo"]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        other = ArrowWeaveList(
            pa.array(["hello", "world", None, "foo", None]), types.String()
        )
        result = __ne__.eager_call(awl, other)
        expected = [False, True, False, True, True]
        assert result.to_pylist_notags() == expected

    def test_other_is_awl_of_different_length_raises_exception(self):
        arrow_data = ["hello", "world", "foo", "bar"]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        other = ArrowWeaveList(pa.array(["hello", "world"]), types.String())
        with pytest.raises(pa.lib.ArrowInvalid):
            __ne__.eager_call(awl, other)

    def test_dictionary_array(self):
        arrow_data = ["hello", "world", None]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = __ne__.eager_call(awl, "hello")
        expected = [True, True, False, True]
        assert result._arrow_data.to_pylist() == expected


class TestLenOp:
    def test_basic(self):
        arrow_data = [
            "abc",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = arrowweavelist_len.eager_call(awl)
        expected = [3, 0, None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "abc",
            "def",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([3, 2, 0, 3]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = arrowweavelist_len.eager_call(awl)
        expected = [None, 0, 3, None]
        assert result._arrow_data.to_pylist() == expected


class TestPartitionOp:
    def _expected_partition(self, arrow_data, sep):
        if sep is None:
            return [None] * len(arrow_data)
        return [
            list(item.partition(sep)) if item is not None else None
            for item in arrow_data
        ]

    def test_basic(self):
        arrow_data = [
            "hello world",
            "hello there",
            "goodbye",
            None,
        ]
        partition_patterns = [" ", "e", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        for pattern in partition_patterns:
            result = partition.eager_call(awl, pattern)
            expected = self._expected_partition(arrow_data, pattern)
            assert result.to_pylist_notags() == expected

    def test_awl_sep(self):
        sep_data = [" ", "e", "foo", None]
        arrow_data = ["hello world", "hello there", None, "foo"]
        sep = ArrowWeaveList(pa.array(sep_data), types.optional(types.String()))
        awl = ArrowWeaveList(pa.array(arrow_data), types.optional(types.String()))
        result = partition.eager_call(awl, sep)
        expected = [
            list(item.partition(s)) if item is not None and s is not None else None
            for item, s in zip(arrow_data, sep_data)
        ]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "hello world",
            "hello there",
            "goodbye",
        ]
        sep = " "
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.optional(types.String()))
        result = partition.eager_call(awl, sep)
        expected = [
            list("goodbye".partition(" ")),
            list("hello there".partition(" ")),
            list("hello world".partition(" ")),
            list("goodbye".partition(" ")),
        ]
        assert result.to_pylist_notags() == expected


class TestConcatenateStrings:
    def test_concatenate_with_string(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = _concatenate_strings(awl, " test")
        expected = ["hello test", "world test", None]
        assert result.to_pylist_notags() == expected

    def test_concatenate_with_awl(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        other = ArrowWeaveList(pa.array([" there", " earth", " moon"]), types.String())
        result = _concatenate_strings(awl, other)
        expected = ["hello there", "world earth", None]
        assert result.to_pylist_notags() == expected

    def test_concatenate_with_awl_different_lengths_raises_exception(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        other = ArrowWeaveList(
            pa.array([" there", " earth", " moon", "foo"]), types.String()
        )
        with pytest.raises(pa.lib.ArrowInvalid):
            # right is longer than left
            _concatenate_strings(awl, other)

        with pytest.raises(pa.lib.ArrowInvalid):
            # left is longer than right
            _concatenate_strings(other, awl)

    def test_concatenate_with_none(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = _concatenate_strings(awl, None)
        expected = [None, None, None]
        assert result.to_pylist_notags() == expected

    # @pytest.mark.xfail(reason="Dictionary array concatenation is not supported yet")
    def test_dictionary_array(self):
        arrow_data = ["hello", "world", None]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = _concatenate_strings(awl, " test")
        expected = [None, "world test", "hello test", None]
        assert result.to_pylist_notags() == expected


class TestStringAddOp:
    def test_basic(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = string_add.eager_call(awl, " test")
        expected = ["hello test", "world test", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = ["hello", "world", None]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = string_add.eager_call(awl, " test")
        expected = [None, "world test", "hello test", None]
        assert result._arrow_data.to_pylist() == expected


class TestAppendOp:
    def test_basic(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = append.eager_call(awl, " test")
        expected = ["hello test", "world test", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = ["hello", "world", None]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = append.eager_call(awl, " test")
        expected = [None, "world test", "hello test", None]
        assert result._arrow_data.to_pylist() == expected


class TestPrependOp:
    def test_basic(self):
        arrow_data = ["hello", "world", None]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = prepend.eager_call(awl, "test ")
        expected = ["test hello", "test world", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = ["hello", "world", None]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = prepend.eager_call(awl, "test ")
        expected = [None, "test world", "test hello", None]
        assert result._arrow_data.to_pylist() == expected


class TestStartsWithOp:
    def test_basic(self):
        arrow_data = [
            "hello world",
            "hello there",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = startswith.eager_call(awl, "hello")
        expected = [True, True, False, None]
        assert result.to_pylist_notags() == expected

    def test_awl_prefix(self):
        arrow_data = ["hello world", "hello there", "goodbye", "", None, "bar"]
        prefix = ArrowWeaveList(
            pa.array(["hello", "goodbye", "goodbye", "", "foo", None]), types.String()
        )
        awl = ArrowWeaveList(pa.array(arrow_data), types.optional(types.String()))
        result = startswith.eager_call(awl, prefix)
        expected = [True, False, True, True, None, None]
        assert result.to_pylist_notags() == expected

    def test_vectorized_data_arrow_data_ignored(self):
        arrow_data = ["hello world", "hello there", "goodbye", "", None, "bar"]
        prefix = ArrowWeaveList(
            pa.array(["hello", "goodbye", "goodbye", "", "foo", None]), types.String()
        )
        awl = ArrowWeaveList(pa.array(arrow_data), types.optional(types.String()))
        result = startswith.eager_call(awl, prefix)
        expected = [True, False, True, True, None, None]
        assert result.to_pylist_notags() == expected

    def test_vectorized_data_suffix_ignored(self):
        arrow_data = ["hello world", "hello there", "goodbye", "", None, "bar"]
        prefix = ArrowWeaveList(
            pa.array(["hello", "goodbye", "goodbye", "", "foo", None]), types.String()
        )
        awl = ArrowWeaveList(pa.array(arrow_data), types.optional(types.String()))
        result = startswith.eager_call(awl, prefix)
        expected = [True, False, True, True, None, None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "hello world",
            "hello there",
            "goodbye",
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = startswith.eager_call(awl, "hello")
        expected = [False, True, True, False]
        assert result._arrow_data.to_pylist() == expected


class TestEndsWithOp:
    def test_basic(self):
        arrow_data = [
            "hello world",
            "hello there",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = endswith.eager_call(awl, "world")
        expected = [True, False, False, None]
        assert result.to_pylist_notags() == expected

    def test_awl_suffix(self):
        arrow_data = ["hello world", "hello there", "goodbye", "", None, "bar"]
        suffix = ArrowWeaveList(
            pa.array(["world", "there", "hello", "", "foo", None]), types.String()
        )
        awl = ArrowWeaveList(pa.array(arrow_data), types.optional(types.String()))
        result = endswith.eager_call(awl, suffix)
        expected = [True, True, False, True, None, None]
        assert result.to_pylist_notags() == expected

    def test_vectorized_data_arrow_data_ignored(self):
        arrow_data = ["hello world", "hello there", "goodbye", "", None, "bar"]
        suffix = ArrowWeaveList(
            pa.array(["world", "there", "hello", "", "foo", None]), types.String()
        )
        awl = ArrowWeaveList(pa.array(arrow_data), types.optional(types.String()))
        result = endswith.eager_call(awl, suffix)
        expected = [True, True, False, True, None, None]
        assert result.to_pylist_notags() == expected

    def test_vectorized_data_suffix_ignored(self):
        arrow_data = ["hello world", "hello there", "goodbye", "", None, "bar"]
        suffix = ArrowWeaveList(
            pa.array(["world", "there", "hello", "", "foo", None]), types.String()
        )
        awl = ArrowWeaveList(pa.array(arrow_data), types.optional(types.String()))
        result = endswith.eager_call(awl, suffix)
        expected = [True, True, False, True, None, None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "hello world",
            "hello there",
            "goodbye",
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = endswith.eager_call(awl, "world")
        expected = [False, False, True, False]
        assert result._arrow_data.to_pylist() == expected


class TestIsAlphaOp:
    def test_basic(self):
        arrow_data = [
            "abc",
            "123",
            "abc123",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = isalpha.eager_call(awl)
        expected = [True, False, False, False, None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "abc",
            "def",
            "123",
            "abc123",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([5, 4, 0, 5, 2, 3]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = isalpha.eager_call(awl)
        expected = [None, False, True, None, False, False]
        assert result._arrow_data.to_pylist() == expected


class TestIsNumericOp:
    def test_basic(self):
        arrow_data = [
            "123",
            "123.45",
            "abc",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = isnumeric.eager_call(awl)
        expected = [True, False, False, False, None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "123",
            "456",
            "123.45",
            "abc",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([5, 4, 0, 5, 2, 3]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = isnumeric.eager_call(awl)
        expected = [None, False, True, None, False, False]
        assert result._arrow_data.to_pylist() == expected


class TestIsAlphaNumericOp:
    def test_basic(self):
        arrow_data = [
            "abc",
            "123",
            "123.45",
            "abc123",
            "",
            "abc-123",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = isalnum.eager_call(awl)
        expected = [True, True, False, True, False, False, None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "abc",
            "def",
            "123",
            "123.45",
            "abc123",
            "",
            "abc-123",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([7, 6, 0, 7, 2, 3, 5, 4]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = isalnum.eager_call(awl)
        expected = [None, False, True, None, True, False, False, True]
        assert result._arrow_data.to_pylist() == expected


class TestLowerOp:
    def test_basic(self):
        arrow_data = [
            "ABC",
            "123",
            "ABC123",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = lower.eager_call(awl)
        expected = ["abc", "123", "abc123", "", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "ABC",
            "DEF",
            "123",
            "ABC123",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([5, 4, 0, 5, 2, 3]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = lower.eager_call(awl)
        expected = [None, "", "abc", None, "123", "abc123"]
        assert result._arrow_data.to_pylist() == expected


class TestUpperOp:
    def test_basic(self):
        arrow_data = [
            "abc",
            "123",
            "abc123",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = upper.eager_call(awl)
        expected = ["ABC", "123", "ABC123", "", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "abc",
            "def",
            "123",
            "abc123",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([5, 4, 0, 5, 2, 3]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = upper.eager_call(awl)
        expected = [None, "", "ABC", None, "123", "ABC123"]
        assert result._arrow_data.to_pylist() == expected


class TestSliceOp:
    def test_basic(self):
        arrow_data = [
            "abcdef",
            "123456",
            "a",
            "ab",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = slice.eager_call(awl, 1, 4)
        expected = ["bcd", "234", "", "b", "", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "abcdef",
            "123456",
            "a",
            "ab",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([5, 4, 0, 5, 2, 3]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = slice.eager_call(awl, 1, 4)
        expected = [None, "", "bcd", None, "", "b"]
        assert result._arrow_data.to_pylist() == expected


class TestReplaceOp:
    def test_basic(self):
        arrow_data = [
            "hello world",
            "hello there",
            "goodbye",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = replace.eager_call(awl, "hello", "hi")
        expected = ["hi world", "hi there", "goodbye", "", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "hello world",
            "hello there",
            "goodbye",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([4, 3, 0, 4, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = replace.eager_call(awl, "hello", "hi")
        expected = [None, "", "hi world", None, "goodbye"]
        assert result._arrow_data.to_pylist() == expected


class TestStripOp:
    def test_basic(self):
        arrow_data = [
            "  abc  ",
            "\t\nxyz\r\n",
            "def",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = strip.eager_call(awl)
        expected = ["abc", "xyz", "def", "", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "  abc  ",
            "  def  ",
            "\t\nxyz\r\n",
            "ghi",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([5, 4, 0, 5, 2, 3]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = strip.eager_call(awl)
        expected = [None, "", "abc", None, "xyz", "ghi"]
        assert result._arrow_data.to_pylist() == expected


class TestLStripOp:
    def test_basic(self):
        arrow_data = [
            "  abc  ",
            "\t\nxyz\r\n",
            "def  ",
            "ghi",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = lstrip.eager_call(awl)
        expected = ["abc  ", "xyz\r\n", "def  ", "ghi", "", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "  abc  ",
            "  def  ",
            "\t\nxyz\r\n",
            "ghi  ",
            "jkl",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([6, 5, 0, 6, 2, 3, 4]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = lstrip.eager_call(awl)
        expected = [None, "", "abc  ", None, "xyz\r\n", "ghi  ", "jkl"]
        assert result._arrow_data.to_pylist() == expected


class TestRStripOp:
    def test_basic(self):
        arrow_data = [
            "  abc  ",
            "\t\nxyz\r\n",
            "  def",
            "ghi",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = rstrip.eager_call(awl)
        expected = ["  abc", "\t\nxyz", "  def", "ghi", "", None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "  abc  ",
            "  def  ",
            "\t\nxyz\r\n",
            "  ghi",
            "jkl",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([6, 5, 0, 6, 2, 3, 4]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = rstrip.eager_call(awl)
        expected = [None, "", "  abc", None, "\t\nxyz", "  ghi", "jkl"]
        assert result._arrow_data.to_pylist() == expected


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

    def test_vectorized_pattern(self):
        arrow_data = [
            "a,b,c",
            "a|b|c",
            "a^b^c",
            None,
        ]
        pattern = [",", "|", "^", "|"]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        pattern_awl = ArrowWeaveList(pa.array(pattern), types.String())
        result = split.eager_call(awl, pattern_awl)

        expected = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"], None]
        assert result.to_pylist_notags() == expected

    def test_vectorized_item_ignored(self):
        arrow_data = ["a,b,c", "a|b|c", "a^b^c", None, "foo"]
        pattern = [",", "|", "^", "|"]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        pattern_awl = ArrowWeaveList(pa.array(pattern), types.String())
        result = split.eager_call(awl, pattern_awl)

        expected = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"], None]
        assert result.to_pylist_notags() == expected

    def test_vectorized_pattern_ignored(self):
        arrow_data = ["a,b,c", "a|b|c", "a^b^c", None]
        pattern = [",", "|", "^", "|", "/"]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        pattern_awl = ArrowWeaveList(pa.array(pattern), types.String())
        result = split.eager_call(awl, pattern_awl)

        expected = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"], None]
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
            indices=pa.array([5, 4, 5, 0, 2, 1]), dictionary=pa.array(arrow_data)
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


class TestJoinToStrOp:
    def _expected_join(self, arrow_data, sep):
        if arrow_data is None:
            return ""
        arrow_data = [item if item is not None else "" for item in arrow_data]
        return sep.join(arrow_data)

    def test_basic(self):
        arrow_data = [
            ["a", "b", "c"],
            ["a", "", "b", "c"],
            ["abc"],
            [],
            [None],
            [None, None],
            ["a", None, "c"],
            ["1", "2", "3"],
            None,
        ]
        separators = [",", "|", " ", "||", "\n", "\t", ""]
        awl = ArrowWeaveList(pa.array(arrow_data), types.List(types.String()))

        for sep in separators:
            result = join_to_str.eager_call(awl, sep)
            expected = [self._expected_join(item, sep) for item in arrow_data]
            assert result.to_pylist_notags() == expected

    def test_sep_is_awl(self):
        arrow_data = [
            ["a", "b", "c"],
            ["a", "", "b", "c"],
            ["abc"],
        ]
        sep = ArrowWeaveList(pa.array([",", "|", " "]), types.String())
        awl = ArrowWeaveList(pa.array(arrow_data), types.List(types.String()))
        result = join_to_str.eager_call(awl, sep)

        expected = ["a,b,c", "a||b|c", "abc"]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            ["a", "b", "c"],
            ["x", "y", "z"],
            ["1", "2", "3"],
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([2, 1, 0, 2]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.List(types.String()))
        sep = ","
        result = join_to_str.eager_call(awl, sep)

        expected = ["1,2,3", "x,y,z", "a,b,c", "1,2,3"]
        assert result._arrow_data.to_pylist() == expected


class TestToNumberOp:
    def test_basic(self):
        arrow_data = [
            "123",
            "123.45",  # TODO: utf8_is_numeric returns false for this
            "abc",
            "",
            None,
        ]
        awl = ArrowWeaveList(pa.array(arrow_data), types.String())
        result = to_number.eager_call(awl)

        expected = [123.0, None, None, None, None]
        assert result.to_pylist_notags() == expected

    def test_dictionary_array(self):
        arrow_data = [
            "123",
            "456",
            "123.45",  # TODO: utf8_is_numeric returns false for this
            "abc",
            "",
            None,
        ]
        dict_array = pa.DictionaryArray.from_arrays(
            indices=pa.array([5, 4, 0, 5, 2, 3]), dictionary=pa.array(arrow_data)
        )
        awl = ArrowWeaveList(dict_array, types.String())
        result = to_number.eager_call(awl)

        expected = [None, None, 123.0, None, None, None]
        assert result._arrow_data.to_pylist() == expected
