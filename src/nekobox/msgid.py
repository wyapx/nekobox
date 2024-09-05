from typing import Tuple

# msg type map:
# 1: guild(group)
# 2: private(friend)


def encode_msgid(typ: int, seq: int) -> str:
    if typ == 1:
        msg_id = str(seq)
    elif typ == 2:
        msg_id = f"private:{seq}"
    else:
        raise ValueError(f"Unsupported message type: {typ}")
    return msg_id


def decode_msgid(msg_id: str) -> Tuple[int, int]:
    if msg_id.isdigit():  # guild
        return 1, int(msg_id)
    elif msg_id.find("private:") == 0:
        return 2, int(msg_id[len("private:") :])
    else:
        raise ValueError(f"Invalid msg id: {msg_id}")
