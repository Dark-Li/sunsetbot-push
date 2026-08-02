import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
import requests


def get_event_icon(title):
    return "🌅" if "日出" in title else "🌇"


def format_time(time_str):
    """'2026-08-02 19:44:25' -> '19:44'（去掉日期与秒数，更紧凑）"""
    if not time_str or time_str == "未知":
        return "未知"
    parts = time_str.split(" ")
    t = parts[1] if len(parts) > 1 else time_str
    return t[:5]


def split_value_text(raw):
    """将 '0.687（中烧）' 拆分为 ('0.687', '中烧')"""
    if not raw or raw == "未知":
        return "未知", ""
    m = re.match(r"^\s*([0-9.]+)\s*[（(]?\s*(.*?)\s*[）)]?\s*$", str(raw))
    if m:
        return m.group(1), m.group(2)
    return str(raw), ""


def quality_emoji(level_text):
    """根据火烧云等级文字返回对应色点"""
    if "世纪" in level_text:
        return "🟣"
    if "大烧" in level_text:
        return "🔴"
    if "中烧" in level_text:
        return "🟠"
    if "小烧" in level_text or "微烧" in level_text:
        return "🟡"
    return "⚪"


WEEKDAYS = "一二三四五六日"


def date_label(day_offset, cn_tz):
    """返回 'MM-DD 周X' 形式的日期标签"""
    d = datetime.now(cn_tz).date() + timedelta(days=day_offset)
    return f"{d.strftime('%m-%d')} 周{WEEKDAYS[d.weekday()]}"


def fix_img_url(img_href):
    """修复 SunsetBot 图片路径问题
    接口返回: /image/cross_section/...
    真实路径: https://sunsetbot.top/static/media/cross_section/...
    """
    if not img_href:
        return ""

    # 将 /image/ 替换为 /static/media/，并去掉末尾多余的斜杠
    fixed_path = img_href.replace("/image/", "/static/media/").rstrip("/")

    if not fixed_path.startswith("http"):
        if not fixed_path.startswith("/"):
            fixed_path = "/" + fixed_path
        return f"https://sunsetbot.top{fixed_path}"

    return fixed_path


def main():
    # 1. 检查环境变量
    sendkey = os.getenv("SENDKEY")
    if not sendkey:
        print("❌ Error: 未找到环境变量 SENDKEY！")
        sys.exit(1)

    # 2. 读取配置文件
    try:
        with open("config.json", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"❌ Error: 读取 config.json 失败: {e}")
        sys.exit(1)

    # 3. 判断时间段 (UTC+8)
    cn_tz = timezone(timedelta(hours=8))
    now = datetime.now(cn_tz)

    if now.hour < 18:
        events = [("今日日落", "set_1", 0), ("明日日出", "rise_2", 1)]
        push_title = "🌇 SunsetBot 晚霞预报"
    else:
        events = [("明日日出", "rise_2", 1), ("明日日落", "set_2", 1)]
        push_title = "🌅 SunsetBot 朝晚霞预报"

    models = ["GFS", "EC"]
    msg_parts = [
        f"> 🗓 {now.strftime('%Y-%m-%d')} 周{WEEKDAYS[now.weekday()]}"
        " · 数据源自 SunsetBot\n\n"
    ]

    # 4. 请求 API 并构建排版
    with requests.Session() as session:
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

        cities = cfg.get("cities", [])
        for c_idx, city in enumerate(cities):
            msg_parts.append(f"## 📍 {city}\n\n")

            for title, event, day_offset in events:
                icon = get_event_icon(title)

                # 先抓取全部模型数据，再统一排版
                rows = []
                for model in models:
                    try:
                        res = session.get(
                            "https://sunsetbot.top/",
                            params={
                                "intend": "select_city",
                                "query_city": city,
                                "event": event,
                                "model": model,
                            },
                            timeout=15,
                        )
                        res.raise_for_status()
                        d = res.json()

                        q_val, q_text = split_value_text(d.get("tb_quality", ""))
                        aod_val, aod_text = split_value_text(d.get("tb_aod", ""))
                        rows.append(
                            {
                                "model": model,
                                "ok": True,
                                "time": format_time(d.get("tb_event_time", "未知")),
                                "quality": f"{quality_emoji(q_text)} **{q_val}** {q_text}".strip(),
                                "aod": f"{aod_val} {aod_text}".strip(),
                                "times_name": d.get("display_times_name", "-"),
                                "img": fix_img_url(d.get("img_href", "")),
                            }
                        )
                    except Exception as err:
                        print(
                            f"⚠️ Warning: 获取 {city} [{title} - {model}] 数据失败: {err}"
                        )
                        rows.append({"model": model, "ok": False})

                # 事件标题带上日期与发生时间，一眼看到重点
                event_time = next(
                    (r["time"] for r in rows if r.get("ok") and r["time"] != "未知"),
                    "",
                )
                head = f"### {icon} {title}（{date_label(day_offset, cn_tz)}）"
                if event_time:
                    head += f" · {event_time}"
                msg_parts.append(head + "\n\n")

                # 精简为三列表格，避免手机端换行错乱
                msg_parts.append("| 模型 | 火烧云质量 | AOD |\n")
                msg_parts.append("| :---: | :---: | :---: |\n")
                for r in rows:
                    if r["ok"]:
                        msg_parts.append(
                            f"| **{r['model']}** | {r['quality']} | {r['aod']} |\n"
                        )
                    else:
                        msg_parts.append(f"| **{r['model']}** | ❌ 获取失败 | - |\n")
                msg_parts.append("\n")

                # 起报时次并入一行引用，不再占用表格列
                names = [
                    f"{r['model']} {r['times_name']}"
                    for r in rows
                    if r.get("ok") and r.get("times_name") not in (None, "", "-")
                ]
                if names:
                    msg_parts.append(f"> ⏱ 起报时次：{' · '.join(names)}\n\n")

                # 拼接渲染正确的图片
                for r in rows:
                    if r.get("ok") and r.get("img"):
                        msg_parts.append(
                            f"**{r['model']} 预报图**\n\n![{r['model']}]({r['img']})\n\n"
                        )

            if c_idx < len(cities) - 1:
                msg_parts.append("---\n\n")

        # 5. 发送推送通知
        desp = "".join(msg_parts)
        push_url = f"https://sctapi.ftqq.com/{sendkey}.send"

        try:
            r = session.post(
                push_url,
                data={"title": push_title, "desp": desp},
                timeout=20,
            )
            print("HTTP Status:", r.status_code)
            print("Response:", r.text)
            r.raise_for_status()
            print("🚀 推送成功！")
        except Exception as e:
            print(f"❌ Error: 推送 Server酱 失败: {e}")


if __name__ == "__main__":
    main()
