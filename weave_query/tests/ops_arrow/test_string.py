import pytest
import pyarrow as pa
from weave_query.arrow.list_ import ArrowWeaveList
from weave_query import weave_types as types
from weave_query.ops_arrow.string import (
    isalpha,
    split,
    isnumeric,
    isalnum,
    lower,
    upper,
    slice,
    replace,
    strip,
    lstrip,
    rstrip,
    arrowweavelist_len,
)


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
