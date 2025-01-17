from sqlalchemy import create_engine;
from sqlalchemy.orm import sessionmaker

from constants.Constants import DATABASE_URL;
from constants.Constants import BASE;

from model.Trade import Trade


from logger.MT5ApiLogger import MT5ApiLogger

fxstreetlogger = MT5ApiLogger()
logger = fxstreetlogger.get_logger(__name__)


class TradeRepository:

    def __init__(self):
        engine = create_engine(DATABASE_URL,pool_pre_ping=True,pool_recycle=3600)
        Session = sessionmaker(bind=engine)
        # Create tables
        self.Session = Session
        BASE.metadata.create_all(engine)
        logger.info("Tables created successfully");

    def save_trade_to_db(self,ticket_id,symbol, trade_type, entry_price, stop_loss, tp1, tp2, volume,action,message_time, telegram_message=None):
        trade = Trade(
            ticket = ticket_id,
            symbol=symbol,
            action=action,
            trade_type=trade_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit1=tp1,
            take_profit2=tp2,
            volume=volume,
            telegram_message=telegram_message,
            timestamp=message_time
        )
        with self.Session() as session:
            session.add(trade)
            session.commit()
        logger.info("Trade saved successfully!")
        
    def process_trade_info(self,message,request,result):
        self.save_trade_to_db(result.order,request['symbol'],request['type'],request['price'],request['sl'],request['tp'],message['tp2'],request['volume'],request['action'],message['time'],str(message))
        
    def get_trade_by_trade_info(self, trade_info):
            """
            Retrieve trades according to the trade info
            :param trade_info: dict
            :return: Trade object or None if not found
            """
            with self.Session() as session:
                trade = (
                    session.query(Trade)
                    .filter(Trade.timestamp == trade_info['time'])
                    .filter(Trade.symbol == trade_info['currency'])
                    .filter(Trade.stop_loss == trade_info['sl'])
                    .filter(Trade.take_profit1 == trade_info['tp1'])
                    .filter(Trade.take_profit2 == trade_info['tp2'])# Exact match
                    .first()  # Get the first trade that matches
                )
            return trade.ticket if trade else None