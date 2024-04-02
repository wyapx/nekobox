import asyncio
from typing import Callable, Coroutine, Type, Optional, TypeVar

from loguru import logger
from lagrange.client.client import Client
from lagrange.client.events import BaseEvent
from satori import EventType
from satori.server import Event

T = TypeVar('T')


def event_register(
        client: Client,
        queue: asyncio.Queue[Event],
        event_type: Type[T],
        handler: Callable[["Client", T], Coroutine[None, None, Optional[Event]]]
):
    async def _after_handle(_client: Client, event: BaseEvent):
        ev = await handler(_client, event)
        if ev:
            if ev.type != EventType.MESSAGE_CREATED:
                logger.debug(f"Event '{ev.type}' was triggered")
            await queue.put(ev)

    client.events.subscribe(event_type, handler=_after_handle)
