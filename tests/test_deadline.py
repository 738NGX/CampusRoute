import asyncio
import unittest
from unittest.mock import patch

from campusroute.deadline import wait_for_reply


class DeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_early_timer_does_not_cancel_pending_reply(self):
        reply = asyncio.get_running_loop().create_future()
        now = 0.0
        waits = []

        async def early_wait(tasks, *, timeout):
            nonlocal now
            self.assertIn(reply, tasks)
            waits.append(timeout)
            if len(waits) == 1:
                now = 2.985
                return set(), {reply}
            now = 2.99
            reply.set_result(b'complete\n')
            return {reply}, set()

        with patch('campusroute.deadline.asyncio.wait', early_wait):
            raw, recovered = await wait_for_reply(reply, 3, clock=lambda: now)
        self.assertEqual(raw, b'complete\n')
        self.assertFalse(recovered)
        self.assertEqual(len(waits), 2)
        self.assertAlmostEqual(waits[1], 0.015)
        self.assertFalse(reply.cancelled())

    async def test_completed_worker_result_wins_at_boundary(self):
        reply = asyncio.get_running_loop().create_future()
        raw, recovered = await wait_for_reply(reply, 3, clock=lambda: 3,
                                              completed=lambda: (b'on time\n', 2.985))
        self.assertEqual(raw, b'on time\n')
        self.assertTrue(recovered)
        self.assertTrue(reply.cancelled())

    async def test_actual_late_frame_is_rejected_even_if_future_is_ready(self):
        reply = asyncio.get_running_loop().create_future()
        reply.set_result(b'late\n')
        with self.assertRaises(TimeoutError):
            await wait_for_reply(reply, 3, clock=lambda: 3.01,
                                 completed=lambda: (b'late\n', 3.001))

    async def test_incomplete_or_late_worker_result_does_not_extend_deadline(self):
        for completed in (lambda: None, lambda: (b'late\n', 3.001)):
            reply = asyncio.get_running_loop().create_future()
            with self.assertRaises(TimeoutError):
                await wait_for_reply(reply, 3, clock=lambda: 3, completed=completed)
            self.assertTrue(reply.cancelled())

    async def test_external_cancellation_does_not_recover_or_restart_io(self):
        reply = asyncio.get_running_loop().create_future()
        task = asyncio.create_task(wait_for_reply(reply, 100, clock=lambda: 0))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(reply.cancelled())


if __name__ == '__main__':
    unittest.main()
