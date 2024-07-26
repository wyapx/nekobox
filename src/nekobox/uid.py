from typing import Dict

uid_dict: Dict[int, str] = {}


def resolve_uid(uin: int) -> str:
    if uin in uid_dict:
        return uid_dict[uin]
    raise ValueError(f"uin {uin} not in uid_dict")


def resolve_uin(uid: str) -> int:
    for k, v in uid_dict.items():
        if v == uid:
            return k
    raise ValueError(f"uid {uid} not found in uid_dict")


def save_uid(uin: int, uid: str) -> None:
    if uin not in uid_dict:
        uid_dict[uin] = uid
