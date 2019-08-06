import pytest

from redclay.telnet import B, Tokenizer


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


def test_tokenizer_iac_iac(tokenizer):
    toks = tokenizer.tokens(B.IAC.byte + B.IAC.byte)
    assert toks == [ Tokenizer.StreamData(B.IAC.byte) ]


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
