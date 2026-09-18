"""Portable ID mapping used by SDK and backend test fixtures."""

import base64


class TwoWayMapping:
    def __init__(self):
        self._ext_to_int_map = {}
        self._int_to_ext_map = {}

        # Useful for testing to ensure caching is working
        self.stats = {
            "ext_to_int": {
                "hits": 0,
                "misses": 0,
            },
            "int_to_ext": {
                "hits": 0,
                "misses": 0,
            },
        }

    def ext_to_int(self, key, default=None):
        if key not in self._ext_to_int_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._int_to_ext_map:
                raise ValueError(f"Default {default} already in use")
            self._ext_to_int_map[key] = default
            self._int_to_ext_map[default] = key
            self.stats["ext_to_int"]["misses"] += 1
        else:
            self.stats["ext_to_int"]["hits"] += 1
        return self._ext_to_int_map[key]

    def int_to_ext(self, key, default):
        if key not in self._int_to_ext_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._ext_to_int_map:
                raise ValueError(f"Default {default} already in use")
            self._int_to_ext_map[key] = default
            self._ext_to_int_map[default] = key
            self.stats["int_to_ext"]["misses"] += 1
        else:
            self.stats["int_to_ext"]["hits"] += 1
        return self._int_to_ext_map[key]


def b64(s: str) -> str:
    # Base64 encode the string
    return base64.b64encode(s.encode("ascii")).decode("ascii")


class DummyIdConverter:
    def __init__(self):
        self._project_map = TwoWayMapping()
        self._run_map = TwoWayMapping()
        self._user_map = TwoWayMapping()

    def ext_to_int_project_id(self, project_id: str) -> str:
        return self._project_map.ext_to_int(project_id, b64(project_id))

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        return self._project_map.int_to_ext(project_id, b64(project_id))

    def ext_to_int_run_id(self, run_id: str) -> str:
        return self._run_map.ext_to_int(run_id, b64(run_id) + ":" + run_id)

    def int_to_ext_run_id(self, run_id: str) -> str:
        exp = run_id.split(":")[1]
        return self._run_map.int_to_ext(run_id, exp)

    def ext_to_int_user_id(self, user_id: str) -> str:
        return self._user_map.ext_to_int(user_id, b64(user_id))

    def int_to_ext_user_id(self, user_id: str) -> str:
        return self._user_map.int_to_ext(user_id, b64(user_id))
