import struct
from typing import Tuple


def encode_msgid(typ: int, seq: int) -> str:
    return struct.pack("!BI", typ, seq).hex()


def decode_msgid(msg_id: str) -> Tuple[int, int]:
    return struct.unpack("!BI", bytes.fromhex(msg_id))  # noqa
