import os
from dotenv import load_dotenv

# load .env file to environment
load_dotenv()

#metatrader account id
METATRADER_ACCOUNT_ID = os.getenv("USERNAME")

METATRADER_PASSWORD = os.getenv("PASS") 

#metatrader broker server
METATRADER_BROKER_SERVER =  os.getenv("METATRADER_BROKER_SERVER")


#Time frame for the candlestick to form one candle
# TIME_FRAME = mt5.TIMEFRAME_H1;
# TIME_FRAME = mt5.TIMEFRAME_D1;




CURRENCIES = ['EURUSD','GBPUSD','USDJPY']
