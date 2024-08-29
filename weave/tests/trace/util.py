import datetime
import re


class RegexStringMatcher(str):
    def __init__(self, pattern):
        self.pattern = pattern

    def __eq__(self, other_string):
        if not isinstance(other_string, str):
            return NotImplemented
        return bool(re.match(self.pattern, other_string))


class DatetimeMatcher:
    def __eq__(self, other):
        return isinstance(other, datetime.datetime)
