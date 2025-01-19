import yaml
from . import register_pipeline
from . import ScorePipeline, PipelineContext, PipelineType
from log import logger


@register_pipeline('current_candle')
class CurrentCandlePipeline(ScorePipeline):
    """
    CurrentCandlePipeline 类处理当前蜡烛图数据，以评估和评分基于当前蜡烛图的模式。
    方法:
        处理包含蜡烛图数据的给定上下文。它检查上下文中是否至少有1根蜡烛。
        然后，它根据当前蜡烛图的颜色和百分比变化来更新上下文中的分数。
        如果当前蜡烛图是绿色且跌幅超过3%，则增加分数。
        如果当前蜡烛图是红色且涨幅超过3%，则减少分数。
        如果在持有多头头寸时当前蜡烛图涨幅超过2%，则减少分数以止盈。
        如果在持有空头头寸时当前蜡烛图跌幅超过2%，则增加分数以止盈。
    """
    """
    CurrentCandlePipeline is a class that processes the current candlestick data to evaluate and score based on the current candle patterns.
    Methods:
        process(context: PipelineContext):
            Processes the given context containing candlestick data. It checks for a minimum of 1 candle in the context.
            It then updates the score in the context based on the color and percentage change of the current candle.
            If the current candle is green and has decreased by more than 3%, it increments the score.
            If the current candle is red and has increased by more than 3%, it decrements the score.
            If holding a long position and the current candle has increased by more than 2%, it decrements the score to take profit.
            If holding a short position and the current candle has decreased by more than 2%, it increments the score to take profit.
    """

    DEFAULT_LONG_TAKE_PROFIT = 2
    DEFAULT_SHORT_TAKE_PROFIT = 2
    DEFAULT_LONG_OPEN = 3
    DEFAULT_SHORT_OPEN = 3

    def __init__(self):
        self.name = 'CurrentCandlePipeline'
        self.type = PipelineType.BOTH
        config_path = __file__.replace('.py', '.yaml')
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            self.long_take_profit = float(config.get('pipeline',{}).get('long_take_profit', CurrentCandlePipeline.DEFAULT_LONG_TAKE_PROFIT))
            self.short_take_profit = float(config.get('pipeline',{}).get('short_take_profit', CurrentCandlePipeline.DEFAULT_SHORT_TAKE_PROFIT))
            self.long_open = float(config.get('pipeline',{}).get('long_open', CurrentCandlePipeline.DEFAULT_LONG_OPEN))
            self.short_open = float(config.get('pipeline',{}).get('short_open', CurrentCandlePipeline.DEFAULT_SHORT_OPEN))
            self.long_take_profit_burst = float(config.get('pipeline',{}).get('long_take_profit_burst', CurrentCandlePipeline.DEFAULT_LONG_TAKE_PROFIT))
            self.short_take_profit_burst = float(config.get('pipeline',{}).get('short_take_profit_burst', CurrentCandlePipeline.DEFAULT_SHORT_TAKE_PROFIT))

        
        logger.debug(str(self))

    def __str__(self):
        return f"CurrentCandlePipeline(long_take_profit={self.long_take_profit}%, short_take_profit={self.short_take_profit}%, long_open={self.long_open}%, short_open={self.short_open}%)"

    def process(self, context: PipelineContext):
        if len(context.current_candles) < 1:
            return

        last_current_candle = context.current_candles[-1]
        
        if context.in_position:
            if context.in_position == 'long':
                total_profit = (last_current_candle.close - context.entry_price)/context.entry_price * 100
                #logger.info(f"burst: %.4f, percent_change: %.4f, current price is:%.4f, entry is:%.4f, total_profit is: %.4f" %(self.long_take_profit_burst, last_current_candle.percent_change, last_current_candle.close, context.entry_price, total_profit))
                if last_current_candle.percent_change >= self.long_take_profit_burst:  # 做多过程中，本周期内涨了 long_take_profit_burst% 止盈
                    context.score = 1
                    context.operation = 'exit'
                    context.setSkipFlag()
                    self.log("做多期间K线周期内涨幅达到设置的阀值 %.2f%%, 止盈获利:%.4f%%" % (self.long_take_profit_burst, total_profit))
                    return
                
                if total_profit >= self.long_take_profit:
                    context.score = 1
                    context.operation = 'exit'
                    context.setSkipFlag()
                    self.log(f"做多期间达到设置的止盈值 %.2f%%, %.4f%%" % (self.long_take_profit, total_profit))
                    return
                
                if total_profit <= 0 - self.long_take_profit:
                    context.score = 1
                    context.operation = 'exit'
                    context.setSkipFlag()
                    self.log(f"做多期间达到设置的止损值 %.2f%%, %.4f%%" % (self.long_take_profit, total_profit))
                    return

            else:
                total_profit = (context.entry_price - last_current_candle.close)/context.entry_price

                if last_current_candle.percent_change < -self.long_take_profit_burst:  # 做空过程中，本周期内跌了 short_take_profit% 平仓止盈
                    context.score = 1
                    context.operation = 'exit'
                    context.setSkipFlag()
                    self.log("做空期间K线周期内跌幅达到设置的阀值 %f%, 止盈获利:%.4f%" % (self.short_take_profit_burst, total_profit))

                total_profit = (context.entry_price - last_current_candle.close)/context.entry_price
                if total_profit >= self.short_take_profit:
                    context.score = 1
                    context.operation = 'exit'
                    context.setSkipFlag()
                    self.log(f"做空期间达到设置的止盈值 %f%, %.4f%" % (self.short_take_profit, total_profit))
                    return
                elif total_profit <= 0 - self.short_take_profit:
                    context.score = 1
                    context.operation = 'exit'
                    context.setSkipFlag()
                    self.log(f"做空期间达到设置的止损值 %f%, %.4f%" % (self.short_take_profit, total_profit))
                
        else:
            if last_current_candle.color == 'green':
                if last_current_candle.percent_change < -self.long_open:  # 绿色蜡烛，本周期内跌了 long_open% 买入做多
                    context.score += (abs(last_current_candle.percent_change) - self.long_open)
                    context.operation = 'long'
                    self.log(f"Score update to {context.score} for increasing by {last_current_candle.percent_change}")
            else:
                if last_current_candle.percent_change > self.short_open:  # 红色蜡烛，本周期内涨了 short_open% 开仓做空
                    context.score -= (last_current_candle.percent_change - self.short_open)
                    context.operation = 'short'
                    self.log(f"Score update to {context.score} for decreasing by {last_current_candle.percent_change}")


