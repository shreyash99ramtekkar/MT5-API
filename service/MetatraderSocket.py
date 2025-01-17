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
    def __init__(self):
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

        

    def get_rates(self):
        df = self.mt5.copy_rates_from_pos('EURUSD',self.mt5.TIMEFRAME_M30,0,1000)
        # ...
        # don't forget to shutdown
        return df

    def check_n_get_order_type(self,symbol_info,type_,price):
        """Check the prices from the vip channel match the symbol current price .if not then its a limit order"""
        if (type_ == "BUY" or type_ == "BUY NOW"):
        # if (type_ == "BUY" or type_ == "BUY NOW") and  math.floor(price) != math.floor(symbol_info.ask):
            logger.info(f"The price [{math.floor(symbol_info.ask)}] doesn't match the telegram price [{math.floor(price)}]: Limit Order BUY")
            return "BUY LIMIT"
        elif (type_ == "SELL" or type_ == "SELL NOW"):
        # elif (type_ == "SELL" or type_ == "SELL NOW") and  math.floor(price) != math.floor(symbol_info.bid):
            logger.info(f"The price [{math.floor(symbol_info.bid)}] doesn't match the telegram price [{math.floor(price)}]: Limit Order SELL")
            return "SELL LIMIT"
        logger.info(f"The price match the telegram price [{price}]: {type_}")
        telegram_obj.sendMessage(f"The order type is: [{type_}]")
        return type_;
 
    def sendOrder(self,message):
        symbol = message['currency']
        type_ = message['trade_type']
        sl = float(message['sl'])
        tp = float(message['tp1'])
        tp2 = float(message['tp2'])
        action_ = None;
        pips = 10
        price = float(message['entry_price'])
        if len(symbol) == 0 or len(type_) == 0 or sl is None or tp is None or price is None:
            logger.warning("Cannot proceed. The trade info not sufficient to make a trade")
            return;
        
        symbol_info = self.mt5.symbol_info(symbol)
        if symbol == "GOLD":
            pips = 20
        point = symbol_info.point  * 10 * pips
        if "BUY" == type_:
            price = price - point
            sl = sl - point
            tp = tp - point
            tp2 = tp2 - point
        elif "SELL" == type_:
            price = price + point
            sl = sl + point
            tp = tp + point
            tp2 = tp2 + point
        logger.info(f"Changing immidiate order to pending order for currency:{symbol} type:{type_} , price: {price}, sl = {sl}, tp = {tp}, tp2 ={tp2}")

        type_ = self.check_n_get_order_type(symbol_info,type_,price)
        message['trade_type'] = type_
        message['sl'] = str(sl)
        message['tp1'] = str(tp)
        message['tp2'] = str(tp2)
        logger.debug(symbol_info.volume_min)
        lot = 0.02;   
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
        telegram_obj.sendMessage(f"Currency: [{message['currency']}], type: [{type_}] SL: {sl}, TP: {tp} Action: {action_}" )
        # if the symbol is unavailable in MarketWatch, add it
        if not symbol_info.visible:
            logger.info(symbol+ "is not visible, trying to switch on")
            if not self.mt5.symbol_select(symbol,True):
                logger.warning("symbol_select({}}) failed, exit" + symbol)

        request = {
            "action": action_,
            "symbol": symbol,
            "volume": lot,
            "type": type_,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": deviation,
            "magic": 77777,
            "comment": str(tp2),
            "type_time": self.mt5.ORDER_TIME_GTC
            # "type_filling": self.mt5.ORDER_FILLING_IOC,
        }
        
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

    def checkOldPositionSymbol(self,symbol):
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
        threshold = 3
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
                tp1 = position.tp
                type_ = position.type
                if self.is_float(comment):
                    tp2 = float(comment)
                else:
                    continue;

                # Current market price
                current_price = self.mt5.symbol_info_tick(symbol).bid if position.type == self.mt5.ORDER_TYPE_SELL else self.mt5.symbol_info_tick(symbol).ask
                logger.info(f"The open position [{ticket}] of symbol [{symbol}]  of  type {type_} is having difference of {abs(current_price - tp1)} pips. Current price: [{current_price}] tp1: [{tp1}]")
                # Check if the price is approaching TP1 (within 2-3 pips)

                if abs(current_price - tp1) <= self.get_tolarance(symbol):  # Assuming 5-digit broker, adjust as needed
                    # Move SL to entry price and TP to TP2
                    self.modify_trade(ticket,symbol, new_sl=entry_price, new_tp=tp2)
                    # Close half the position
                    self.close_position(ticket, symbol, type_, volume)
            logger.debug("Sleeping for 5 seconds")
            sleep(2)  # Avoid overloading the terminal

    def get_tolarance(self,symbol):
        usd_factor=1
        if "USD" in symbol:
            usd_factor = 4
        if symbol == "GOLD" or symbol =="XAUUSD":
            return 0.10 * usd_factor
        elif "JPY" in symbol:
            return 0.005 * usd_factor
        return 0.00005 * usd_factor

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
            "tp": new_tp,
        }
        logger.info(f"The modify request is {str(request)}")
        result = self.mt5.order_send(request)
        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.info(f"Failed to modify trade {ticket}: {result.comment}")
        else:
            logger.info(f"Trade {ticket} modified: SL={new_sl}, TP={new_tp}")
            telegram_obj.sendMessage(f"Trade {ticket} modified for symbol [{symbol}]: SL={new_sl}, TP={new_tp}")

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
            half_volume = max(volume / 2, MIN_VOLUME)

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
    
    def close_trade(self,trade_info):
        ticket_id = self.tradedao.get_trade_by_trade_info(trade_info)
        if ticket_id:
            logger.info(f"The trade that matches the trade info description is having ticket id {ticket_id}")
            orders = self.mt5.orders_get(ticket=ticket_id) 
            if orders is None or len(orders) == 0:
                orders = self.mt5.positions_get(ticket=ticket_id)
            if orders is None or len(orders) == 0:
                logger.error(f"Order with ticket ID {ticket_id} not found.")
                return
            for order in orders:
                logger.info(f"Found the order on mt5 : {str(order)}")
                if self.check_pending_order(order):
                    self.close_pending_order(ticket_id)
                else:
                    self.close_position(ticket_id,trade_info['currency'],order.type,order.volume,True)
        else:
            logger.info(f"Trade not found in db for the trade info: {str(trade_info)}")
            
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
    
    def test(self):
         point = self.mt5.symbol_info("GOLD").point *10*50
         print(point)
    
    def close_connection(self):
        self.mt5.shutdown()