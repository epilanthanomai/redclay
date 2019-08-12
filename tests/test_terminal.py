from asynctest import Mock, CoroutineMock, patch
import pytest

from redclay.telnet import B
from redclay.terminal import Terminal


pytestmark = pytest.mark.asyncio


def mock_reader():
    return Mock(read=CoroutineMock())


def mock_writer():
    return Mock(
        drain=CoroutineMock(),
        wait_closed=CoroutineMock(),
    )


@pytest.fixture
def reader():
    return mock_reader()


@pytest.fixture
def writer():
    return mock_writer()


@pytest.fixture
def terminal():
    return Terminal(mock_reader(), mock_writer())


async def test_context_manager_drains_and_closes(reader, writer):
    async with Terminal(reader, writer) as term:
        pass

    writer.drain.assert_called()
    writer.close.assert_called()
    writer.wait_closed.assert_called()


@patch('asyncio.sleep')
async def test_sleep(mock_sleep, terminal):
    await terminal.sleep(120)
    mock_sleep.assert_called_with(120)


@patch('asyncio.sleep')
async def test_sleep_drains_writer(mock_sleep, terminal):
    await terminal.sleep(120)
    terminal.writer.drain.assert_called()


async def test_write_stuffs_data(terminal):
    # StreamStuffer itself is tested in test_terminal.
    await terminal.write('abc\n')
    terminal.writer.write.assert_called_with(b'abc\r\n')


async def test_input_simple_line(terminal):
    terminal.reader.read.return_value = b'abc\r\n'

    line = await terminal.input('> ')

    terminal.writer.write.assert_called_with(b'> ')
    terminal.writer.drain.assert_called()
    assert line == 'abc\n'


async def test_input_multi_read_line(terminal):
    terminal.reader.read.side_effect = [
        b'abc',
        b'\r\n',
    ]

    line = await terminal.input('> ')

    assert line == 'abc\n'


async def test_input_multiple_lines(terminal):
    terminal.reader.read.return_value = b'abc\r\ndef\r\n'

    line = await terminal.input('> ')
    assert line == 'abc\n'

    line = await terminal.input('> ')
    assert line == 'def\n'


async def test_input_eof(terminal):
    terminal.reader.read.return_value = b''

    try:
        line = await terminal.input('> ')
        assert False  # expected EOFError
    except EOFError:
        pass


async def test_input_ignores_commands(terminal):
    terminal.reader.read.return_value = (
        b'abc' +
        B.IAC.byte + B.NOP.byte +
        b'\r\n'
    )

    line = await terminal.input('> ')
    assert line == 'abc\n'


async def test_input_ignores_options(terminal):
    terminal.reader.read.return_value = (
        b'abc' +
        B.IAC.byte + B.WILL.byte + bytes([6]) +
        b'\r\n'
    )

    line = await terminal.input('> ')
    assert line == 'abc\n'


async def test_input_ignores_subnegotiations(terminal):
    terminal.reader.read.return_value = (
        b'abc' +
        B.IAC.byte + B.SB.byte + bytes([1]) +
        b'xxxxxxxx' +
        B.IAC.byte + B.SE.byte +
        b'\r\n'
    )

    line = await terminal.input('> ')
    assert line == 'abc\n'
