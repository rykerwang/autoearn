import yaml
from . import register_pipeline
from . import ScorePipeline, PipelineContext, PipelineType
from log import logger


@register_pipeline('consecutive_candle')
class ConsecutiveCandlePipeline(ScorePipeline):
    """
    ConsecutiveCandlePipeline 类处理一系列蜡烛图数据，以评估和评分基于连续相反的蜡烛图模式。
    方法:
        处理包含蜡烛图数据的给定上下文。它检查上下文中是否至少有3根蜡烛。
        然后，它以相反的顺序迭代蜡烛，以计算连续相反蜡烛的数量和累计百分比变化。
        如果有3根或更多连续相反的蜡烛，它会根据连续相反蜡烛的数量和累计百分比变化增加上下文中的分数。
    """
    """
    ConsecutiveCandlePipeline is a class that processes a series of candlestick data to evaluate and score based on consecutive opposite candle patterns.
    Methods:
        process(context: PipelineContext):
            Processes the given context containing candlestick data. It checks for a minimum of 3 candles in the context. 
            It then iterates through the candles in reverse order to count consecutive opposite candles and calculate the cumulative percentage change.
            If there are 3 or more consecutive opposite candles, it increments the score in the context based on the number of consecutive opposite candles and the cumulative percentage change.
    """

    DEFAULT_CUMULATIVE_CANDLE_COUNT = 3

    def __init__(self):
        self.name = 'ConsecutiveCandlePipeline'
        self.type = PipelineType.OPEN_ONLY
        self.cumulative_candle_count = ConsecutiveCandlePipeline.DEFAULT_CUMULATIVE_CANDLE_COUNT
        config_path = __file__.replace('.py', '.yaml')
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            self.cumulative_candle_count = config.get('pipeline.cumulative_candle_count', 3)
        
        logger.debug(str(self))

    def __str__(self):
        return f"ConsecutiveCandlePipeline(cumulative_candle_count={self.cumulative_candle_count})"
    
    def process(self, context: PipelineContext):
        if len(context.last_candles) < self.cumulative_candle_count:
            #self.log("Not enough candles to process")
            return
        
        consecutive_opposite = 0
        cumulative_change = 0

        #取context.last_candles的最后self.cumulative_candle_count个
        # for c in context.last_candles[-self.cumulative_candle_count:]:
        #     self.log(f"Last candles: {c}")
        
        for i in range(-2, -len(context.last_candles)-1, -1):
            prev_candle = context.last_candles[i]
            prev_open = prev_candle.open
            prev_close = prev_candle.close
            pct_change = prev_candle.percent_change
            #logger.info(f"###### idx {i} Prev candle: {prev_candle.color}, current color {context.last_candles[-1].color}")

            if context.last_candles[-1].color == 'green' and prev_close <= prev_open: #当前最后一个是涨的，前一个是跌的
                consecutive_opposite += 1
                cumulative_change += abs(pct_change)
            elif context.last_candles[-1].color == 'red' and prev_close >= prev_open: #当前最后一个是跌的，前一个是涨的
                consecutive_opposite += 1
                cumulative_change += abs(pct_change)
            else:
                break

        #logger.info(f"当前的颜色是{context.last_candles[-1].color}, 连续相反的蜡烛数量是{consecutive_opposite}, 累计变化是{cumulative_change}")

        if consecutive_opposite >= self.cumulative_candle_count:
            context.score += (consecutive_opposite - self.cumulative_candle_count) * 0.2
            context.score += float(cumulative_change)
            context.operation = 'long'
            self.log(f"连续{consecutive_opposite}次阴线后，初次阳线出现，且累计跌幅为{cumulative_change}%, 评分更新为{context.score}, 做多")
        elif consecutive_opposite <= - self.cumulative_candle_count:
            context.score += (consecutive_opposite + self.cumulative_candle_count) * 0.2
            context.score += float(cumulative_change)
            context.operation = 'short'
            self.log(f"连续{consecutive_opposite}次阳线后，初次阴线出现，且累计涨幅为{cumulative_change}%, 评分更新为{context.score}, 做空")
        else:
            pass
            #self.log(f"Consecutive opposite is {consecutive_opposite}, unreached the threshold of {self.cumulative_candle_count} candles")

