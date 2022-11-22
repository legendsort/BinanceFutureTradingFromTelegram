from telethon.sync import TelegramClient, events

from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.tl.functions.messages import (GetHistoryRequest)
from telethon.tl.types import (
PeerChannel
)

env = open("env", "r+")
TEL_API_ID = env.readline().split("=")[1].rstrip()
TEL_API_HASH = env.readline().split("=")[1].rstrip()
TEL_API_PHONE = env.readline().split("=")[1].rstrip()
CHANNEL_NAME = env.readline().split("=")[1].rstrip()
client = TelegramClient(TEL_API_PHONE, TEL_API_ID, TEL_API_HASH)

client.connect()
if not client.is_user_authorized():
    print("Not authorized")
    client.send_code_request(TEL_API_PHONE)
    client.sign_in(TEL_API_PHONE, input('Enter the code: '))
print("Connected")

with client:
    
    chats = []
    last_date = None
    chunk_size = 200
    groups=[]
    chat = ""

    result = client(GetDialogsRequest(
                offset_date=last_date,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=chunk_size,
                hash = 0
            ))
    

    chats.extend(result.chats)
    for chat in chats:
        try:
            if chat.title == 'CRYPTO GURU VIP SIGNALS':
                print(chat)
                pass
        except:
            continue
    print(groups)

    offset_id = 0
    limit = 20
    all_messages = []
    total_messages = 0
    total_count_limit = 0

    while True:
        print("Current Offset ID is:", offset_id, "; Total Messages:", total_messages)
        history = client(GetHistoryRequest(
            peer='CRYPTO GURU VIP SIGNALS',
            offset_id=offset_id,
            offset_date=None,
            add_offset=0,
            limit=limit,
            max_id=0,
            min_id=0,
            hash=0
        ))
        if not history.messages:
            break
        messages = history.messages
        for message in messages:
            print(message.to_dict()['message'])

# @client.on(events.NewMessage(chats = [CHANNEL_NAME]))
# async def handler(event):
#     newMessage = event.message.to_dict()['message']
#     print("New signal: ", newMessage)

# client.start()
# client.run_until_disconnected()