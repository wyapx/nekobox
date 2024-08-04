from typing import Any, Callable, Coroutine

from satori.server import Request
from lagrange.client.client import Client

API_HANDLER = Callable[[Client, Request], Coroutine[None, None, Any]]
