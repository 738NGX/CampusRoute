import asyncio
import io
import threading
import unittest
from unittest.mock import patch

from campusroute.socketbridge import open_socket_connection


class SocketBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_connect_closes_socket_that_opens_later(self):
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        class Connection:
            def settimeout(self, _):
                pass
            def setsockopt(self, *_):
                pass
            def makefile(self, _):
                return io.BytesIO()
            def shutdown(self, _):
                pass
            def close(self):
                closed.set()
        def delayed_connect(*_, **__):
            entered.set()
            release.wait(2)
            return Connection()
        with patch('campusroute.socketbridge.socket.create_connection', delayed_connect):
            operation = asyncio.create_task(open_socket_connection('127.0.0.1', 1))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 1))
                operation.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await operation
            finally:
                release.set()
            self.assertTrue(await asyncio.to_thread(closed.wait, 1))

    async def test_fragmented_lines_and_oversized_reply(self):
        async def respond(reader, writer):
            try:
                writer.write(b'{"id":')
                await writer.drain()
                await asyncio.sleep(0.01)
                writer.write(b'1}\nsecond\n' + b'x' * 65)
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        server = await asyncio.start_server(respond, '127.0.0.1', 0)
        reader, writer = await open_socket_connection('127.0.0.1', server.sockets[0].getsockname()[1], limit=64)
        try:
            self.assertEqual(await reader.readline(), b'{"id":1}\n')
            snapshot = reader.diagnostic_snapshot(0)
            self.assertTrue(snapshot['read']['newline'])
            self.assertEqual(snapshot['read']['line_bytes'], len(b'{"id":1}\n'))
            self.assertGreater(snapshot['read']['chunks'], 0)
            self.assertNotIn('{"id":1}', str(snapshot))
            self.assertEqual(await reader.readline(), b'second\n')
            with self.assertRaisesRegex(ValueError, '长度限制'):
                await reader.readline()
        finally:
            writer.close()
            await writer.wait_closed()
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    unittest.main()
