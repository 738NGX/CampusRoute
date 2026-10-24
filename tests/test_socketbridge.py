import asyncio
import unittest

from campusroute.socketbridge import open_socket_connection


class SocketBridgeTests(unittest.IsolatedAsyncioTestCase):
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
        async def respond(reader, writer):
            try:
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
        server = await asyncio.start_server(respond, '127.0.0.1', 0)
        reader, writer = await open_socket_connection('127.0.0.1', server.sockets[0].getsockname()[1])
        try:
            pending = asyncio.create_task(reader.readline())
            await asyncio.sleep(0.01)
            writer.close()
            self.assertEqual(await asyncio.wait_for(pending, 2), b'')
            await writer.wait_closed()
        finally:
            writer.close()
            server.close()
            await server.wait_closed()
