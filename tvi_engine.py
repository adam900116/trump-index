#!/usr/bin/env python3
"""
TVI - Trump Volatility Index 动态计算引擎
每日自动抓取数据，重新计算指数，更新仪表盘
"""

import json
import os
import time
import datetime
import urllib.request
import urllib.parse
from pathlib import Path

# ─── 配置 ───────────────────────────────────────────────
WORKSPACE = Path(__file__).parent
DATA_FILE = WORKSPACE / "tvi_data.json"
OUTPUT_HTML = WORKSPACE / "index.html"
GATEWAY_PORT = os.environ.get("AUTH_GATEWAY_PORT", "19000")


# ─── 搜索工具 ────────────────────────────────────────────

def search_news(keyword: str, days_back: int = 7) -> list:
    """通过 ProSearch 搜索最新新闻"""
    from_time = int(time.time()) - (days_back * 86400)
    payload = json.dumps({"keyword": keyword, "from_time": from_time}).encode("utf-8")
    
    try:
        req = urllib.request.Request(
            f"http://localhost:{GATEWAY_PORT}/proxy/prosearch/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("data", {}).get("docs", [])
    except Exception as e:
        print(f"[搜索失败] {keyword}: {e}")
        return []


# ─── 各维度计算 ──────────────────────────────────────────

def calculate_political_pressure() -> float:
    """政治压力指数 (0-10)"""
    score = 5.0
    docs = search_news("Trump approval rating poll 2025", days_back=14)
    negative_kw = ["impeach", "lawsuit", "indictment", "resign", "low approval", "unpopular"]
    positive_kw = ["high approval", "popular", "winning", "landslide"]
    for doc in docs[:5]:
        text = (doc.get("passage", "") + doc.get("title", "")).lower()
        for kw in negative_kw:
            if kw in text:
                score += 0.5
        for kw in positive_kw:
            if kw in text:
                score -= 0.3
    return min(10.0, max(0.0, score))


def calculate_economic_pressure() -> float:
    """经济压力指数 (0-10)"""
    score = 5.0
    docs = search_news("US stock market economy recession 2025", days_back=7)
    bad_kw = ["recession", "crash", "plunge", "inflation high", "unemployment rise", "bear market"]
    good_kw = ["rally", "boom", "growth", "bull market", "record high"]
    for doc in docs[:5]:
        text = (doc.get("passage", "") + doc.get("title", "")).lower()
        for kw in bad_kw:
            if kw in text:
                score += 0.6
        for kw in good_kw:
            if kw in text:
                score -= 0.4
    return min(10.0, max(0.0, score))


def calculate_media_attention() -> float:
    """媒体关注度 (0-10)，关注度越低发病概率越高"""
    score = 5.0
    docs = search_news("Trump news today", days_back=3)
    if len(docs) < 3:
        score += 2.0
    elif len(docs) > 8:
        score -= 1.0
    return min(10.0, max(0.0, score))


def calculate_days_since_last_incident() -> float:
    """距上次发病天数 (0-10)"""
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        last_incident = data.get("last_incident_date")
        if last_incident:
            last_dt = datetime.datetime.fromisoformat(last_incident)
            days = (datetime.datetime.now() - last_dt).days
            return min(10.0, days / 14.0 * 10.0)
    return 5.0


def calculate_legal_pressure() -> float:
    """司法压力指数 (0-10)"""
    score = 5.0
    docs = search_news("Trump court case legal trial 2025", days_back=14)
    keywords = ["trial", "verdict", "guilty", "conviction", "sentenced", "appeal"]
    for doc in docs[:5]:
        text = (doc.get("passage", "") + doc.get("title", "")).lower()
        for kw in keywords:
            if kw in text:
                score += 0.4
    return min(10.0, max(0.0, score))


def predict_direction() -> dict:
    """预测发病方向"""
    directions = {
        "中国": 0.60,
        "伊朗/中东": 0.25,
        "欧盟": 0.10,
        "拉美": 0.05,
    }
    china_docs = search_news("Trump China trade tariff", days_back=7)
    iran_docs = search_news("Trump Iran Middle East", days_back=7)
    if len(china_docs) > 3:
        directions["中国"] = min(0.80, directions["中国"] + 0.05)
    if len(iran_docs) > 3:
        directions["伊朗/中东"] = min(0.40, directions["伊朗/中东"] + 0.05)
    total = sum(directions.values())
    return {k: round(v / total, 2) for k, v in directions.items()}


# ─── 主计算 ──────────────────────────────────────────────

def calculate_tvi() -> dict:
    print("[TVI] 开始计算特朗普发病指数...")

    political = calculate_political_pressure()
    economic = calculate_economic_pressure()
    media = calculate_media_attention()
    interval = calculate_days_since_last_incident()
    legal = calculate_legal_pressure()

    raw_score = (
        political * 0.30 +
        economic * 0.25 +
        media * 0.20 +
        interval * 0.15 +
        legal * 0.10
    )
    tvi = round(raw_score * 10, 1)

    if tvi >= 80:
        risk_level, risk_color = "极危", "#FF2D2D"
    elif tvi >= 65:
        risk_level, risk_color = "高危", "#FF6B00"
    elif tvi >= 45:
        risk_level, risk_color = "警戒", "#FFD600"
    else:
        risk_level, risk_color = "安全", "#00FF87"

    directions = predict_direction()

    result = {
        "tvi": tvi,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "components": {
            "political": round(political, 2),
            "economic": round(economic, 2),
            "media": round(media, 2),
            "interval": round(interval, 2),
            "legal": round(legal, 2),
        },
        "directions": directions,
        "updated_at": datetime.datetime.now().isoformat(),
        "next_window": "4月1-15日",
        "confidence": 72,
    }

    print(f"[TVI] 计算完成: {tvi}/100 · {risk_level}")
    return result


def save_data(data: dict):
    history = []
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            existing = json.load(f)
            history = existing.get("history", [])

    history.append({
        "date": datetime.date.today().isoformat(),
        "tvi": data["tvi"],
        "risk_level": data["risk_level"],
    })
    history = history[-90:]

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({**data, "history": history}, f, ensure_ascii=False, indent=2)

    print(f"[TVI] 数据已保存: {DATA_FILE}")


def fetch_recent_incidents() -> list:
    """搜索最近重大事件，返回时间线条目"""
    incidents = []

    queries = [
        ("Trump Iran attack threat nuclear deal 2025 2026", "🇮🇷 伊朗/中东"),
        ("Trump tariff trade war China 2025 2026", "🇨🇳 中国"),
        ("Trump threat sanction Europe NATO 2025 2026", "🇪🇺 欧盟"),
        ("Trump Cuba Venezuela Latin America 2025 2026", "🌎 拉美"),
    ]

    for query, direction in queries:
        docs = search_news(query, days_back=180)
        for doc in docs[:2]:
            title = doc.get("title", "").strip()
            date = doc.get("date", "")[:10]
            passage = doc.get("passage", "").strip()[:80]
            if title and date and len(title) > 5:
                # 简单评分：标题越短越精准
                incidents.append({
                    "date": date,
                    "direction": direction,
                    "title": title[:30],
                    "desc": passage,
                    "score": None,  # 待计算
                })

    # 按日期排序，取最近8条
    incidents.sort(key=lambda x: x["date"], reverse=True)
    return incidents[:8]


def update_html(data: dict):
    """直接把最新数据写进HTML静态内容，彻底替换硬编码数字"""
    if not OUTPUT_HTML.exists():
        print("[TVI] 警告: index.html不存在，跳过HTML更新")
        return

    import re

    tvi = int(data["tvi"])
    risk_level = data["risk_level"]
    directions = data["directions"]

    if tvi >= 80:
        risk_en = "EXTREME RISK"
    elif tvi >= 65:
        risk_en = "HIGH RISK"
    elif tvi >= 45:
        risk_en = "MEDIUM RISK"
    else:
        risk_en = "LOW RISK"

    html = OUTPUT_HTML.read_text(encoding="utf-8")

    # 1. 替换主分数
    html = re.sub(r'(<div class="tvi-score-bg"[^>]*>)\d+\.?\d*(</div>)', rf'\g<1>{tvi}\2', html)
    html = re.sub(r'(<div class="tvi-score"[^>]*>)\d+\.?\d*(</div>)', rf'\g<1>{tvi}\2', html)
    html = re.sub(r'(<div class="gauge-value"[^>]*>)\d+\.?\d*(</div>)', rf'\g<1>{tvi}\2', html)

    # 2. 替换风险标签
    html = re.sub(
        r'(<div class="risk-badge"[^>]*>)\s*<span>⚠</span>[^<]*(</div>)',
        rf'\g<1>\n      <span>⚠</span> {risk_level} · {risk_en}\n    \2',
        html
    )

    # 3. 替换顶部状态栏
    html = re.sub(
        r'(<div style="color: var\(--red\)">)[^<]*(</div>)',
        rf'\g<1>{risk_level}\2', html
    )

    # 4. 替换方向概率
    dir_flags = ["🇨🇳", "🇮🇷", "🇪🇺", "🌎"]
    dir_items = list(directions.items())
    for i, (name, prob) in enumerate(dir_items[:4]):
        pct = int(prob * 100)
        flag = dir_flags[i]
        # 替换百分比数字和进度条宽度
        html = re.sub(
            rf'({re.escape(flag)}</div>\s*<div class="direction-name">[^<]*</div>\s*<div class="direction-bar-wrap"><div class="direction-bar" style="width:)\d+%',
            rf'\g<1>{pct}%', html
        )
        html = re.sub(
            rf'({re.escape(flag)}.*?direction-pct">)\d+%(</div>)',
            rf'\g<1>{pct}%\2', html, flags=re.DOTALL
        )

    # 5. 更新时间线（搜索最新事件）
    print("[TVI] 搜索最新发病事件...")
    incidents = fetch_recent_incidents()
    if incidents:
        timeline_html = ""
        for inc in incidents:
            hot_class = ' hot' if inc["date"] >= "2025-01-01" else ''
            timeline_html += f'''      <div class="timeline-item{hot_class}">
        <div class="timeline-date">{inc["date"]} · {inc["direction"]}</div>
        <div class="timeline-event">{inc["title"]}</div>
        <div class="timeline-score">TVI 自动更新</div>
      </div>\n'''

        html = re.sub(
            r'(<div class="timeline">)\s*.*?(</div>\s*</div>\s*<!-- Market)',
            rf'\g<1>\n{timeline_html}    \2',
            html, flags=re.DOTALL
        )

    # 6. 更新JSON数据块
    json_str = json.dumps({**data}, ensure_ascii=False, indent=2)
    html = re.sub(
        r'<script id="tvi-data">[\s\S]*?</script>',
        f'<script id="tvi-data">\nwindow.TVI_DATA = {json_str};\n</script>',
        html
    )

    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"[TVI] HTML已更新: TVI={tvi}, {risk_level}, 时间线{len(incidents)}条")


def main():
    print("=" * 50)
    print("  TVI - Trump Volatility Index Engine v2.1")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    data = calculate_tvi()
    save_data(data)
    update_html(data)

    print("\n" + "=" * 50)
    print(f"  TVI: {data['tvi']}/100 · {data['risk_level']}")
    print(f"  主要方向: {list(data['directions'].keys())[0]}")
    print(f"  下次窗口: {data['next_window']}")
    print("=" * 50)

    return data


if __name__ == "__main__":
    main()
