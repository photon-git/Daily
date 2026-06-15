"""
日负荷预测图片生成工具 — Streamlit 界面
用法：streamlit run app.py
"""

import streamlit as st
import sys, os, json
from datetime import datetime
from PIL import Image

# 把 daily/ 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daily_parser       import parse_daily_report
from daily_png_renderer import render_daily_png

# ── 页面配置 ──────────────────────────────────────────
st.set_page_config(
    page_title="日负荷预测图片生成",
    page_icon="⚡",
    layout="centered",
)

st.title("⚡ 日负荷预测图片生成工具")
st.caption("支持口语、微信消息、正式报告等任意格式输入")

# ── 输入区 ────────────────────────────────────────────
raw_text = st.text_area(
    "粘贴预测文字",
    height=220,
    placeholder="""例如：
各位，今天是6月10日，明天6月11日（周三）预计全网最大负荷10.05亿千瓦，
七天内最高可能到10.80，没什么预警。
今天6月10日的实际是9.75，之前预报的9.68，准确率99.3%，原因没啥问题。"""
)

dept = st.text_input("来源单位", value="用电监测分析专班")

col1, col2 = st.columns([2, 1])
with col1:
    generate_btn = st.button("🚀 一键生成", type="primary", use_container_width=True)
with col2:
    st.caption("⏱ 约 5-10 秒")

# ── 生成逻辑 ──────────────────────────────────────────
if generate_btn:
    if not raw_text.strip():
        st.warning("请先输入预测文字")
        st.stop()

    # Step 1: 解析
    with st.status("⚙️ Agent① 解析文本中...", expanded=True) as status:
        try:
            data = parse_daily_report(raw_text)
            if dept:
                data['dept'] = dept
            status.update(label="✅ 文本解析完成", state="complete")
        except Exception as e:
            status.update(label=f"❌ 解析失败：{e}", state="error")
            st.stop()

    # 展示解析结果
    with st.expander("📋 解析结果预览", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("预测日期", data.get("forecast_date", "-"))
            st.metric("发布日期", data.get("report_date", "-"))
        with col_b:
            forecast = data.get("forecast", [])
            if forecast:
                st.metric("明日最大负荷", forecast[0].get("value", "-") + " 亿千瓦")
            if len(forecast) > 1:
                st.metric("未来七天峰值", forecast[1].get("value", "-") + " 亿千瓦")

        review = data.get("review", [])
        if review:
            st.markdown("**昨日复盘：**")
            for r in review:
                st.markdown(
                    f"- {r.get('date','')}：实际 **{r.get('actual','')}** 亿千瓦｜"
                    f"预测 {r.get('forecast','')}｜准确率 **{r.get('accuracy','')}**"
                )

    # Step 2: 生成图片
    with st.status("🎨 Agent② 生成图片中...", expanded=True) as status:
        try:
            today   = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            out_dir = os.path.join(os.path.dirname(__file__), "output")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"daily_{today}.png")

            render_daily_png(data, output_path=out_path)
            status.update(label="✅ 图片生成完成", state="complete")
        except Exception as e:
            status.update(label=f"❌ 生成失败：{e}", state="error")
            st.error(str(e))
            st.stop()

    # 展示图片
    st.divider()
    img = Image.open(out_path)
    st.image(img, caption=f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", use_column_width=True)

    # 下载按钮
    with open(out_path, "rb") as f:
        st.download_button(
            label="⬇️ 下载 PNG",
            data=f,
            file_name=f"日负荷预测_{data.get('forecast_date','')}.png",
            mime="image/png",
            type="primary",
            use_container_width=True,
        )

# ── 侧边栏：历史记录 ──────────────────────────────────
with st.sidebar:
    st.header("📁 历史记录")
    out_dir = os.path.join(os.path.dirname(__file__), "output")
    if os.path.exists(out_dir):
        pngs = sorted(
            [f for f in os.listdir(out_dir) if f.endswith(".png") and f != "daily_test.png"],
            reverse=True
        )[:10]
        if pngs:
            for fname in pngs:
                fpath = os.path.join(out_dir, fname)
                with open(fpath, "rb") as f:
                    st.download_button(
                        label=f"📄 {fname}",
                        data=f,
                        file_name=fname,
                        mime="image/png",
                        key=fname,
                    )
        else:
            st.caption("暂无历史记录")
    else:
        st.caption("暂无历史记录")

    st.divider()
    st.caption("需要 DEEPSEEK_API_KEY 环境变量")
    if os.environ.get("DEEPSEEK_API_KEY"):
        st.success("✅ API Key 已配置")
    else:
        st.error("❌ 未配置 API Key")
        st.code("export DEEPSEEK_API_KEY=sk-xxx")
