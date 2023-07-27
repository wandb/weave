import gc
import os
import logging
import datetime
import threading
import traceback
import signal
import sys
import typing
import pathlib
from types import FrameType


from . import environment


def dump_folder() -> pathlib.Path:
    raw_folder = os.environ.get("WEAVE_DEBUG_DUMP_FOLDER", "")
    folder = pathlib.Path(raw_folder)
    tmp = pathlib.Path("/tmp")
    if raw_folder == "" or not folder.exists():
        if raw_folder == "":
            logging.warning(
                f"WEAVE_DEBUG_DUMP_FOLDER {folder} does not exist, using /tmp"
            )
        folder = tmp
    return folder.absolute()


def make_output_path(root: str) -> str:
    return str(
        dump_folder()
        / f"{root}-{os.getpid()}-{datetime.datetime.now().isoformat()}.txt".replace(
            " ", "_"
        )
    )


def dump_stack_traces(signal: int, frame: typing.Optional[FrameType]) -> None:
    """Function to be executed when the signal is received."""

    id_to_name = dict([(th.ident, th.name) for th in threading.enumerate()])
    code = []
    for threadId, stack in sys._current_frames().items():
        thread_name = id_to_name.get(threadId, "")
        if thread_name == "MainThread" and frame is not None:
            stack = frame
        code.append("\n# Thread: %s(%d)" % (thread_name, threadId))
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                code.append("  %s" % (line.strip()))

    output_path = make_output_path("weave_server_stack_dump")
    with open(output_path, "w+") as f:
        f.write("\n".join(code))


def objgraph_getnewids(signal: int, frame: typing.Optional[FrameType]) -> None:
    import objgraph

    gc.collect()
    output_path = make_output_path("weave_server_objgraph_newids")
    with open(output_path, "w") as f:
        objgraph.get_new_ids(limit=100, file=f)


def objgraph_showgrowth(signal: int, frame: typing.Optional[FrameType]) -> None:
    import objgraph

    gc.collect()
    output_path = make_output_path("weave_server_objgraph_growth")
    with open(output_path, "w") as f:
        objgraph.show_growth(limit=100, file=f)


def install_signal_handler_to_be_called_after_existing(
    signum: int, handler: typing.Callable[[int, typing.Optional[FrameType]], None]
) -> None:
    cur_sig_handler = signal.getsignal(signum)
    if (
        cur_sig_handler is not None
        and cur_sig_handler != signal.SIG_DFL
        and cur_sig_handler != signal.SIG_IGN
    ):

        def new_handler(signal: int, frame: typing.Optional[FrameType]) -> None:
            cur_sig_handler(signal, frame)  # type: ignore
            handler(signal, frame)

        signal.signal(signum, new_handler)
    else:
        signal.signal(signum, handler)


def install_signal_handlers() -> None:
    if (
        environment.memdump_sighandler_enabled()
        or environment.stack_dump_sighandler_enabled()
    ):
        # Here we set the SIGUSR1 signal handler to our function dump_stack_traces
        # To use, send a SIGUSR1 signal to set a baseline, then do some requests.
        # Then send a SIGUSR2 signal to drop the server into pdb and do
        # import objgraph
        # obj_ids = objgraph.get_new_ids()
        # This will contain all the ids of objects that have been created since
        # the last call to objgraph.get_new_ids()
        # Then you can inspect objects like:
        # obj_id = obj_ids['TypedDict'][0]
        # obj = objgraph.at(obj_id)
        # objgraph.show_backrefs([obj], max_depth=15)
        #
        # Other useful objgraph commands:
        # objgraph.show_most_common_types(limit=20)
        # obj = objgraph.by_type('TypedDict')[100]

        def sigusr1_handler(signal: int, frame: typing.Optional[FrameType]) -> None:
            if environment.memdump_sighandler_enabled():
                objgraph_getnewids(signal, frame)
            if environment.stack_dump_sighandler_enabled():
                dump_stack_traces(signal, frame)

        install_signal_handler_to_be_called_after_existing(
            signal.SIGUSR1, sigusr1_handler
        )

        if environment.memdump_sighandler_enabled():
            install_signal_handler_to_be_called_after_existing(
                signal.SIGUSR2, objgraph_showgrowth
            )

        def sigterm_handler(signal: int, frame: typing.Optional[FrameType]) -> None:
            sys.exit(0)

        if environment.sigterm_sighandler_enabled():
            signal.signal(signal.SIGTERM, sigterm_handler)
