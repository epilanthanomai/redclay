import asyncio
import collections
import contextlib
import enum
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
        self.update_buffer = []
        self.prompt_mgr = None

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

    async def write(self, texts, drain=False):
        if texts is None:
            texts = []
        if not isinstance(texts, list):
            texts = [texts]

        for text in texts:
            self._write(text)
        if drain:
            await self.writer.drain()

    def _write(self, text):
        if isinstance(text, str):
            text = StreamParser.UserData(text)

        out_data = self.encoder.stuff(text)
        logger.debug(f'writing term:{id(self)} data:{out_data!r}')
        self.writer.write(out_data)

    @contextlib.contextmanager
    def prompt(self, prompt):
        self.prompt_mgr = Prompt(prompt)
        try:
            yield
        finally:
            self.prompt_mgr = None

    async def input(self, prompt):
        with self.prompt(prompt):
            while True:
                line = await self._input()
                if line:
                    return line

    async def _input(self):
        await self.require_line_buffer()

        annotations, line = self.line_buffer.pop()
        for annotation in annotations:
            handler_name =  'annotation_' + annotation.__class__.__name__
            handler = getattr(self, handler_name)
            await handler(annotation)

        return line

    async def require_line_buffer(self):
        while not self.line_buffer.has_line():
            await self.require_update_buffer()
            update = self.update_buffer.pop(0)
            await self.write(self.handle_update(update), drain=True)

    async def require_update_buffer(self):
        while not self.update_buffer:
            await self.write(
                self.prompt_mgr.require_has_prompt(),
                drain=True,
            )
            self.update_buffer = await self.fetch_updates()

    async def fetch_updates(self):
        data = await self.reader.read(self.READ_SIZE)
        logger.debug(f'read term:{id(self)} data:{data!r}')
        if not data:
            raise EOFError()

        toks = self.tokenizer.tokens(data)
        return self.parser.stream_updates(toks)

    async def annotation_TimingMark(self, annotation):
        await self.write(annotation.option.accept(), drain=True)

    #
    # input stream updates
    #

    def handle_update(self, update):
        handle = getattr(self, 'update_' + update.__class__.__name__, None)
        if not handle:
            logger.info(f'unhandled update:{update} on term:{id(self)}')
            return

        return handle(update)

    def update_UserData(self, update):
        self.line_buffer.append(update.data)
        self.prompt_mgr.mark_user_data()

    #
    # telnet options
    #

    def update_OptionNegotiation(self, request):
        handler = self.get_option_handler(request)
        return handler(request)

    def get_option_handler(self, request):
        if request.option is None:
            return self.option_unhandled

        handler_name = 'option_' + request.option.name
        handler = getattr(self, 'option_' + request.option.name, None)
        return handler or self.option_unhandled

    def option_TM(self, request):
        if not request.state:
            # client is rejecting this option. we only send it when it's
            # requested, so it's safe to ignore this.
            logger.debug(f'ignoring unmatched request:{request} on term:{id(self)}')
            return

        if request.host == StreamParser.Host.LOCAL:
            # client is requesting a TM.
            logger.info(f'ACCEPTING request:{request} on term:{id(self)}')
            self.line_buffer.annotate(self.TimingMark(request))
            return

        # otherwise client is sending us a TM, which we didn't request. ignore it.
        logger.debug(f'ignoring unrequested request:{request} on term:{id(self)}')

    def option_unhandled(self, request):
        if request.state:
            # Peer is requesting an unsupported option. Refuse.
            logger.info(f'rejecting request:{request} on term:{id(self)}')
            return request.refuse()

        # else client is requesting to disable an option. we support no
        # options, so all are off. ignore it.
        else:
            logger.debug(f'ignoring request:{request} on term:{id(self)}')

    # telnet commands

    def update_Command(self, command):
        handler = self.get_command_handler(command)
        return handler(command)

    def get_command_handler(self, command):
        if command.command is None:
            return self.command_unhandled

        handler_name = 'command_' + command.command.name
        handler = getattr(self, handler_name, None)
        return handler or self.command_unhandled

    def command_unhandled(self, command):
        logger.info(f'unhandled command:{command} on term:{id(self)}')

    def command_IP(self, command):
        logger.debug(f'interrupt process on term:{id(self)}')
        # Currently we only ever read peer input during prompting, so
        # there's no process to interrupt. For bonus complexity there's a
        # fair chance the peer will send a timing mark request and discard
        # everything it gets before we acknowledge, so there's no point
        # sending a prompt unless we're sure they're ready. For no just
        # clear the input.
        self.line_buffer.clear()
        self.prompt_mgr.mark_interrupt()

    TimingMark = collections.namedtuple('TimingMark', ['option'])


class Prompt:
    def __init__(self, text):
        self.text = text
        self.state = self.PromptState.NO_PROMPT

    class PromptState(enum.Enum):
        NO_PROMPT = enum.auto()
        AT_PROMPT = enum.auto()
        USER_INPUT = enum.auto()
        INTERRUPT = enum.auto()

    def require_has_prompt(self):
        if self.state not in {
            self.PromptState.AT_PROMPT,
            self.PromptState.USER_INPUT,
        }:
            result = ''
            if self.state != self.PromptState.NO_PROMPT:
                result += '\n'
            result += self.text
            self.state = self.PromptState.AT_PROMPT
            return result

    def mark_user_data(self):
        self.state = self.PromptState.USER_INPUT

    def mark_interrupt(self):
        self.state = self.PromptState.INTERRUPT
