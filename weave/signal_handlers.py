import gc
import os
import datetime
import threading
import traceback
import signal
import sys
import typing
from types import FrameType


from . import environment


def install_signal_handlers() -> None:
    import objgraph

    if (
        environment.memdump_sighandler_enabled()
        or environment.stack_dump_sighandler_enabled()
    ):

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

            with open(
                f"/tmp/weave_thread_stacks.{os.getpid()}-{datetime.datetime.now()}.txt".replace(
                    " ", "_"
                ),
                "w+",
            ) as f:
                f.write("\n".join(code))

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

        def objgraph_getnewids(signal: int, frame: typing.Optional[FrameType]) -> None:
            gc.collect()
            fname = f"/tmp/weave-server-objgraph-newids-{os.getpid()}-{datetime.datetime.now().isoformat()}.txt"
            with open(fname, "w") as f:
                objgraph.get_new_ids(limit=100, file=f)

        def sigusr1_handler(signal: int, frame: typing.Optional[FrameType]) -> None:
            if environment.memdump_sighandler_enabled():
                objgraph_getnewids(signal, frame)
            if environment.stack_dump_sighandler_enabled():
                dump_stack_traces(signal, frame)

        signal.signal(signal.SIGUSR1, sigusr1_handler)

        if environment.memdump_sighandler_enabled():

            def objgraph_showgrowth(
                signal: int, frame: typing.Optional[FrameType]
            ) -> None:
                gc.collect()
                fname = f"/tmp/weave-server-objgraph-growth-{os.getpid()}-{datetime.datetime.now().isoformat()}.txt"
                with open(fname, "w") as f:
                    objgraph.show_growth(limit=100, file=f)

            signal.signal(signal.SIGUSR2, objgraph_showgrowth)
