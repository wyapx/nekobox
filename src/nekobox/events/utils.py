import asyncio
from typing import Type, TypeVar, Callable, Optional, Coroutine

from loguru import logger
from satori import EventType
from satori.server import Event
from lagrange.client.client import Client
from lagrange.client.events import BaseEvent

TEvent = TypeVar("TEvent", bound=BaseEvent)


def event_register(
    client: Client,
    queue: asyncio.Queue[Event],
    event_type: Type[TEvent],
    handler: Callable[["Client", TEvent], Coroutine[None, None, Optional[Event]]],
):
    async def _after_handle(_client: Client, event: TEvent):
        ev = await handler(_client, event)
        if ev:
            if ev.type != EventType.MESSAGE_CREATED:
                logger.debug(f"Event '{ev.type}' was triggered")
            await queue.put(ev)

    client.events.subscribe(event_type, handler=_after_handle)
