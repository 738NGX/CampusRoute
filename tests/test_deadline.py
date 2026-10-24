import asyncio
import time
import unittest

from campusroute.deadline import wait_for_reply


class DeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_arrives_before_deadline(self):
        operation = asyncio.create_task(asyncio.sleep(0.01, result=b'complete\n'))
        result, recovered = await wait_for_reply(operation, time.perf_counter() + 2)
        self.assertEqual(result, b'complete\n')
        self.assertFalse(recovered)

    async def test_expired_deadline_cancels_pending_operation(self):
        operation = asyncio.create_task(asyncio.sleep(10))
        with self.assertRaises(TimeoutError):
            await wait_for_reply(operation, time.perf_counter() - 1)
        self.assertTrue(operation.cancelled())

    async def test_external_cancellation_closes_pending_operation(self):
        operation = asyncio.create_task(asyncio.sleep(10))
        task = asyncio.create_task(wait_for_reply(operation, time.perf_counter() + 5))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(operation.cancelled())
