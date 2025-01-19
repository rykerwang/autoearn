from log import logger
from okx import Account,TradingData,Trade


class RestfulClient:

    def __init__(self, apikey, secretkey, passphrase, flag='1'):
        self.apikey = apikey
        self.secretkey = secretkey
        self.passphrase = passphrase
        self.flag = flag
        logger.info(f"Creating RestfulClient with apikey: {apikey}, secretkey: {secretkey}, passphrase: {passphrase}, flag: {flag}")

        self.AccountAPI = None
        self.TradingDataAPI = None
        self.TradeApi = None

    def tradeDataAPI(self):
        if self.TradingDataAPI is None:
            self.TradingDataAPI = Trade.TradingDataAPI(self.apikey, self.secretkey, self.passphrase, use_server_time=False, flag=self.flag, debug='False')
        return self.TradingDataAPI


    def accountAPI(self):
        if self.AccountAPI is None:
            #logger.info("Creating AccountAPI, with apikey: {self.apikey}, secretkey: {self.secretkey}, passphrase: {self.passphrase}, flag: {self.flag}")
            self.AccountAPI = Account.AccountAPI(self.apikey, self.secretkey, self.passphrase, flag=self.flag, debug='False')
        return self.AccountAPI
    
    def tradeAPI(self):
        if self.TradeApi is None:
            self.TradeApi = Trade.TradeAPI(self.apikey, self.secretkey, self.passphrase, flag=self.flag, debug='False')
        return self.TradeApi
    

    def place_order(self, orderId, instId, side, sz, attachAlgoOrds=None):
        logger.info(f"Placing order[{orderId}] for {sz} {instId} {side}")
        result = self.tradeAPI().place_order(
            clOrdId=orderId,
            instId=instId, 
            side=side, 
            sz="%s" % sz,
            tdMode="cash", 
            ordType="market")
        return result
    
    def get_order(self, instId, ordId, clOrdId):
        result = self.tradeAPI().get_order(instId, ordId = ordId, clOrdId=clOrdId)
        return result
        

    def close(self):
        if self.TradeApi is not None:
            self.TradeApi.close()

        if self.AccountAPI is not None:
            self.AccountAPI.close()
        
        if self.TradingDataAPI is not None:
            self.TradingDataAPI.close()


    def __del__(self):
        self.close()
