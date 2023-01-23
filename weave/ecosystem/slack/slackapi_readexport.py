import json
import pathlib

import weave


def dirsize(path) -> int:
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())


@weave.type()
class SlackReadExportApi:
    data_dir: weave.Dir

    def channel_names(self):
        return (n.name for n in pathlib.Path(self.data_dir.path).glob("*"))

    def channel_path(self, channel_name):
        return pathlib.Path(self.data_dir.path) / channel_name

    def channel_export_size(self, channel_name: str):
        return dirsize(self.channel_path(channel_name))

    # Returns a dict in the slack export format. TODO
    def channel_messages(self, channel_name: str):
        files = self.channel_path(channel_name).glob("*.json")
        channel_messages = []
        for f in sorted(files):
            channel_messages += json.load(open(f))
        return channel_messages
