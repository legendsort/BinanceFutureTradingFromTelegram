from telethon.sync import TelegramClient, events

from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.tl.functions.messages import (GetHistoryRequest)
from telethon.tl.types import (
PeerChannel
)

import configparser
import json
import math
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
import asyncio

config = configparser.ConfigParser()
config.read('config.ini')
telegramConfig = config['telegram']
tradingConfig = config['trading']
binanceConfig = config['binance']


TEL_API_ID = telegramConfig['TELEGRAM_API_ID']
TEL_API_HASH = telegramConfig['TELEGRAM_API_HASH']
TEL_PHONE = telegramConfig['PHONE']
TEL_CHANNEL_NAME = telegramConfig['CHANNEL_NAME']

LEVEL = json.loads(tradingConfig['LEVEL'])
MOVE_STOP = tradingConfig['MOVE_STOP'] == 'YES'
INVEST_PERCENT = float(tradingConfig['INVEST_PERCENT'])

API_KEY = binanceConfig['API_KEY']
SECRET_KEY = binanceConfig['SECRET_KEY']
TEST = binanceConfig['TEST']

def parseMessage(message):
    print(TEST)
    if TEST == "true" and message == "":
        message = open("sampleSignal.txt", "r+", encoding='utf8').read()
    try:
        messageList = message.split("\n")
        if not messageList[0].endswith('VIP Signal'):
            return False, False, False, False, False, False
        type = messageList[2][1:]

        name = messageList[3].split(": ")[1]
        marginMode = messageList[4].split(": ")[1]
        entryPrice = float(messageList[7])
        targets = [float(messageList[i].split(" ")[1]) for i in range(10, 14)]

        StopLoss = int(messageList[17].split("%")[0])
        return type, name, marginMode, entryPrice, targets, StopLoss
    except Exception as e:
        print("an exception has occured when parsing - {}".format(e))
        return False, False, False, False, False, False


try:
    binanceClient = Client(API_KEY, SECRET_KEY, testnet=True)
    binanceClient.ping()
except Exception as e:
    print("an exception has occured when connecting binance api - {}".format(e))
    raise e

info = binanceClient.futures_exchange_info()


def getQuantityPrecision(symbol):
    for x in info['symbols']:
        if x['symbol'] == symbol:
            return x['quantityPrecision']
        pass

def getPricePrecision(symbol):
   for x in info['symbols']:
    if x['symbol'] == symbol:
        return x['pricePrecision']

def getTargetPrecision(symbol):
    step_size = 0
    for x in info['symbols']:
        if x['symbol'] == symbol:
            step_size = x['filters'][0]['tickSize']
    precision = int(round(-math.log(float(step_size), 10), 0))
    return precision

def getAsset(type):
    assets = binanceClient.futures_account_balance()
    for asset in assets:
        if asset['asset'] == type:
            print(type, " --->", asset['balance'])
            return asset['balance']
    print(type, " --->", 0)
    return 0

def adjustLeverage(symbol, client, leverage=20):
    client.futures_change_leverage(symbol=symbol, leverage=leverage)

def adjustMargintype(symbol, client, type='CROSSED'):
    client.futures_change_margin_type(symbol=symbol, marginType=type)
sampleSymbol = 'BTCUSDT'

def pricecalc(symbol, limit = 0.95):
    rawPrice = float(binanceClient.futures_symbol_ticker(symbol = symbol)['price'])
    # return rawPrice
    decLen = len(str(rawPrice).split('.')[1])
    price = rawPrice * limit
    return round(price, decLen)

def quantityCalc(symbol, investment):
    price = pricecalc(symbol)
    quantity = investment / price
    return float(round(quantity, getQuantityPrecision(symbol)))

def makeOrder(type, name, marginMode, entryPrice, targets, stopLoss=5):
    # try:

        names = name.split("/")
        print(names)
        A, B = names[0], names[1]
        ABal = getAsset(A)

        print("current A assest", A, ABal)

        BBal = getAsset(B)
        print("current B assest", B, BBal)

        symbol = '' + A + B
        # print("symbol -> ", symbol)
        # for x in info['symbols']:
        #     if x['symbol'] == symbol:
        #         print(x)
        side = Client.SIDE_BUY if type == "Long" else Client.SIDE_SELL

        price = float(BBal) * INVEST_PERCENT / 100.0
        quantity = quantityCalc(symbol, price)
        print(price, quantity)

        print("side ->", side)
        
        if side == Client.SIDE_BUY:
            # market order first
            marketOrder = binanceClient.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            print("===========>",marketOrder)
            stopPrice = round(entryPrice * (100 - stopLoss) / 100.0, getPricePrecision(symbol))
            print("Stop Price", stopPrice)
            futuresStopLoss = binanceClient.futures_create_order(
                symbol=symbol,
                type='STOP_MARKET',
                side='SELL',
                stopPrice=stopPrice,
                closePosition=True
            )
            print(futuresStopLoss)

            total = quantity
            for i in range(4):
                
                q = quantityCalc(symbol, float(BBal) * INVEST_PERCENT / 100.0 * LEVEL[i] / 100) if i < 3 else round(total, getQuantityPrecision(symbol))
                target = round(targets[i], getTargetPrecision(symbol))
                print(target,  q)
                total -= q
                
                try:
                    limitOrder = binanceClient.futures_create_order(
                        symbol=symbol,
                        type='LIMIT',
                        price=target,
                        side='SELL',
                        quantity = q,
                        timeInForce='GTX',
                    )
                except Exception as e:
                    print("Limit order")
            if MOVE_STOP == True:
                pre = 5
                while True:
                    orders = binanceClient.futures_get_open_orders(symbol=symbol)
                    now = len(orders)
                    if now < 2:
                        break
                    if pre != now:
                        print("----->", now)
                        binanceClient.futures_cancel_order(symbol=symbol, orderId = stopId)
                        if now == 4:
                            stopPrice = round(entryPrice, getPricePrecision(symbol))
                        else:
                            stopPrice = round(targets[3 - now], getPricePrecision(symbol))
                        
                        print("Stop Price changed to ", stopPrice)
                        futuresStopLoss = binanceClient.futures_create_order(
                            symbol=symbol,
                            type='STOP_MARKET',
                            side='SELL',
                            stopPrice=stopPrice,
                            closePosition=True
                        )
                        stopId = futuresStopLoss['orderId']
                        pre = now
                pass
                binanceClient.futures_cancel_order(symbol=symbol, orderId = stopId)
            pass
        else:
            # market order first
            marketOrder = binanceClient.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            print("===========>",marketOrder)

            stopPrice = round(entryPrice * (100 + stopLoss) / 100.0, getPricePrecision(symbol))
            
            print("Stop Price", stopPrice)
            futuresStopLoss = binanceClient.futures_create_order(
                symbol=symbol,
                type='STOP_MARKET',
                side='BUY',
                stopPrice=stopPrice,
                closePosition=True
            )
            print(futuresStopLoss)
            stopId = futuresStopLoss['orderId']
            
            total = quantity
            for i in range(4):
                q = quantityCalc(symbol, float(BBal) * INVEST_PERCENT / 100.0 * LEVEL[i] / 100) if i < 3 else round(total, getQuantityPrecision(symbol))

                target = round(targets[i], getTargetPrecision(symbol))
                print(target, q)
                total -= q
                try:
                    limitOrder = binanceClient.futures_create_order(
                        symbol=symbol,
                        type='LIMIT',
                        price=target,
                        side='BUY',
                        quantity = q,
                        timeInForce='GTX',
                    )
                    print(limitOrder)
                except Exception as e:
                    print("Limit order")
            if MOVE_STOP == True:
                pre = 5
                while True:
                    orders = binanceClient.futures_get_open_orders(symbol=symbol)
                    now = len(orders)
                    if now < 2:
                        break
                    if pre != now:
                        print("----->", now)
                        binanceClient.futures_cancel_order(symbol=symbol, orderId = stopId)
                        if now == 4:
                            stopPrice = round(entryPrice, getPricePrecision(symbol))
                        else:
                            stopPrice = round(targets[3 - now], getPricePrecision(symbol))
                        
                        print("Stop Price changed to ", stopPrice)
                        futuresStopLoss = binanceClient.futures_create_order(
                            symbol=symbol,
                            type='STOP_MARKET',
                            side='BUY',
                            stopPrice=stopPrice,
                            closePosition=True
                        )
                        stopId = futuresStopLoss['orderId']
                        pre = now
                binanceClient.futures_cancel_order(symbol=symbol, orderId = stopId)    
                pass
        

        
if TEST == "true":
    type, name, marginMode, entryPrice, targets, stopLoss = parseMessage("")
    print("======>", type, name, marginMode, entryPrice, targets, stopLoss)
    if name != False:
        makeOrder(type, name, marginMode, entryPrice, targets, stopLoss)

client = TelegramClient(TEL_PHONE, TEL_API_ID, TEL_API_HASH)

@client.on(events.NewMessage(chats = [1001682398986]))
async def handler(event):
    try:
        newMessage = event.message.to_dict()['message']
        print("New signal: ", newMessage)
        type, name, marginMode, entryPrice, targets, stopLoss = parseMessage(newMessage)
        print("======>", type, name, marginMode, entryPrice, targets, stopLoss)
        if name != False:
            makeOrder(type, name, marginMode, entryPrice, targets, stopLoss)
    except Exception as e:
        print("an exception has occured when traiding - {}".format(e))
        raise e
client.connect()
client.start()

client.run_until_disconnected()