import asyncio
import time


async def wait_for_reply(awaitable, deadline, *, completed=None):
    operation = asyncio.ensure_future(awaitable)
    try:
        while True:
            if operation.done():
                result = operation.result()
                frame = completed() if completed else None
                if frame is not None and frame[1] > deadline:
                    raise TimeoutError('Android 回执在截止时间之后到达。')
                return result, False
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                # 处理已排队的通知，再核对完整回复的实际接收时间。
                await asyncio.sleep(0)
                if operation.done():
                    continue
                frame = completed() if completed else None
                if frame is not None and frame[1] <= deadline:
                    operation.cancel()
                    await asyncio.gather(operation, return_exceptions=True)
                    return frame[0], True
                raise TimeoutError('等待 Android 回执达到截止时间。')
            # 定时器可能提前唤醒，每次都重新核对高精度截止时间。
            await asyncio.wait({operation}, timeout=remaining)
    except BaseException:
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        raise
