import ccxt
import math
import pandas as pd
import time
from datetime import datetime
from config import myconfig

display_all_data = True
INVESTMENT_AMOUNT_DOLLARS = 100
MIN_PROFIT_DOLLARS = 5
BROKERAGE_PER_TRANSACTION_PERCENT = 0.1
skim = 1
base_currency = 'USDT'
testing = False

exchange = ccxt.binance({
    "apiKey": myconfig.API_KEY,
    "secret": myconfig.API_SECRET
})


def truncate(number, digits) -> float:
    # Improve accuracy with floating point operations, to avoid truncate(16.4, 2) = 16.39 or truncate(-1.13, 2) = -1.12
    nbDecimals = len(str(number).split('.')[1]) 
    if nbDecimals <= digits:
        return number
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper

# gets all possible triangular arbitrage combinations from exchange
def get_crypto_combinations(market_symbols, base):
    combinations = []
    for sym1 in market_symbols:   
        sym1_token1 = sym1.split('/')[0]
        sym1_token2 = sym1.split('/')[1]   
        if (sym1_token2 == base):
            for sym2 in market_symbols:
                sym2_token1 = sym2.split('/')[0]
                sym2_token2 = sym2.split('/')[1]
                if (sym1_token1 == sym2_token2):
                    for sym3 in market_symbols:
                        sym3_token1 = sym3.split('/')[0]
                        sym3_token2 = sym3.split('/')[1]
                        if((sym2_token1 == sym3_token1) and (sym3_token2 == sym1_token2)):
                            combination = {
                                'base':sym1_token2,
                                'intermediate':sym1_token1,
                                'ticker':sym2_token1,
                            }
                            combinations.append(combination)
    return combinations
        

# fethces the price of ticker by averaging the top 10 bids in orderbook
def fetch_current_ticker_price(ticker):
    ticker_details = exchange.fetch_ticker(ticker)
    close_price = ticker_details['close'] if ticker_details is not None else None
    market = exchange.load_markets()
    orderbook = exchange.fetch_order_book(ticker)
    bids = orderbook['bids']
    asks = orderbook['asks']

    if not bids or not asks:
        return 0

    # return average of top ask and bid
    ticker_price = (bids[0][0] + asks[0][0])/2

    return ticker_price

# checks if a triangular arbitrage combination makes profit via buy buy sell 
def check_buy_buy_sell(scrip1, scrip2, scrip3,initial_investment):
    
    # first scrip
    investment_amount1 = initial_investment
    current_price1 = fetch_current_ticker_price(scrip1)
    final_price = 0
    scrip_prices = {}
    
    if current_price1 != 0:
        buy_quantity1 = round(investment_amount1 / current_price1, 8)*skim
        time.sleep(1)

        ## second scrip
        investment_amount2 = buy_quantity1     
        current_price2 = fetch_current_ticker_price(scrip2)
        if current_price2 != 0:
            buy_quantity2 = round(investment_amount2 / current_price2, 8)*skim
            time.sleep(1)

            ## third scrip
            investment_amount3 = buy_quantity2     
            current_price3 = fetch_current_ticker_price(scrip3)
            if current_price3 != 0:
                sell_quantity3 = buy_quantity2
                final_price = round(sell_quantity3 * current_price3,3)
                scrip_prices = {scrip1 : current_price1, scrip2 : current_price2, scrip3 : current_price3}

    if(display_all_data):
        print(f'BUY BUY SELL: {scrip1} -> {scrip2} -> {scrip3}      Return: {final_price}')
                
    return final_price, scrip_prices

# checks if a triangular arbitrage combination makes profit via buy sell sell 
def check_buy_sell_sell(scrip1, scrip2, scrip3,initial_investment):
    # first scrip
    investment_amount1 = initial_investment
    current_price1 = fetch_current_ticker_price(scrip1)
    final_price = 0
    scrip_prices = {}
    if current_price1 != 0:
        buy_quantity1 = round(investment_amount1 / current_price1, 8)*skim
        time.sleep(1)

        # second scrip
        investment_amount2 = buy_quantity1     
        current_price2 = fetch_current_ticker_price(scrip2)
        
        if current_price2 != 0:
            sell_quantity2 = buy_quantity1
            sell_price2 = round(sell_quantity2 * current_price2,8)
            time.sleep(1)

            # third scrip
            investment_amount3 = sell_price2     
            current_price3 = fetch_current_ticker_price(scrip3)
            if current_price3 != 0:
                sell_quantity3 = sell_price2
                final_price = round(sell_quantity3 * current_price3,3)
                scrip_prices = {scrip1 : current_price1, scrip2 : current_price2, scrip3 : current_price3}

    print(f'BUY SELL SELL: {scrip1} -> {scrip2} -> {scrip3}      Return: {final_price}')

    return final_price,scrip_prices

# determines the profit/loss of an arbitrage combination 
def check_profit_loss(total_price_after_sell,initial_investment,transaction_brokerage, min_profit):
    apprx_brokerage = (transaction_brokerage * initial_investment/100 * 3)
    min_profitable_price = initial_investment + apprx_brokerage + min_profit
    profit_loss = round(total_price_after_sell - min_profitable_price,3)
    return profit_loss

# places a buy order
def place_buy_order(scrip, quantity, limit, balance):
    print(f'BUYING: {quantity} {scrip} at {fetch_current_ticker_price(scrip)}')
    if not testing:
        quantity = quantity*skim
        order = exchange.create_limit_buy_order(scrip, quantity, limit)
    else:
        params = {
            'test': True
        }
        order = exchange.create_order(scrip, 'limit', 'buy', quantity, limit, params)
    time.sleep(1)
    return order

# places a sell order
def place_sell_order(scrip, quantity, limit):
    print(f'SELLING: {quantity} {scrip} at {fetch_current_ticker_price(scrip)}')
    if not testing:
        order = exchange.create_limit_sell_order(scrip, quantity, limit)
    else:
        params = {
            'test': True
        }
        order = exchange.create_order(scrip, 'limit', 'buy', quantity, limit, params)

    time.sleep(1)
    return order 

# execute three way trade 
def place_trade_orders(type, scrip1, scrip2, scrip3, initial_amount, scrip_prices):
    final_amount = 0.0



    if type == 'BUY_BUY_SELL':
        #buy intermediate
        inter = scrip1.split('/')[0]
        s1_price = scrip_prices[scrip1]
        s1_quantity = initial_amount/s1_price
        bal = exchange.fetch_balance()
        inter_init_amount = bal[inter]['free']
        order1 = place_buy_order(scrip1, s1_quantity, s1_price, initial_amount)

        #update actual quantity of intermediate
        start = time.time()
        if not testing:
            while(1):
                # If waiting for more than 20 seconds, cancel order and place again
                if time.time() - start >= 20:
                    print(f'Cancelling order and retrying...')
                    exchange.cancel_order(order1['id'], scrip1, {'type': 'BUY'})
                    s1_price = fetch_current_ticker_price(scrip1)
                    s1_quantity = initial_amount/s1_price
                    order1 = place_buy_order(scrip1, s1_quantity, s1_price, initial_amount)
                    start = time.time()

                print(f'Waiting for {inter}')
                time.sleep(2)
                BALANCE = exchange.fetch_balance() #update balances
                quantity = BALANCE[inter]
                s1_quantity = quantity['free']
                if s1_quantity > inter_init_amount:
                    break

            

        print(f'You now have {s1_quantity} {inter}')

        #buy ticker
        tick = scrip2.split('/')[0]
        s2_price = scrip_prices[scrip2]
        adj_price = math.ceil(s2_price * 100000000)/100000000
        s2_quantity = s1_quantity/adj_price
        bal = exchange.fetch_balance()
        tick_init_amount = bal[tick]['free']
        order2 = place_buy_order(scrip2, s2_quantity, s2_price, s1_quantity)

        #update actual quantity of ticker
        start = time.time()
        if not testing:
            while(1):
                # If waiting for more than 20 seconds, cancel order and place again
                if time.time() - start >= 20:
                    print(f'Cancelling order and retrying...')
                    exchange.cancel_order(order2['id'], scrip2, {'type': 'BUY'})
                    s2_price = fetch_current_ticker_price(scrip2)
                    adj_price = math.ceil(s2_price * 100000000)/100000000
                    s2_quantity = s1_quantity/adj_price
                    order2 = place_buy_order(scrip2, s2_quantity, s2_price, s1_quantity)
                    start = time.time()
                print(f'Waiting for {tick}')
                time.sleep(2)
                BALANCE = exchange.fetch_balance() #update balances
                quantity2 = BALANCE[tick]
                s2_quantity = quantity2['free']
                if s2_quantity > tick_init_amount:
                    break

            

        print(f'You now have {s2_quantity} {tick}')

        #sell ticker for base coin
        base = scrip3.split('/')[1]
        s3_price = scrip_prices[scrip3]
        s3_quantity = s2_quantity
        bal = exchange.fetch_balance()
        base_init_amount = bal[base]['free']
        order3 = place_sell_order(scrip3, s3_quantity, s3_price)

        #update actual quantity of base coin
        start = time.time()
        if not testing:
            while(1):
                # If waiting for more than 20 seconds, cancel order and place again
                if time.time() - start >= 20:
                    print(f'Cancelling order and retrying...')
                    exchange.cancel_order(order3['id'], scrip3, {'type': 'SELL'})
                    s3_price = fetch_current_ticker_price(scrip3)
                    s3_quantity = s2_quantity
                    order3 = place_sell_order(scrip3, s3_quantity, s3_price)
                    start = time.time()

                print(f'Waiting for {base}')
                time.sleep(2)
                BALANCE = exchange.fetch_balance()
                quantity3 = BALANCE[base]
                s3_quantity = quantity3['free']
                if s3_quantity > base_init_amount:
                    break

        print(f'You now have {s3_quantity} {base}')
            
            

        
    elif type == 'BUY_SELL_SELL':
        #buy intermediate
        inter = scrip1.split('/')[0]
        s1_price = scrip_prices[scrip1]
        s1_quantity = initial_amount/s1_price
        bal = exchange.fetch_balance()
        inter_init_amount = bal[inter]['free']
        order1 = place_buy_order(scrip1, s1_quantity, s1_price, initial_amount)

        #update actual quantity of intermediate
        start = time.time()
        if not testing:
            while(1): 
                # If waiting for more than 20 seconds, cancel order and place again
                if time.time() - start >= 20:
                    print(f'Cancelling order and retrying...')
                    exchange.cancel_order(order1['id'], scrip1, {'type': 'BUY'})
                    s1_price = fetch_current_ticker_price(scrip1)
                    s1_quantity = initial_amount/s1_price
                    order1 = place_buy_order(scrip1, s1_quantity, s1_price, initial_amount)
                    start = time.time()

                print(f'Waiting for {inter}')
                time.sleep(2)
                BALANCE = exchange.fetch_balance() #update balances
                quantity = BALANCE[inter]
                s1_quantity = quantity['free']
                if s1_quantity > inter_init_amount:
                    break

            

        print(f'You now have {s1_quantity} {inter}')
        
        #sell intermediate for ticker
        tick = scrip2.split('/')[1]
        s2_price = scrip_prices[scrip2]
        s2_quantity = s1_quantity
        bal = exchange.fetch_balance()
        tick_init_amount = bal[tick]['free']
        order2 = place_sell_order(scrip2, s2_quantity, s2_price)

        #update actual quantity of ticker
        start = time.time()
        if not testing:
            while(1):
                # If waiting for more than 20 seconds, cancel order and place again
                if time.time() - start >= 20:
                    print(f'Cancelling order and retrying...')
                    exchange.cancel_order(order2['id'], scrip2, {'type': 'SELL'})
                    s2_price = fetch_current_ticker_price(scrip2)
                    s2_quantity = s1_quantity
                    order2 = place_sell_order(scrip2, s2_quantity, s2_price)
                    start = time.time()

                print(f'Waiting for {tick}')
                time.sleep(2)
                BALANCE = exchange.fetch_balance() #update balances
                quantity2 = BALANCE[tick]
                s2_quantity = quantity2['free']
                if s2_quantity > tick_init_amount:
                    break

            

        print(f'You now have {s2_quantity} {tick}')
        
        # sell ticker for base coin
        base = scrip3.split('/')[1]
        s3_price = scrip_prices[scrip3]
        s3_quantity = s2_quantity
        bal = exchange.fetch_balance()
        base_init_amount = bal[base]['free']
        order3  = place_sell_order(scrip3, s3_quantity, s3_price)

        #update actual quantity of base coin
        start = time.time()
        if not testing:
            while(1):
                # If waiting for more than 20 seconds, cancel order and place again
                if time.time() - start >= 20:
                    print(f'Cancelling order and retrying...')
                    exchange.cancel_order(order3['id'], scrip3, {'type': 'SELL'})
                    s3_price = fetch_current_ticker_price(scrip3)
                    s3_quantity = s2_quantity*s2_price
                    order3 = place_sell_order(scrip3, s3_quantity, s3_price)
                    start = time.time()

                print(f'Waiting for {base}')
                time.sleep(2)
                BALANCE = exchange.fetch_balance()
                quantity3 = BALANCE[base]
                s3_quantity = quantity3['free']
                if s3_quantity > base_init_amount:
                    break

        print(f'You now have {s3_quantity} {base}')
            
    return final_amount

# check if a given arbitrage combination is profitable
def perform_triangular_arbitrage(scrip1, scrip2, scrip3, arbitrage_type,initial_investment, 
                               transaction_brokerage, min_profit):
    final_price = 0.0
    if(arbitrage_type == 'BUY_BUY_SELL'):
        # Check this combination for triangular arbitrage: scrip1 - BUY, scrip2 - BUY, scrip3 - SELL
        final_price, scrip_prices = check_buy_buy_sell(scrip1, scrip2, scrip3,initial_investment)
        
    elif(arbitrage_type == 'BUY_SELL_SELL'):
        # Check this combination for triangular arbitrage: scrip1 - BUY, scrip2 - SELL, scrip3 - SELL
        final_price, scrip_prices = check_buy_sell_sell(scrip1, scrip2, scrip3,initial_investment)
        
    profit_loss = check_profit_loss(final_price,initial_investment, transaction_brokerage, min_profit)

    if profit_loss>0:
        print(f"PROFIT-{datetime.now().strftime('%H:%M:%S')}:"\
              f"{arbitrage_type}, {scrip1},{scrip2},{scrip3}, Profit/Loss: {round(final_price-initial_investment,3)} ")
        place_trade_orders(arbitrage_type, scrip1, scrip2, scrip3, initial_investment, scrip_prices)



markets = exchange.fetchMarkets()
#market_symbols = [market['symbol'] for market in markets]

market_symbols = []
for market in markets:
    if(market['contract'] == False) and (market['info']['status'] == 'TRADING'):        
        market_symbols.append(market['symbol'])
        
print(f'No. of market symbols: {len(market_symbols)}')

base_combinations = get_crypto_combinations(market_symbols, base_currency)
print(f'No. of crypto combinations: {len(base_combinations)}')

cominations_df = pd.DataFrame(base_combinations)
cominations_df.head()

BALANCE = exchange.fetch_balance()
BASE_CURRENCY_BALANCE = BALANCE[base_currency]
# INVESTMENT_AMOUNT_DOLLARS = (BASE_CURRENCY_BALANCE['total'] - 30)*0.99975

print(f'INVESTMENT AMOUNT: {INVESTMENT_AMOUNT_DOLLARS}')

#while(1):
for combination in base_combinations:
        base = combination['base']
        intermediate = combination['intermediate']
        ticker = combination['ticker']


        s1 = f'{intermediate}/{base}'    # Eg: BTC/ADA
        s2 = f'{ticker}/{intermediate}'  # Eg: ETH/BTC
        s3 = f'{ticker}/{base}'          # Eg: ETH/ADA

        # Check triangular arbitrage for buy-buy-sell 
        perform_triangular_arbitrage(s1,s2,s3,'BUY_BUY_SELL',INVESTMENT_AMOUNT_DOLLARS,
                                BROKERAGE_PER_TRANSACTION_PERCENT, MIN_PROFIT_DOLLARS)
        time.sleep(1) 

        # Check triangular arbitrage for buy-sell-sell 
        perform_triangular_arbitrage(s3,s2,s1,'BUY_SELL_SELL',INVESTMENT_AMOUNT_DOLLARS,
                                BROKERAGE_PER_TRANSACTION_PERCENT, MIN_PROFIT_DOLLARS)
        time.sleep(1) 

print(f'PROGRAM EXECUTED ALL COMBINATIONS')
