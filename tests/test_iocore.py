import selectors
import socket
from contextlib import contextmanager
from unittest.mock import patch, Mock

import pytest

from redclay.iocore import Server


def stash_mock_key(target, attr_name):
    def _stash(fileobj, events, data):
        key = Mock(
            fileobj=fileobj, events=events, data=data
        )
        setattr(target, attr_name, key)
    return _stash


@contextmanager
def stashing_register(server, attr_name):
    server.selector.register.side_effect = stash_mock_key(
        server, attr_name
    )
    yield
    server.selector.register.side_effect = None


def init_test_server():
    with patch('selectors.DefaultSelector'):
        return Server()


def init_mock_listener(server):
    with \
        stashing_register(server, 'mock_listener_key'), \
        patch('socket.socket') \
    :
        server.start_listener()


def init_mock_connection(server):
    listener_key = server.mock_listener_key
    server.selector.select.return_value = [
        (listener_key, selectors.EVENT_READ)
    ]
    listener_key.fileobj.accept.return_value = Mock(), Mock()
    with stashing_register(server, 'mock_connection_key'):
        server.events()


@pytest.fixture
def listening_server():
    result = init_test_server()
    init_mock_listener(result)

    result.selector.reset_mock()
    return result


@pytest.fixture
def connected_server():
    result = init_test_server()
    init_mock_listener(result)
    init_mock_connection(result)

    result.selector.reset_mock()
    return result


@patch('selectors.DefaultSelector')
def test_server_creates_selector(mock_DefaultSelector):
    server = Server()
    assert mock_DefaultSelector.called
    assert server.selector is mock_DefaultSelector.return_value


@patch('selectors.DefaultSelector')
@patch('socket.socket')
def test_start_listener(mock_socket, mock_DefaultSelector):
    server = Server()
    server.start_listener()

    assert mock_socket.called
    assert server.selector.register.called
    (sock, events, _), _ = server.selector.register.call_args
    assert sock is mock_socket.return_value
    assert events == selectors.EVENT_READ
    sock.setsockopt.assert_called_with(
        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
    )
    sock.setblocking.assert_called_with(False)
    assert sock.bind.called
    assert sock.listen.called


@patch('selectors.DefaultSelector')
@patch('socket.socket')
def test_listener_socket_error(mock_socket, mock_DefaultSelector):
    mock_socket.side_effect = SystemError()

    server = Server()
    try:
        server.start_listener()
    except SystemError:
        pass  # intended behavior is to propagate this exception
    else:
        assert False  # expected exception to propagate


@patch('selectors.DefaultSelector')
@patch('socket.socket')
def test_listener_socket_config_error(mock_socket, mock_DefaultSelector):
    sock = mock_socket.return_value
    sock.bind.side_effect = SystemError()

    server = Server()
    try:
        server.start_listener()
    except SystemError:
        # intended behavior is to close the socket and propagate this
        # exception
        assert sock.close.called
    else:
        assert False  # expected exception to propagate


def test_new_peer_event(listening_server):
    selector = listening_server.selector
    listener_key = listening_server.mock_listener_key
    selector.select.return_value = [
        (listener_key, selectors.EVENT_READ)
    ]
    sock = listener_key.fileobj
    conn, address = sock.accept.return_value = Mock(), Mock()

    results = listening_server.events()

    conn.setblocking.assert_called_with(False)
    assert selector.register.called
    conn_key = selector.register.return_value
    (register_sock, register_events, _), _ = selector.register.call_args
    assert register_sock is conn
    assert register_events == selectors.EVENT_READ
    assert results == [
        Server.NewPeer(key=conn_key, address=address)
    ]


def test_select_error(listening_server):
    selector = listening_server.selector
    selector.select.side_effect = SystemError()

    try:
        results = listening_server.events()
    except SystemError:
        # intended behavior is to propagate the exception.
        pass
    else:
        assert False  # intended behavior is to propagate this exception


def test_accept_error(listening_server):
    selector = listening_server.selector
    listener_key = listening_server.mock_listener_key
    listener_key.fileobj.accept.side_effect = SystemError()
    selector.select.return_value = [
        (listener_key, selectors.EVENT_READ)
    ]

    results = listening_server.events()

    (result,) = results
    assert isinstance(result, Server.ListenerError)
    assert result.exc_type == SystemError


def test_connection_socket_config_error(listening_server):
    selector = listening_server.selector
    listener_key = listening_server.mock_listener_key
    selector.select.return_value = [
        (listener_key, selectors.EVENT_READ)
    ]
    sock = listener_key.fileobj
    conn, address = sock.accept.return_value = Mock(), Mock()
    conn.setblocking.side_effect = SystemError()

    results = listening_server.events()

    (result,) = results
    assert isinstance(result, Server.PeerInitError)
    assert conn.close.called
    assert result.address is address
    assert result.exc_type == SystemError


def test_peer_data_event(connected_server):
    TEST_BYTES = b'Hello, world!'
    selector = connected_server.selector
    connection_key = connected_server.mock_connection_key
    selector.select.return_value = [
        (connection_key, selectors.EVENT_READ)
    ]
    conn = connection_key.fileobj
    conn.recv.return_value = TEST_BYTES

    results = connected_server.events()

    assert not selector.unregister.called
    assert results == [
        Server.PeerData(key=connection_key, data=TEST_BYTES)
    ]


def test_peer_disconnect_event(connected_server):
    selector = connected_server.selector
    connection_key = connected_server.mock_connection_key
    selector.select.return_value = [
        (connection_key, selectors.EVENT_READ)
    ]
    conn = connection_key.fileobj
    conn.recv.return_value = b''

    results = connected_server.events()

    selector.unregister.assert_called_with(conn)
    conn.close.assert_called()

    assert results == [
        Server.PeerDisconnect(key=connection_key)
    ]


def test_peer_data_error(connected_server):
    selector = connected_server.selector
    connection_key = connected_server.mock_connection_key
    selector.select.return_value = [
        (connection_key, selectors.EVENT_READ)
    ]
    conn = connection_key.fileobj
    conn.recv.side_effect = SystemError()

    results = connected_server.events()

    (result,) = results
    assert isinstance(result, Server.PeerDataError)
    assert result.key is connection_key
    selector.unregister.assert_called_with(conn)
    conn.close.assert_called()
    assert result.exc_type == SystemError


def test_context_manager_closes():
    with \
        patch('selectors.DefaultSelector'), \
        Server() as server \
    :
        init_mock_listener(server)
        init_mock_connection(server)

        selector = server.selector
        listener_key = server.mock_listener_key
        connection_key = server.mock_connection_key.fileobj

        selector.get_map.return_value = {
            listener_key.fileobj: listener_key,
            connection_key.fileobj: connection_key,
        }


    listener_key.fileobj.close.assert_called()
    connection_key.fileobj.close.assert_called()
    selector.close.assert_called()
