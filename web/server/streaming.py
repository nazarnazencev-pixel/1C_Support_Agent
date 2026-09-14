import asyncio
import json
from collections.abc import Callable
from queue import Empty, Full, Queue
from threading import Event

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.gigachat.errors import GigaChatNetworkError, to_user_message
from app.gigachat.streaming import VisibleTextFilter, receive_tokens


def event_bytes(payload: dict) -> bytes:
    return ('data: ' + json.dumps(payload, ensure_ascii=False) + '\n\n').encode('utf-8')


def stream_response(operation: Callable[[], str], close: Callable[[], None] | None = None) -> StreamingResponse:
    async def events():
        queue = Queue(maxsize=64)
        stopped = Event()

        def publish(payload: dict):
            while not stopped.is_set():
                try:
                    queue.put(payload, timeout=0.2)
                    return
                except Full:
                    continue
            raise GigaChatNetworkError('Соединение с браузером закрыто.')

        def work():
            cleaner = VisibleTextFilter()

            def on_token(fragment: str):
                if stopped.is_set():
                    raise GigaChatNetworkError('Соединение с браузером закрыто.')
                visible = cleaner.feed(fragment)
                if visible:
                    publish({'type': 'delta', 'text': visible})

            try:
                with receive_tokens(on_token):
                    answer = operation()
                remaining = cleaner.finish()
                if remaining:
                    publish({'type': 'delta', 'text': remaining})
                publish({'type': 'done', 'answer': VisibleTextFilter.clean(answer)})
            except Exception as failure:
                if not stopped.is_set():
                    detail = failure.detail if isinstance(failure, HTTPException) else to_user_message(failure)
                    try:
                        publish({'type': 'error', 'detail': detail})
                    except GigaChatNetworkError:
                        pass
            finally:
                if close:
                    close()

        worker = asyncio.create_task(asyncio.to_thread(work))
        try:
            yield event_bytes({'type': 'status', 'status': 'thinking'})
            while True:
                try:
                    payload = await asyncio.to_thread(queue.get, True, 2)
                except Empty:
                    yield b': keep-alive\n\n'
                    continue
                yield event_bytes(payload)
                if payload['type'] in {'done', 'error'}:
                    break
        finally:
            stopped.set()
            worker.cancel()

    return StreamingResponse(events(), media_type='text/event-stream', headers={
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
    })
