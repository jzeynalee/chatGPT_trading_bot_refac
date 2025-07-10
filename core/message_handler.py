
async def handle_message(data, df_store, order_books):
    
     if 'ticker' in data.get('subscribe', ''):
        
        symbol = data['subscribe'].split('.')[-1]
        
        from core.signal_handler import process_tick_data
        
        try:
            await process_tick_data(data, symbol, df_store)
            
            from core.tick_handler import check_signals
            
            check_signals()
            
        except Exception as e:
            logger.error(f"[DATA HANDLER ERROR] {symbol}: {e}")
