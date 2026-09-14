from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.gigachat.errors import GigaChatNetworkError


token_receiver: ContextVar[Callable[[str], None] | None] = ContextVar('token_receiver', default=None)


@contextmanager
def receive_tokens(receiver: Callable[[str], None]):
    token = token_receiver.set(receiver)
    try:
        yield
    finally:
        token_receiver.reset(token)


@dataclass
class CompletedMessage:
    content: str


@dataclass
class CompletedChoice:
    message: CompletedMessage


@dataclass
class CompletedStream:
    choices: list[CompletedChoice]


def collect_stream(client, request, receiver: Callable[[str], None]) -> CompletedStream:
    fragments = []
    finish_reason = None
    current_role = 'assistant'
    stream = client.stream(request)
    try:
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            role = getattr(choice.delta, 'role', None)
            if role is not None:
                current_role = getattr(role, 'value', role)
            if current_role == 'assistant' and choice.delta.content:
                fragments.append(choice.delta.content)
                receiver(choice.delta.content)
            if choice.finish_reason:
                finish_reason = choice.finish_reason
        if finish_reason != 'stop':
            raise GigaChatNetworkError('Поток ответа не завершён.')
        return CompletedStream([CompletedChoice(CompletedMessage(''.join(fragments)))])
    finally:
        close = getattr(stream, 'close', None)
        if close:
            close()


class VisibleTextFilter:
    MARKER = '###STATE_UPDATE###'

    def __init__(self):
        self.pending = ''
        self.hidden = False

    def feed(self, fragment: str) -> str:
        if self.hidden:
            return ''
        self.pending += fragment
        marker_index = self.pending.find(self.MARKER)
        if marker_index >= 0:
            visible = self.pending[:marker_index]
            self.pending = ''
            self.hidden = True
            return visible
        held_characters = 0
        for length in range(1, min(len(self.pending), len(self.MARKER) - 1) + 1):
            if self.pending.endswith(self.MARKER[:length]):
                held_characters = length
        visible_length = len(self.pending) - held_characters
        visible = self.pending[:visible_length]
        self.pending = self.pending[visible_length:]
        return visible

    def finish(self) -> str:
        visible = '' if self.hidden else self.pending
        if self.pending.startswith('###S'):
            visible = ''
        self.pending = ''
        return visible

    @classmethod
    def clean(cls, text: str) -> str:
        cleaner = cls()
        return (cleaner.feed(text) + cleaner.finish()).strip()
