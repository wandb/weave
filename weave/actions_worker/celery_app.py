from celery import Celery

from weave.trace_server import environment as wf_env

app = Celery("tasks", broker=wf_env.wf_action_queue(), backend=wf_env.wf_action_queue())
