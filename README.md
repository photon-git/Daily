# 飞书智能图片生成服务

4 个飞书机器人，接收消息自动生成图片回传。

## 项目结构

```
├── webhook.py          # FastAPI 主入口
├── requirements.txt
├── bots/
│   ├── daily/          # 日报机器人
│   ├── weekly/         # 周报机器人
│   ├── province/       # 省份周榜机器人
│   └── elec_week/      # 电量周度数据机器人
├── assets/             # 图片素材
├── fonts/              # 字体文件
└── output/             # 生成图片（不入库）
```

## 部署

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp .env.example .env
# 填入各机器人的 App ID / App Secret 和 DeepSeek API Key
```

### 启动服务

```bash
uvicorn webhook:app --host 0.0.0.0 --port 8080
```

## Webhook 路由

| 机器人 | 路由 | 触发方式 |
|--------|------|----------|
| 日报 | `/webhook` | 群内发文字 |
| 周报 | `/webhook/weekly` | 群内发 Word 文件 |
| 省份周榜 | `/webhook/province` | 群内发 Excel 文件 |
| 电量周度 | `/webhook/elec_week` | 群内 @ 机器人发文字 |
