import os
import json
import os
import urllib.error
import urllib.request
from itertools import chain
from pathlib import Path, PurePath
from typing import Generator, Tuple, Union

import ipykernel
from jupyter_core.paths import jupyter_runtime_dir
from traitlets.config import MultipleInstanceError


FILE_ERROR = "Can't identify the notebook {}."
CONN_ERROR = "Unable to access server;\n" \
           + "ipynbname requires either no security or token based security."


def _list_maybe_running_servers(runtime_dir=None) -> Generator[dict, None, None]:
    """ Iterate over the server info files of running notebook servers.
    """
    if runtime_dir is None:
        runtime_dir = jupyter_runtime_dir()
    runtime_dir = Path(runtime_dir)

    if runtime_dir.is_dir():
        # Get notebook configuration files, sorted to check the more recently modified ones first
        for file_name in sorted(
            chain(
                runtime_dir.glob('nbserver-*.json'),  # jupyter notebook (or lab 2)
                runtime_dir.glob('jpserver-*.json'),  # jupyterlab 3
            ),
            key=os.path.getmtime,
            reverse=True,
        ):
            try:
                yield json.loads(file_name.read_bytes())
            except json.JSONDecodeError as err:
                # Sometimes we encounter empty JSON files. Ignore them.
                pass


def _get_kernel_id() -> str:
    """ Returns the kernel ID of the ipykernel.
    """
    connection_file = Path(ipykernel.get_connection_file()).stem
    kernel_id = connection_file.split('-', 1)[1]
    return kernel_id


def _get_sessions(srv):
    """ Given a server, returns sessions, or HTTPError if access is denied.
        NOTE: Works only when either there is no security or there is token
        based security. An HTTPError is raised if unable to connect to a
        server.
    """
    try:
        qry_str = ""
        token = srv['token']
        if token:
            qry_str = f"?token={token}"
        if not token and "JUPYTERHUB_API_TOKEN" in os.environ:
            token = os.environ["JUPYTERHUB_API_TOKEN"]
        url = f"{srv['url']}api/sessions{qry_str}"
        # Use a timeout in case this is a stale entry.
        with urllib.request.urlopen(url, timeout=0.5) as req:
            return json.load(req)
    except Exception:
        raise urllib.error.HTTPError(CONN_ERROR)


def _find_nb_path() -> Union[Tuple[dict, PurePath], Tuple[None, None]]:
    try:
        kernel_id = _get_kernel_id()
    except (MultipleInstanceError, RuntimeError):
        return None, None  # Could not determine
    for srv in _list_maybe_running_servers():
        try:
            sessions = _get_sessions(srv)
            for sess in sessions:
                if sess['kernel']['id'] == kernel_id:
                    return srv, PurePath(sess['path'])
        except Exception:
            pass  # There may be stale entries in the runtime directory
    return None, None


def name() -> str:
    """ Returns the short name of the notebook w/o the .ipynb extension,
        or raises a FileNotFoundError exception if it cannot be determined.
    """
    _, path = _find_nb_path()
    if path:
        return path.stem
    raise FileNotFoundError(FILE_ERROR.format('name'))


def path() -> Path:
    """ Returns the absolute path of the notebook,
        or raises a FileNotFoundError exception if it cannot be determined.
    """
    srv, path = _find_nb_path()
    if srv and path:
        root_dir = Path(srv.get('root_dir') or srv['notebook_dir'])
        return root_dir / path
    raise FileNotFoundError(FILE_ERROR.format('path'))
