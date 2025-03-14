from flask_restful import Resource, reqparse
from logger.MT5ApiLogger import MT5ApiLogger
from flask import jsonify

from service.MetatraderSocket import MT5_OBJ
fxstreetlogger = MT5ApiLogger()
logger = fxstreetlogger.get_logger(__name__)
socket = MT5_OBJ;

class Symbol(Resource):
    def get(self,symbol_name):
        symbol_info = socket.get_symbol_info(symbol_name)
        # Check if the symbol exists
        if symbol_info is None:
            return {"error": f"Symbol '{symbol_name}' not found"}, 404
        
        symbol_info_dict = {key: float(value) if isinstance(value, (int, float)) else str(value) 
                            for key, value in symbol_info._asdict().items()}
        return symbol_info_dict
        
        