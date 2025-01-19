import asyncio,json
from log import logger
from okx.websocket.WsPublicAsync import WsPublicAsync
from okx.websocket.WsPrivateAsync import WsPrivateAsync
from websockets.exceptions import ConnectionClosedError
import warnings

class PublicClient:
    def __init__(self, url, subscriptions, callback):
        self.url = url
        self.ws_public_async = WsPublicAsync(url=url)
        self.subscriptions = subscriptions
        self.callback = callback
        self.loop = asyncio.get_event_loop()
        self.loop.set_exception_handler(self.handle_exception)

    def handle_exception(self, loop, context):
        exception = context.get('exception')
        if isinstance(exception, ConnectionClosedError):
            logger.error(f"Connection closed with error: {exception}. Reconnecting...")
            self.loop.create_task(self.handle_disconnection())
        else:
            logger.error(f"Unhandled exception: {context}")

    async def subscribe(self, params, callback):
        self.callback = callback
        self.subscriptions = params
        await self.ws_public_async.start()
        await self.ws_public_async.subscribe(params, callback)

    async def handle_disconnection(self):
        logger.info("Connection lost. Reconnecting...")
        await self.ws_public_async.stop()
        await asyncio.sleep(2)
        await self.ws_public_async.start()
        await self.resubscribe()

    async def resubscribe(self):
        if self.subscriptions:
            logger.info("Resubscribing to active channels...")
            await self.ws_public_async.subscribe(self.subscriptions, self.callback)

    def stop(self):
        if self.loop.is_running():
            self.loop.run_until_complete(self.ws_public_async.stop())
            tasks = asyncio.all_tasks(self.loop)
            for task in tasks:
                task.cancel()
            self.loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

    def run(self):
        try:
            self.loop.run_until_complete(self.run_client())
        except KeyboardInterrupt:
            logger.info("Received exit signal. Closing WebSocket client...")
        except RuntimeError as e:
            logger.error(f"Runtime error: {e}")
        finally:
            self.stop()
            if not self.loop.is_closed():
                self.loop.close()

    async def run_client(self):
        while True:
            try:
                await self.subscribe(self.subscriptions, self.callback)
                await asyncio.Future()  # Keep the client running until interrupted
            except ConnectionClosedError as e:
                logger.error(f"Connection closed with error: {e}. Reconnecting...")
                await self.handle_disconnection()
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break



class PrivateClient(WsPrivateAsync):
    def __init__(self, url, apiKey, passphrase, secretKey):
        super().__init__(url=url, apiKey=apiKey, passphrase=passphrase, secretKey=secretKey, useServerTime=True)

    """
market：市价单
limit：限价单
post_only：只做maker单
ioc：立即成交并取消剩余

tdMode:
保证金模式
isolated：逐仓 ；cross：全仓
    """
    async def place_market_order(self, ordId, instId, side, sz, callback):
        self.callback = callback
        await self.connect()
        logRes = await self.login()
        await asyncio.sleep(5)
        if logRes:
            payload = json.dumps({
                "op": "order",
                "args": [
                    {
                    "instId": instId,
                    "tdMode": "isolated",
                    "clOrdId": ordId,
                    "side": side,
                    "ordType": "market",
                    "sz": sz
                    }
                ]
            })
            await self.websocket.send(payload)
        # await self.consume()

    
    def place_order(self, ordId, instId, side, sz, callback):
        self.loop.run_until_complete(self.place_market_order(ordId, instId, side, sz, callback))