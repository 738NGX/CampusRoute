"""Bounded socket I/O in worker threads, independent of Windows IOCP streams."""

import asyncio
import socket
import threading
import time


class SocketStream:
    def __init__(self, connection: socket.socket, limit: int):
        self.socket = connection
        self.limit = limit
        self.pending = bytearray()
        self.buffer = bytearray()
        self.closed = False
        self.read_done = threading.Event()
        self.write_done = threading.Event()
        self.read_done.set()
        self.write_done.set()
        self.read_trace = {}
        self.write_trace = {}
        self._completed_frame = None

    @staticmethod
    def new_trace():
        return {'queued': time.perf_counter(), 'started': None, 'finished': None,
                'first_byte': None, 'last_byte': None, 'bytes': 0, 'chunks': 0,
                'line_bytes': 0, 'newline': False, 'eof': False, 'error': None}

    async def readline(self):
        trace = self.new_trace()
        self.read_trace = trace
        self._completed_frame = None

        def receive():
            self.read_done.clear()
            trace['started'] = time.perf_counter()
            try:
                while True:
                    newline = self.buffer.find(b'\n')
                    if newline >= 0:
                        if newline + 1 > self.limit:
                            raise ValueError('Android 回执超过长度限制。')
                        raw = bytes(self.buffer[:newline + 1])
                        del self.buffer[:newline + 1]
                        trace.update(line_bytes=len(raw), newline=True)
                        self._completed_frame = (raw, trace['last_byte'] or trace['started'])
                        return raw
                    if len(self.buffer) > self.limit:
                        raise ValueError('Android 回执超过长度限制。')
                    chunk = self.socket.recv(min(4096, self.limit + 1 - len(self.buffer)))
                    now = time.perf_counter()
                    if not chunk:
                        trace['eof'] = True
                        raw = bytes(self.buffer)
                        self.buffer.clear()
                        trace['line_bytes'] = len(raw)
                        return raw
                    if trace['first_byte'] is None:
                        trace['first_byte'] = now
                    trace['last_byte'] = now
                    trace['bytes'] += len(chunk)
                    trace['chunks'] += 1
                    self.buffer.extend(chunk)
            except BaseException as error:
                trace['error'] = self.error_code(error)
                raise
            finally:
                trace['finished'] = time.perf_counter()
                self.read_done.set()

        return await asyncio.to_thread(receive)

    def completed_frame(self):
        """Only a full frame for the current read; never expose it to diagnostics."""
        return self._completed_frame

    @staticmethod
    def error_code(error):
        return f'{type(error).__name__}(errno={getattr(error, "errno", None)}, winerror={getattr(error, "winerror", None)})'

    def write(self, data):
        if self.closed:
            raise ConnectionError('Android 连接已关闭。')
        if len(self.pending) + len(data) > self.limit:
            raise ValueError('Android 指令超过长度限制。')
        self.read_trace = {}
        self._completed_frame = None
        self.pending.extend(data)

    async def drain(self):
        payload = bytes(self.pending)
        self.pending.clear()
        trace = self.new_trace()
        self.write_trace = trace

        def send():
            self.write_done.clear()
            trace['started'] = time.perf_counter()
            try:
                self.socket.sendall(payload)
                trace['bytes'] = len(payload)
            except BaseException as error:
                trace['error'] = self.error_code(error)
                raise
            finally:
                trace['finished'] = time.perf_counter()
                self.write_done.set()

        await asyncio.to_thread(send)

    def diagnostic_snapshot(self, started_at):
        def snapshot(trace):
            result = dict(trace)
            for key in ('queued', 'started', 'finished', 'first_byte', 'last_byte'):
                value = result.get(key)
                result[key + '_ms'] = round((value - started_at) * 1000, 1) if value is not None else None
                result.pop(key, None)
            return result
        return {'transport': 'threaded-socket-v3', 'closed': self.closed,
                'read_active': not self.read_done.is_set(), 'write_active': not self.write_done.is_set(),
                'buffered_bytes': len(self.buffer), 'read': snapshot(self.read_trace), 'write': snapshot(self.write_trace)}

    def close(self):
        if self.closed:
            return
        self.closed = True
        # Cancellation of to_thread cannot interrupt recv itself. Shutdown wakes the
        # reader so cancellation cannot leave a worker blocked on recv.
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()

    async def wait_closed(self):
        for done in (self.read_done, self.write_done):
            if not done.is_set() and not await asyncio.to_thread(done.wait, 0.4):
                raise TimeoutError('Android socket 工作线程尚未退出。')


async def open_socket_connection(host: str, port: int, *, limit=8192, timeout=2):
    abandoned = threading.Event()
    guard = threading.Lock()
    opened = []

    def connect():
        connection = socket.create_connection((host, port), timeout=timeout)
        try:
            connection.settimeout(None)
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            stream = SocketStream(connection, limit)
        except BaseException:
            connection.close()
            raise
        with guard:
            if abandoned.is_set():
                stream.close()
                return None
            opened.append(stream)
        return stream

    try:
        stream = await asyncio.to_thread(connect)
    except BaseException:
        # A cancelled handshake may still finish connecting in its worker. Both
        # sides of that race close the newly opened socket instead of leaking it.
        with guard:
            abandoned.set()
            for stream in opened:
                stream.close()
        raise
    return stream, stream
