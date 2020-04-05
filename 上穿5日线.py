# 导入函数库
from jqdata import *
import datetime
import types

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 为全部交易品种设定滑点为0
    set_slippage(FixedSlippage(0))
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order','error')
    # 避免未来数据
    set_option("avoid_future_data", True)
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
    
    # 日期-选票kv
    g.chosenStock = {}
    # 跌停票列表
    g.limitDown = []
    # 普通卖出失败股票列表，目测永远不会执行
    g.failedSold = []
    # 交易记录kv
    g.tradeRecord = {}
    # 持仓率kv
    g.positionRate = {}
    # 连板数kv
    g.limitHigh = {}
    # 连板记录，数据结构为{1:[code列表],2:[code列表],……,total:{code1:[连板次数,日期],code2:[连板次数,日期]……}}，其中数字部分对应连板无股票则删除
    # 并初始化记录表kv
    log.info('初始化连板记录')
    log.info(datetime.datetime.now())
    g.continousRisingLimit = {}
    g.continousRisingLimit['total'] = {}
    continousAddInit(context)
    log.info(datetime.datetime.now())
    # 日收益率kv
    g.dailyEarning = {}
    # 盘中监测跌停股票开盘已卖出后，防止收盘时重复下单kv
    g.monitoring = {}
    # 盘中监测开关
    g.monitorSwitch = False
    # 收盘集合竞价时间：深市2006年7月（日期不详），沪市2018年8月20日及以后,创板应该一直有
    g.time60 = datetime.datetime.strptime("2018-08-20", "%Y-%m-%d")
    g.time00_30 = datetime.datetime.strptime("2006-07-01", "%Y-%m-%d")
    
    # 开盘前运行
    # run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 收盘时运行
    # run_daily(before_market_close_callAuction, time='15:00', reference_security='000300.XSHG')
    
    # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
    # 盘中监测及收盘前运行跌停价卖出
    run_daily(before_market_close_marketOrder, time='every_bar', reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')


# 每日开盘前初始化   
def before_trading_start(context):
    tradeDays = get_trade_days(count=5, end_date=context.current_dt)
    g.todayStr = str(tradeDays[-1])# 今天日期的字符串
    g.yesterdayStr = str(tradeDays[-2])# 昨天日期的字符串
    g.yesterdayBeforeStr = str(tradeDays[-3])# 前天日期的字符串
    g.todaySell = {}# 下单成功flag，检查普通卖单是否创建成功（不代表交易成功，交易记录盘后选股时比对），成功则不再下单,0创建失败1创建成功
    g.todayBuy = {}# 下单成功flag，检查普通买单是否成功，用于盘中监测
    g.limitDownRecord = {}#已加入跌停列表记录
    g.todayLimitDown = {}# 下单成功flag，检查跌停卖单是否成功，成功则不再下单,0失败、1成功
    g.positions = list(context.portfolio.long_positions.values())# 开盘前暂存持仓
    g.monitoring[g.todayStr] = []
    
    
    
# 策略结束后调用
def on_strategy_end(context):
    # 输出选股记录
    current_data = get_current_data()
    outputStr = ''
    for _date,_codes in g.chosenStock.items():
        outputStr += str(_date) + '选股 '
        if _codes:
            for _code in _codes:
                outputStr += _code +''+ current_data[_code].name +' '
        else:
            outputStr += ''
        outputStr += '\n'
    log.info(outputStr)
    # 输出交易记录表
    outputStr = '日期 股票代码 股票名字 交易数量 交易价格 波动率 操作方向 收益率 持仓天数\n'
    for _date,_records in g.tradeRecord.items():
        outputStr += str(_date)
        if len(_records) != 0:
            for _record in _records:
                outputStr += ' '+_record['code'] +' '+_record['name'] +' '+ str(_record['amount']) +' '+str(_record['fluctuation'])+' '+str(_record['price'])
                if _record["direct"] == 'close':
                    outputStr += ' 卖 '+str(_record["earningRate"]) +' '+str(_record["holdingDays"])+'\n'
                if _record["direct"] == 'limitdown':
                    outputStr += ' 卖（有过跌停） '+str(_record["earningRate"]) +' '+str(_record["holdingDays"])+'\n'
                if _record["direct"] == 'open' :
                    outputStr += ' 买\n'
        else:
            outputStr += '\n'
    log.info(outputStr)
    # 输出交易记录描述
    # outputStr = ''
    # for _date,_records in g.tradeRecord.items():
    #     outputStr += str(_date) + '：'
    #     if _records:
    #         for _record in _records:
    #             outputStr += _record['desc'] +'\n'
    #     else:
    #         outputStr += '无\n'
    # log.info(outputStr)
    # 输出持仓率、连板个数、各天总收益率
    outputStr = '日期 持仓率 最高连板个数 日收益率\n'
    for _date,rate in g.positionRate.items():
        outputStr +=  str(_date) +' '+str(rate)+' '+str(g.limitHigh[_date])+' '+str(g.dailyEarning[_date]/context.portfolio.inout_cash)+'\n'
    log.info(outputStr)
    
    log.info('账户总权益：',context.portfolio.total_value)
    log.info('账户可用资金：',context.portfolio.available_cash)
    log.info('收益率为：'+str(context.portfolio.total_value/context.portfolio.inout_cash - 1))
    
    
    
# 开盘时运行函数
def market_open(context):
    # log.info('交易函数(market_open):'+str(context.current_dt))
    
    # 跌停股票池挂跌停卖出
    if len(g.limitDown) > 0:
        log.error('今日待卖出跌停股票列表:'+str(g.limitDown))
    for _limitDown in g.limitDown:
        if(_limitDown in g.todayLimitDown and g.todayLimitDown[_limitDown] == 1):
            continue
        else:
            _todayPrice = get_price(_limitDown, count=1, fields=['low_limit'], end_date=g.todayStr)
            result = order_target( _limitDown,0,LimitOrderStyle(_todayPrice['low_limit']))
            if result:
                g.todayLimitDown[_limitDown] = 1

    # 非跌停原因未未卖出股票开盘价卖出，目测永远不会执行
    for _failedSell in g.failedSold:
        log.error('非跌停原因卖不出去的股票:'+str(g.failedSold))
        order_target(_failedSell, 0)
   


# 按分钟交易函数
def before_market_close_marketOrder(context):
    money = context.portfolio.total_value * 0.1
    
    # 选股日为昨天的股票，买入
    if (g.yesterdayStr in g.chosenStock and g.chosenStock[g.yesterdayStr]):
        if context.current_dt.time()>=datetime.time(9,30,00):
            money = context.portfolio.available_cash / len(g.chosenStock[g.yesterdayStr])
            
        if context.current_dt.time()>=datetime.time(9,30,00) and context.current_dt.time()<=datetime.time(9,33,00):
            log.info('账户总权益：',context.portfolio.total_value)
            log.info('账户可用资金：',context.portfolio.available_cash)
            for orderStock in g.chosenStock[g.yesterdayStr]:
                if orderStock in g.todayBuy and g.todayBuy[orderStock] == 1:
                    continue
                result = order_value(orderStock, money)
                if result:
                    g.todayBuy[orderStock] = 1
                else:
                    log.error('下单失败，检查原因')
    
    # 盘中价格监测,出现跌停直接挂单卖出
    if g.monitorSwitch == True:
        if(g.yesterdayStr in g.chosenStock and g.chosenStock[g.yesterdayStr]):#昨天选出的股票列表存在
            for orderStock in g.chosenStock[g.yesterdayStr]:
                if (orderStock in g.todayBuy) and (g.todayBuy[orderStock] == 1):#今天买进成功的股票才进行操作
                    minutePrice = get_price(orderStock, count=1, frequency='minute',fields=['low_limit','high_limit','open','close','low','high'], end_date=context.current_dt)
                    if float(minutePrice['low_limit']) == float(minutePrice['close']) or float(minutePrice['low_limit']) == float(minutePrice['open']):# 发现跌停
                        if(orderStock in g.monitoring[g.todayStr]):#查看是否已进入跌停列表
                            continue
                        else:#发现未记录跌停则加入
                            log.error('发现盘中跌停，加入跌停列表:'+orderStock)
                            g.limitDown.append(orderStock)
                            g.monitoring[g.todayStr].append(orderStock)


    # 选股日的上一天的股票，临近收盘普通收盘价卖出，操作为挂跌停卖出
    if context.current_dt.time()<datetime.time(14,57,00):
        return
    elif context.current_dt.time()<=datetime.time(15,00,00):
        if(g.yesterdayBeforeStr in g.chosenStock and g.chosenStock[g.yesterdayBeforeStr]):
            for orderStock in g.chosenStock[g.yesterdayBeforeStr]:
                # if ((context.current_dt>g.time60 and orderStock.startswith('60')) or (context.current_dt>g.time00_30 and (orderStock.startswith('00') or orderStock.startswith('30')))) == 0:
                if(orderStock in g.todaySell and g.todaySell[orderStock] == 1):
                    continue
                elif orderStock in g.monitoring[g.yesterdayStr]:
                    continue
                else:
                    _todayPrice = get_price(orderStock, count=1, fields=['low_limit'], end_date=g.todayStr)
                    result = order_target( orderStock,0,LimitOrderStyle(_todayPrice['low_limit']))
                    if result:
                        g.todaySell[orderStock] = 1
    return



## 收盘后运行函数  
def after_market_close(context):
    # log.info(str('收盘选股函数(after_market_close):'+str(context.current_dt)))
    current_data = get_current_data()
    g.tradeRecord[g.todayStr] = []
    trades = get_trades()
    
    # 更新每日收益率
    if g.yesterdayStr not in g.dailyEarning:
        g.dailyEarning[g.todayStr] = context.portfolio.total_value - context.portfolio.inout_cash
    else:
        g.dailyEarning[g.todayStr] = context.portfolio.total_value - context.portfolio.inout_cash - g.dailyEarning[g.yesterdayStr]
    # 更新每日持仓率
    g.positionRate[g.todayStr] = round((context.portfolio.positions_value/context.portfolio.total_value),4)

    #订单查询
    check_trades(context,'limitdown')#这个必须在前
    
    check_trades(context,'open')
    check_trades(context,'close')
    
    # 选股
    g.chosenStock[g.todayStr] = chose_stocks(context)
    
    # 连板统计(删除未涨停代码)
    continousDelete(context)
    # todolist：盘中波动统计、停牌优化
    # log.info('##############################################################')
  
  
    
# 选股及连板统计新增当日
def chose_stocks(context):
    # log.info('选股计时')
    # log.info(datetime.datetime.now())
    count = 0
    chosenArr = []
    current_data = get_current_data()
    trades = get_trades()
    # 批量获取股票代码,建立股票代码数组
    allCode = get_all_securities(types=['stock'], date=None)[:].index
    for code in allCode:
        count+=1
        singleAttr = attribute_history(code, 4, '1d', ('open','close','high','high_limit'),skip_paused=False)
        todayPrice = get_price(code, count=1, fields=['open','close','high_limit'], end_date=g.todayStr)
        todayClose = float(todayPrice['close'])#当日收盘价
        todayOpen = float(todayPrice['open'])#当日开盘价
        todayHighLimit = float(todayPrice['high_limit'])#当日涨停价
        yesterdayHigh = singleAttr.iat[-1,2]#昨日最高价
        yesterdayClose = singleAttr.iat[-1,1]#昨日收盘价
        yesterdayHighlimit = singleAttr.iat[-1,3]#昨日涨停价
        sumClose = singleAttr['close'].sum() + todayClose
        MA5 = sumClose / 5# 当日收盘价5日均值
        
        # 跳过停牌,只要4天内有一次停牌就直接踢掉，等后期优化todo
        if skipSuspension(context, code) == 0:
            continue
        
        # 连板统计当日新增
        continousAddToday(context, code)
        
        chosen = 1 #选股flag
        stockName = current_data[code].name #获取股票名称
        # 昨日烂板
        if(yesterdayHigh>=yesterdayHighlimit and yesterdayClose<yesterdayHigh) == 0:
            chosen = 0
        # 当日低开
        if(todayOpen < yesterdayClose) == 0:
            chosen = 0
        # 上穿5日线
        if( (todayOpen<MA5) and (todayClose>=MA5) ) == 0:
            chosen = 0
        # 涨幅不大    
        if( (todayClose-todayOpen)<=todayOpen*0.05) == 0:
            chosen = 0
        # 剔除st股票
        if current_data[code].is_st == 1:
            chosen = 0
        # 是否新股
        if isNewListing(context, code):
            chosen = 0
        #10日内涨停2次及以上
        singleAttr = attribute_history(code, 11, '1d', ('open','close','high','high_limit'),skip_paused=False)
        limitCount = 0
        timeCount = -2
        while timeCount >= -11:
            currentHighLimit = singleAttr.iat[timeCount,3]
            currentClose = singleAttr.iat[timeCount,1]
            if currentClose >= currentHighLimit:
                limitCount += 1
            timeCount -= 1
        if limitCount < 2:
            chosen = 0
        # # 选股测试代码start
        # if str(context.current_dt.date()) == '2019-04-24':
        #     if '002477' in code:
        #         log.info(singleAttr)
        #         log.info(todayOpen)
        #         log.info(todayClose)
        #         log.info(yesterdayHighlimit)
        #         log.info(yesterdayHigh)
        #         log.info(current_data[code].name)
        #         log.info(current_data[code].is_st)
        # # 选股测试代码end
        # 将选中的股票加入chosenArr
        if chosen == 1:
            chosenArr.append(code)
            
    # log.info(datetime.datetime.now())
    # log.info(count)
    return chosenArr
    
    
    
# 连板统计(删除未涨停代码)
def continousDelete(context):
    continousTotalKeys = []
    for _key in g.continousRisingLimit['total'].keys():
        continousTotalKeys.append(_key)
    continousKeys = []
    for _key in g.continousRisingLimit.keys():
        continousKeys.append(_key)
    for _key in continousTotalKeys:
        if g.continousRisingLimit['total'][_key][1] != context.current_dt:
            limitTime = g.continousRisingLimit['total'][_key][0]
            del g.continousRisingLimit['total'][_key]
            g.continousRisingLimit['limit'+str(limitTime)].remove(_key)
    for _key in continousKeys:
        if len(g.continousRisingLimit[_key]) == 0 and _key != 'total':
            del g.continousRisingLimit[_key]
    limitHigh = 0
    for _key in g.continousRisingLimit.keys():
        if _key != 'total':
            count = int(_key[5:])
            if count > limitHigh:
                limitHigh = count
    # 连板数据保存
    g.limitHigh[g.todayStr] = limitHigh



# 订单检查
def check_trades(context,direct):
    current_data = get_current_data()
    trades = get_trades()
    
    # 基本信息预处理
    if direct == 'open':
        dayStr = g.yesterdayStr
        errorDirect = '买入'
        decWord = '直接放弃：'
        operation = direct
    elif direct == 'close':
        dayStr = g.yesterdayBeforeStr
        errorDirect = '卖出'
        decWord = '加入跌停列表：'
        operation = direct
    elif direct == 'limitdown':
        errorDirect = '卖出（跌停）'
        decWord = '加入跌停列表：'
        operation = 'close'
        
    nullCheckStock = []#用于null值筛选
    stocks = []#用于记录订单列表
    if direct == 'limitdown':
        for _stock in g.limitDown:
            nullCheckStock = g.limitDown
    else:
        if(dayStr in g.chosenStock):
            nullCheckStock = g.chosenStock[dayStr]
            
    for _stock in nullCheckStock:
        stocks.append(_stock)
    # # 订单查询测试代码start
    # checkStocks = []
    # for _stock in nullCheckStock:
    #     checkStocks.append(_stock)
    #     log.info(checkStocks)
    # for check in checkStocks:
    #     if str(context.current_dt.date()) == '2018-01-08':
    #         if '002856' in check:
    #             log.info(get_orders(security=check))
    #             break
    # # 订单查询测试代码end
    
    for _stock in nullCheckStock:
        # 盘中跌停时会遇到加入跌停列表的股票的卖出时间与正常股票的卖出时间相同，即选股日的t+2，此段代码处理重复记录交易的问题
        if direct == 'close' and g.monitorSwitch == True:
            log.info(g.monitoring)
            if _stock in g.monitoring[g.yesterdayStr]:
                continue

        todayPrice = get_price(_stock, count=1, fields=['open','close','high','low','high_limit','factor'], end_date=g.todayStr)
        orders = get_orders(security=_stock)
        if(len(orders.values()) == 0):
            log.error(errorDirect+'订单有空值,应该是下单失败'+str(_stock+current_data[_stock].name))
            continue
        if(len(orders.values()) > 1):
            log.error(str(context.current_dt) +' '+ str(_stock+current_data[_stock].name)+' 金额('+errorDirect+')太大，一个订单放不下或跌停')
        for _trade in list(trades.values()):
            orderObj = list(orders.values())[0]
            if(_trade.order_id == orderObj.order_id and orderObj.action == operation):
                stocks.remove(_stock)
                todayFactor = todayPrice['factor']
                if(float(todayFactor) != 1.0):
                    log.error('复权因子不是1')
                single = {}
                single['desc'] = errorDirect+_stock+current_data[_stock].name+'，复权价格为'+str(orderObj.price)+'，除权价格为'+str(orderObj.price/float(todayFactor))+',股数为'+str(orderObj.amount)
                single['name'] = current_data[_stock].name
                single['amount'] = orderObj.amount
                single['price'] = orderObj.price
                single['code'] = _stock
                single['direct'] = direct
                # 波动计算方法为开盘价和最低价？最低价和最高价？
                single['fluctuation'] = float(abs(todayPrice['open']/todayPrice['low'] - 1))
                
                if operation == 'close':
                    # 计算收益率和持仓天数
                    buyDate = context.current_dt.date()
                    for position in g.positions:
                        if _stock in position.security:
                            single['earningRate'] = (orderObj.price*orderObj.amount-orderObj.commission)/(position.avg_cost*orderObj.amount) - 1
                            single['holdingDays'] = len(get_trade_days(start_date=position.init_time.date(), end_date=context.current_dt.date()))
                            break
                        
                g.tradeRecord[g.todayStr].append(single)
                log.info(single)
                break
    
    # 失败订单处理
    if direct == 'close':
        if(len(stocks) != 0):
            log.error('有普通股票未能在当天'+errorDirect+'(一般因为跌停)，' +decWord+str(stocks))
        # 卖出失败股票处理，当日新产生的跌停股票加入跌停列表，普通未卖出加入待卖出列表
        for _code in stocks:
            soldTodayPrice = get_price(_code,count=1,fields=['close','low_limit','factor'], end_date=g.todayStr)
            # 此处可优化为最低价达到跌停价的百分比即跌停卖出？
            if(float(soldTodayPrice['close']) <= float(soldTodayPrice['low_limit'])):
                g.limitDown.append(_code)
            else:
                # 目测永远不会执行
                g.failedSold.append(_code)
                
    elif direct == 'open':
        if(len(stocks) != 0):
            log.error('有普通股票未能在当天'+errorDirect+'，' +decWord+str(stocks))
        #买入失败后踢出选中名单
        for _code in stocks:
            g.chosenStock[g.yesterdayStr].remove(_code)
            
    elif direct == 'limitdown':
        if(len(stocks) != 0):
            errorStr = '有跌停股票未能在当天'+errorDirect+'，' +decWord+str(stocks)
            if g.monitorSwitch == True:
                errorStr += '（含盘中监测跌停股票，在当天无法卖出）'
            log.error(errorStr)
            g.limitDown = stocks
        else:
            g.limitDown = []
                
    
         
# 连板统计当日新增
def continousAddToday(context,code):
        singleAttr = attribute_history(code, 1, '1d', ('open','close','high', 'volume','high_limit','factor'),skip_paused=False)
        todayPrice = get_price(code, count=1, fields=['open','close','high_limit','factor'], end_date=g.todayStr)
        todayClose = float(todayPrice['close'])#当日收盘价
        todayHighLimit = float(todayPrice['high_limit'])#当日涨停价
        # 连板记录数据结构为{limit1:[code列表],limit2:[code列表],……,total:{code1:[连板次数,日期],code2:[连板次数,日期]……}}
        # 其中数字部分对应连板无股票则删除，前半段(limitN)为正查表，后半段(total)为反查表
        # 连板统计（增补今日涨停）
        if todayHighLimit == todayClose:
            continousTotalKeys = g.continousRisingLimit['total'].keys()
            continousKeys = g.continousRisingLimit.keys()
            if code in continousTotalKeys:#反查表里有这个票，表示昨天已涨停
                continousTime = g.continousRisingLimit['total'][code][0]#获取连板次数并+1
                # 正查表操作
                g.continousRisingLimit['limit'+str(continousTime)].remove(code)#从正查表n连板中删除
                continousTime+=1
                if ('limit'+str(continousTime)) in continousKeys:#n+1连板数组如果存在
                    g.continousRisingLimit['limit'+str(continousTime)].append(code)#从正查表n+1连板中增加
                else:
                    g.continousRisingLimit['limit'+str(continousTime)] = [code]
                #反查表更新日期和次数
                g.continousRisingLimit['total'][code] = [continousTime, context.current_dt]
            else:#反查表里没有这个票，表示新加入1连板
                #反查表新增日期和次数
                g.continousRisingLimit['total'][code] = [1, context.current_dt]
                # 正查表操作
                if 'limit1' in continousKeys:
                   g.continousRisingLimit['limit1'].append(code) 
                else:#如果1连板股票一个都没有就新建一个1连板数组
                   g.continousRisingLimit['limit1'] = [code]
           
           
                
# 连板初始新增
def continousAddInit(context):
    date = context.current_dt.date() + datetime.timedelta(days=-1)
    tradeDay = get_trade_days(count=1, end_date=date)
    startDay = tradeDay[0]
    continousKeys = g.continousRisingLimit.keys()
    # 保存当天涨停板
    allCode = get_all_securities(types=['stock'], date=None)[:].index
    for _allCode in allCode:
        if skipSuspension(context, _allCode) == 0:
            continue
        todayPrice = get_price(_allCode, count=1, fields=['close','high_limit'], end_date=tradeDay[0])
        todayClose = float(todayPrice['close'])#当日收盘价
        todayHighLimit = float(todayPrice['high_limit'])#当日涨停价
        if todayHighLimit == todayClose:
            g.continousRisingLimit['total'][_allCode] = [1, tradeDay[0]]
            # 正查表操作
            if 'limit1' in continousKeys:
              g.continousRisingLimit['limit1'].append(_allCode)
            else:#如果1连板股票一个都没有就新建一个1连板数组
              g.continousRisingLimit['limit1'] = [_allCode]
              
    #处理历史涨停板
    whileFlag = True
    tradeDayRecord = startDay#“昨日”，并初始化为startday
    searchDay = startDay#“今日”，并初始化为startday
    while(whileFlag):
        whileFlag = False#下边发现涨停置为true，使得while循环继续进行
        tradeDays = get_trade_days(count=2, end_date=searchDay)
        tradeDayRecord = tradeDays[1]
        searchDay = tradeDays[0]
        keyList = []
        for totalKey in g.continousRisingLimit['total'].keys():
            keyList.append(totalKey)#所有涨停股票列表
        continousTotalKeys = g.continousRisingLimit['total'].keys()
        continousKeys = g.continousRisingLimit.keys()
        for _listCode in keyList:
            if skipSuspension(context, _allCode) == 0:
                continue
            limitRecordDay = g.continousRisingLimit['total'][_listCode][1]#获取保存的连板日
            if limitRecordDay == tradeDayRecord:
                todayPrice = get_price(_listCode, count=1, fields=['close','high_limit'], end_date=searchDay)
                todayClose = float(todayPrice['close'])#当日收盘价
                todayHighLimit = float(todayPrice['high_limit'])#当日涨停价
                if todayHighLimit != todayClose:
                    continue
                whileFlag = True
                if _listCode in continousTotalKeys:#反查表里有这个票，表示昨天已涨停
                    continousTime = g.continousRisingLimit['total'][_listCode][0]#获取连板次数并+1
                    # 判断这个涨停与昨日是否相连，不是则跳过
                    if limitRecordDay != tradeDayRecord:
                        continue
                    # 正查表操作
                    g.continousRisingLimit['limit'+str(continousTime)].remove(_listCode)#从正查表n连板中删除
                    continousTime+=1
                    if ('limit'+str(continousTime)) in continousKeys:#n+1连板数组如果存在
                        g.continousRisingLimit['limit'+str(continousTime)].append(_listCode)#从正查表n+1连板中增加
                    else:
                        g.continousRisingLimit['limit'+str(continousTime)] = [_listCode]
                    
                    # 反查表操作：更新日期和次数
                    g.continousRisingLimit['total'][_listCode] = [continousTime, searchDay]
    
    #涨停时间调回startday，删除空limit数组
    for key in g.continousRisingLimit['total'].keys():
        if key != 'total':
            g.continousRisingLimit['total'][key][1] = startDay
            
    keys = []
    for key in g.continousRisingLimit.keys():
        keys.append(key)
    for key in keys:
        if len(g.continousRisingLimit[key]) == 0:
           del g.continousRisingLimit[key] 



# 跳过停牌：这段逻辑是只要4天内有一次停牌就直接踢掉，等后期优化
def skipSuspension(context, code):
    singleAttr = attribute_history(code, 4, '1d', ('open','close','high', 'volume','high_limit','factor'),skip_paused=False)
    volumes = singleAttr['volume'].tolist()
    suspension = 1 # 0是停牌，1是未停牌
    for volume in volumes:
        if volume <= 0:
            suspension = 0
            break
    return suspension
    
   
    
# 判断是否是新股上市
def isNewListing(context, code): 
    startDate = get_security_info(code).start_date
    days = len(get_trade_days(start_date=startDate, end_date=context.current_dt.date()))
    if days <= 45:
        return True
    else:
        return False
        
        
        
# 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    send_message('美好的一天~')
    
    
# 弃用
def before_market_close_callAuction(context):
    money = context.portfolio.total_value * 0.1
    if(g.yesterdayBeforeStr in g.chosenStock and g.chosenStock[g.yesterdayBeforeStr]):
        for orderStock in g.chosenStock[g.yesterdayBeforeStr]:
            if (context.current_dt>g.time60 and orderStock.startswith('60')) or (context.current_dt>g.time00_30 and (orderStock.startswith('00') or orderStock.startswith('30'))):
                order_target(orderStock, 0)
    