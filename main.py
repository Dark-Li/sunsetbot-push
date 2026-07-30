import os,requests
from datetime import datetime,timedelta,timezone
import json

print("SENDKEY =", repr(os.getenv("SENDKEY")))

cfg=json.load(open("config.json",encoding="utf-8"))
SENDKEY=os.environ["SENDKEY"]
cn=timezone(timedelta(hours=8))
h=datetime.now(cn).hour
events=[("今日日落","set_1"),("明日日出","rise_2")] if h<18 else [("明日日出","rise_2"),("明日日落","set_2")]
models=["GFS","EC"]
msg=""
for city in cfg["cities"]:
    msg+=f"# {city}\n"
    for title,event in events:
        msg+=f"## {title}\n"
        for model in models:
            d=requests.get("https://sunsetbot.top/",params={"intend":"select_city","query_city":city,"event":event,"model":model},timeout=30).json()
            img="https://sunsetbot.top"+d["img_href"]
            msg+=f"### {model}\n- 火烧云：{d['tb_quality']}\n- 时间：{d['tb_event_time']}\n- AOD：{d['tb_aod']}\n\n![]({img})\n"
url = f"https://sctapi.ftqq.com/{SENDKEY}.send"

print(url)

r = requests.post(
    url,
    data={
        "title": "🌇 SunsetBot 每日预报",
        "desp": msg
    },
    timeout=30
)

print("HTTP:", r.status_code)
print("Response:")
print(r.text)

r.raise_for_status()
