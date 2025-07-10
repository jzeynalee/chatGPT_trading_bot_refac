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

async def run_bot() -> None:
    # Initialize all components and configuration
    
    config = load_configuration()
    components = initialize_components(config)
    
    # Set up WebSocket client with dependencies injected
    
    ws_client = components['websocket_client']
    ws_client.set_message_callback(handle_message)
    
    # Start the application
    
    components['logger'].info("🔄 Starting Trading Bot...")

    while True:
        try:
            await ws_client.connect()                
            # If we get here, it means the connection was closed gracefully or max retries reached
            if not ws_client.is_running or ws_client.max_retries_reached():
                break           
            
            # Ensure all cleanup happens even during keyboard interrupt  
            cleanup_successful=False  
            while not cleanup_successful:     
                cleanup_successful=await ws_client.graceful_shutdown()    
                break 
            
        except KeyboardInterrupt:
            components['logger'].info("🛑 Received shutdown signal...")        
        except Exception as e:
            components['logger'].error(f"Unexpected error: {e}")
            break  # Exit on unexpected errors

def main() -> None:
    """Main entry point for the application - pure orchestration."""
    loop=asyncio.new_event_loop()  
    asyncio.set_event_loop(loop)  

    try :     
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
