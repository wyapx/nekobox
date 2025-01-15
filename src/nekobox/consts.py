from typing import Optional
from satori.server import Server

PLATFORM = "nekobox"
SERVER: Optional[Server] = None


def _set_server(server: Server):
    global SERVER
    SERVER = server
    return server


def get_server():
    return SERVER
