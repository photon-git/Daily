# Railway 部署步骤

## 前提条件
- GitHub 账号
- Railway 账号（railway.app，用 GitHub 登录）
- DeepSeek API Key

## 第一步：准备 GitHub 仓库

把 `daily/` 目录推到 GitHub（注意：fonts/ 里只上传思源黑体，微软雅黑有版权不要上传）：

```bash
cd daily/

# 创建 .gitignore
cat > .gitignore << 'EOF'
__pycache__/
output/*.png
output/*.html
fonts/msyh.ttf
fonts/msyh-b.ttf
.env
EOF

git init
git add .
git commit -m "init daily forecast app"

# 推到 GitHub
git remote add origin https://github.com/你的用户名/daily-forecast.git
git push -u origin main
```

## 第二步：Railway 部署

1. 打开 [railway.app](https://railway.app)，用 GitHub 登录
2. 点 **New Project** → **Deploy from GitHub repo**
3. 选择刚才的仓库
4. 点 **Deploy Now**

## 第三步：配置环境变量

在 Railway 项目页面 → **Variables** → 添加：

```
DEEPSEEK_API_KEY = sk-你的key
```

## 第四步：获取访问地址

部署完成后，Railway 自动生成地址：
```
https://daily-forecast-xxx.up.railway.app
```

把这个地址发给业务员即可，HTTPS 已自动配好。

## 费用

- 免费额度：$5/月（约够跑 500 小时）
- 超出后：按用量计费，内部工具基本用不完

## 注意事项

- Railway 服务器在海外，国内访问可能略慢（1-3秒）
- 如果团队在国内且对速度有要求，改用阿里云轻量服务器
- `output/` 目录的图片在 Railway 上重启后会清空（是临时存储），用户下载后保存到本地即可
