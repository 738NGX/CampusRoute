import asyncio
from contextlib import asynccontextmanager
import unittest

from campusroute.socketbridge import open_socket_connection


class SocketBridgeTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def idle_connection(self):
        connected = asyncio.Event()
        finished = asyncio.Event()

        async def respond(reader, writer):
            connected.set()
            try:
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                finished.set()
        server = await asyncio.start_server(respond, '127.0.0.1', 0)
        reader, writer = await open_socket_connection('127.0.0.1', server.sockets[0].getsockname()[1])
        try:
            await asyncio.wait_for(connected.wait(), 2)
            yield reader, writer
        finally:
            writer.close()
            await writer.wait_closed()
            await asyncio.wait_for(finished.wait(), 2)
            server.close()
            await server.wait_closed()

    async def test_fragmented_lines_and_oversized_reply(self):
        async def respond(reader, writer):
            try:
                writer.write(b'first')
                await writer.drain()
                await asyncio.sleep(0.01)
                writer.write(b'\nsecond\n' + b'x' * 65)
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        server = await asyncio.start_server(respond, '127.0.0.1', 0)
        reader, writer = await open_socket_connection('127.0.0.1', server.sockets[0].getsockname()[1], limit=64)
        try:
            self.assertEqual(await reader.readline(), b'first\n')
            self.assertTrue(reader.diagnostic_snapshot(0)['read']['newline'])
            self.assertEqual(await reader.readline(), b'second\n')
            with self.assertRaises(ValueError):
                await reader.readline()
        finally:
            writer.close()
            await writer.wait_closed()
            server.close()
            await server.wait_closed()

    async def test_close_unblocks_pending_receive(self):
        for delay in (0, 0.001, 0.01):
            with self.subTest(delay=delay):
                async with self.idle_connection() as (reader, writer):
                    pending = asyncio.create_task(reader.readline())
                    await asyncio.sleep(delay)
                    writer.close()
                    self.assertEqual(await asyncio.wait_for(pending, 2), b'')
                    await writer.wait_closed()
                    self.assertTrue(reader.read_done.is_set())
                    self.assertEqual(reader.socket.fileno(), -1)
                    self.assertTrue(reader.read_trace['eof'])

    async def test_read_after_close_returns_eof(self):
        async with self.idle_connection() as (reader, writer):
            writer.close()
            self.assertEqual(await reader.readline(), b'')
            self.assertIsNone(reader.completed_frame())

    async def test_unexpected_socket_error_is_not_hidden(self):
        async with self.idle_connection() as (reader, writer):
            reader.socket.close()
            self.assertFalse(reader.closed)
            with self.assertRaises(OSError):
                await reader.readline()
