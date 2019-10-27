import asyncio

import pytest
from asynctest import CoroutineMock, Mock, patch

import redclay.game
import redclay.server
from redclay.server import ConnectionServer, Connection, async_run_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def connection():
    terminal = Mock()
    return Connection(terminal)


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

    await async_run_server()

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
        redclay.game.run_shell, reader, writer
    )


@patch("redclay.server.Terminal")
@patch("redclay.server.logging_context", wraps=redclay.logging.logging_context)
@patch("redclay.server.Connection")
async def test_handle_connection(MockConnection, mock_logging_context, MockTerminal):
    run_shell = CoroutineMock()
    reader = Mock()
    writer = Mock()
    mock_terminal = MockTerminal.return_value
    mock_terminal.__aenter__.return_value = mock_terminal
    mock_connection = MockConnection.return_value

    conn_server = ConnectionServer()
    await conn_server.handle_connection(run_shell, reader, writer)

    MockTerminal.assert_called_once_with(reader, writer)
    mock_logging_context.assert_called_once_with(term=id(mock_terminal))
    MockConnection.assert_called_once_with(mock_terminal)
    run_shell.assert_called_once_with(mock_connection)


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
