# type: ignore
# This is currently unused. Keeping it around for a little longer...

import dataclasses
import typing
import requests

from . import storage
from . import context
import time

STATUS_RUNNING = -1
STATUS_DONE_OK = 0
STATUS_DONE_ERROR = 1


class AutomationStatus(typing.TypedDict):
    status: int
    message: str


COMMANDS: dict[str, str] = {}
STATUS: dict[str, AutomationStatus] = {}


def add_command(automation_id, command):
    commands = COMMANDS.setdefault(automation_id, [])
    commands.append(command)


def commands_after(automation_id, after):
    return COMMANDS[automation_id][after:]


def set_status(automation_id, status: AutomationStatus):
    STATUS[automation_id] = status


def get_status(automation_id):
    return STATUS.get(automation_id, {"status": STATUS_RUNNING, "message": ""})


@dataclasses.dataclass
class AutomationHandle:
    id: str
    commands: list[str] = dataclasses.field(default_factory=list)

    @property
    def object_name(self) -> str:
        return "weave-automation-%s" % self.id

    def __post_init__(self):
        storage.save([], self.object_name)

    def send_raw_command(self, command: str):
        client = context.get_client()
        requests.post(
            "%s/__weave/automate/%s/add_command" % (client.url, self.id),
            json={"command": "run_js", "js": command},
        )

    def send_end_command(self):
        client = context.get_client()
        requests.post(
            "%s/__weave/automate/%s/add_command" % (client.url, self.id),
            json={"command": "end"},
        )

    def wait_for_status(self) -> AutomationStatus:
        client = context.get_client()
        while True:
            status: AutomationStatus = requests.get(
                "%s/__weave/automate/%s/status" % (client.url, self.id),
            ).json()
            if status["status"] == STATUS_RUNNING:
                time.sleep(1)
            else:
                return status

    def assert_ok(self):
        self.send_end_command()
        status = self.wait_for_status()
        if status["status"] == STATUS_DONE_ERROR:
            print("WeaveJS error.\n%s" % status["message"])
        assert status["status"] == STATUS_DONE_OK

    def open_config(self):
        self.send_raw_command(
            "const button = document.querySelector('.button[data-test=panel-config]'); button.click();"
        )

    def _focus_config_ee(self, num):
        self.send_raw_command(
            """
            document.querySelector('div[data-test=config-panel]')
              .querySelectorAll('div[data-test=expression-editor-container]')[%s]
              .querySelector('div[data-slate-editor=true]')
              .focus()
        """
            % num
        )

    def add_ee_text(self, num, text):
        self._focus_config_ee(num)
        self.send_raw_command(
            """
            const container = document.querySelector('div[data-test=config-panel]')
              .querySelectorAll('div[data-test=expression-editor-container]')[%s];
            const editorId = container.getAttribute('data-test-ee-id');
            const editorState = weaveExpressionEditors[editorId];
            const editor = editorState.editor;
            SlateLibs.Transforms.select(editor, SlateLibs.Editor.end(editor, []));
            editor.insertText('%s');
        """
            % (num, text)
        )
        self._submit_ee(num)

    def _submit_ee(self, num):
        self.send_raw_command(
            """
            document.querySelector('div[data-test=config-panel]')
              .querySelectorAll('div[data-test=expression-editor-container]')[%s]
              .querySelector('button').click()
        """
            % num
        )

    def set_slider(self, value):
        self.send_raw_command(
            """
            const slider = document.querySelector('div[data-test=config-panel]')
              .querySelector('input[type=range]');
            slider.value = %s;
            slider.dispatchEvent(new Event('input', {bubbles: true}));
        """
            % value
        )

    def submit_config(self):
        self.send_raw_command(
            """
            document.querySelector('div[data-test=config-panel]')
              .querySelector('button[data-test=ok-panel-config]')
              .click()
        """
        )
