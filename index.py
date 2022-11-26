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
        entryPrice = messageList[7]
        targets = [messageList[i].split(" ")[1] for i in range(10, 14)]

        StopLoss = messageList[17].split("%")[0]
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
    rawPrice = float(binanceClient.get_symbol_ticker(symbol = symbol)['price'])
    decLen = len(str(rawPrice).split('.')[1])
    price = rawPrice * limit
    return round(price, decLen)

def quantityCalc(symbol, investment):
    info = binanceClient.get_symbol_info(symbol=symbol)
    Lotsize = float([i for i in info['filters'] if 
        i['filterType'] == 'LOT_SIZE'][0]['minQty'])
    price = pricecalc(symbol)
    print(price, Lotsize)
    qty = round(investment/price, 2)
    return qty

def makeOrder(type, name, marginMode, entryPrice, targets, stopLoss=5):
    # try:
        [A, B] = name.split("/")
        ABal = getAsset(A)
        print("current A assest", A, ABal)

        BBal = getAsset(B)
        print("current B assest", B, BBal)

        symbol = '' + A + B
        print("symbol -> ", symbol)

        side = Client.SIDE_BUY if type == "Long" else Client.SIDE_SELL

        price = float(BBal)
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

            for i in range(4):
                limitOrder = binanceClient.futures_create_order(
                    symbol=symbol,
                    type='LIMIT',
                    price=targets[i],
                    side='SELL',
                    quantity = quantity / 4,
                    timeInForce='GTC',
                )
                print(limitOrder)
                stopPrice = entryPrice * (100 - stopLoss) / 100.0
                print(stopPrice)
                stopSellOrder = binanceClient.futures_create_order(
                    symbol=symbol,
                    type='STOP_MARKET',
                    side='SELL',
                    quantity = quantity / 4,
                    timeInForce='GTC',
                    stopPrice = stopPrice
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


makeOrder("Short", "ANKR/USDT", 20, 16957, [16952, 16954, 16956, 16958])

client = TelegramClient(TEL_PHONE, TEL_API_ID, TEL_API_HASH)

client.connect()
if not client.is_user_authorized():
    print("Not authorized")
    client.send_code_request(TEL_PHONE)
    client.sign_in(TEL_PHONE, input('Enter the code: '))
print("Connected")

@client.on(events.NewMessage(chats = [TEL_CHANNEL_NAME]))
async def handler(event):
    newMessage = event.message.to_dict()['message']
    print("New signal: ", newMessage)
    name, marginMode, entryPrice, targets, stopLoss = parseMessage(newMessage)
    print("======>", name, marginMode, entryPrice, targets, stopLoss)
    if name != False:
        makeOrder(name, marginMode, entryPrice, targets, stopLoss)

    

client.start()
client.run_until_disconnected()