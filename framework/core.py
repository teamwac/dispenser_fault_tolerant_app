import asyncio
import logging

logger = logging.getLogger(__name__)

class AbstractService:
    """Anything with .run() and .name can be supervised."""
    def __init__(self, name):
        self.name = name
    
    async def run(self):
        raise NotImplementedError("Subclasses must implement run()")


class Worker(AbstractService):
    def __init__(self, name):
        super().__init__(name)
        self.queue = asyncio.Queue()
        self.running = True

    async def send(self, msg):
        await self.queue.put(msg)

    async def send_and_wait(self, msg):
        future = asyncio.Future()
        await self.queue.put((msg, future))
        response = await future
        return response

    async def run(self):
        logger.info(f"[{self.name}] started")
        while self.running:
            msg = await self.queue.get()
            try:
                await self.handle(msg)
                if isinstance(msg, tuple) and len(msg) == 2 and isinstance(msg[1], asyncio.Future):
                    if not msg[1].done():
                        msg[1].set_result({"status": "ok", "message": f"Task completed by {self.name}"})
            except Exception as e:
                logger.error(f"[{self.name}] crashed: {e}")
                if isinstance(msg, tuple) and len(msg) == 2 and isinstance(msg[1], asyncio.Future):
                    if not msg[1].done():
                         msg[1].set_exception(e)
                raise

    async def handle(self, msg):
        """Override in subclass"""
        raise NotImplementedError


async def supervisor(service: AbstractService):
    """Runs a service and restarts it if it crashes."""
    while True:
        try:
            await service.run()
        except Exception as e:
            logger.error(f"[Supervisor] {service.name} crashed: {e}. Restarting...")
            await asyncio.sleep(2)  # Delay before restart
        else:
            logger.warning(f"[Supervisor] {service.name} exited normally. It will not be restarted.")
            break