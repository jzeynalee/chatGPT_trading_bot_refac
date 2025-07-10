
async def process_tick_data(data, symbol, df_store):
    
     tf = "1min"  # Can be made dynamic if needed
    
     tick_price = float(data['tick']['latest'])
     ts = datetime.utcfromtimestamp(data['ts'] / 1000)
     
     df = df_store[symbol][tf]
     
     if df['timestamp'].iloc[-1] < ts:
         
         new_row = df.iloc[-1].copy()
         new_row.update({
             'timestamp': ts,
             'close_price': tick_price 
         })
         
         df_store[symbol][tf] = update_dataframe(df, new_row)
         
         processed_df = calculate_indicators(df)
         
         signal = detect_signal(processed_df, symbol, tick_price)
         
         if signal: 
             await handle_new_signal(signal)

def update_dataframe(df, new_row):
    
     updated_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True) 
     
     return updated_df.iloc[-100:]  # Keep last 100 rows only


def calculate_indicators(df): 
    
     from modules.indicator import IndicatorCalculator 
     
     return (
         IndicatorCalculator(df)
            .calculate_macd()
            .calculate_ichimoku()
            .get_df() 
      )

def detect_signal(df, symbol, price): 
    
      from modules.strategy import IchimokuDayStrategy  
      
      result = IchimokuDayStrategy(df)  
      
      if result:  
          return {
              "symbol": symbol,
              "entry": price,
              "direction": result  
          }

async def handle_new_signal(signal):  
      
      atr_value = calculate_atr(signal)  
      
      trade_plan = create_trade_plan(signal, atr_value)  
      
      await execute_trade(trade_plan)  
      
      log_trade(trade_plan)

# ... helper functions ...
