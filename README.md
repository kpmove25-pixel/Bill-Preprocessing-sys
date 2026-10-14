# 票据预处理与 OCR 归档系统

局域网可用的发票预处理与 OCR 归档 Web 应用。将图片 / PDF 发票转换为 JPG，通过 OCR 或 PDF 文本层提取关键字段，去重，按购买方归档，并导出 Excel 汇总。

## 功能特性

- **多格式导入**：支持 JPG / PNG / BMP / TIFF / WEBP 等图片及 PDF（电子发票优先文本层，扫描件渲染后 OCR）
- **OCR 引擎可插拔**：默认 RapidOCR（纯 CPU、内置 ONNX 模型、离线可用），可选 PaddleOCR，缺失时优雅降级
- **字段自动提取**：发票类型、代码、号码、购买方/销售方、金额、税额、税率、开票日期、校验码、开票人等
- **低置信度标记**：OCR 置信度低于阈值时字段标记“待人工确认”，支持在线人工校正后重新导出
- **去重**：按「代码 + 号码」去重（20 位全电发票号码兜底），并跨任务历史查重（全局号码台账），生成重复报告
- **按购买方归档**：自动分文件夹、生成各购买方 Excel 与 Word 文档及总汇总表，支持 Word 打包下载
- **后台任务队列**：上传后异步处理，支持进度查看、取消、重试失败文件、删除
- **简单登录**：可选开启的 Bearer Token 登录（内存令牌，重启失效）

## 目录结构

```
票据凭证系统/
├── app/
│   ├── api/            # FastAPI 路由（auth/tasks/invoices/health/deps）
│   ├── core/           # 配置、数据库、安全、日志
│   ├── models/         # SQLAlchemy 模型（Task/Invoice/FileRecord/AuditLog）
│   ├── schemas/        # Pydantic 请求/响应模型
│   ├── services/       # OCR/图片/PDF/解析/去重/Excel/归档/任务编排
│   ├── workers/        # 后台线程队列
│   └── utils/          # 文件工具
├── web/                # 前端（原生 JS SPA）
├── scripts/            # 模拟票据生成脚本
├── tests/              # 单元测试
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── run.py              # 本地启动入口
```

## 快速开始

### 方式一：Docker（推荐）

```bash
docker compose up -d --build
```

默认访问 http://localhost:8000，账号 `admin` / 密码 `admin123`（见 `docker-compose.yml`）。

### 方式二：本地运行

```bash
# Linux / macOS
./start.sh

# Windows
start.bat

# 或手动
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

> 注意：`requirements.txt` 中的 `rapidocr-onnxruntime` 体积较大（含 ONNX 运行时）。若仅需无 OCR 的文本层提取，可将 `OCR_ENGINE` 设为 `none` 并跳过该依赖。

### Windows 部署前提

在 Windows 上原生运行前，请先安装：

1. **Python 3.9+**：安装时勾选 **Add Python to PATH**；
2. **Microsoft Visual C++ Redistributable**（x64）：RapidOCR 的 onnxruntime 依赖它；
3. **7-Zip**（或 WinRAR）：用于解压 `.rar` 压缩包（应用会自动探测 `7z` / `unrar`）。

完成后双击 `start.bat`，即可自动创建虚拟环境、安装依赖并启动服务。

## 配置

复制 `.env.example` 为 `.env` 后按需修改（应用启动时自动读取 `.env`）：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `APP_HOST` / `APP_PORT` | 监听地址 / 端口 | `0.0.0.0` / `8000` |
| `DATABASE_URL` | 数据库连接串 | `sqlite:///./data/app.db` |
| `USE_AUTH` | 是否开启登录 | `true` |
| `APP_USERNAME` / `APP_PASSWORD` | 登录账号 / 密码 | `admin` / `admin123` |
| `OCR_ENGINE` | OCR 引擎：`rapidocr` / `paddleocr` / `baidu` / `none` | `rapidocr` |
| `OCR_LANG` | OCR 语言 | `ch` |
| `BAIDU_API_KEY` | 百度云 API Key（`OCR_ENGINE=baidu` 时必填） | 空 |
| `BAIDU_SECRET_KEY` | 百度云 Secret Key（`OCR_ENGINE=baidu` 时必填） | 空 |
| `OCR_CONFIDENCE_THRESHOLD` | 置信度阈值 | `0.6` |
| `MAX_UPLOAD_SIZE_MB` | 单文件大小上限 | `50` |
| `JPG_QUALITY` | JPG 质量 | `92` |

## 测试

```bash
source .venv/bin/activate
pytest tests/ -v
```

生成模拟票据用于验收：

```bash
python scripts/make_sample_invoice.py          # 图片样例 -> samples/
python scripts/make_sample_invoice.py --pdf    # 额外生成多页 PDF
```

## 使用流程

1. 登录（若开启鉴权）
2. 拖拽或选择发票图片 / PDF，点击上传
3. 等待后台任务处理，查看进度
4. 在「识别结果」页校正低置信度字段
5. 点击「重新导出」触发去重 + 归档 + Excel 生成
6. 在「结果下载」页下载全部 Word 文档（zip）

## 说明与限制

- 登录令牌为内存实现，服务重启后失效（MVP 方案）
- RapidOCR 首次运行需加载模型，可能稍慢
- 去重键为「代码 + 号码」（20 位全电发票号码单独兜底）；历史号码入库全局台账，支持跨任务自动查重与「历史查重」手动查询
- 归档 / 导出以“人工校正后重新导出”为准，校正前仅作临时结果
