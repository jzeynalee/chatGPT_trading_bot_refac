import asyncio
import logging
from dotenv import load_dotenv

from core.initialization import initialize_components, load_configuration
from core.message_handler import handle_message
from modules.trade_planner import TradePlanner
from modules.indicator import IndicatorCalculator
from utils.logger import setup_logger


async def run_bot() -> None:
    # Initialize all components and configuration
    config = load_configuration()
    components = initialize_components(config)

    # Set up WebSocket client with dependencies injected
    logger = components['logger']
    ws_client = components['websocket_client']
    trader = components['trader'] # kept for future use

    # Start the application
    logger.info(f"✅ Starting Trading Bot...")

    try:
        await ws_client.run()  # reconnect loop lives inside
    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        logger.info(f"✅ Received shutdown signal...")
    except Exception:
        logger.error("Fatal WS error in run_bot()!")
    finally:
        await ws_client.graceful_shutdown()
        logger.info("👋 Bot stopped cleanly.")


def main() -> None:
    """
    Sync wrapper for Windows/Python <3.11 compatibility.
    """
    try:
        asyncio.run(run_bot())
    except RuntimeError as e:
        # Fallback for environments where asyncio.run() is problematic
        logging.getLogger(__name__).warning("asyncio.run failed (%s); using manual loop.", e)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_bot())
        finally:
            # cancel remaining tasks
            pending = asyncio.all_tasks(loop=loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

if __name__ == "__main__":
    main()
