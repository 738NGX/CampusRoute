"""Wait for a reply without cancelling it on an early asyncio timer callback."""

import asyncio
import time


async def wait_for_reply(awaitable, deadline, *, completed=None, clock=None):
    """Return (reply, boundary_recovered); retain one operation and a strict deadline.

    completed() optionally exposes a worker's (full_frame, perf_counter_timestamp).
    This lets an on-time frame win even if its Future notification is still queued.
    """
    clock = clock or time.perf_counter
    operation = asyncio.ensure_future(awaitable)
    try:
        while True:
            if operation.done():
                result = operation.result()
                frame = completed() if completed else None
                if frame is not None and frame[1] > deadline:
                    raise TimeoutError('Android 回执在截止时间之后到达。')
                return result, False
            remaining = deadline - clock()
            if remaining <= 0:
                # Drain notifications already queued by the worker before looking
                # at its independently timestamped result. Do not start a new read.
                await asyncio.sleep(0)
                if operation.done():
                    continue
                frame = completed() if completed else None
                if frame is not None and frame[1] <= deadline:
                    operation.cancel()
                    await asyncio.gather(operation, return_exceptions=True)
                    return frame[0], True
                raise TimeoutError('等待 Android 回执达到截止时间。')
            # wait() does not cancel the I/O. Windows timers may wake one clock
            # tick early; always recheck the high-resolution clock after waking.
            await asyncio.wait({operation}, timeout=remaining)
    except BaseException:
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        raise
