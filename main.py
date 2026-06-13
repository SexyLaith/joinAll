import sys
import types

class DummyAudioop:
    error = Exception
    def mul(self, cp, size, factor): return b''
    def max(self, cp, size): return 0
    def lin2lin(self, fragment, width, newwidth): return b''
    def ratecv(self, fragment, width, nchannels, inrate, outrate, state): return (b'', None)
    def ulaw2lin(self, fragment, width): return b''
    def lin2ulaw(self, fragment, width): return b''
    def alaw2lin(self, fragment, width): return b''
    def lin2alaw(self, fragment, width): return b''

sys.modules['audioop'] = DummyAudioop()

import asyncio
import json
import os
from flask import Flask
import websockets
from werkzeug.serving import make_server
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "AFK System is Live 24/7"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    # استخدام سرفر أهدأ وأكثر توافقاً مع الخيوط (Threads)
    server = make_server('0.0.0.0', port, app)
    print(f"[*] Flask server starting on port {port}...", flush=True)
    server.serve_forever()

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# قراءة المتغيرات وضمان إزالة المسافات الزائدة
RAW_TOKENS = os.getenv("ACCOUNT_TOKEN", "")
TOKENS = [t.strip() for t in RAW_TOKENS.split(",") if t.strip()]

GUILD_ID = os.getenv("GUILD_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")

class DiscordVoiceAFK:
    def __init__(self, token, guild_id, channel_id, account_index):
        self.token = token
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.account_id = f"Account #{account_index}" 
        self.ws_url = "wss://gateway.discord.gg/?v=9&encoding=json"
        self.heartbeat_interval = None
        self.sequence = None
        self.user_id = None  

    async def send_heartbeat(self, ws):
        while True:
            if self.heartbeat_interval:
                await asyncio.sleep(self.heartbeat_interval / 1000)
                heartbeat_payload = {"op": 1, "d": self.sequence}
                try:
                    await ws.send(json.dumps(heartbeat_payload))
                except:
                    break
            else:
                await asyncio.sleep(1)

    async def join_voice(self, ws):
        voice_state_payload = {
            "op": 4,
            "d": {
                "guild_id": self.guild_id,
                "channel_id": self.channel_id,
                "self_mute": True,
                "self_deaf": True,
                "self_video": False
            }
        }
        await ws.send(json.dumps(voice_state_payload))

    async def start(self):
        # تفعيل flush=True لضمان ظهور النص في لـ Render فوراً
        print(f"[*] [{self.account_id}] Trying to connect to Discord Gateway...", flush=True)
        
        async for ws in websockets.connect(self.ws_url, max_size=None, ping_interval=None):
            try:
                hello_msg = await ws.recv()
                hello_data = json.loads(hello_msg)
                
                if hello_data['op'] == 10:  
                    self.heartbeat_interval = hello_data['d']['heartbeat_interval']
                    asyncio.create_task(self.send_heartbeat(ws))
                
                identify_payload = {
                    "op": 2,
                    "d": {
                        "token": self.token,
                        "capabilities": 8189,
                        "properties": {
                            "os": "Android",
                            "browser": "Discord Android",
                            "device": "phone"
                        },
                        "presence": {
                            "status": "dnd",
                            "since": 0,
                            "activities": [],
                            "afk": False
                        },
                        "compress": False
                    }
                }
                await ws.send(json.dumps(identify_payload))
                
                await asyncio.sleep(1.5)
                await self.join_voice(ws)
                print(f"[+] [{self.account_id}] Connected! Joined channel: {self.channel_id}", flush=True)

                async for message in ws:
                    data = json.loads(message)
                    if data.get('s'):
                        self.sequence = data['s']
                        
                    op = data.get('op')
                    t = data.get('t')
                    d = data.get('d', {})

                    if t == "READY":
                        self.user_id = d.get('user', {}).get('id')
                        print(f"[+] [{self.account_id}] Account Ready. User ID: {self.user_id}", flush=True)

                    elif t == "VOICE_STATE_UPDATE":
                        if self.user_id and d.get('user_id') == self.user_id:
                            current_channel = d.get('channel_id')
                            if current_channel != self.channel_id:
                                print(f"[!] [{self.account_id}] Kicked/Left. Rejoining...", flush=True)
                                await self.join_voice(ws)

                    if op == 7:
                        print(f"[!] [{self.account_id}] Reconnect requested by Discord.", flush=True)
                        break

            except websockets.ConnectionClosed as cc:
                print(f"[!] [{self.account_id}] Connection Closed ({cc.code}). Reconnecting in 5s...", flush=True)
                await asyncio.sleep(5)
                continue
            except Exception as e:
                print(f"[X] [{self.account_id}] Error occurred: {e}", flush=True)
                await asyncio.sleep(5)
                continue

async def main():
    tasks = []
    for index, token in enumerate(TOKENS, start=1):
        bot = DiscordVoiceAFK(token, GUILD_ID, CHANNEL_ID, index)
        tasks.append(bot.start())
    
    if tasks:
        await asyncio.gather(*tasks)
    else:
        print("[X] Critical Error: No valid tokens found to process!", flush=True)

if __name__ == "__main__":
    print("[*] Script initiated...", flush=True)
    if not TOKENS:
        print("[X] Critical Error: Missing ACCOUNT_TOKEN!", flush=True)
        sys.exit(1)
        
    if not GUILD_ID or not CHANNEL_ID:
        print("[X] Critical Error: Missing GUILD_ID or CHANNEL_ID!", flush=True)
        sys.exit(1)
        
    print(f"[*] Loaded tokens count: {len(TOKENS)}", flush=True)
    
    keep_alive()
    
    # تشغيل الاسينك وبدء العمل
    asyncio.run(main())
