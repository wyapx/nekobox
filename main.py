import os

from satori.server import Server

from nekobox import NekoBoxAdapter

server = Server(host="localhost", port=7777)
server.apply(
    NekoBoxAdapter(
        int(os.environ.get("LAGRANGE_UIN", "0")),
        "fa1ccfd6a9fcac523f3af2f67575e54230b1aef5df69a6886a3bae140e39a13b",
        os.environ.get("LAGRANGE_SIGN_URL", ""),
        "linux",
        "DEBUG",
    )
)
server.run()
