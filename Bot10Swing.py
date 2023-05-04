from BotConfig import *
from BotUtil import *
from BotKIKr import BotKIKr
from dateutil.relativedelta import *
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
import datetime
import threading
import os
import copy
from pprint import pprint

class Bot10Swing():

    
    def __init__(self):

        self.mock = True
        self.key = KI_APPKEY_IMITATION if self.mock else KI_APPKEY_PRACTICE
        self.secret = KI_APPSECRET_IMITATION if self.mock else KI_APPSECRET_PRACTICE
        self.account = KI_ACCOUNT_IMITATION if self.mock else KI_ACCOUNT_PRACTICE

        self.bkk = BotKIKr(self.key, self.secret, self.account, self.mock)
        self.bdf = None
        self.b_l = None
        self.q_l = None
        self.r_l = None

        self.tot_evl_price = 0
        self.buy_max_price = 0

        self.bool_marketday = False
        self.bool_stockorder = False
        self.bool_stockorder_timer = False
        self.bool_marketday_end = False
        self.bool_threshold = False

        self.init_marketday = None
        self.init_stockorder_timer = None


    def init_per_day(self):

        self.bkk = BotKIKr(self.key, self.secret, self.account, self.mock)
        self.bdf = load_xlsx(FILE_URL_DATA_10M).set_index('date')
        self.b_l = self.bdf.columns.to_list()
        self.q_l = self.get_guant_code_list()
        self.r_l = list(set(self.get_balance_code_list()).difference(self.q_l))

        _ttl_prc = int(self.bkk.fetch_balance()['output2'][0]['tot_evlu_amt'])
        _buy_cnt = len(self.q_l) if len(self.q_l) > 20 else 20
        
        self.tot_evl_price = _ttl_prc if _ttl_prc < 30000000 else 30000000
        self.buy_max_price = self.tot_evl_price / _buy_cnt
        self.init_marketday = self.bkk.fetch_marketday()

        line_message(f'Bot10Swing \n평가금액 : {self.tot_evl_price}원, 다른종목: {len(self.r_l)}개')
    

    def stock_order(self):

        tn = datetime.datetime.now()
        tn_153000 = tn.replace(hour=15, minute=30, second=0)
        tn_div = tn.minute % 10
        tn_del = None

        if tn_div == 0:
            tn_del = 1
        elif tn_div == 1:
            tn_del = 2
        elif tn_div == 2:
            tn_del = 3
        elif tn_div == 3:
            tn_del = 4
        elif tn_div == 4:
            tn_del = 5
        elif tn_div == 5:
            tn_del = 6
        elif tn_div == 6:
            tn_del = 7
        elif tn_div == 7:
            tn_del = 8
        elif tn_div == 8:
            tn_del = 9
        elif tn_div == 9:
            tn_del = 10

        tn_del_min = tn - datetime.timedelta(minutes=tn_del)
        tn_df_idx = tn_del_min.strftime('%Y%m%d%H%M00') if tn < tn_153000 else tn.strftime('%Y%m%d153000')
        tn_df_req = tn_del_min.strftime('%H%M00') if tn < tn_153000 else '153000'

        print('##################################################')

        if self.bool_threshold and tn_div == 9:
            self.bdf = self.bdf[:-1]
        self.bool_threshold = False

        bal_lst = self.get_balance_code_list(True)
        sel_lst = []

        if os.path.isfile(FILE_URL_BLNC_10M):
            obj_lst = load_file(FILE_URL_BLNC_10M)
        else:
            obj_lst = {}
            save_file(FILE_URL_BLNC_10M, obj_lst)

        for code in self.b_l:

            min_lst = self.bkk.fetch_today_1m_ohlcv(code, tn_df_req, True)['output2'][:10]
            chk_cls = float(min_lst[0]['stck_prpr'])
            chk_opn = float(min_lst[9]['stck_oprc'])
            chk_hig = max([float(min_lst[i]['stck_hgpr']) for i in range(10)])
            chk_low = min([float(min_lst[i]['stck_lwpr']) for i in range(10)])
            chk_vol = sum([int(min_lst[i]['cntg_vol']) for i in range(10)])
            self.bdf.at[tn_df_idx, code] = str(chk_opn) + '|' + str(chk_hig) + '|' + str(chk_low) + '|' + str(chk_cls) + '|' + str(chk_vol)
            
            is_late = tn_div == 2 or tn_div == 3 or tn_div == 4 or tn_div == 5 or tn_div == 6 or tn_div == 7 or tn_div == 8 or tn_div == 9

            if (not is_late):

                is_remain = code in self.r_l
                is_alread = code in bal_lst

                if is_alread and not (code in obj_lst):
                    obj_lst[code] = {'x': copy.deepcopy(bal_lst[code]['p']), 'a': copy.deepcopy(bal_lst[code]['a']), 's': 1, 'd': datetime.datetime.now().strftime('%Y%m%d')}
                
                if (not is_alread) and (not is_remain):

                    df = min_max_height(moving_average(get_code_df(self.bdf, code)))
                    df_t = df.tail(1)

                    if \
                    (df_t['close'].iloc[-1] < (df_t['close_p'].iloc[-1] * 1.05)) and \
                    (df_t['height'].iloc[-1] > 1.1) and \
                    (df_t['ma05'].iloc[-1] > df_t['ma20'].iloc[-1] > df_t['ma60'].iloc[-1]) and \
                    (df_t['ma20'].iloc[-1] * 1.05 > df_t['close'].iloc[-1] > df_t['ma20'].iloc[-1]) and \
                    (df_t['close'].iloc[-1] > df_t['ma05'].iloc[-1])\
                    :
                        if chk_cls < self.buy_max_price:

                            ord_q = get_qty(chk_cls, self.buy_max_price)
                            buy_r = self.bkk.create_market_buy_order(code, ord_q) if tn < tn_153000 else self.bkk.create_over_buy_order(code, ord_q)

                            if buy_r['rt_cd'] == '0':
                                print(f'매수 - 종목: {code}, 수량: {ord_q}주')
                                obj_lst[code] = {'a': chk_cls, 'x': chk_cls, 's': 1, 'd': datetime.datetime.now().strftime('%Y%m%d')}
                                sel_lst.append({'c': '[B] ' + code, 'r': str(ord_q) + '주'})
                            else:
                                msg = buy_r['msg1']
                                print(f'{msg}')

                obj_ntnul = not (not obj_lst)

                if is_alread and obj_ntnul:

                    obj_d = obj_lst[code]['d']
                    now_d = datetime.datetime.now().strftime('%Y%m%d')
                    dif_d = datetime.datetime(int(now_d[:4]), int(now_d[4:6]), int(now_d[6:])) - datetime.datetime(int(obj_d[:4]), int(obj_d[4:6]), int(obj_d[6:]))

                    if (dif_d.days) >= 14:

                        bal_fst = bal_lst[code]['a']
                        bal_cur = bal_lst[code]['p']
                        bal_qty = bal_lst[code]['q']

                        sel_r = self.bkk.create_market_sell_order(code, bal_qty) if tn < tn_153000 else self.bkk.create_over_sell_order(code, bal_qty)
                        _ror = ror(bal_fst * bal_qty, bal_cur * bal_qty)

                        if sel_r['rt_cd'] == '0':
                            print(f'매도 - 종목: {code}, 수익: {round(_ror, 4)}')
                            sel_lst.append({'c': '[SL] ' + code, 'r': round(_ror, 4)})
                            obj_lst.pop(code, None)
                        else:
                            msg = sel_r['msg1']
                            print(f'{msg}')

                    else:

                        t1 = 0.05
                        t2 = 0.065
                        t3 = 0.08
                        ct = 0.8
                        hp = 100

                        if obj_lst[code]['x'] < bal_lst[code]['p']:
                            obj_lst[code]['x'] = copy.deepcopy(bal_lst[code]['p'])
                            obj_lst[code]['a'] = copy.deepcopy(bal_lst[code]['a'])

                        if obj_lst[code]['x'] > bal_lst[code]['p']:

                            bal_pft = bal_lst[code]['pft']
                            bal_fst = bal_lst[code]['a']
                            bal_cur = bal_lst[code]['p']
                            bal_qty = bal_lst[code]['q']
                            rto_01 = 0.2
                            rto_02 = (3/8)
                            ord_qty_01 = int(bal_qty * rto_01) if int(bal_qty * rto_01) != 0 else 1
                            ord_qty_02 = int(bal_qty * rto_02) if int(bal_qty * rto_02) != 0 else 1
                            is_qty_01 = bal_qty == ord_qty_01
                            is_qty_02 = bal_qty == ord_qty_02
                            obj_max = obj_lst[code]['x']
                            obj_fst = obj_lst[code]['a']
                            obj_pft = obj_max / obj_fst
                            los_dif = obj_pft - bal_pft
                            sel_cnt = copy.deepcopy(obj_lst[code]['s'])

                            if 1 < bal_pft < hp:

                                if (sel_cnt == 1) and (t1 <= los_dif):

                                    sel_r = self.bkk.create_market_sell_order(code, ord_qty_01) if tn < tn_153000 else self.bkk.create_over_sell_order(code, ord_qty_01)
                                    _ror = ror(bal_fst * ord_qty_01, bal_cur * ord_qty_01)

                                    if sel_r['rt_cd'] == '0':
                                        print(f'매도 - 종목: {code}, 수익: {round(_ror, 4)}')
                                        sel_lst.append({'c': '[S1] ' + code, 'r': round(_ror, 4)})
                                        obj_lst[code]['s'] = sel_cnt + 1
                                        obj_lst[code]['d'] = datetime.datetime.now().strftime('%Y%m%d')

                                        if is_qty_01:
                                            obj_lst.pop(code, None)
                                    else:
                                        msg = sel_r['msg1']
                                        print(f'{msg}')
                                
                                elif (sel_cnt == 2) and (t2 <= los_dif):

                                    sel_r = self.bkk.create_market_sell_order(code, ord_qty_02) if tn < tn_153000 else self.bkk.create_over_sell_order(code, ord_qty_02)
                                    _ror = ror(bal_fst * ord_qty_02, bal_cur * ord_qty_02)

                                    if sel_r['rt_cd'] == '0':
                                        print(f'매도 - 종목: {code}, 수익: {round(_ror, 4)}')
                                        sel_lst.append({'c': '[S2] ' + code, 'r': round(_ror, 4)})
                                        obj_lst[code]['s'] = sel_cnt + 1
                                        obj_lst[code]['d'] = datetime.datetime.now().strftime('%Y%m%d')

                                        if is_qty_02:
                                            obj_lst.pop(code, None)
                                    else:
                                        msg = sel_r['msg1']
                                        print(f'{msg}')

                                elif (sel_cnt == 3) and (t3 <= los_dif):
                                        
                                    sel_r = self.bkk.create_market_sell_order(code, bal_qty) if tn < tn_153000 else self.bkk.create_over_sell_order(code, bal_qty)
                                    _ror = ror(bal_fst * bal_qty, bal_cur * bal_qty)

                                    if sel_r['rt_cd'] == '0':
                                        print(f'매도 - 종목: {code}, 수익: {round(_ror, 4)}')
                                        sel_lst.append({'c': '[S3] ' + code, 'r': round(_ror, 4)})
                                        obj_lst[code]['s'] = sel_cnt + 1
                                        obj_lst[code]['d'] = datetime.datetime.now().strftime('%Y%m%d')
                                        obj_lst.pop(code, None)
                                    else:
                                        msg = sel_r['msg1']
                                        print(f'{msg}')

                            elif hp <= bal_pft:

                                sel_r = self.bkk.create_market_sell_order(code, bal_qty) if tn < tn_153000 else self.bkk.create_over_sell_order(code, bal_qty)
                                _ror = ror(bal_fst * bal_qty, bal_cur * bal_qty)

                                if sel_r['rt_cd'] == '0':
                                    print(f'매도 - 종목: {code}, 수익: {round(_ror, 4)}')
                                    sel_lst.append({'c': '[S+] ' + code, 'r': round(_ror, 4)})
                                    obj_lst.pop(code, None)
                                else:
                                    msg = sel_r['msg1']
                                    print(f'{msg}')

                            elif bal_pft <= ct:

                                sel_r = self.bkk.create_market_sell_order(code, bal_qty) if tn < tn_153000 else self.bkk.create_over_sell_order(code, bal_qty)
                                _ror = ror(bal_fst * bal_qty, bal_cur * bal_qty)

                                if sel_r['rt_cd'] == '0':
                                    print(f'매도 - 종목: {code}, 수익: {round(_ror, 4)}')
                                    sel_lst.append({'c': '[S-] ' + code, 'r': round(_ror, 4)})
                                    obj_lst.pop(code, None)
                                else:
                                    msg = sel_r['msg1']
                                    print(f'{msg}')


        save_file(FILE_URL_BLNC_10M, obj_lst)

        sel_txt = ''
        for sl in sel_lst:
            sel_txt = sel_txt + '\n' + str(sl['c']) + ' : ' + str(sl['r'])
        
        _tn = datetime.datetime.now()
        _tn_152000 = _tn.replace(hour=15, minute=20, second=0)
        _tn_div = _tn.minute % 10
        _tn_sec = _tn.second
        _tn_del = None

        if _tn_div == 0:
            if tn_div == 9: 
                _tn_del = 0
                _tn_sec = 0
            else:
                _tn_del = 10
        elif _tn_div == 1:
            if tn_div == 9: 
                _tn_del = 0
                _tn_sec = 0
            else:
                _tn_del = 9
        elif _tn_div == 2:
            _tn_del = 8
        elif _tn_div == 3:
            _tn_del = 7
        elif _tn_div == 4:
            _tn_del = 6
        elif _tn_div == 5:
            _tn_del = 5
        elif _tn_div == 6:
            _tn_del = 4
        elif _tn_div == 7:
            _tn_del = 3
        elif _tn_div == 8:
            _tn_del = 2
        elif _tn_div == 9:
            _tn_del = 1

        if _tn > _tn_152000:
            self.init_stockorder_timer = threading.Timer((60 * (30 - _tn.minute)) - _tn_sec, self.stock_order)
        else:
            self.init_stockorder_timer = threading.Timer((60 * _tn_del) - _tn_sec, self.stock_order)

        if self.bool_stockorder_timer:
            self.init_stockorder_timer.cancel()

        self.init_stockorder_timer.start()

        line_message(f'Bot10Swing \n시작 : {tn}, \n표기 : {tn_df_idx} \n종료 : {_tn}, {sel_txt}')


    # def market_to_excel(self, rebalance=False, filter=False):

    #     tn = datetime.datetime.now()
    #     if rebalance:
    #         tn = tn.replace(hour=15, minute=30, second=0)
    #     tn_092000 = tn.replace(hour=9, minute=20, second=0)
        
    #     if tn > tn_092000:

    #         tn_div = tn.minute % 10
    #         tn_del = None

    #         if tn_div == 0:
    #             tn_del = 11
    #         elif tn_div == 1:
    #             tn_del = 12
    #         elif tn_div == 2:
    #             tn_del = 13
    #         elif tn_div == 3:
    #             tn_del = 14
    #         elif tn_div == 4:
    #             tn_del = 15
    #         elif tn_div == 5:
    #             tn_del = 16
    #         elif tn_div == 6:
    #             tn_del = 17
    #         elif tn_div == 7:
    #             tn_del = 18
    #         elif tn_div == 8:
    #             tn_del = 19
    #         elif tn_div == 9:
    #             tn_del = 10

    #         tn_req = ''
    #         tn_int = int(tn.strftime('%H%M%S'))
    #         tn_pos_a = 153000 <= tn_int
    #         tn_pos_b = 152000 < tn_int and tn_int < 153000
    #         tn_pos_c = tn_int <= 152000

    #         if tn_pos_a:
    #             tn_req = '153000'
    #         elif tn_pos_b:
    #             tn_req = '151900'
    #         elif tn_pos_c:
    #             tn_req = (tn - datetime.timedelta(minutes=tn_del)).strftime('%H%M00')

    #         if filter:
    #             fltr_list = self.bkk.filter_code_list()
    #             if len(fltr_list) > 0:
    #                 save_file(FILE_URL_SMBL_10M, fltr_list)

    #         _code_list = list(set(self.get_guant_code_list() + self.get_balance_code_list()))
            
    #         df_a = []
    #         for c, code in enumerate(_code_list):
    #             print(f"{c + 1}/{len(_code_list)} {code}")
    #             df_a.append(self.bkk.df_today_1m_ohlcv(code, tn_req, 10))
    #         df = pd.concat(df_a, axis=1)
    #         df = df.loc[~df.index.duplicated(keep='last')]

    #         print('##################################################')
    #         line_message(f'Bot10Swing Total Symbol Data: {len(_code_list)}개, \n{_code_list} \nFile Download Complete : {FILE_URL_DATA_10M}')
    #         print(df)
    #         df.to_excel(FILE_URL_DATA_10M)

    #         _tn = datetime.datetime.now()
    #         _tn_div = _tn.minute % 10

    #         if tn_pos_c and _tn_div == 9:
    #             self.bool_threshold = True


    # def deadline_to_excel(self):
    #     sym_lst = self.bkk.filter_code_list()
    #     if len(sym_lst) > 0:
    #         print('##################################################')
    #         line_message(f'Bot10Swing Symbol List: {len(sym_lst)}개, \n{sym_lst} \nFile Download Complete : {FILE_URL_SMBL_10M}')
    #         save_file(FILE_URL_SMBL_10M, sym_lst)


    def _market_to_excel(self):

        symbols = fdr.StockListing('KRX')
        
        kosp_list = self.bkk._filter_kospi_code_list()
        kosd_list = self.bkk._filter_kosdaq_code_list()
        remn_list = self.get_balance_code_list()

        q_list = kosp_list + kosd_list
        f_list = list(set(kosp_list + kosd_list + remn_list))

        f_list_a = []
        i = 1
        for fl in f_list:

            print(f'market check : {i} / {len(f_list)}')

            mk = symbols.loc[symbols['Code'] == fl]['Market'].iloc[-1]
            if mk == 'KOSPI':
                f_list_a.append(fl+'.KS')
            elif mk == 'KOSDAQ':
                f_list_a.append(fl+'.KQ')
            
            i += 1

        # f_list_a = ['060540.KQ', '043150.KQ', '168360.KQ', '038870.KQ', '124500.KQ', '001060.KS', '005420.KS', '042700.KS', '033240.KS', '303030.KQ', '263020.KQ', '014580.KS', '307750.KQ', '002620.KS', '105840.KS', '047040.KS', '099430.KQ', '047400.KS', '003310.KQ', '002760.KS', '042110.KQ', '378850.KS', '085370.KQ', '027710.KQ', '207760.KQ', '032620.KQ', '173130.KQ', '014440.KS', '417500.KQ', '008700.KS', '018470.KS', '066130.KQ', '023160.KQ', '039420.KQ', '170030.KQ', '095500.KQ', '053050.KQ', '126600.KQ', '092220.KS', '164060.KQ', '085660.KQ', '077360.KQ', '066670.KQ', '396300.KQ', '220260.KQ', '105630.KS', '024840.KQ', '118990.KQ', '040610.KQ', '001250.KS', '012800.KS', '017900.KS', '017960.KS', '054090.KQ', '083420.KS', '138490.KS', '007660.KS', '009190.KS', '006880.KS', '067080.KQ', '023350.KS', '086980.KQ', '009160.KS', '092300.KQ', '081150.KQ', '244920.KS', '075970.KQ', '287410.KQ', '125210.KQ', '006340.KS', '042370.KQ', '310200.KQ', '015230.KS', '047560.KQ', '257720.KQ', '002720.KS', '008350.KS', '058820.KQ', '002700.KS', '005010.KS', '248070.KS', '033100.KQ', '035810.KQ', '119850.KQ', '000430.KS', '000910.KS', '005390.KS', '267260.KS', '103590.KS', '012510.KS', '136480.KQ', '004710.KS', '049720.KQ', '053700.KQ', '002140.KS', '078150.KQ', '019550.KQ', '352480.KQ', '010040.KS', '090350.KS', '382480.KQ', '001430.KS', '131030.KQ', '010100.KS', '001780.KS', '045390.KQ', '009450.KS', '053980.KQ', '037270.KS', '053270.KQ', '036890.KQ', '119500.KQ', '267270.KS', '006060.KS', '021050.KS', '001790.KS', '013310.KQ', '317400.KS', '005160.KQ', '025320.KQ', '050760.KQ', '001390.KS', '061250.KQ', '032850.KQ', '094820.KQ', '094840.KQ', '182360.KQ', '441270.KQ', '204610.KQ', '040160.KQ', '046390.KQ', '094480.KQ', '037950.KQ', '027970.KS', '353810.KQ', '126880.KQ', '293480.KS', '281740.KQ', '084650.KQ', '005680.KS', '008970.KS', '004310.KS', '011330.KS', '053690.KS', '032960.KQ', '065440.KQ', '120240.KQ', '285490.KQ', '241690.KQ', '017040.KS', '005690.KS', '353200.KS', '041190.KQ', '004560.KS', '027580.KQ', '036120.KQ', '102370.KQ', '137950.KQ', '335890.KQ', '071200.KQ', '003070.KS', '205470.KQ', '010470.KQ', '008040.KS', '011150.KS', '060560.KQ', '000480.KS', '064800.KQ']

        tn_d = datetime.datetime.today()

        df_10m_a = []
        i = 1
        for fsl in f_list_a:

            print(f'yfinance download : {i} / {len(f_list_a)}')

            df_10m_a_a = []

            for x in reversed(range(8)):
                tn_b = tn_d - relativedelta(days=x)
                tn_a = tn_d - relativedelta(days=x+1)

                df_base_10m = yf.download(tickers=fsl, start=tn_a.strftime('%Y-%m-%d'), end=tn_b.strftime('%Y-%m-%d'), interval='5m', prepost=True)
                if not (df_base_10m.empty):
                    pprint(df_base_10m.index.to_list())
                    df_base_10m['Open_p'] = df_base_10m['Open'].shift(-1)
                    df_base_10m['High_p'] = df_base_10m['High'].shift(-1)
                    df_base_10m['Low_p'] = df_base_10m['Low'].shift(-1)
                    df_base_10m['Adj Close_p'] = df_base_10m['Adj Close'].shift(-1)
                    df_base_10m['Volume_p'] = df_base_10m['Volume'].shift(-1)

                    df_10m_a_a_a = []
                    j = 0
                    for x, row in df_base_10m.iterrows():
                        if j % 2 == 0:
                            if not (math.isnan(row['Adj Close_p'])):
                                str_o = row['Open']
                                str_h = max(row['High'], row['High_p'])
                                str_l = min(row['Low'], row['Low_p'])
                                str_c = row['Adj Close_p']
                                str_v = sum([row['Volume'], row['Volume_p']])
                                df_10m_a_a_a.append(str(str_o) + '|' + str(str_h) + '|' + str(str_l) + '|' + str(str_c) + '|' + str(str_v))
                            else:
                                df_10m_a_a_a.append(str(row['Open']) + '|' + str(row['High']) + '|' + str(row['Low']) + '|' + str(row['Adj Close_p']) + '|' + str(row['Volume']))
                        j += 1

                    df_10m_a_a.append(pd.DataFrame({fsl.split('.')[0]: df_10m_a_a_a}))

            df_10m_a.append(pd.concat(df_10m_a_a, axis=0).tail(80).reset_index(level=None, drop=True))

            i += 1

        fnal_df = pd.concat(df_10m_a, axis=1)
        print('##################################################')
        save_file(FILE_URL_SMBL_10M, q_list)
        save_xlsx(FILE_URL_DATA_10M, fnal_df)
        line_message(f'Bot10Swing Total Symbol Data: {len(f_list)}개, \n{f_list} \nFile Download Complete : {FILE_URL_DATA_10M}')
        print(fnal_df)
        
    
    def get_balance_code_list(self, obj=False):
        l = self.bkk.fetch_balance()['output1']
        a = []
        o = {}
        if len(l) > 0:
            for i in l:
                if int(i['ord_psbl_qty']) != 0:
                    if obj:
                        p = i['prpr']
                        q = i['ord_psbl_qty']
                        a = i['pchs_avg_pric']
                        o[i['pdno']] = {
                            'q': int(q),
                            'p': float(p),
                            'a': float(a),
                            'pft': float(p)/float(a),
                            'ptp': float(a) * int(q),
                            'ctp': float(p) * int(q)
                        }
                    else:
                        a.append(i['pdno'])
        return o if obj else a
    
    
    def get_guant_code_list(self):
        _l = load_file(FILE_URL_SMBL_10M)
        l = [str(int(i)).zfill(6) for i in _l]
        return l
    

if __name__ == '__main__':

    B10 = Bot10Swing()
    B10._market_to_excel()

    while True:

        try:

            t_n = datetime.datetime.now()
            t_083000 = t_n.replace(hour=8, minute=30, second=0)
            t_091000 = t_n.replace(hour=9, minute=10, second=0)
            t_152500 = t_n.replace(hour=15, minute=25, second=0)
            t_153000 = t_n.replace(hour=15, minute=30, second=0)
            t_160000 = t_n.replace(hour=16, minute=0, second=0)

            if t_n >= t_083000 and t_n <= t_153000 and B10.bool_marketday == False:
                if B10.bkk.fetch_marketday() == 'Y':
                    B10._market_to_excel()
                if os.path.isfile(os.getcwd() + '/token.dat'):
                    os.remove('token.dat')
                B10.init_per_day()
                B10.bool_marketday = True
                B10.bool_marketday_end = False

                line_message(f'Bot10Swing Stock Start' if B10.init_marketday == 'Y' else 'Bot10Swing Holiday Start')

            if B10.init_marketday == 'Y':

                if t_n > t_152500 and t_n < t_153000 and B10.bool_stockorder_timer == False:
                    B10.bool_stockorder_timer = True

                if t_n >= t_091000 and t_n <= t_153000 and B10.bool_stockorder == False:
                    B10.stock_order()
                    B10.bool_stockorder = True

            if t_n == t_160000 and B10.bool_marketday_end == False:

                if B10.init_marketday == 'Y':
                    # B10._market_to_excel(True, True)
                    B10.bool_stockorder_timer = False
                    B10.bool_stockorder = False

                B10.bool_marketday = False
                B10.bool_marketday_end = True

                line_message(f'Bot10Swing Stock End' if B10.init_marketday == 'Y' else 'Bot10Swing Holiday End')

        except Exception as e:

            line_message(f"Bot10Swing Error : {e}")
            break