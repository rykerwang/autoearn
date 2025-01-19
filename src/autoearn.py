from abc import ABC, abstractmethod
import asyncio    
import json
from common import dict2str
from database import Database, Operation
from log import logger
from wsclient import PublicClient,PrivateClient
from pipeline import CalculateScorePipeline, PipelineContext
from datetime import datetime, timezone, timedelta
from restfulclient import RestfulClient
import yaml
import os


class OperationType:
    BUY = 1
    SELL = 0
    


class AccountConfig:
    
    def __init__(self, api_key:str, api_secret_key:str, passphrase:str, flag:str):
        self.api_key = api_key
        self.api_secret_key = api_secret_key
        self.passphrase = passphrase
        self.flag = flag


class TradeConfig:

    def __init__(self, inst, balance, runtime, candle_interval='5m'):
        self.inst = inst
        self.balance = balance
        self.runtime = runtime
        self.candle_interval = candle_interval

class DebugConfig:
    def __init__(self, debug, datafile):
        self.debug = debug
        self.datafile = datafile

class Candle:

    COLOR_GREEN = 'green'
    COLOR_RED = 'red'
    COLOR_DOJI = 'doji'

    def __init__(self, timestamp:int, open:float, high:float, low:float, close:float, isfinish:bool):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.isfinish = isfinish

    @staticmethod
    def from_json(json_data):
        return Candle(json_data['timestamp'], json_data['open'], json_data['high'], json_data['low'], json_data['close'], json_data['isfinish'])

    def __str__(self):
        return f"Timestamp: {self.timestamp}, Open: {self.open}, High: {self.high}, Low: {self.low}, Close: {self.close}, Isfinish: {self.isfinish}, Color: {self.color}, Percent change: {self.percent_change:.4f}%"

    @staticmethod
    def from_data(data):
        [timestamp, _open, high, low, close, isfinish] = data
        timestamp = int(timestamp)
        _open = float(_open)
        high = float(high)
        low = float(low)
        close = float(close)
        return Candle(timestamp, _open, high, low, close, isfinish == '1')

    @property
    def color(self):
        if self.close > self.open:
            return Candle.COLOR_GREEN
        elif self.close < self.open:
            return Candle.COLOR_RED
        else:
            return Candle.COLOR_DOJI
        
    @property
    def percent_change(self):
        return (self.close - self.open) / self.open * 100
    

class OrderInfo:
    def __init__(self, ordId, clOrdId, instId, side, avgPx, fillSz, utime):
        self.ordId = ordId
        self.clOrdId = clOrdId
        self.instId = instId
        self.px = avgPx
        self.sz = fillSz
        self.side = side
        self.utime = utime

    @staticmethod
    def fromOrderData(json_data):
        return OrderInfo(json_data['ordId'], 
                         json_data['clOrdId'], 
                         json_data['instId'], 
                         json_data['side'], 
                         float(json_data['avgPx']), 
                         float(json_data['accFillSz']),
                         int(json_data['uTime']))
    
    def __str__(self):
        szStr = "%.8f" % self.sz
        return f"Order ID: {self.ordId}, Client Order ID: {self.clOrdId}, Instrument ID: {self.instId}, Side: {self.side}, Average Price: {self.px}, Size: {szStr}, Update Time: {self.utime}"


class AutoEarn(object):

    @staticmethod
    def from_config(config_path):

        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            account_config = config.get("account", {})
            trade_config = config.get("trade", {})
            debug_config = config.get("debug", {})
            account = AccountConfig(account_config.get("api_key"), account_config.get("api_secret_key"), account_config.get("passphrase"), str(account_config.get("flag")))
            trade = TradeConfig(trade_config.get("inst"), trade_config.get("balance"), trade_config.get("runtime",-1),candle_interval=trade_config.get("candle_interval", "5m"))
            debug = DebugConfig(debug_config.get("debug", False), debug_config.get("datafile"))
        return AutoEarn(account, trade, debug)


    def __init__(self, account_config: AccountConfig, trade_config: TradeConfig, debug_config: DebugConfig):
        self.id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.account_config = account_config
        self.trade_config = trade_config
        self.debug_config = debug_config
        
        if self.debug_config and self.debug_config.debug:
            self.db = Database("sqlite:///autoearn.db")
        else:
            self.db = Database("postgresql+psycopg2://autoearn:autoearn@localhost/autoearn")

        self.last_candles: list[Candle] = []  # To store the last 30 candles
        self.current_candles: list[Candle] = []
        self.available_balance = int(trade_config.balance)  # Available funds for trading
        self.position_stock = 0  # Quantity of stocks in the current position
        self.in_position = None  # Track whether we are in a position ('long' or 'short')
        self.entry_price = 0  # Price at which we entered the position
        self.profit_percentage = 0  # Current profit percentage
        # self.stop_loss_pct = -5  # Stop loss percentage (e.g., -5%)
        # self.take_profit_pct = 10  # Take profit percentage (e.g., 10%)

        self.score_pipeline = CalculateScorePipeline()
        self.restful_client = RestfulClient(account_config.api_key, account_config.api_secret_key, account_config.passphrase, account_config.flag)
        

    def set_candles(self, candles):
        self.last_candles = candles

    def __str__(self):
        return f"Available balance: {self.available_balance}\nIn position: {self.in_position}\nEntry price: {self.entry_price}\nProfit percentage: {self.profit_percentage}\n"

    def dump(self):
        return {
            'available_balance': self.available_balance,
            'in_position': self.in_position,
            'entry_price': self.entry_price,
            'profit_percentage': self.profit_percentage
        }


    def parseData(self, message):
        if self.debug_config and self.debug_config.debug:
            pass
        else:
            with open(f"testdata/data-{self.id}", "a") as f:
                f.write(message)
                f.write("\n")


        parsed_data = json.loads(message)
        if "data" not in parsed_data:
            return
        if len(parsed_data['data']) == 0:
            return
        [timestamp, _open, high, low, close, isfinish] = parsed_data['data'][0]
        # Remove the oldest candle if we have more than 30
        if len(self.last_candles) > 30:
            self.last_candles.pop(0)

        # Make a decision only when the candle is finished
        candle = Candle.from_data([timestamp, _open, high, low, close, isfinish])
        
        if candle.isfinish:
            #logger.info("Last candle: %s", candle)
            #logger.info(self.last_candles)
            self.last_candles.append(candle)
            self.current_candles = []
        else:
            #logger.info("Current candle: %s", candle)
            self.current_candles.append(candle)
        
        self.makeDecision()
           

    def makeDecision(self):
        op, score = self.calculateScore()
        if not op:
            logger.debug("No trade operation. skip")
            return

        if self.in_position:
            if op:
                self.exitPosition()
        else:
            if score:
                if len(self.current_candles) > 0:
                    current_close = self.current_candles[-1].close
                else:
                    current_close = self.last_candles[-1].close
                # Buy conditions (Long position)
                if self.available_balance > 0:
                    self.buy(current_close, score)
                # Sell conditions (Short position)
                elif self.available_balance > 0:
                    self.sell(current_close, score)
                else:
                    logger.info("No trade made. with score: %s", score)
            


    def calculateScore(self):
        context = PipelineContext(
            self.last_candles, 
            self.current_candles,
            self.in_position, 
            self.position_stock, 
            self.entry_price)
        self.score_pipeline.execute(context)
        #logger.info(context)
        return context.operation, context.score

    
    def operation(self, side, quantity=None):
        if quantity is None:
            quantity = self.position_stock
        message = f"{side} {quantity} USDT {self.trade_config.inst}"
        logger.debug("message %s" % message)
        if self.debug_config and self.debug_config.debug:
            with open(f"testdata/op-{self.id}", "a") as f:
                f.write(message+"\n")
        else:
            orderInfo = self.place_order(side, quantity)
            logger.debug("order info %s" % orderInfo)
            op = Operation()
            op.insid = self.trade_config.inst
            op.side = OperationType.BUY if side == "buy" else OperationType.SELL
            op.price = orderInfo.px
            op.quantity = orderInfo.sz
            op.available_balance = self.available_balance + float(orderInfo.sz) * float(orderInfo.px)
            self.db.insert_operation(op)

        return orderInfo

        


    def place_order(self, side, quantity): #side: buy or sell quantity=USDT
        clOrderId = f"{side}%s" % datetime.now().strftime("%Y%m%d%H%M%S")
        logger.info("place order %s %s %s %.8f" % (clOrderId, self.trade_config.inst, side, quantity))
        quantity_str = "%.8f" % quantity
        result = self.restful_client.place_order(clOrderId, self.trade_config.inst, side, quantity_str)
        logger.info("result %s" % result)
        ordId = result['data'][0]['ordId']

        if not ordId:
            logger.error("Failed to place order, error code: %s, error message: %s" % (result['data'][0]['sCode'], result['data'][0]['sMsg']))
            return None 
        
        order_info = self.restful_client.get_order(self.trade_config.inst, ordId = ordId, clOrdId = clOrderId)
        #logger.info("order info %s" % order_info)
        return OrderInfo.fromOrderData(order_info['data'][0])

    def get_account_balance(self):
        res = self.restful_client.accountAPI().get_account_balance()
        if res['code'] == '0':
            return res['data'][0]['details']
        else:
            logger.error("Failed to get account balance, error code: %s, error message: %s" % (res['code'], res['msg']))
            return None
    
    def get_account_total_USD(self):
        balance_info = self.get_account_balance()
        total = 0
        for item in balance_info:
            total += float(item['eqUsd'])
        return total

    
    def get_account_config(self):
        return self.restful_client.accountAPI().get_account_config()
    
    
    def buy(self, current_close_price, score):
        if self.available_balance <= 0: #没有资金了
            return
        
        if self.in_position and self.in_position == "long": #已经持仓了
            return

        if not self.in_position:
            if score >= 1:
                buy_quantity = int(self.available_balance)
            else:
                buy_quantity = int(self.available_balance * score)

            self.available_balance -= buy_quantity
            self.in_position = "long"
            logger.info("Opened long position")
            try:
                orderInfo = self.operation("buy", buy_quantity)
                self.position_stock = orderInfo.sz
                self.entry_price = orderInfo.px
            except Exception as e:
                logger.error("Failed to open long position: %s" % e)
                return

        else: #in position and in short position
            logger.info("Closed short position")
            try:
                orderInfo = self.operation("buy") #close short position
                self.position_stock = 0
                self.entry_price = 0
            except Exception as e:
                logger.error("Failed to close short position: %s" % e)
                return
            
            
        #self.operation(f"Bought {buy_quantity} stocks for {buy_amount:.4f}$. Remaining balance: {self.available_balance:.4f}, Position stock: {self.position_stock}, Price: {current_close_price}")

    def sell(self, current_close_price, score):
        if self.available_balance <= 0:
            return
        
        if self.in_position and self.in_position == "short": #已经持仓了
            return
        
        if not self.in_position:
            if score >= 1:
                sell_quantity = int(self.available_balance)
            else:
                sell_quantity = int(self.available_balance * score)
        
            self.available_balance += sell_quantity
            self.in_position = "short"
            logger.info("Opened short position")
            try:
                orderInfo = self.operation("sell", sell_quantity)
                self.position_stock = orderInfo.sz
                self.entry_price = orderInfo.px
            except Exception as e:
                logger.error("Failed to open short position: %s" % e)
                return
        else:
            logger.info("Closed long position in sell")
            try:
                orderInfo = self.operation("sell") #close long position
                self.position_stock = 0
                self.entry_price = 0
            except Exception as e:
                logger.error("Failed to close long position: %s" % e)
                return

        #self.operation(f"Sold {sell_quantity} stocks for {sell_amount:.4f}$. Remaining balance: {self.available_balance:.4f}, Position stock: {self.position_stock}, Price: {current_close_price}")

    def exitPosition(self):
        if self.in_position == "short":  # Close short position
            # Calculate total cost to close short position
            logger.info("Closed short position")
            try:
                self.in_position = None
                self.position_stock = 0
                self.entry_price = 0
                orderInfo = self.operation("buy", self.position_stock)
            except Exception as e:
                logger.error("Failed to close short position: %s" % e)
                return

            #self.operation(f"Bought {self.position_stock} stocks for {buy_amount:.4f}$. Remaining balance: {self.available_balance:.4f}, Position stock: {self.position_stock}, Price: {current_close_price}")
        
        elif self.in_position == "long":  # Close long position
            # Calculate total revenue from selling stocks
            logger.debug("Closed long position")
            try:
                self.in_position = None
                self.position_stock = 0
                self.entry_price = 0
                self.operation("sell", self.position_stock)
            except Exception as e:
                logger.error("Failed to close long position: %s" % e)
                return

            #self.operation(f"Sold {self.position_stock} stocks for {sell_amount:.4f}$. Remaining balance: {self.available_balance:.4f}, Position stock: {self.position_stock}, Price: {current_close_price}")

    def check_account(self):
        ca = self.restful_client.accountAPI().get_account_balance()
        logger.info(ca)
        return ca['data'][0]['details']

    def start(self):
        #self.check_account()

        if self.debug_config and self.debug_config.debug and self.debug_config.datafile:
            logger.info("Reading data from file %s" % self.debug_config.datafile)
            with open(self.debug_config.datafile, "r") as f:
                for line in f:
                    self.parseData(line)
        else:
            puburl = "wss://wspap.okx.com:8443/ws/v5/business"
            args = {"channel": "index-candle%s" % self.trade_config.candle_interval, "instId": self.trade_config.inst}
            logger.info("Starting Connect Public WS...")
            logger.info("Parameters:\n%s", dict2str(args))
            pub_client = PublicClient(puburl, [args], self.parseData)
            pub_client.run()


    def testMakedecision(self):
        data = [
            {'timestamp': '1733925600000', 'open': 0.272302, 'high': 0.272775, 'low': 0.269947, 'close': 0.270027},
            {'timestamp': '1733925900000', 'open': 0.270029, 'high': 0.270313, 'low': 0.268241, 'close': 0.268363},
            {'timestamp': '1733926200000', 'open': 0.268376, 'high': 0.268855, 'low': 0.266881, 'close': 0.267855},
            {'timestamp': '1733926500000', 'open': 0.267841, 'high': 0.268992, 'low': 0.267366, 'close': 0.271784},
        ]
        self.set_candles(data)
        score = self.makeDecision()
        logger.info(score)


    def testParseData(self):
        message = '{"arg":{"channel":"index-candle15m","instId":"OL-USDT"},"data":[["1734787800000","0.231277","0.234458","0.228937","0.233068","1"]]}'
        self.parseData(message)


    def testBuy(self):
        self.buy(0.233068, 10)