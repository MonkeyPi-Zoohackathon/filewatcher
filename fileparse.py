import asyncio
import contextlib
import csv
import datetime
import json
import re
import os
from typing import NamedTuple
import LatLon23
import utm
import websockets

from twilio.rest import Client


ACCOUNT_SID = ""
AUTH_TOKEN = ""
#CLIENT = Client(ACCOUNT_SID, AUTH_TOKEN)

FILE = os.path.join(os.path.dirname(__file__), "data.csv")


class Alert(NamedTuple):
    alert_type: str
    time: str
    location: str
    context: str
    audio_message: str

def create_alert(row):
    loc = parse_location(row[4])
    if loc:
        loc_str = format_location(loc)
    else:
        loc_str = ''
    return Alert(row[0], f"{row[2]} {row[3]}", loc_str, row[5], generate_audio_alert(row[2], fuzz_location(loc), row[0], row[5]))

EMOJI_MAP = {
    "CAMERA ALERT": "📷",
    "GROUND SENSOR ALERT": "👣🐾",
    "RANGER EMERGENCY ALERT": "👮🎆",
    "ARMED INTRUDER": "🔫"
}

def generate_audio_alert(time, location, alert_type=None, context=None):
    return f"THREAT ALERT. {time}. WATERHOLE 6. {context or alert_type or ''}"

def generate_sms(alert):
    alert_emoji = EMOJI_MAP.get(alert.alert_type, alert.alert_type)
    context_emoji = EMOJI_MAP.get(alert.context, alert.context)

    return f"‼️ {alert_emoji or ''} {context_emoji or ''} WATERHOLE 6 {alert.time}"

def fuzz_location(latlon):
    if latlon:
        return f"""{latlon.lat.degree}°{abs(latlon.lat.minute)}'{abs(int(latlon.lat.second))}\", {latlon.lon.degree}°{abs(latlon.lon.minute)}'{abs(int(latlon.lon.second))}\""""
    return ''

def format_location(latlon):
    return f"""{latlon.lat.degree}°{abs(latlon.lat.minute)}'{abs(latlon.lat.second)}\", {latlon.lon.degree}°{abs(latlon.lon.minute)}'{abs(latlon.lon.second)}\""""

UTM_REGEX = re.compile(r"^UTM (\d\d)([A-Za-z]) (\d+) (\d+)$")
def parse_location(raw):
    raw = raw.strip()
    utm_mo = re.fullmatch(UTM_REGEX, raw)
    with contextlib.suppress(ValueError):
        if utm_mo:
            gps = utm.to_latlon(int(utm_mo[3]), int(utm_mo[4]), int(utm_mo[1]), utm_mo[2])
            latlon = LatLon23.LatLon(gps[0], gps[1])
        else:
            _, lat, lon = raw.split()
            latlon = LatLon23.string2latlon(lat, lon, 'd%°%m%\'%S%"%H')
        return latlon
    return None

async def watch_file(websocket, path):
    print(f"Connected {websocket}")
    last_time = os.stat(FILE).st_mtime
    sent_alerts = set()
    while True:
        m_time = os.stat(FILE).st_mtime
        if m_time > last_time:
            print("File modified")
            last_time = m_time
            with open(FILE, 'r', encoding='latin_1') as f:
                c = csv.reader(f)
                for row in c:
                    if row[0].startswith('#'):
                        continue
                    alert = create_alert(row)
                    if alert not in sent_alerts:
                        print(f"Sending alert: {alert}")
                        await websocket.send(json.dumps(alert._asdict()))
                        # CLIENT.api.account.messages.create(
                        #     to="+447786820992",
                        #     from_="+441746802047",
                        #     body=generate_sms(alert))
                    sent_alerts.add(alert)


start_server = websockets.serve(watch_file, '0.0.0.0', 9998)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
