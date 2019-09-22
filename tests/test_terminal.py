from asynctest import Mock, CoroutineMock, patch
from unittest.mock import call
import pytest

from redclay.telnet import B, OPTIONS
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


async def test_write_none_is_noop(terminal):
    await terminal.write(None)
    terminal.writer.write.assert_not_called()


async def test_write_stuffs_single_item(terminal):
    # StreamStuffer itself is tested in test_terminal.
    await terminal.write('abc\n')
    terminal.writer.write.assert_called_with(b'abc\r\n')


async def test_write_stuffs_multiple(terminal):
    await terminal.write(['abc\n', 'def\n'])
    terminal.writer.write.assert_any_call(b'abc\r\n')
    terminal.writer.write.assert_any_call(b'def\r\n')


async def test_write_none_with_drain(terminal):
    await terminal.write(None, drain=True)
    terminal.writer.drain.assert_called()


async def test_write_multiple_with_drain(terminal):
    await terminal.write(['abc\n', 'def\n'], drain=True)
    terminal.writer.write.assert_any_call(b'abc\r\n')
    terminal.writer.write.assert_any_call(b'def\r\n')
    terminal.writer.drain.assert_called()


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


async def test_input_rejects_unknown_options(terminal):
    terminal.reader.read.return_value = (
        b'abc' +
        B.IAC.byte + B.WILL.byte + bytes([42]) +
        b'\r\n'
    )

    line = await terminal.input('> ')
    terminal.writer.write.assert_called_with(
        B.IAC.byte + B.DONT.byte + bytes([42])
    )
    terminal.writer.drain.assert_called()
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


async def test_input_secret_simple_line(terminal):
    terminal.reader.read.return_value = b'abc\r\n'

    line = await terminal.input_secret('> ')

    terminal.writer.write.assert_any_call(b'> ')
    terminal.writer.write.assert_any_call(
        B.IAC.byte + B.WILL.byte + OPTIONS.ECHO.byte
    )
    terminal.writer.write.assert_any_call(b'\r\n')
    terminal.writer.write.assert_any_call(
        B.IAC.byte + B.WONT.byte + OPTIONS.ECHO.byte
    )
    terminal.writer.drain.assert_called()
    assert line == 'abc\n'


async def test_input_handles_interrupt_with_tm(terminal):
    # Typically when the user hits ^C the peer will send IAC IP IAC DO TM
    # and then ignore everything until it receivs IAC WILL TM. This tests
    # that happy path use case.
    terminal.reader.read.side_effect = [
        (
            b'abc' +
            B.IAC.byte + B.IP.byte +
            B.IAC.byte + B.DO.byte + OPTIONS.TM.byte
        ),
        (
            b'def' +
            b'\r\n'
        ),
    ]

    line = await terminal.input('> ')
    assert line == 'def\n'

    # The expected behavior is:
    #  * write sends the prompt and drains
    #  * read gets abc IAC IP IAC DO TM
    #  * abc adds to line buffer
    #  * IAC IP clears line buffer
    #  * IAC DO TM adds a TM annotation to line buffer
    #  * line buffer pops the bare annotation
    #  * write sends IAC WILL TM and drains
    #  * write sends \n, re-sends the prompt and drains
    #  * read gets def\r\n
    #  * def\n gets added to the line buffer
    #  * input returns def\n
    assert terminal.writer.write.call_args_list == [
        call(b'> '),
        call(B.IAC.byte + B.WILL.byte + OPTIONS.TM.byte),
        call(b'\r\n> '),
    ]
    terminal.writer.drain.assert_called()


async def test_input_handles_bare_interrupt(terminal):
    # Hypothetically a client could just send IAC IP without a IAC DO TM.
    terminal.reader.read.side_effect = [
        (
            b'abc' +
            B.IAC.byte + B.IP.byte
        ),
        (
            b'def' +
            b'\r\n'
        ),
    ]

    line = await terminal.input('> ')
    assert line == 'def\n'

    # The expected behavior is:
    #  * write sends the prompt and drains
    #  * read gets abc IAC IP
    #  * abc adds to line buffer
    #  * IAC IP clears line buffer
    #  * write sends \n, re-sends the prompt and drains
    #  * read gets def\r\n
    #  * def\n gets added to the line buffer
    #  * input returns def\n
    assert terminal.writer.write.call_args_list == [
        call(b'> '),
        call(b'\r\n> '),
    ]
    terminal.writer.drain.assert_called()


async def test_input_handles_bare_tm(terminal):
    # Hypothetically a client could send IAC DO TM without IAC IP. It's not
    # clear what use case would cause this, so here we're mostly testing
    # that we do something reasonable.
    terminal.reader.read.side_effect = [
        (
            b'ab' +
            B.IAC.byte + B.DO.byte + OPTIONS.TM.byte
        ),
        (
            b'c\r\n'
        ),
    ]

    line = await terminal.input('> ')
    assert line == 'abc\n'

    # Our behavior in this case is:
    #  * write sends the prompt and drains
    #  * read gets ab IAC DO TM
    #  * ab adds to line buffer
    #  * IAC DO TM adds the TM annotation to the line buffer
    #  * read gets d\r\n
    #  * d\n gets added to the line buffer
    #  * abc\n pops from the line with the TM annotation
    #  * write sends IAC WILL TM and drains
    assert terminal.writer.write.call_args_list == [
        call(b'> '),
        call(B.IAC.byte + B.WILL.byte + OPTIONS.TM.byte),
    ]
    terminal.writer.drain.assert_called()


async def test_interrupt_tm_split(terminal):
    # Hypothetically network congestion or other weirdness could separate
    # IAC IP from IAC DO TM across reads. This is an unusual edge case, so
    # let's just make sure we do something sensible with it.
    terminal.reader.read.side_effect = [
        (
            b'abc' +
            B.IAC.byte + B.IP.byte
        ),
        (
            B.IAC.byte + B.DO.byte + OPTIONS.TM.byte
        ),
        (
            b'def' +
            b'\r\n'
        ),
    ]

    line = await terminal.input('> ')
    assert line == 'def\n'

    # The expected behavior is:
    #  * write sends the prompt and drains
    #  * read gets abc IAC IP
    #  * abc adds to line buffer
    #  * IAC IP clears line buffer
    #  * write sends \n, re-sends the prompt and drains
    #  * peer ignores the above because no IAC WILL TM yet
    #  * read gets IAC DO TM
    #  * IAC DO TM adds a TM annotation to line buffer
    #  * line buffer pops the bare annotation
    #  * write sends IAC WILL TM and drains
    #  * read gets def\r\n
    #  * def\n gets added to the line buffer
    #  * input returns def\n
    assert terminal.writer.write.call_args_list == [
        call(b'> '),
        call(b'\r\n> '),
        call(B.IAC.byte + B.WILL.byte + OPTIONS.TM.byte),
    ]
    terminal.writer.drain.assert_called()


async def test_input_secret_peer_refuse_echo(terminal):
    terminal.reader.read.return_value = (
        B.IAC.byte + B.DONT.byte + OPTIONS.ECHO.byte +
        b'abc\r\n'
    )

    line = await terminal.input_secret('> ')

    terminal.writer.write.assert_any_call(b'> ')
    terminal.writer.write.assert_any_call(
        B.IAC.byte + B.WILL.byte + OPTIONS.ECHO.byte
    )
    terminal.writer.write.assert_any_call(b'\r\n')
    terminal.writer.drain.assert_called()
    assert line == 'abc\n'


async def test_input_secret_peer_accepts_then_disables_echo(terminal):
    terminal.reader.read.return_value = (
        B.IAC.byte + B.DO.byte + OPTIONS.ECHO.byte +
        b'abc' +
        B.IAC.byte + B.DONT.byte + OPTIONS.ECHO.byte +
        b'\r\n'
    )

    line = await terminal.input_secret('> ')

    terminal.writer.write.assert_any_call(b'> ')
    terminal.writer.write.assert_any_call(
        B.IAC.byte + B.WILL.byte + OPTIONS.ECHO.byte
    )
    terminal.writer.write.assert_any_call(
        B.IAC.byte + B.WONT.byte + OPTIONS.ECHO.byte
    )
    terminal.writer.write.assert_any_call(b'\r\n')
    terminal.writer.drain.assert_called()
    assert line == 'abc\n'


async def test_input_refuses_peer_echo_request(terminal):
    terminal.reader.read.return_value = (
        b'abc' +
        B.IAC.byte + B.WILL.byte + OPTIONS.ECHO.byte +
        b'\r\n'
    )

    line = await terminal.input('> ')

    terminal.writer.write.assert_any_call(b'> ')
    terminal.writer.write.assert_any_call(
        B.IAC.byte + B.DONT.byte + OPTIONS.ECHO.byte
    )
    terminal.writer.drain.assert_called()
    assert line == 'abc\n'


async def test_input_refuses_local_echo_request(terminal):
    terminal.reader.read.return_value = (
        b'abc' +
        B.IAC.byte + B.DO.byte + OPTIONS.ECHO.byte +
        b'\r\n'
    )

    line = await terminal.input('> ')

    terminal.writer.write.assert_any_call(b'> ')
    terminal.writer.write.assert_any_call(
        B.IAC.byte + B.WONT.byte + OPTIONS.ECHO.byte
    )
    terminal.writer.drain.assert_called()
    assert line == 'abc\n'
