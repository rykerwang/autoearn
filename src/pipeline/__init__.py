
from collections import defaultdict
from log import logger

class PipelineType:
    OPEN_ONLY = 'open'  # 开仓判断
    CLOSE_ONLY = 'close' # 平仓判断
    BOTH = 'both'       # 开仓和平仓判断

class ScorePipeline:

    def log(self, message):
        logger.info(f"{self.name}: {message}")

    def checktype(self, context):
        if self.type == PipelineType.OPEN_ONLY:
            if context.in_position:
                #self.log("Skip open pipeline as already in position")
                return False
        elif self.type == PipelineType.CLOSE_ONLY:
            if not context.in_position:
                #self.log("Skip close pipeline as not in position")
                return False
        else:
            #self.log("Both open and close pipeline")
            return True
        
        return True


class PipelineContext:
    def __init__(self, 
                 last_candles: list, 
                 current_candles: list,
                 in_position: str = None, 
                 position_stock: int = 0, 
                 entry_price: float= 0.0):
        
        self.last_candles = last_candles        # 已完成的历史K线数据
        self.current_candles = current_candles  # 当前K线数据
        self.in_position = in_position          # 是否持仓，long(做多中) or short(做空中)
        self.position_stock = position_stock
        self.entry_price = entry_price

        self.score = 0                          # 评分，用于评估交易信号, 评分越高, 信号越强, 操作时的量也会随之增加
        self.operation = None                   # 操作，long(做多) or short(做空) or None(不操作)
        self.skip = False                       # 是否跳过pipeline，当有pipeline计算到特别重要的操作时，可以设置为True, 这样后续的pipeline就不会执行, 将直接进入操作 
        

    def setSkipFlag(self):
        self.skip = True

    def isSkip(self):
        return self.skip

    def __str__(self):
        s = "\n"
        s += f"- Score: {self.score}\n"
        s += f"- In Position: {self.in_position}\n"
        s += f"- Position Stock: {self.position_stock}\n"
        s += f"- Entry Price: {self.entry_price}\n"
        s += f"- Last candel Count: {len(self.last_candles)}\n"
        s += f"- Current candel Count: {len(self.current_candles)}\n"
        return s


class PreparePipeline(ScorePipeline):
    def process(self, context):
        pass


def _invalid_config_type():
    raise RuntimeError("Invalid pipeline type")

class PipelineFactory():
    PIPELINES = defaultdict(_invalid_config_type)

def register_pipeline(config_type):
    def decorator(cls):
        PipelineFactory.PIPELINES[config_type] = cls
        cls.config_type = config_type
        return cls
    return decorator
    


# class DumpDataPipeline(ScorePipeline):
#     def process(self, context):
#         context.details = {
#             'score': context.score,
#             'in_position': context.in_position,
#             'position_stock': context.position_stock,
#             'entry_price': context.entry_price,
#             'current_candle_color': context.current_candle_color
#         }



class CalculateScorePipeline:
    def execute(self, context:PipelineContext) -> PipelineContext:
        PreparePipeline().process(context)
        for pipeline in PipelineFactory.PIPELINES.values():
            if context.isSkip():
                break
            p = pipeline()
            if p.checktype(context):
                p.process(context)
        

from .consecutive_candle import ConsecutiveCandlePipeline
from .current_candle import CurrentCandlePipeline




