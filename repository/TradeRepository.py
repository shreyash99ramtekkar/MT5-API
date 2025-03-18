from sqlalchemy import create_engine;
from sqlalchemy.orm import sessionmaker
from constants.Constants import DATABASE_URL;
from constants.Constants import BASE;
from sqlalchemy import select
from model.Trade import Trade
from sqlalchemy.exc import SQLAlchemyError

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

    def save_trade_to_db(self,ticket_id,symbol, trade_type, entry_price, stop_loss, tp1, tp2,tp3, volume,action,message_time, telegram_message=None):
        trade = Trade(
            ticket = ticket_id,
            symbol=symbol,
            action=action,
            trade_type=trade_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit1=tp1,
            take_profit2=tp2,
            take_profit3=tp3,
            volume=volume,
            telegram_message=telegram_message,
            timestamp=message_time
        )
        session = self.Session()  # Manually create session
        try:
            session.add(trade)
            session.commit()
            logger.info(f"Trade {ticket_id} saved successfully!")  
        except SQLAlchemyError as e:
            session.rollback()  # Safe rollback, session is still open
            logger.error(f"Failed to save trade {ticket_id}: {e}")
        finally:
            session.close()  # # Rollback in case of error
        logger.info("Trade saved successfully!")
        
    def update_trade_to_db(self,trade_info):
        session = self.Session()  # Manually create session
        try:
            trade = session.query(Trade).filter_by(ticket=trade_info['trade_id']).first()
            if not trade:
                logger.error(f"Trade {trade_info['trade_id']} not found")
                return {"error": "Trade not found"}
            # Update only the provided fields
            if "sl" in trade_info:
                trade.stop_loss = trade_info["sl"]
            if "tp1" in trade_info:
                trade.take_profit1 = trade_info["tp1"]
            if "tp2" in trade_info:
                trade.take_profit2 = trade_info["tp2"]
            trade.telegram_message= str(trade_info)
            session.commit()  # Save changes to DB
            logger.info(f"Trade {trade_info['trade_id']} updated successfully!")

        except SQLAlchemyError as e:
            session.rollback()  # Safe rollback, session is still open
            logger.error(f"Failed to save trade {trade_info['trade_id']}: {e}")
        finally:
            session.close()  # # Rollback in case of error
    def process_trade_info(self,message,request,result):
        self.save_trade_to_db(result.order,
                              self.validate_key('symbol',request),
                              self.validate_key('type',request),
                              self.validate_key('price',request),
                              self.validate_key('sl',request),
                              self.validate_key('tp1',message),
                              self.validate_key('tp2',message),
                              self.validate_key('tp3',message),
                              self.validate_key('volume',request),
                              self.validate_key('action',request),
                              message['time'],
                              str(message))
        
        
    def validate_key(self,key,request):
        if key in request:
            return request[key]
        return None
    
    def get_trade_by_trade_info(self, trade_info):
        """
        Retrieve a trade based on the given trade information.

        :param trade_info: dict containing trade details.
        :return: Trade ticket (ID) or None if not found.
        """
        with self.Session() as session:
            stmt = (
                select(Trade)
                .where(Trade.timestamp == trade_info["time"])
                .where(Trade.symbol == trade_info["currency"])
                .where(Trade.stop_loss == trade_info["sl"])
                .where(Trade.take_profit1 == trade_info["tp1"])
                .where(Trade.take_profit2 == trade_info["tp2"])  # Exact match
            )

            trade = session.execute(stmt).scalars().first()  # Extract result
        
        return trade.ticket if trade else None
        
    def get_trade_by_trade_ticket(self, ticket_id):
        """Fetch a trade by its ticket ID only if SL, TP1, and TP2 are NOT NULL.

        Args:
            ticket_id (int): The trade ticket ID.

        Returns:
            Trade object or None
        """
        with self.Session() as session:  # Ensure session is correctly managed
            stmt = (
                select(Trade)
                .where(Trade.ticket == ticket_id)
                .where(Trade.stop_loss.is_not(None))  # SQLAlchemy 2.0 uses is_not()
                .where(Trade.take_profit1.is_not(None))
            )

            result = session.execute(stmt).scalars().first()  # Extract result
        return result  # Return trade object or None
        
        