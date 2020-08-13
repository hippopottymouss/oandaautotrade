from oandapyV20 import API
from oandapyV20.exceptions import V20Error
from oandapyV20.endpoints.pricing import PricingStream
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.positions as positions
from time import sleep
import pandas as pd
import datetime
import pytz

#use this as referrence: https://qiita.com/THERE2/items/f716565c884e7750c6c1

#set account and token
accountID = "yourid"
access_token = 'yourtoken'

api = API(access_token=access_token, environment="practice")


def prices_to_df(apireq):
    """Get pandas dataframe with info on candlecharts.
    input: API credentials
    output: dataframe"""
    w = 20

    df_list = []
    for data in apireq['candles']:
        if data['complete'] == True:
            df_dict = data['mid']
            df_dict['time'] = data['time']
            df_list.append(df_dict)

    # print(df_list)

    df = pd.DataFrame(df_list)

    df = df.set_index('time')
    df['MA20'] = round(df['c'].rolling(window=w).mean(), 3)
    df['20dSTD'] = round(df['c'].rolling(window=w).std(), 3)

    df['Upper'] = df['MA20'] + (df['20dSTD'] * 2)
    df['Lower'] = df['MA20'] - (df['20dSTD'] * 2)

    return df

def closing_time():
    """determine if it's time to close trades
    input: None
    output: bool (True/False)"""
    now = datetime.datetime.now(tz=pytz.timezone('US/Eastern'))
    current_hour = now.hour
    current_minute = now.minute
    current_weekday = now.weekday()

    if (current_weekday == 4) and (current_hour == 16) and (current_minute >= 49):
        return True

    return False

def daily_closing():
    """determine if it's time to close the script for today
    input: None
    output: bool (True/False)"""
    now = datetime.datetime.now(tz=pytz.timezone('US/Eastern'))
    current_hour = now.hour
    current_minute = now.minute

    if (current_hour == 16) and (current_minute >= 50):
        "Closing for now..."
        return False

    return True

def change_pos(df):
    """determine whether to buy/sell/close
    input: pandas dataframe
    output: sig (str) variable (None, buy, sell, close)"""

    if df.empty:
        return None

    # close if trading hours almost closing
    if closing_time():
        # Close
        return("close")

    if (float(df.iloc[[-1]]["o"].values[0]) > float(df.iloc[[-1]]["Upper"].values[0])) and (float(df.iloc[[-1]]["c"].values[0]) < float(df.iloc[[-1]]["Upper"].values[0])):
        # Sell
        return("sell")

    elif (float(df.iloc[[-1]]["o"]) < float(df.iloc[[-1]]["Lower"])) and (float(df.iloc[[-1]]["c"]) > float(df.iloc[[-1]]["Lower"])):
        # Buy
        return("buy")

    return None

def close_order(sig, number):
    """close existing positions per position.
    inputs: sig (str) variable (None, buy, sell, close)
    AND number (str) variable
    output: None"""

    # depending on long/short, vary data inputted to API request
    if sig == "long":
        units = "longUnits"
    elif sig == "short":
        units = "shortUnits"

    data = {
      units: number
    }


    r = positions.PositionClose(accountID=accountID,
                                 instrument='USD_JPY',
                                 data=data)
    api.request(r)

def close_all_positions():
    """close existing positions before proceeding.
    input: None
    output: None"""

    pos_dict = {}
    r = positions.OpenPositions(accountID=accountID)
    if not api.request(r)['positions'] == []:
        for position in api.request(r)['positions']:
            if position["long"]:
                pos_dict['long'] = position["long"]['units']
            if position["short"]:
                pos_dict['short'] = position["short"]['units']

        if 'long' in pos_dict:
            if pos_dict['long'] != '0':
                close_order('long', pos_dict['long'])
        if 'short' in pos_dict:
            if pos_dict['short'] != '0':
                close_order('short', pos_dict['short'])

def make_order(sig):
    """ make an order based on signal.
    input: sig (str) variable (None, buy, sell, close)
    output: bool (True or False)"""

    # first check your positions and close if necessary
    close_all_positions()

    # part 2: enter new positions!

    if sig == "close":
        return False

    #Buy if buy
    if sig == "buy":
        units = "150"

    #Sell if sell
    elif sig == "sell":
        units = "-150"


    data = {
     "order": {
        "units": units,
        "instrument": "USD_JPY",
        "timeInForce": "FOK",
        "type": "MARKET",
        "positionFill": "DEFAULT"
      }
    }

    r = orders.OrderCreate(accountID, data=data)
    api.request(r)

    return daily_closing()

def not_closed():
    """input: None
    output: bool (True/False)"""
    now = datetime.datetime.now(tz=pytz.timezone('US/Eastern'))
    current_hour = now.hour
    current_weekday = now.weekday()

    if (current_weekday ==5):
        print("Saturday-- closed for now...")
        return False

    if (current_weekday ==4) and (current_hour > 16):
        print("Friday after hours-- closed for now...")
        return False

    if (current_weekday ==6) and (current_hour < 17):
        print("Sunday before hours-- closed for now...")
        return False

    return True

def check_position():
    """close existing positions before proceeding.
    input: None
    output: None"""

    pos_dict = {}
    r = positions.OpenPositions(accountID=accountID)
    if not api.request(r)['positions'] == []:
        for position in api.request(r)['positions']:
            if position["long"]:
                pos_dict['long'] = position["long"]['units']
            if position["short"]:
                pos_dict['short'] = position["short"]['units']

        if 'long' in pos_dict:
            if pos_dict['long'] != '0':
                print('I have an existing Long position')
                return "buy"
        if 'short' in pos_dict:
            if pos_dict['short'] != '0':
                print('I have an existing Short position')
                return "sell"
    return None

def main():

    keep = not_closed()

    prior_sig = check_position()
    print(prior_sig)

    while keep == True:

        # get df
        params = {
          "count": 25,
          "granularity": "M10"
        }
        r = instruments.InstrumentsCandles(instrument="USD_JPY", params=params)

        try:
            df = prices_to_df(api.request(r))
        except TypeError:
            print("TypeError !!")
            # return empty dataframe
            df = pd.DataFrame({'A' : []})

        #find signal
        sig = change_pos(df)


        if sig:
            print("sig")
            prior_sig = check_position()
            if prior_sig != sig:
                prior_sig = sig
                # should close if closing time
                keep = make_order(sig)

        else:
            print("No Sig")
            keep = daily_closing()

        # rest & run every 10 mins
        print("resting...")
        if keep == True:
            sleep(550)

        else:
            print("Done!")

    print ("Job done, sleeping...")

if __name__ == "__main__":
    main()