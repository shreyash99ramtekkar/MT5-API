from mt5linux import MetaTrader5
from constants.MetatraderConstants import METATRADER_ACCOUNT_ID
from constants.MetatraderConstants import METATRADER_BROKER_SERVER
from constants.MetatraderConstants import METATRADER_PASSWORD

from repository.TradeRepository import TradeRepository;
from logger.MT5ApiLogger import MT5ApiLogger
import os
import math
from time import sleep

from notifications.Telegram import Telegram;

telegram_obj = Telegram()

fxstreetlogger = MT5ApiLogger()
logger = fxstreetlogger.get_logger(__name__)

class MetatraderSocket:
    
    open_trades = {}
    
    def __init__(self):
        """Initialize the connections to MT5, SQL
        """
        self.tradedao = TradeRepository();
        logger.info(os.getenv("MT5_SERVER") + " port: "+ str(os.getenv("MT5_PORT")))
        # connecto to the server
        self.mt5 = MetaTrader5(
            host = os.getenv("MT5_SERVER"),
            port = os.getenv("MT5_PORT")
        ) 
        account_id = int(os.getenv('ACCOUNT_NO')) # Replace with your account number
        # print(type(account_id))
        password = os.getenv("PASS") # Replace with your password
        server = os.getenv("METATRADER_BROKER_SERVER") # Replace with your broker's server

        # use as you learned from: https://www.mql5.com/en/docs/integration/python_metatrader5/
        if not self.mt5.initialize(login=account_id,password=password,server=server):
            logger.error("initialize() failed, error code =",self.mt5.last_error())
            telegram_obj.sendMessage("Problem connecting to Metatrader5" + str(self.mt5.last_error()))
        self.mt5.terminal_info()
        
    def check_n_get_order_type(self,symbol,type_,price):
        """Check the current value is matching the telegram price if not return the buy limit or sell limit order type

        Args:
            symbol_info (_type_): Symbol info for the symbol
            type_ (_type_): Type of the telegram order
            price (_type_): Telegram price

        Returns:
            string: Type (BUY/SELL)
        """
        # # Number of pips (1 pip is typically 1, unless you need a smaller value, e.g., for precision)
        # if symbol_info.name == "GOLD":
        #     return type_;
        symbol_info = self.mt5.symbol_info(symbol)
        pips = 10
        if symbol_info.name == "GOLD":
            pips = 5
        # Calculate pip value from point
        pip_value = symbol_info.point * 10 * pips
        #print(symbol_info.name)
        
        # Get current bid/ask prices
        current_ask = symbol_info.ask
        current_bid = symbol_info.bid

        logger.info(f"Pip Value: {pip_value}")

        if type_ in ["BUY", "BUY NOW"]:
            if abs(price - current_ask) <= pip_value:
                logger.info(f"The price {current_ask} matches the Telegram price [{price}]: {type_}")
                return type_
            else:
                logger.info(f"The price [{current_ask}] doesn't match the Telegram price [{price}]: Limit Order BUY")
                return "BUY LIMIT"

        elif type_ in ["SELL", "SELL NOW"]:
            if abs(price - current_bid) <= pip_value:
                logger.info(f"The price {current_bid} matches the Telegram price [{price}]: {type_}")
                return type_
            else:
                logger.info(f"The price [{current_bid}] doesn't match the Telegram price [{price}]: Limit Order SELL")
                return "SELL LIMIT"

        logger.warning(f"Unknown order type received: {type_}")
        return type_  # Return original type if not recognized
    
    def create_trade(self,message):
        logger.info(f"Received message {message}")
        symbol = message['currency']
        action_ = None;
        if not self.mt5.symbol_select(symbol,True):
            logger.warning("symbol_select({}}) failed, exit" + symbol)
        symbol_info = self.mt5.symbol_info(symbol)
            
        type_ = message['trade_type']
        sl, tp, tp2, tp3, price = None, None, None, None, None
        # Required parameter already check in the request
        if message['sl'] is not None and message['tp1'] is not None and message['entry_price'] is not None:
            sl = float(message['sl'])
            tp = message['tp1']
            tp2 = float(message['tp2'])
            tp3 = float(message['tp3'])
            price = float(message['entry_price'])
            type_ = self.check_n_get_order_type(symbol,type_,price)
            
        #print(type_)
        # message['trade_type'] = type_
        # message['sl'] = str(sl)
        # message['tp1'] = str(tp)
        # message['tp2'] = str(tp2)
        # logger.debug(symbol_info.volume_min)
        lot = 0.03;   
        #lot = symbol_info.volume_min;   
        deviation = 10
        
        if "buy limit" in type_.lower():
            action_ = self.mt5.TRADE_ACTION_PENDING;
            type_ = self.mt5.ORDER_TYPE_BUY_LIMIT
        elif "buy now" in type_.lower() or "buy" in type_.lower():
            action_ = self.mt5.TRADE_ACTION_DEAL;
            type_ = self.mt5.ORDER_TYPE_BUY
            price = symbol_info.ask
        elif "sell limit" in type_.lower():
            action_ = self.mt5.TRADE_ACTION_PENDING;
            type_ = self.mt5.ORDER_TYPE_SELL_LIMIT
        elif "sell now" in type_.lower() or 'sell' in type_.lower():
            action_ = self.mt5.TRADE_ACTION_DEAL;
            type_ = self.mt5.ORDER_TYPE_SELL
            price = symbol_info.bid
        else:
            logger.warning("Type not valid please check the code");
            telegram_obj.sendMessage("Type not valid.")
            return
   
        if action_ is None:
            logger.warning("Action is None cannot proceed")
            return;
        telegram_obj.sendMessage(f"Currency: [{message['currency']}],price: {price}, type: [{type_}] SL: {sl}, TP: {tp} Action: {action_}" )
        # if the symbol is unavailable in MarketWatch, add it
       

        request = {
            "action": action_,
            "symbol": symbol,
            "volume": lot,
            "type": type_,
            "price": price,
            "deviation": deviation,
            "magic": 77777,
            "type_time": self.mt5.ORDER_TIME_DAY,
            "comment": message['channel']
            # "type_filling": self.mt5.ORDER_FILLING_IOC,
        }
        if sl is not None and tp is not None:
            request["sl"] = sl
            request["tp"] = tp3
            #Add more tp if you like
         
        logger.info("The request is ["+str(request)+"]")
        # send a trading request
        if (self.checkOldPosition()) or (self.checkOldPositionSymbol(symbol)) :
            return
        result = self.mt5.order_send(request)
        logger.info(f"The result from metatrader5 : {str(result)}")
        # check the execution result
        logger.info("1. order_send(): by {} {} lots at {} with deviation={} points".format(symbol,lot,price,deviation));
        if result.retcode == self.mt5.TRADE_RETCODE_DONE:
            logger.info("Processing the trade transaction into db")
            self.tradedao.process_trade_info(message,request,result)
            return result.order;
        elif result.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.error("2. order_send failed, retcode={}, Reason={}".format(result.retcode,result.comment))
            telegram_obj.sendMessage("Order failed..." + str(result.comment))
            # request the result as a dictionary and display it element by element
            result_dict=result._asdict()
            for field in result_dict.keys():
                # logger.error("   {}={}".format(field,result_dict[field]))
                # if this is a trading request structure, display it element by element as well
                if field=="request":
                    traderequest_dict=result_dict[field]._asdict()
                    logger.error(f"traderequest: {str(traderequest_dict)}")
                    # for tradereq_filed in traderequest_dict:
                    #     logger.error("traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))
        return None
                    
    def update_trade(self,message):
        """Update the existing trade which is matching the message
        
        Keyword arguments:
        message -- the existing trade info
        Return: return_description
        """
        updated = self.modify_trade(message['trade_id'],message['currency'],message['sl'],message['tp3'])
        if updated: 
            logger.info("Trade updated on the metatrader5")
            self.tradedao.update_trade_to_db(message)
            if message['trade_id'] in MetatraderSocket.open_trades:
                MetatraderSocket.open_trades.pop(message['trade_id'])
                logger.info('update the temp store')
            logger.info("Trade updated in the db")
        else:
            logger.info("Problem while updating trade with new sl/tps")
            
            
            
        
    def get_symbol_info(self,symbol):
        return self.mt5.symbol_info(symbol)

        
        
        
        

    def checkOldPositionSymbol(self,symbol):
        """Cheks the positions open for the specific symbol is above threshold value

        Args:
            symbol (_type_): Symbol(GOLD/GBPUSD)

        Returns:
            boolean: is above the threshold or not
        """
        threshold = 2
        orders=self.mt5.positions_get(symbol=symbol)
        if orders is None:
            logger.info("No orders on ["+ symbol +"] error code={}".format(self.mt5.last_error()))
            return False;
        else:
            logger.info("Open orders for the symbol " + symbol + " are " )
            for order in orders:
                logger.info(order)
            if len(orders)<threshold:
                logger.info(f"Open orders on currency [{symbol}] are [{len(orders)}] which is less than Threshold [{threshold}]")
                return False;
            logger.warning("Already open position on the symbol")
            logger.info(f"Total orders on [{symbol}] : {str(len(orders))} which is more than Threshold [{threshold}]")
            telegram_obj.sendMessage(f"Total orders on [{symbol}] : {str(len(orders))} which is more than Threshold [{threshold}]. Please take the action on the open orders")
        return True;

    def checkOldPosition(self):
        """Cheks all open positions is above threshold value

        Returns:
            boolean: above threshold or not
        """
        threshold = 10
        orders=self.mt5.positions_get()
        if orders is None:
            logger.info("No open orders error code={}".format(self.mt5.last_error()))
            return False;
        else:
            logger.info("Open orders are " )
            for order in orders:
                logger.info(order)
            if len(orders)>=threshold:
                logger.info(f"Open orders are [{len(orders)}] which is more than Threshold [{threshold}]")
                telegram_obj.sendMessage(f"Total orders : {str(len(orders))} which is more than Threshold [{threshold}]. Please take the action on the open orders")
                return True;
            else:
                return False

    def monitor_close_half_update_tp(self):
        """Monitor the open trades, Close half of the open positions and update the tp to new tp"""
        
        # Monitor trades and perform updates
        while True:
            positions = self.mt5.positions_get()
            if positions is None:
                logger.info("No open positions or error:", self.mt5.last_error())
                continue
            
            for position in positions:
                # Extract trade details
                ticket = position.ticket
                symbol = position.symbol
                entry_price = position.price_open
                volume = position.volume
                comment = position.comment
                tp3 = position.tp
                sl = position.sl
                tp1 = None
                type_ = position.type
                if ticket not in MetatraderSocket.open_trades:
                    trade = self.tradedao.get_trade_by_trade_ticket(ticket)
                    if trade is not None:
                       MetatraderSocket.open_trades[trade.ticket]=trade
                       
                if ticket in MetatraderSocket.open_trades:
                    tp1 = MetatraderSocket.open_trades[ticket].take_profit1
                    tp2 = MetatraderSocket.open_trades[ticket].take_profit2
                    tp3 = MetatraderSocket.open_trades[ticket].take_profit3
                    
                    
                if tp1 is None or sl == tp1:
                    continue;

                # Current market price
                current_price = self.mt5.symbol_info_tick(symbol).bid if position.type == self.mt5.ORDER_TYPE_SELL else self.mt5.symbol_info_tick(symbol).ask
                # logger.info(f"The open position [{ticket}] of symbol [{symbol}]  of  type {type_} is having difference of {round(abs(current_price - tp1),5)} pips. Current price: [{current_price}] tp1: [{tp1}]")
                logger.info(f"The open position [{ticket}] of symbol [{symbol}]  of  type {type_} . Current price: [{current_price}] tp1: [{tp1}] tp2: [{tp2}] tp3: [{tp3}]")
                # Check if the price is approaching TP1 (within 2-3 pips)
                #0 - buy
                #1 - sell
                if sl != entry_price and ((type_ == 0 and current_price >= tp1) or (type_ == 1 and current_price <= tp1)):   # Assuming 5-digit broker, adjust as needed
                    # Move SL to entry price and TP to TP2
                    updated = self.modify_trade(ticket,symbol, new_sl=entry_price, new_tp=tp3)
                    if updated:
                        # Close half the position
                        self.close_position(ticket, symbol, type_, volume)
                      # Check if the price is approaching TP2
                elif (type_ == 0 and current_price >= tp2) or (type_ == 1 and current_price <= tp2):
                    # Move SL to TP1 and TP to TP3
                    # updated = self.modify_trade(ticket, symbol, new_sl=tp1, new_tp=tp3)
                    # if updated:
                        # Close half the position
                    self.close_position(ticket, symbol, type_, volume)
            
            logger.debug("Sleeping for 2 seconds")
            sleep(2)  # Avoid overloading the terminal

   

    def is_float(self,string):
        try:
        # Return true if float
            float(string)
            return True
        except ValueError:
        # Return False if Error
            return False

    def modify_trade(self,ticket,symbol, new_sl, new_tp):
        request = {
            "action": self.mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_sl,
            "tp": new_tp
        }
        logger.info(f"The modify request is {str(request)}")
        result = self.mt5.order_send(request)
        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.info(f"Failed to modify trade {ticket}: {result.comment} : {str(self.mt5.last_error())}")
            telegram_obj.sendMessage(f"Failed to modify trade {ticket} with symbol {symbol}: {result.comment}")
            return False
        else:
            logger.info(f"Trade {ticket} modified: SL={new_sl}, TP={new_tp}")
            telegram_obj.sendMessage(f"Trade {ticket} modified for symbol [{symbol}]: SL={new_sl}, TP={new_tp}")
            return True

    # Close half of the trade volume
    def close_position(self,ticket, symbol, position_type, volume,full_close=False):
        # MetaTrader 5 minimum lot size (typically 0.01, but can vary by broker)
        MIN_VOLUME = 0.01
        if full_close:
            MIN_VOLUME = volume;
        

        # If the current volume is the minimum, close the entire position
        if volume <= MIN_VOLUME:
            logger.info(f"Full close Flag(partial/close order recived): {full_close}. Volume {volume} is too small to close half. Closing the entire position.")
            half_volume = volume  # Close the full position
        else:
            # Calculate half volume and ensure it's at least MIN_VOLUME
            half_volume = max(round(volume / 3,2), MIN_VOLUME)

         # Determine the counter-order type
        counter_order_type = self.mt5.ORDER_TYPE_BUY if position_type == self.mt5.ORDER_TYPE_SELL else self.mt5.ORDER_TYPE_SELL

        # Calculate the price based on the counter-order type
        price = self.mt5.symbol_info_tick(symbol).ask if counter_order_type == self.mt5.ORDER_TYPE_BUY else self.mt5.symbol_info_tick(symbol).bid

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": half_volume,
            "type": counter_order_type,
            "position": ticket,
            "price": price,
            "deviation": 10,
        }
        result = self.mt5.order_send(request)
        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.info(f"Failed to close half of the trade {ticket}: {result.comment}")
        else:
            logger.info(f"Half of the currency [{symbol}] trade {ticket} closed: {half_volume}")
    
    def close_trade(self,order_id):
        """_summary_

        Args:
            order_id (_type_): _description_
        """
        status = True
        orders = self.mt5.orders_get(ticket=order_id) 
        if orders is None or len(orders) == 0:
            orders = self.mt5.positions_get(ticket=order_id)
        if orders is None or len(orders) == 0:
            logger.error(f"Order with ticket ID {order_id} not found.")
            return
        for order in orders:
            logger.info(f"Found the order on mt5 : {str(order)}")
            if self.check_pending_order(order):
                logger.info(f"Pending order for order id {order_id}. Deleting the order")
                self.close_pending_order(order_id)
            else:
                if order.type == self.mt5.ORDER_TYPE_BUY and order.sl >= order.price_open:
                    logger.info(f"The sl is greater than the open price. So not closing the order {order_id}")
                    status = False
                    continue
                elif order.type == self.mt5.ORDER_TYPE_SELL and order.sl <= order.price_open:
                    logger.info(f"The sl is less than the open price. So not closing the order {order_id}")
                    status = False
                    continue
                new_sl = self.calculate_new_sl(order.symbol,order.price_open,order.type)
                logger.info(f"New SL is {new_sl}")
                self.modify_trade(order_id, order.symbol, new_sl, order.tp)
                # 
                # self.close_position(order_id,order.symbol,order.type,order.volume,True)
        return status
            
    def calculate_new_sl(self, symbol, price_open, order_type,risk_pips=30):
        """Calculate the new SL based on the risk in pips.

        Args:
            price_open (float): The opening price of the order.
            risk_pips (int): The number of pips to set the SL away from the opening price.
            order_type (int): The type of the order (0 for BUY, 1 for SELL).

        Returns:
            float: The new SL price.
        """
        pip_value = self.mt5.symbol_info(symbol).point * 10
        if order_type == self.mt5.ORDER_TYPE_BUY:
            logger.info(f"Calculating new SL for BUY order: {price_open} - ({risk_pips} * {pip_value})")
            new_sl = price_open - (risk_pips * pip_value)
        else:
            logger.info(f"Calculating new SL for SELL order: {price_open} + ({risk_pips} * {pip_value})")
            new_sl = price_open + (risk_pips * pip_value)
        return new_sl
        
    
    def close_pending_order(self,order_id):
        """
        Cancel a pending order (e.g., BUY LIMIT, SELL LIMIT).
        
        :param order_id: The ticket ID of the pending order to cancel.
        """
        request = {
            "action": self.mt5.TRADE_ACTION_REMOVE,  # Action to cancel the pending order
            "order": order_id,  # The ticket ID of the pending order
        }
        result = self.mt5.order_send(request)

        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.info(f"Failed to cancel pending order {order_id}: {result.comment}")
            return False
        else:
            logger.info(f"Pending order {order_id} canceled successfully.")
            return True
        
    def check_pending_order(self,order):
        # Check if the order is a pending order based on the order type
        if order.type in [self.mt5.ORDER_TYPE_BUY_LIMIT, self.mt5.ORDER_TYPE_SELL_LIMIT,
                        self.mt5.ORDER_TYPE_BUY_STOP, self.mt5.ORDER_TYPE_SELL_STOP]:
            logger.info(f"Order {order.ticket} is a pending order.")
            return True
        return False
    

    
    
    def close_connection(self):
        self.mt5.shutdown()
        
        
MT5_OBJ = MetatraderSocket()
