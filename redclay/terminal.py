import asyncio
import logging

from redclay.telnet import StreamStuffer, Tokenizer, StreamParser
from redclay.textutil import LineBuffer


logger = logging.getLogger(__name__)


class Terminal:
    READ_SIZE = 2 ** 12  # arbitrary pleasant number?

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

        self.encoder = StreamStuffer()
        self.tokenizer = Tokenizer()
        self.parser = StreamParser()
        self.line_buffer = LineBuffer()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def close(self):
        await self.writer.drain()
        self.writer.close()
        await self.writer.wait_closed()

    async def sleep(self, secs):
        await self.writer.drain()
        await asyncio.sleep(secs)

    async def write(self, text):
        if isinstance(text, str):
            text = StreamParser.UserData(text)

        # doesn't technically need to be async, but it did before and could
        # again. also, for consistency with the rest of the interface
        out_data = self.encoder.stuff(text)
        self.writer.write(out_data)

    async def input(self, prompt):
        await self.write(prompt)
        await self.writer.drain()

        while not self.line_buffer.has_line():
            data = await self.reader.read(self.READ_SIZE)
            if not data:
                raise EOFError()
            toks = self.tokenizer.tokens(data)
            updates = self.parser.stream_updates(toks)
            for update in updates:
                self.handle_update(update)

        return self.line_buffer.pop()

    def handle_update(self, update):
        handle = getattr(self, 'update_' + update.__class__.__name__, None)
        if handle:
            handle(update)
        else:
            logger.info(f'unhandled {update} on term {id(self)}')

    def update_UserData(self, update):
        self.line_buffer.append(update.data)

