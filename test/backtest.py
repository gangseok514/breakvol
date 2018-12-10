
import sys
from datetime import date, datetime, timedelta
import numpy as np
import json


KSIZE = 20
RSIZE = 18
TARGET_VOL = 0.05

klist = {}
k = {}
rlist = {}
r = {}
charts = {}
vol = {}
merged_data = {}

slippage = 0.998

def merge_data(start, end, currencies, timediff=9): # -9: UTC, 0: KST
    for c in currencies:
        cs = start
        merged_data[c] = {}    
        while cs <= end:
            o,h,l,cl = -1,-1,9999999999,-1
            scs = datetime(cs.year, cs.month, cs.day) + timedelta(hours=timediff)
            ecs = scs + timedelta(days=1)
            while scs < ecs:
                try:
                    d = charts[c][scs.strftime('%Y%m%dT%H')]            
                    if o < 0:
                        o = d['open']
                    if d['high'] > h:
                        h = d['high']
                    if d['low'] < l:
                        l = d['low']
                    cl = d['close']
                except Exception as e:
                    #print('[{}] Error get_data: {}'.format(c, e))
                    pass                
                scs += timedelta(hours=1)

            merged_data[c][cs.strftime('%Y%m%d')] = {
                'open': o,
                'high': h,
                'low' : l,
                'close': cl,
            }
            cs += timedelta(days=1)

def get_data(start, c):
    return merged_data[c][start.strftime('%Y%m%d')]
    
def get_range(start, c):
    '''
    Range 가져오기
    '''
    d = get_data(start, c)
    return d['high'] - d['low']

def calc_k(start, c, d):
    #d = get_data(start, c)    
    noise = 1 - abs(d['open'] - d['close'])/(d['high'] - d['low'])
    
    if klist.get(c) is None:
        klist[c] = []
    klist[c].append(noise)
    if len(klist[c]) <= KSIZE:
        return

    if k.get(c) is None:
        k[c] = {}

    dateformat = start.strftime('%Y%m%d')
    k[c][dateformat] = np.mean(klist[c][:-1])
    klist[c] = klist[c][1:]

def calc_r(start, c, d):
    #d = get_data(start, c)
    m = (d['high'] + d['low'])/2 # open? close?
    
    if rlist.get(c) is None:
        rlist[c] = []

    rlist[c].append(m)

    if len(rlist[c]) <= 20:
        return

    rcount = 0
    malist = []
    for i in range(4, RSIZE+4):
        ma = np.mean(rlist[c][-i:-1]) # 3~20일의 이동평균선
        malist.append(ma)

    if r.get(c) is None:
        r[c] = {}

    dateformat = start.strftime('%Y%m%d')
    r[c][dateformat] = malist
    rlist[c] = rlist[c][1:]

def get_k(start, c):
    '''
    K값 가져오기
    '''
    dateformat = start.strftime('%Y%m%d')
    return k[c][dateformat]

def get_r(start, c, price):
    '''
    베팅비율 가져오기(R값)
    '''
    dateformat = start.strftime('%Y%m%d')
    rcount = 0
    for ma in r[c][dateformat]:
        if price > ma:
            rcount += 1

    return rcount/18

def load_charts(c):
    '''
    차트가져오기
    '''

    with open('../charts/charts_upbit_{}.json'.format(c), 'r') as f:
        d = f.read()
        charts[c] = json.loads(d)

def run(start, end, currencies, seed):       
        
    total_money = seed
    buy, win = 0, 0
    pmoney, mmoney = 0, 0
    mdd = 0

    # 날짜별 루프
    max_total_money = total_money
    while start <= end:
        y = start - timedelta(days=1)
        total_seed = total_money
        cseed = total_money #/len(currencies) # 매수전 seed 기준으로, 총 자본금을 코인수만큼 나눔
        is_buy = False

        try:
            for c in currencies:                
                p = get_data(start, c)
                range = get_range(y, c) # Range 가져오기
                k = get_k(y, c) # K값 가져오기                                

                bp = int(p['open'] + (range*k))                
                if p['high'] < bp: # 기준값에 해당되지 않으면 다음날로 스킵
                    continue

                r = get_r(start, c, bp) # 이평선스코어 가져오기(R값)

                v = TARGET_VOL/(range/bp)
                if v > 1:
                    v = 1
                v = v/len(currencies) # 변동성조절 비율 가져오기(V값)                

                is_buy = True
                # 기준값을 넘으면 매수, 지정시간에 매도후 손익값 전날 seed에 반영하여 업데이트
                sp = int(p['close'])
                if cseed * r * v > cseed:
                    print('WARNING: CSEED!!!')
                cseed = int(cseed * r * v)
                if cseed < 500: ## 500원 이하는 매수 불가
                    continue
                units = round((cseed/bp), 4)
                cmoney = int(units * sp * slippage)
                cresult = cmoney-cseed
                total_money += cresult

                buy += 1

                if cresult > 0:
                    pmoney += cresult
                    win += 1
                else:
                    mmoney -= cresult
                
                print('[{}] BP: {}, SP:{}, SEED: {}, UNITS: {}, PL: {}, range:{}, k:{}, r:{}, v:{}'.format(
                    c, bp, sp, cseed, units, cresult, range, k, r, v))

            if total_money > max_total_money:
                max_total_money = total_money

            dd = (max_total_money-total_money)/max_total_money
            if dd > mdd:
                mdd = dd

            if is_buy:
                print('[{}] Money: {}, PL: {}'.format(start.strftime('%Y%m%d'), total_money, int(total_money - total_seed)))
        except Exception as e:
            print('Error: {}'.format(e))
        start += timedelta(days=1)

    return total_money, pmoney, mmoney, buy, win, mdd

def main():

    if len(sys.argv) < 3:
        print('Usage: test.py 2018-01-01 2018-09-30')
        return

    a1 = sys.argv[1].split('-')
    a2 = sys.argv[2].split('-')
    #print(a1,a2)

    start = date(int(a1[0]), int(a1[1]), int(a1[2]))
    end = date(int(a2[0]), int(a2[1]), int(a2[2]))

    #print('{}~{}'.format(start.strftime('%Y%m%d'), end.strftime('%Y%m%d')))

    currencies = [        
        'BTC',
        'ETH',
        'XRP',
        'BCH',
        #'EOS',
    ]

    for c in currencies:
        load_charts(c)
        #print(charts)

    cs = start - timedelta(days=20) # 20일 이전 평균계산이 필요하므로
    merge_data(cs, end, currencies, 10) # 시작기간,종료기간,코인종류,시가
    while cs <= end:
        for c in currencies:
            d = get_data(cs, c)
            calc_r(cs,c,d)
            calc_k(cs,c,d)
        cs += timedelta(days=1)
    # 날짜별
    #   이동평균선 미리 계산
    #   K값 미리 계산

    #print(get_data(start, 'XRP'))
    # 전략 실행
    seed = 10000000
    money, pmoney, mmoney, buy, win, mdd = run(start, end, currencies, seed)    
    pl_ratio = (pmoney/win) / (mmoney/(buy-win))
    p = win/buy
    q = 1 - p
    b = money/seed
    kelly = (p*b - q)/b
    if kelly < 0:
        kelly = 0

    print('[{}~{}] Total: {}/{}({}%), Buy: {}, Win: {}({}%), PL_ratio: {}, MDD: {}%, Kelly: {}'.format(
        start.strftime('%Y%m%d'), end.strftime('%Y%m%d'),
        round(money), seed, round((money-seed)/seed*100,2),
        buy, win, round(win/buy*100,1), round(pl_ratio,2), round(mdd*100,2), round(kelly, 3),
    ))


main()
