from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Enum
from  constants.Constants import BASE;
from sqlalchemy.orm import relationship
from datetime import datetime


# Trade Table with Telegram message included
class Trade(BASE):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket = Column(Integer, nullable=False, index=True)
    symbol = Column(String(10), nullable=False)
    action = Column(Integer, nullable=False)
    trade_type = Column(Integer, nullable=False)  # Using MT5 trade type numbers
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit1 = Column(Float, nullable=True)
    take_profit2 = Column(Float, nullable=True)
    volume = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    result = Column(Float, nullable=True)
    telegram_message = Column(Text, nullable=False)  # Store the Telegram message content directly
