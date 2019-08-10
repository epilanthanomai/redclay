import pytest

from redclay.telnet import (
    B,
    Tokenizer,
    StreamParser,
    StreamStuffer,
    CrlfTransformer,
)

#
# Tokenizer tests
#

@pytest.fixture
def tokenizer():
    return Tokenizer()


def test_tokenizer_empty(tokenizer):
    toks = tokenizer.tokens(b'')
    assert toks == []


def test_tokenizer_data(tokenizer):
    TEST_DATA = b'abcde'
    toks = tokenizer.tokens(TEST_DATA)
    assert toks == [ Tokenizer.StreamData(TEST_DATA) ]


def test_tokenizer_command(tokenizer):
    toks = tokenizer.tokens(B.IAC.byte + B.NOP.byte)
    assert toks == [ Tokenizer.Command(B.NOP.value) ]


def test_tokenizer_option(tokenizer):
    toks = tokenizer.tokens(B.IAC.byte + B.WILL.byte + bytes([42]))
    assert toks == [ Tokenizer.Option(B.WILL.value, 42) ]


def test_split_command(tokenizer):
    toks = tokenizer.tokens(b'abc' + B.IAC.byte)
    assert toks == [ Tokenizer.StreamData(b'abc') ]

    toks = tokenizer.tokens(B.NOP.byte + b'def')
    assert toks == [
        Tokenizer.Command(B.NOP.value),
        Tokenizer.StreamData(b'def'),
    ]


def test_split_option(tokenizer):
    toks = tokenizer.tokens(b'abc' + B.IAC.byte + B.WONT.byte)
    assert toks == [ Tokenizer.StreamData(b'abc') ]

    toks = tokenizer.tokens(bytes([42]) + b'def')
    assert toks == [
        Tokenizer.Option(B.WONT, 42),
        Tokenizer.StreamData(b'def'),
    ]


#
# StreamParser tests
#

@pytest.fixture
def stream_parser():
    return StreamParser()


def test_stream_user_data(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.StreamData(b'Hello, world!')
    ])
    assert events == [
        StreamParser.UserData('Hello, world!')
    ]


def test_stream_user_data_crlf(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.StreamData(b'Hello,\r\nworld!')
    ])
    assert events == [
        StreamParser.UserData('Hello,'),
        StreamParser.UserData('\n'),
        StreamParser.UserData('world!'),
    ]


def test_stream_user_data_nonascii(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.StreamData(b'abc\xabdef')
    ])
    assert events == [
        StreamParser.UserData('abcdef')
    ]


def test_stream_command(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.Command(B.NOP.value)
    ])
    assert events == [
        StreamParser.UnhandledCommand(B.NOP.value)
    ]


def test_stream_iac(stream_parser):
    # IAC IAC produces a single IAC on the user stream. This is not a valid
    # ascii character, so it's filtered by decoding.
    events = stream_parser.stream_updates([
        Tokenizer.Command(B.IAC.value)
    ])
    assert events == []


def test_stream_sb(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.Option(B.SB, 42),
        Tokenizer.StreamData(b'1234'),
        Tokenizer.Command(B.SE.value),
    ])
    assert events == [
        StreamParser.UnhandledSubnegotiation(42)
    ]


def test_stream_will(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.Option(B.WILL, 42)
    ])
    assert events == [
        StreamParser.OptionRequest(42, StreamParser.Host.PEER, True)
    ]


def test_stream_wont(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.Option(B.WONT, 42)
    ])
    assert events == [
        StreamParser.OptionRequest(42, StreamParser.Host.PEER, False)
    ]


def test_stream_do(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.Option(B.DO, 42)
    ])
    assert events == [
        StreamParser.OptionRequest(42, StreamParser.Host.LOCAL, True)
    ]


def test_stream_dont(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.Option(B.DONT, 42)
    ])
    assert events == [
        StreamParser.OptionRequest(42, StreamParser.Host.LOCAL, False)
    ]


def test_stream_command_in_crlf(stream_parser):
    events = stream_parser.stream_updates([
        Tokenizer.StreamData(b'abc\r'),
        Tokenizer.Command(B.NOP.value),
        Tokenizer.StreamData(b'\ndef'),
    ])
    assert events == [
        StreamParser.UserData('abc'),
        StreamParser.UnhandledCommand(B.NOP.value),
        StreamParser.UserData('\n'),
        StreamParser.UserData('def'),
    ]

#
# StreamStuffer
#

@pytest.fixture
def stuffer():
    return StreamStuffer()


def test_stuffer_text(stuffer):
    stuffed = stuffer.stuff('abc')
    assert stuffed == b'abc'


def test_stuffer_nonascii(stuffer):
    try:
        stuffed = stuffer.stuff('abcdéf')
        assert False  # should have thrown an exception
    except UnicodeEncodeError:
        pass  # expected behavior under test


def test_stuffer_crlf(stuffer):
    stuffed = stuffer.stuff('abc\ndef\rghi')
    assert stuffed == b'abc\r\ndef\r\0ghi'

#
# CrlfTransformer tests
#

@pytest.fixture
def crlf():
    return CrlfTransformer()


def test_crlf_text(crlf):
    TEST_DATA = b'Hello, world!'
    transformed = crlf.unstuff(TEST_DATA)
    assert transformed == TEST_DATA


def test_crlf_cr_lf(crlf):
    transformed = crlf.unstuff(b'abc\r\ndef')
    assert transformed == b'abc\ndef'


def test_crlf_cr_nul(crlf):
    transformed = crlf.unstuff(b'abc\r\0def')
    assert transformed == b'abc\rdef'


def test_crlf_cr_bare(crlf):
    transformed = crlf.unstuff(b'abc\rdef')
    assert transformed == b'abc\rdef'


def test_crlf_lf_bare(crlf):
    transformed = crlf.unstuff(b'abc\ndef')
    assert transformed == b'abc\ndef'


def test_crlf_cr_cr_lf(crlf):
    # GIGO, but here's what we do
    transformed = crlf.unstuff(b'abc\r\r\ndef')
    assert transformed == b'abc\r\ndef'


def test_crlf_split_cr_lf(crlf):
    transformed = crlf.unstuff(b'abc\r')
    assert transformed == b'abc'

    transformed = crlf.unstuff(b'\ndef')
    assert transformed == b'\ndef'


def test_crlf_split_cr_bare(crlf):
    transformed = crlf.unstuff(b'abc\r')
    assert transformed == b'abc'

    transformed = crlf.unstuff(b'def')
    assert transformed == b'\rdef'


def test_crlf_split_lf_bare(crlf):
    transformed = crlf.unstuff(b'abc\n')
    assert transformed == b'abc\n'

    transformed = crlf.unstuff(b'def')
    assert transformed == b'def'


def test_crlf_stuff_text(crlf):
    transformed = crlf.stuff(b'abc')
    assert transformed == b'abc'


def test_crlf_stuff_cr(crlf):
    transformed = crlf.stuff(b'abc\rdef')
    assert transformed == b'abc\r\0def'


def tets_crlf_stuff_lf(crlf):
    transformed = crlf.stuff(b'abd\ndef')
    assert transformed == b'abc\r\ndef'


#
# integration
#

def test_integration(tokenizer, stream_parser):
    data = (
        b'Hel' +
        B.IAC.byte + B.NOP.byte +
        b'lo,\r' +
        # start a subneg
        B.IAC.byte + B.SB.byte + bytes([42]) +
        b'abc' +
        # literal IAC SE as subneg data
        B.IAC.byte + B.IAC.byte + B.SE.byte +
        b'def' +
        # finish the subneg
        B.IAC.byte + B.SE.byte +
        b'\0wor' +
        B.IAC.byte + B.DO.byte + bytes([42]) +
        b'ld!'
    )
    atomized = [bytes([b]) for b in data]  # process it one byte at a time

    toks = sum([tokenizer.tokens(b) for b in atomized], [])
    events = sum([stream_parser.stream_updates([tok]) for tok in toks], [])

    assert events == [
        StreamParser.UserData('H'),
        StreamParser.UserData('e'),
        StreamParser.UserData('l'),
        StreamParser.UnhandledCommand(B.NOP.value),
        StreamParser.UserData('l'),
        StreamParser.UserData('o'),
        StreamParser.UserData(','),
        StreamParser.UnhandledSubnegotiation(42),
        StreamParser.UserData('\r'),
        StreamParser.UserData('w'),
        StreamParser.UserData('o'),
        StreamParser.UserData('r'),
        StreamParser.OptionRequest(42, StreamParser.Host.LOCAL, True),
        StreamParser.UserData('l'),
        StreamParser.UserData('d'),
        StreamParser.UserData('!'),
    ]
