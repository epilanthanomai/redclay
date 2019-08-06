import collections
import selectors
import socket
import sys


class Server:
    def __init__(self):
        self.selector = selectors.DefaultSelector()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        for sock in self.selector.get_map().keys():
            sock.close()
        self.selector.close()

    def start_listener(self):
        sock = socket.socket()
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setblocking(False)
            sock.bind(('', 6666))
            sock.listen(10)

            self.selector.register(
                sock,
                selectors.EVENT_READ,
                self.listener_io,
            )
        except:
            sock.close()
            raise

    def events(self):
        # NOTE We specifically want to return a list here, not a generator.
        # We want to make sure the io handler in key.data is called before
        # exiting this method. Many callers will handle these io events by
        # changing sending additional io updates to this server, and we want
        # the io handlers here representt the state before Cany of the
        # caller's handlers run.
        raw_results = self.selector.select()
        return [
            key.data(key, mask)
            for key, mask in raw_results
        ]

    def listener_io(self, key, mask):
        sock = key.fileobj
        try:
            conn, address = sock.accept()
        except:
            return self.ListenerError(*sys.exc_info())

        try:
            conn.setblocking(False)
        except:
            conn.close()
            return self.PeerInitError(address, *sys.exc_info())

        conn_key = self.selector.register(
            conn,
            selectors.EVENT_READ,
            self.connection_io,
        )

        return self.NewPeer(conn_key, address)

    def connection_io(self, key, mask):
        sock = key.fileobj
        try:
            data = sock.recv(4096)
        except:
            self.selector.unregister(sock)
            sock.close()
            return self.PeerDataError(key, *sys.exc_info())

        if data:
            return self.PeerData(key, data)
        else:
            self.selector.unregister(sock)
            sock.close()
            return self.PeerDisconnect(key)

    NewPeer = collections.namedtuple(
        'NewPeer', ['key', 'address']
    )

    ListenerError = collections.namedtuple(
        'ListenerError', ['exc_type', 'exc_value', 'exc_traceback']
    )

    PeerInitError = collections.namedtuple(
        'PeerInitError', [
            'address', 'exc_type', 'exc_value', 'exc_traceback'
        ]
    )

    PeerData = collections.namedtuple(
        'PeerData', ['key', 'data']
    )

    PeerDisconnect = collections.namedtuple(
        'PeerDisconnect', ['key']
    )

    PeerDataError = collections.namedtuple(
        'PeerDataError', [
            'key', 'exc_type', 'exc_value', 'exc_traceback'
        ]
    )
