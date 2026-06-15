# 日负荷预测图片生成工具 — 使用文档

## 目录结构

```
daily/
├── run_daily.py            # 入口：自然语言 → 自动出图
├── daily_parser.py         # Agent：DeepSeek 解析文本
├── daily_png_renderer.py   # Agent：matplotlib 渲染 PNG
├── assets/
│   ├── bj.png              # 背景图
│   ├── jiaobiao.png        # 左上角标
│   └── lm.png              # 左侧光晕装饰
├── fonts/
│   ├── msyh.ttf            # 微软雅黑 Regular
│   ├── msyh-b.ttf          # 微软雅黑 Bold
│   ├── SourceHanSansSC-Regular.otf
│   └── SourceHanSansSC-Bold.otf
└── output/                 # 生成的图片存放目录
```

---

## 依赖安装

```bash
pip install matplotlib pillow numpy openai
```

---

## 使用方式

### 方式一：测试渲染（不需要 API，用内置 mock 数据）

```bash
cd /path/to/daily
python3 daily_png_renderer.py
```

输出：`output/daily_test.png`

---

### 方式二：完整流程（自然语言输入 → DeepSeek 解析 → 出图）

```bash
cd /path/to/daily
export DEEPSEEK_API_KEY=sk-xxxxxx
python3 run_daily.py
```

运行后粘贴预测文字，按 **Ctrl+D** 提交，自动出图到 `output/daily_YYYY-MM-DD.png`。

---

## 支持的输入格式

工具支持任意格式的自然语言，DeepSeek 自动提取关键数据：

**口语流水账：**
```
各位，今天是6月9日，明天6月10日（周二）预计全网最大负荷9.83亿千瓦，
未来七天峰值预计10.63亿千瓦，暂无预警。
昨天6月8日实际跑了9.39，我们预测的是9.52，准确率98.6%，偏差不大。
```

**微信群消息：**
```
6/10号数据：
明天11号（周四）预测10.2亿
七天最高10.9亿，预警：无
昨天复盘：实际9.8 预测9.75 准确率99.5%
```

**正式报告：**
```
预测日期明天6月12日星期五，最大负荷预计9.60亿千瓦。
七天内高点10.40亿千瓦，无预警。
昨天复盘：实际9.75，预测9.50，准确率97.4%，
偏差原因：华南气温比预期高2度，空调负荷超预期。
```

---

## 输出样式

- **尺寸**：1920 × 动态高度（随数据行数自动变化）
- **内容**：
  - 顶部角标 + 标题
  - 发布日期 / 来源单位
  - 预测表（明日负荷 / 未来七天 / 预警信息）
  - 复盘表（实际值 / 预测值 / 准确率 / 偏差原因）
