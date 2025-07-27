import asyncio
import os
from dotenv import load_dotenv
import pandas as pd

from core.initialization import initialize_components, load_configuration
from core.message_handler import handle_message
from modules.trade_planner import TradePlanner
from modules.indicator import IndicatorCalculator
from utils.logger import setup_logger

# Load environment variables
load_dotenv(dotenv_path="config.env")

# Setup logger
logger = setup_logger(__name__)

async def run_bot() -> None:
    # Initialize all components and configuration
    config = load_configuration()
    components = initialize_components(config)

    # Set up WebSocket client with dependencies injected
    ws_client = components['websocket_client']
    trader = components['trader']
    symbol_data_provider = components['data_provider']
    trade_planner = TradePlanner()

    # Start the application
    logger.info(f"✅ Starting Trading Bot...")

    try:
        await ws_client.run() 
    except KeyboardInterrupt:
        logger.info(f"✅ Received shutdown signal...")
    except Exception:
        logger.error("Fatal WS error in run_bot()!")
    finally:
        await ws_client.graceful_shutdown()


def main() -> None:
    """Main entry point for the application - pure orchestration."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(run_bot())
    finally:   
        # Gather all pending tasks and cancel them properly
        pending = asyncio.all_tasks(loop=loop)
        if pending:
            # Use gather for better error handling
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        loop.close()

if __name__ == "__main__":
    main()
