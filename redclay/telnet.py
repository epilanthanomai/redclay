import codecs
import collections
import enum


class ByteEnum(enum.IntEnum):
    @property
    def byte(self):
        return bytes([self.value])

    @classmethod
    def try_lookup(cls, val):
        try:
            return cls(val)
        except ValueError:
            return None


class B(ByteEnum):
    SE = 240
    NOP = 241
    DM = 242
    BRK = 243
    IP = 244
    AO = 245
    AYT = 246
    EC = 247
    EL = 248
    GA = 249
    SB = 250
    WILL = 251
    WONT = 252
    DO = 253
    DONT = 254
    IAC = 255


class Tokenizer:
    def __init__(self):
        self.state = self.State.DATA
        self.command = None

    def tokens(self, data):
        return list(self.gen_tokens(data))

    def gen_tokens(self, data):
        while data:
            get_token = getattr(self, '_get_token_' + self.state.name)
            consumed, token = get_token(data)
            data = data[consumed:]
            if token is not None:
                yield token

    def _get_token_DATA(self, data):
        iac = data.find(B.IAC.byte)
        if iac == -1:
            return len(data), self.StreamData(data)
        elif iac == 0:
            self.state = self.State.COMMAND
            return 1, None
        else:
            self.state = self.State.COMMAND
            return iac + 1, self.StreamData(data[:iac])

    def _get_token_COMMAND(self, data):
        command_i = data[0]
        if command_i in {
            B.SB.value, B.WILL.value, B.WONT.value, B.DO.value, B.DONT.value
        }:
            self.state = self.State.OPTION
            self.command = B(command_i)
            return 1, None
        else:
            self.state = self.State.DATA
            return 1, self.Command(command_i)

    def _get_token_OPTION(self, data):
        option_b = data[0]
        command = self.command
        self.command = None
        self.state = self.State.DATA
        return 1, self.Option(command, option_b)

    class State(enum.Enum):
        DATA = enum.auto()
        COMMAND = enum.auto()
        OPTION = enum.auto()

    StreamData = collections.namedtuple(
        'StreamData', ['data']
    )

    Command = collections.namedtuple(
        'Command', ['command']
    )

    Option = collections.namedtuple(
        'Option', ['command', 'option']
    )


class StreamParser:
    def __init__(self):
        self.stream = self.Stream.USER
        self.user_crlf = CrlfTransformer()
        self.user_decoder = (
            codecs.lookup('ascii')
            .incrementaldecoder(errors='ignore')
        )
        self.subnegotiation_option = None

    def stream_updates(self, tokens):
        return list(self.gen_stream_updates(tokens))

    def gen_stream_updates(self, tokens):
        for token in tokens:
            yield from self.handle_token(token)

    def handle_token(self, token):
        handler = getattr(self, 'token_' + token.__class__.__name__)
        return handler(token)

    # StreamData

    def token_StreamData(self, token):
        return self.handle_stream_data(token.data)

    def handle_stream_data(self, data):
        handler = getattr(self, 'streamData_' + self.stream.name)
        return handler(data)

    def streamData_USER(self, data):
        chunks = self.user_crlf.gen_unstuffed_crlf(data)
        decoded = (
            self.user_decoder.decode(chunk)
            for chunk in chunks
        )
        return (
            self.UserData(chunk)
            for chunk in decoded
            if chunk
        )

    def streamData_SUBNEGOTIATION(self, data):
        # For now we're ignoring all subneg data.
        return []

    # Command

    def token_Command(self, token):
        # NOTE: This handles commands in both user and subneg mode.
        handler = self.get_command_handler(token.command)
        if handler:
            return handler(token)
        else:
            return [ self.UnhandledCommand(token.command) ]

    def get_command_handler(self, command_i):
        command = B.try_lookup(command_i)
        if command is not None:
            return getattr(self, 'command_' + command.name, None)

    def command_SE(self, token):
        if self.stream == self.Stream.SUBNEGOTIATION:
            subneg = self.subnegotiation_option
            self.subnegotiation_option = None
            self.stream = self.Stream.USER
            return [ self.UnhandledSubnegotiation(subneg) ]
        else:
            return [ self.UnhandledCommand(B.SE) ]

    def command_IAC(self, token):
        return self.handle_stream_data(B.IAC.byte)

    # Option

    def token_Option(self, token):
        # NOTE: This handles commands in both user and subneg mode. It's not
        # entirely clear what we should do if someone sends IAC WILL etc
        # inside of a subnegotiation, but we'll try to handle them as
        # commands. And IAC SB will override a subneg in process. This is
        # probably a protocol error, so GIGO. OTOH maybe we should spit out
        # an UnhandledCommand or something?
        handler = getattr(self, 'option_' + token.command.name)
        return handler(token)

    def option_SB(self, token):
        self.stream = self.Stream.SUBNEGOTIATION
        self.subnegotiation_option = token.option
        # We register the event when it's complete
        return []

    def option_WILL(self, token):
        return [
            self.OptionRequest(token.option, self.Host.PEER, True)
        ]

    def option_WONT(self, token):
        return [
            self.OptionRequest(token.option, self.Host.PEER, False)
        ]

    def option_DO(self, token):
        return [
            self.OptionRequest(token.option, self.Host.LOCAL, True)
        ]

    def option_DONT(self, token):
        return [
            self.OptionRequest(token.option, self.Host.LOCAL, False)
        ]

    class Stream(enum.Enum):
        USER = enum.auto()
        SUBNEGOTIATION = enum.auto()

    class Host(enum.Enum):
        LOCAL = enum.auto()
        PEER = enum.auto()

    UserData = collections.namedtuple(
        'UserData', ['data']
    )

    OptionRequest = collections.namedtuple(
        'OptionRequest', ['option', 'host', 'request']
    )

    UnhandledCommand = collections.namedtuple(
        'UnhandledCommand', ['command']
    )

    UnhandledSubnegotiation = collections.namedtuple(
        'UnhandledSubnegotiation', ['option']
    )


class CrlfTransformer:
    def __init__(self):
        self.state = self.State.TEXT

    def unstuff(self, data):
        return b''.join(self.gen_unstuffed_crlf(data))

    def gen_unstuffed_crlf(self, data):
        while data:
            unstuff = getattr(self, 'unstuff_' + self.state.name)
            consumed, chunk = unstuff(data)
            data = data[consumed:]
            yield chunk

    def unstuff_TEXT(self, data):
        cr = data.find(self.Crlf.CR.byte)
        if cr == -1:
            return len(data), data
        else:
            self.state = self.State.CR
            return cr + 1, data[:cr]

    def unstuff_CR(self, data):
        next_b = data[:1]
        if next_b == self.Crlf.LF.byte:
            self.state = self.State.TEXT
            return 1, self.Crlf.LF.byte
        elif next_b == self.Crlf.NUL.byte:
            self.state = self.State.TEXT
            return 1, self.Crlf.CR.byte
        else:
            self.state = self.State.TEXT
            return 0, self.Crlf.CR.byte

    class State(enum.Enum):
        TEXT = enum.auto()
        CR = enum.auto()

    class Crlf(ByteEnum):
        NUL = 0
        LF = 10
        CR = 13
