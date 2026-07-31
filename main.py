import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
import requests


def get_event_icon(title):
    return "🌅" if "日出" in title else "🌇"


def format_time(time_str):
    """将 '2026-07-31 19:45:51' 提炼为简短的时间 '19:45:51'"""
    if not time_str or time_str == "未知":
        return "未知"
    parts = time_str.split(" ")
    return parts[1] if len(parts) > 1 else time_str


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
    now_hour = datetime.now(cn_tz).hour

    if now_hour < 18:
        events = [("今日日落", "set_1"), ("明日日出", "rise_2")]
    else:
        events = [("明日日出", "rise_2"), ("明日日落", "set_2")]

    models = ["GFS", "EC"]
    msg_parts = []

    # 4. 请求 API 并构建排版
    with requests.Session() as session:
        session.headers.update({"User-Agent": "SunsetBot-Notifier/1.0"})

        cities = cfg.get("cities", [])
        for c_idx, city in enumerate(cities):
            msg_parts.append(f"# 📍 {city}\n\n")

            for title, event in events:
                icon = get_event_icon(title)
                msg_parts.append(f"### {icon} {title}\n\n")

                # 生成精简对齐的表格头
                msg_parts.append(
                    "| 模型 | 火烧云质量指数 | 发生时间 | AOD | 起报时次 |\n"
                )
                msg_parts.append(
                    "| :---: | :---: | :---: | :---: | :---: |\n"
                )

                images = []

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

                        # 提取质量数值并加粗突出 (例如将 '0.004（微烧）' 格式化为 '🔥 **0.004** (微烧)')
                        raw_quality = d.get("tb_quality", "未知")
                        quality_match = re.match(
                            r"^([0-9.]+)(.*)$", raw_quality
                        )
                        if quality_match:
                            val, text = quality_match.groups()
                            quality_display = f"🔥 **{val}** {text}"
                        else:
                            quality_display = f"**{raw_quality}**"

                        tb_time = format_time(d.get("tb_event_time", "未知"))
                        tb_aod = d.get("tb_aod", "未知")
                        times_name = d.get("display_times_name", "-")

                        img_url = f"https://sunsetbot.top{d.get('img_href', '')}"
                        images.append((model, img_url))

                        # 填充表格行
                        msg_parts.append(
                            f"| **{model}** | {quality_display} | `{tb_time}` | `{tb_aod}` | {times_name} |\n"
                        )

                    except Exception as err:
                        print(
                            f"⚠️ Warning: 获取 {city} [{title} - {model}] 数据失败: {err}"
                        )
                        msg_parts.append(
                            f"| **{model}** | ❌ 失败 | - | - | - |\n"
                        )

                msg_parts.append("\n")

                # 拼接图片区
                if images:
                    for model_name, img_link in images:
                        msg_parts.append(
                            f"**{model_name} 预报图：**\n\n![{model_name}]({img_link})\n\n"
                        )

            if c_idx < len(cities) - 1:
                msg_parts.append("---\n\n")

        # 5. 发送推送通知
        desp = "".join(msg_parts)
        push_url = f"https://sctapi.ftqq.com/{sendkey}.send"

        try:
            r = session.post(
                push_url,
                data={"title": "🌇 SunsetBot 晚霞预报", "desp": desp},
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
