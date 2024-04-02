from typing import Callable, Coroutine, Union

from lagrange.client.client import Client
from satori.server import Request

API_HANDLER = Callable[[Client, Request], Coroutine[None, None, Union[list, dict]]]
