import asyncio

import pytest
from asynctest import CoroutineMock, Mock, patch

import redclay.game
import redclay.server
from redclay.server import ConnectionServer, Connection, async_run_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def connection():
    return Connection(Mock(), Mock())


@pytest.fixture
def conn_server():
    return ConnectionServer()


def mock_Terminal():
    MockTerminal = Mock()
    mock_terminal = MockTerminal.return_value
    mock_terminal.__aenter__ = CoroutineMock(return_value=mock_terminal)
    mock_terminal.__aexit__ = CoroutineMock()
    mock_terminal.write = CoroutineMock()
    mock_terminal.sleep = CoroutineMock()
    mock_terminal.input = CoroutineMock(return_value="\n")
    mock_terminal.input_secret = CoroutineMock(return_value="\n")
    return MockTerminal


@patch("redclay.server.ConnectionServer")
@patch("asyncio.start_server", new_callable=CoroutineMock)
async def test_run_server_callback(mock_start_server, MockConnectionServer):
    # Test that async_run_server() creates a ConnectionServer and calls
    # asyncio.start_server() with a wrapper around its .handle_connection().

    # First test that it actually calls asyncio server logic.
    mock_io_server = Mock(
        serve_forever=CoroutineMock(),
        __aenter__=CoroutineMock(),
        __aexit__=CoroutineMock(),
    )
    mock_start_server.return_value = mock_io_server
    mock_connection_server = Mock(handle_connection=CoroutineMock())
    MockConnectionServer.return_value = mock_connection_server
    Session = Mock()

    await async_run_server(Session)

    mock_start_server.assert_called_once()
    mock_start_server.return_value.serve_forever.assert_called_once_with()

    # Now check the wrapper that async_run_server() passed into
    # asyncio.start_server. Call it like asyncio will, and verify that it
    # translates to an appropriate handle_connection() call.
    start_server_args, start_server_kwargs = mock_start_server.call_args
    handle, addr, port = start_server_args
    reader = Mock()
    writer = Mock()

    await handle(reader, writer)

    mock_connection_server.handle_connection.assert_called_once_with(
        redclay.game.boot, reader, writer
    )


@patch("redclay.server.Terminal", new_callable=mock_Terminal)
@patch("redclay.server.logging_context", wraps=redclay.logging.logging_context)
@patch("redclay.server.Connection")
async def test_handle_connection_fast_path(
    MockConnection, mock_logging_context, MockTerminal
):
    async def boot(conn):
        await conn.stop()

    mock_terminal = MockTerminal.return_value
    mock_connection = MockConnection.return_value
    Session = Mock()
    reader = Mock()
    writer = Mock()

    conn_server = ConnectionServer(Session)
    await conn_server.handle_connection(boot, reader, writer)

    MockTerminal.assert_called_once_with(reader, writer)
    mock_logging_context.assert_called_once_with(term=id(mock_terminal))
    MockConnection.assert_called_once_with(Session, mock_terminal)


@patch("redclay.server.Terminal", new_callable=mock_Terminal)
async def test_handle_connection_runs_prompt(MockTerminal):
    class CaptureAndStop:
        prompt = "prompt> "

        def __init__(self):
            self.captured_line = None

        async def handle_input(self, conn, line):
            self.captured_line = line
            await conn.stop()

    prompt = CaptureAndStop()

    async def boot(conn):
        await conn.push(prompt=prompt)

    mock_terminal = MockTerminal.return_value
    mock_terminal.input.return_value = "test input\n"

    conn_server = ConnectionServer(Mock())
    await conn_server.handle_connection(boot, Mock(), Mock())

    mock_terminal.input.assert_called_once_with(CaptureAndStop.prompt)
    assert prompt.captured_line == "test input"


@patch("redclay.server.Terminal", new_callable=mock_Terminal)
async def test_handle_connection_runs_obscured_prompt(MockTerminal):
    class CaptureAndStopObscured:
        prompt = "prompt> "
        obscure_input = True

        def __init__(self):
            self.captured_line = None

        async def handle_input(self, conn, line):
            self.captured_line = line
            await conn.stop()

    prompt = CaptureAndStopObscured()

    async def boot(conn):
        await conn.push(prompt=prompt)

    mock_terminal = MockTerminal.return_value
    mock_terminal.input_secret.return_value = "test input\n"

    conn_server = ConnectionServer(Mock())
    await conn_server.handle_connection(boot, Mock(), Mock())

    mock_terminal.input_secret.assert_called_once_with(CaptureAndStopObscured.prompt)
    assert prompt.captured_line == "test input"


@patch("redclay.server.Terminal", new=mock_Terminal())
async def test_handle_connection_calls_prompt():
    class CallablePrompt:
        def __init__(self):
            self.captured_prompt_conn = None

        def prompt(self, conn):
            self.captured_prompt_conn = conn
            return "prompt> "

        async def handle_input(self, conn, line):
            await conn.stop()

    prompt = CallablePrompt()
    captured_boot_conn = None

    async def boot(conn):
        nonlocal captured_boot_conn
        captured_boot_conn = conn
        await conn.push(prompt=prompt)

    conn_server = ConnectionServer(Mock())
    await conn_server.handle_connection(boot, Mock(), Mock())

    assert prompt.captured_prompt_conn == captured_boot_conn


@patch("redclay.server.Terminal", new=mock_Terminal())
async def test_handle_connection_loops():
    class StopAfterThree:
        prompt = "> "
        MAX_INPUTS = 3

        def __init__(self):
            self.inputs_handled = 0

        async def handle_input(self, conn, line):
            self.inputs_handled += 1
            if self.inputs_handled >= self.MAX_INPUTS:
                await conn.stop()

    prompt = StopAfterThree()

    async def boot(conn):
        await conn.push(prompt=prompt)

    conn_server = ConnectionServer(Mock())
    await conn_server.handle_connection(boot, Mock(), Mock())

    assert prompt.inputs_handled == 3


async def test_connection_set_context(connection):
    await connection.set_context(a=1, b=2)
    assert connection.context() == {"a": 1, "b": 2}
    await connection.set_context(b=3, c=4)
    assert connection.context() == {"a": 1, "b": 3, "c": 4}


async def test_connection_stack(connection):
    await connection.set_context(a=1, b=2)
    await connection.push()
    await connection.set_context(b=3, c=4)
    assert connection.context() == {"a": 1, "b": 3, "c": 4}
    await connection.pop()
    assert connection.context() == {"a": 1, "b": 2}


async def test_connection_stack_setters(connection):
    await connection.set_context(a=1, b=2)
    await connection.push(b=3, c=4)
    assert connection.context() == {"a": 1, "b": 3, "c": 4}
    await connection.pop(d=5, a=6)
    assert connection.context() == {"a": 6, "b": 2, "d": 5}


async def test_connection_getitem(connection):
    await connection.set_context(a=1, b=2)
    assert connection["a"] == 1
    assert connection["d"] is None
