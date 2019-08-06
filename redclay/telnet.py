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
        if command_i == B.IAC.value:
            return 1, self.StreamData(B.IAC.byte)
        elif command_i in {
            B.SB.value, B.WILL.value, B.WONT.value, B.DO.value, B.DONT.value
        }:
            self.state = self.State.OPTION
            self.command = B(command_i)
            return 1, None
        else:
            command = B(command_i)
            self.state = self.State.DATA
            return 1, self.Command(command)

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
