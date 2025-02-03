from flask_restful import Resource, reqparse
from datetime import datetime

from logger.MT5ApiLogger import MT5ApiLogger
from service.MetatraderSocket import MetatraderSocket;

fxstreetlogger = MT5ApiLogger()
logger = fxstreetlogger.get_logger(__name__)
socket = MetatraderSocket();

add_trade_parser = reqparse.RequestParser(bundle_errors=True)
add_trade_parser.add_argument("currency",type=str,required=True)
add_trade_parser.add_argument("trade_type",type=str, required = True,choices=("BUY","SELL","BUY LIMIT", "SELL LIMIT"),help="Invalid Trade type : {error_msg}")
# add_trade_parser.add_argument("entry_price",type=float,dest="price")
add_trade_parser.add_argument("entry_price",type=float)
add_trade_parser.add_argument("sl",type=float)
add_trade_parser.add_argument("tp1",type=float)
add_trade_parser.add_argument("tp2",type=float)
add_trade_parser.add_argument("time", type=str,required = True,help="Time should be sent in string")


class Trade(Resource):
    def get(self,name):
        logger.info("Get method called")
        df = socket.get_rates()
        return {"message":f"hello {df}"}
    
    def post(self):
        args = add_trade_parser.parse_args()
        socket.create_trade(args)
        return {"message": f'Trade recived successfully {str(args)}'}
    
    def put(self):
        args = add_trade_parser.parse_args()
        socket.update_trade(args)
        return {"message": f'Trade update request recived successfully {str(args)}'}
    
    def delete(self):
        return {'message': "This is a response to a DELETE request"}