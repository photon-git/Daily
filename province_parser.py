"""
province_parser.py
读取「市场信息收集表.xlsx」，生成 province_renderer.py 所需的 data 字典
"""

import os
import re
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_XLSX = os.path.join(_HERE, "assets", "市场信息收集表.xlsx")


def _extract_date_range(filename: str) -> str:
    """从文件名中提取日期范围，如「市场信息收集表（6.22-6.28）.xlsx」→「6月22日-6月28日」"""
    m = re.search(r'[（(](\d+)\.(\d+)-(\d+)\.(\d+)[）)]', filename)
    if m:
        m1, d1, m2, d2 = m.group(1), m.group(2), m.group(3), m.group(4)
        if m1 == m2:
            return f"{m1}月{d1}日-{d2}日"
        return f"{m1}月{d1}日-{m2}月{d2}日"
    return ""


def parse_xlsx(xlsx_path: str = DEFAULT_XLSX, date_range: str = "") -> dict:
    """
    读取 xlsx，返回 render_province_png 所需的 data 字典。

    date_range: 如 "6月22日-26日"，不传则从文件名自动提取
    """
    if not date_range:
        date_range = _extract_date_range(os.path.basename(xlsx_path))
    xl = pd.ExcelFile(xlsx_path)

    # ── 读各 sheet ──────────────────────────────────────
    # 总累计：省公司统计
    df_total_prov = xl.parse("(总累计省公司统计)省公司统计", header=0)
    df_total_prov.columns = ["省份", "报送数量", "覆盖地市数", "总地市数", "覆盖率", "覆盖区县数", "区县总数", "区县覆盖率"]

    # 总累计：合计行
    df_total_sum = xl.parse("(总累计省公司统计-合计)合计", header=0)
    df_total_sum.columns = ["合计", "报送数量", "覆盖地市数", "总地市数", "覆盖率", "覆盖区县数", "区县总数", "区县覆盖率"]
    total_row = df_total_sum.iloc[0]

    # 周累计：省公司统计
    df_week_prov = xl.parse("(周累计省公司统计)省公司统计", header=0)
    df_week_prov.columns = ["省份", "报送数量", "覆盖地市数", "总地市数", "覆盖率", "覆盖区县数", "区县总数", "区县覆盖率"]

    # 周累计：地市统计
    df_week_city = xl.parse("(周累计统计地市)统计地市", header=0)
    df_week_city.columns = ["省份", "地市", "上报数", "覆盖区县数"]

    # ── Block 1: 报送信息覆盖情况 ────────────────────────
    # 省份数：总累计中有报送的省份数
    prov_count = int((df_total_prov["报送数量"] > 0).sum())
    # 地市数、区县数从合计行取
    city_count   = int(total_row["覆盖地市数"])
    county_count = int(total_row["覆盖区县数"])

    block_overview = {
        "title": "报送信息覆盖情况",
        "cols": 3,
        "items": [
            {"name": "省份", "value": prov_count},
            {"name": "地市", "value": city_count},
            {"name": "区县", "value": county_count},
        ]
    }

    # ── Block 2: 地市全覆盖的省 ──────────────────────────
    # 覆盖率 == 1 即 覆盖地市数 == 总地市数
    full_cov = df_total_prov[
        (df_total_prov["覆盖地市数"] == df_total_prov["总地市数"]) &
        (df_total_prov["总地市数"] > 0)
    ].copy()
    full_cov = full_cov.sort_values("报送数量", ascending=False)

    full_items = []
    for _, row in full_cov.iterrows():
        n = int(row["覆盖地市数"])
        full_items.append({
            "name": str(row["省份"]),
            "city": f"{n}/{n}",
            "county": int(row["覆盖区县数"]),
        })

    block_full_cov = {
        "title": "地市全覆盖的省",
        "cols": 3,
        "items": full_items,
    }

    # ── Block 3: 本周报送信息最多的省 ────────────────────
    # 取本周有报送的省，按报送数量降序，最多5个，保留并列
    week_prov = df_week_prov[df_week_prov["报送数量"] > 0].sort_values("报送数量", ascending=False)
    top_prov = _top_with_ties(week_prov, "报送数量", base_n=3, max_n=5)

    block_top_prov = {
        "title": "本周报送信息最多的省",
        "layout": "single_row",
        "items": [
            {"name": str(r["省份"]), "value": int(r["报送数量"])}
            for _, r in top_prov.iterrows()
        ]
    }

    # ── Block 4: 本周报送信息最多的市 ────────────────────
    # 按地市上报数降序，最多5个，保留并列
    week_city = df_week_city[df_week_city["上报数"] > 0].sort_values("上报数", ascending=False)
    top_city = _top_with_ties(week_city, "上报数", base_n=3, max_n=5)

    block_top_city = {
        "title": "本周报送信息最多的市",
        "layout": "single_row",
        "items": [
            {"name": str(r["地市"]), "value": int(r["上报数"])}
            for _, r in top_city.iterrows()
        ]
    }

    return {
        "title": "用电市场跟踪周榜",
        "date_range": date_range,
        "blocks": [block_overview, block_full_cov, block_top_prov, block_top_city],
    }


def _top_with_ties(df, col, base_n=3, max_n=5):
    """取前 base_n 名，若第 base_n 名有并列则继续纳入，但不超过 max_n 条。"""
    if len(df) == 0:
        return df
    df = df.reset_index(drop=True)
    cutoff_val = df[col].iloc[min(base_n, len(df)) - 1]
    result = df[df[col] >= cutoff_val]
    return result.head(max_n)


# ── 测试 ──────────────────────────────────────────────
if __name__ == "__main__":
    import json
    data = parse_xlsx(date_range="6月22日-28日")
    print(json.dumps(data, ensure_ascii=False, indent=2))
