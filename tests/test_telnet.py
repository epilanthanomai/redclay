import pytest

from redclay.telnet import B, Tokenizer, CrlfTransformer

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
