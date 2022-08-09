import dataclasses
import json
import pathlib


def dirsize(path) -> int:
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())


@dataclasses.dataclass
class SlackReadExportApi:
    data_dir: pathlib.Path  # TODO: change to weave.Dir

    def channel_names(self):
        return (n.name for n in self.data_dir.glob("*"))

    def channel_path(self, channel_name):
        return self.data_dir / channel_name

    def channel_export_size(self, channel_name: str):
        return dirsize(self.channel_path(channel_name))

    # Returns a dict in the slack export format. TODO
    def channel_messages(self, channel_name: str):
        files = self.channel_path(channel_name).glob("*.json")
        channel_messages = []
        for f in sorted(files):
            channel_messages += json.load(open(f))
        return channel_messages
