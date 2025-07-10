'''
project/
├── config/
│   └── config.json
├── core/
│   ├── __init__.py
│   ├── signal_handler.py
│   ├── tick_handler.py
│   ├── message_handler.py
│   └── initialization.py
├── modules/
│   ├── websocket_client_real_time.py
│   ├── indicator.py
│   ├── strategy.py
│   ├── trader.py
│   └── signalChecker.py
├── notifiers/
│   └── SignalDispatcher.py
├── utils/
│   └── logger.py
├── main.py
└── signals.csv
'''
import asyncio

from core.initialization import initialize_components, load_configuration
from core.message_handler import handle_message

def main() -> None:
    """Main entry point for the application - pure orchestration."""
    # Initialize all components and configuration
    
    config = load_configuration()
    components = initialize_components(config)
    
    # Set up WebSocket client with dependencies injected
    
    ws_client = components['websocket_client']
    ws_client.set_message_callback(handle_message)
    
    # Start the application
    
    components['logger'].info("🔄 Starting Trading Bot...")
    asyncio.run(ws_client.connect())

if __name__ == "__main__":
    main()
