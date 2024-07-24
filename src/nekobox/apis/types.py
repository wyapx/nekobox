from typing import Callable, Coroutine, Any

from lagrange.client.client import Client
from satori.server import Request

API_HANDLER = Callable[[Client, Request], Coroutine[None, None, Any]]
