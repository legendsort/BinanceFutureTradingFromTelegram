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

def parseMessage(message):
    # message = open("sampleSignal.txt", "r+", encoding='utf8').read()
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
    
def getPrecision(symbol):
   for x in info['symbols']:
    if x['symbol'] == symbol:
        print(x)
        return x['pricePrecision']

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
    decLen = len(str(rawPrice).split('.')[1])
    price = rawPrice * limit
    return round(price, decLen)

def quantityCalc(symbol, investment):
    info = binanceClient.futures_exchange_info() 
    info = info['symbols']
    step_size = 0
    for x in range(len(info)):
        if info[x]['symbol'] == symbol:
            for f in info[x]['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    break
    price = pricecalc(symbol)
    quantity = investment / price
    precision = int(round(-math.log(step_size, 10), 0))
    quantity = float(round(quantity, precision))
    return quantity

def makeOrder(type, name, marginMode, entryPrice, targets, stopLoss=5):
    # try:
        names = name.split("/")
        print(names)
        A, B = name[0], name[1]
        ABal = getAsset(A)

        print("current A assest", A, ABal)

        BBal = getAsset(B)
        print("current B assest", B, BBal)

        symbol = '' + A + B
        print("symbol -> ", symbol)

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
            print(marketOrder)
            stopPrice = round(entryPrice * (100 - stopLoss) / 100.0, getPrecision(symbol))
            print("Stop Price", stopPrice)
            futuresStopLoss = binanceClient.futures_create_order(
                symbol=symbol,
                type='STOP_MARKET',
                side='SELL',
                stopPrice=stopPrice,
                closePosition=True
            )
            print(futuresStopLoss)
            for i in range(4):
                print(targets[i], quantity)
                limitOrder = binanceClient.futures_create_order(
                    symbol=symbol,
                    type='LIMIT',
                    price=targets[i],
                    side='SELL',
                    quantity = round(quantity * LEVEL[i]/ 100.0, getPrecision(symbol)),
                    timeInForce='GTX',
                )
                
            pass
        else:
            # market order first
            order = binanceClient.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity,
            )
            for i in range(4):
                limitOrder = binanceClient.futures_create_order(
                    symbol=symbol,
                    type='LIMIT',
                    price=targets[i],
                    side='BUY',
                    quantity = quantity / 4,
                    timeInForce='GTC',
                )
                print(limitOrder)
                stopPrice = entryPrice * (100 + stopLoss) / 100.0
                print(stopPrice)
                stopBuyOrder = binanceClient.futures_create_order(
                    symbol=symbol,
                    type='STOP_MARKET',
                    side='BUY',
                    quantity = quantity / 4,
                    timeInForce='GTC',
                    stopPrice = stopPrice
                )
            pass

# type, name, marginMode, entryPrice, targets, stopLoss = parseMessage("AS")
# print("======>", type, name, marginMode, entryPrice, targets, stopLoss)
# if name != False:
#     makeOrder(type, name, marginMode, entryPrice, targets, stopLoss)


client = TelegramClient(TEL_PHONE, TEL_API_ID, TEL_API_HASH)


# for dialog Zin client.iter_dialogs():
#   if dialog.is_channel:
#       print(f'{dialog.id}:{dialog.title}')
# ans = client.get_entity(1001682398986)
# print(ans)
@client.on(events.NewMessage(chats = [1001682398986]))
async def handler(event):
    newMessage = event.message.to_dict()['message']
    print("New signal: ", newMessage)
    type, name, marginMode, entryPrice, targets, stopLoss = parseMessage(newMessage)
    print("======>", type, name, marginMode, entryPrice, targets, stopLoss)
    if name != False:
        makeOrder(name, marginMode, entryPrice, targets, stopLoss)
client.connect()
client.start()

client.run_until_disconnected()