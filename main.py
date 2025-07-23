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
    #ws_client.set_message_callback(handle_message)

    trader = components['trader']
    symbol_data_provider = components['data_provider']
    trade_planner = TradePlanner()

    # Start the application
    logger.info("🔄 Starting Trading Bot...")

    while True:
        try:
            await ws_client.connect()                
            # If we get here, it means the connection was closed gracefully or max retries reached
            if not ws_client.is_running or ws_client.max_retries_reached():
                break

            cleanup_successful = False
            while not cleanup_successful:
                cleanup_successful = await ws_client.graceful_shutdown()
                break

        except KeyboardInterrupt:
            logger.info("🛑 Received shutdown signal...")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break

        # Example hook for SL/TP planning after signal detection
        # Replace this section with your actual signal routing logic
        try:
            signal = components.get("latest_signal")
            if signal:
                symbol = signal['symbol']
                entry_price = signal['entry']
                timeframes = ['15m', '1h', '4h']

                data_by_tf = {}
                for tf in timeframes:
                    df = symbol_data_provider.get_ohlcv(symbol, tf)
                    df = IndicatorCalculator(df).add_swing_points().calculate_ma(50).df
                    data_by_tf[tf] = df

                fib_levels = {}

                sl_tp_plan = trade_planner.generate_sl_tp_plan(
                    entry_price=entry_price,
                    symbol=symbol,
                    data_by_timeframe=data_by_tf,
                    fib_levels=fib_levels
                )

                best_plan = trade_planner.select_best_sl_tp(sl_tp_plan)

                if 'error' not in best_plan:
                    sl = best_plan['sl']
                    tp = best_plan['tp']
                    logger.info(f"✅ Executing trade for {symbol} with SL: {sl}, TP: {tp} using method {best_plan['method']}")
                    trader.place_order(symbol=symbol, entry=entry_price, sl=sl, tp=tp)
                else:
                    logger.warning(f"No valid SL/TP plan found for {symbol}. Trade skipped.")
        except Exception as e:
            logger.error(f"Failed to plan trade: {e}")

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
