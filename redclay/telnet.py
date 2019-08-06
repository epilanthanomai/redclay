import collections
import enum


class B(enum.IntEnum):
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

    @property
    def byte(self):
        return bytes([self.value])

    @classmethod
    def try_lookup(cls, val):
        try:
            return cls(val)
        except ValueError:
            return None


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
