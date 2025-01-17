from flask import Flask
from flask_restful import  Api
from logger.MT5ApiLogger import MT5ApiLogger
from controller.Trade import Trade
import threading;
from service.MetatraderSocket import MetatraderSocket


fxstreetlogger = MT5ApiLogger()
logger = fxstreetlogger.get_logger(__name__)

socket = MetatraderSocket()

app = Flask(__name__)
app.config['BUNDLE_ERRORS'] = True
api = Api(app)


    
    
api.add_resource(Trade,'/trade')
def start_monitoring():
    monitor_thread = threading.Thread(target=socket.monitor_close_half_update_tp, name="OpenPositionMonitor")
    monitor_thread.daemon = True  # Allows the thread to exit when the main program does
    monitor_thread.start()
    logger.info("Monitoring thread started.")
    socket.test()
    

with app.app_context():
    start_monitoring()
    
if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0")
    
