"""Out-of-process evaluation worker (client-coupled glue layer).

This package runs user evaluations/models in an isolated subprocess with a live
WeaveClient, so it deliberately imports BOTH the trace-server contract and the
Weave client SDK. It sits OUTSIDE the trace-server <-> client import-linter
contracts on purpose: the trace server depends only on the
EvaluateModelDispatcher seam (weave.trace_server.eval_model_dispatcher), and the
concrete dispatcher (in the core repo) wires this worker in at runtime.
"""
