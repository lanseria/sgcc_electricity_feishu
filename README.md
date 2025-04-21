# sgcc_electricity_feishu

国家电网飞书应用多维表格数据抓取

## Features

- 基于 Typer 的 CLI 命令行结构
- 丰富的终端输出（Rich）
- Python 项目配置（pyproject.toml）
- pytest 测试用例支持

## Installation

运行前请配置 `.env` 文件，可以从 `.env.example` 复制：

```bash
cp .env.example .env
```

`.env` 文件需包含以下参数（需从飞书获取）：

- 机器人 app id：`FEISHU_APP_ID=`
- 机器人 app secret：`FEISHU_APP_SECRET=`
- 表格 appToken：`BITABLE_APP_TOKEN=`
- 表格ID：`BITABLE_TABLE_ID=`
- 表格视图ID：`BITABLE_VIEW_ID=`

```bash
# 创建虚拟环境
python3 -m venv myenv
python3.12 -m venv myenv
source myenv/bin/activate  # macOS/Linux
# .\myenv\Scripts\Activate.ps1  # Windows

# 安装依赖
pip install -e .
```

## Usage

```bash
sef run-sync-job
sef schedule-daily
```

## Development

Run tests:
```bash
pytest
```

## Deployment

```bash
cp .env.example .env.prod
docker build -t sgcc_electricity_feishu:latest .
# 国内 
# docker build -t sgcc_electricity_feishu:latest -f Dockerfile.local .
docker compose up -d
```

## Project Structure

```
src/
  sgcc_electricity_feishu/
    __init__.py    # Package initialization
    cli.py         # CLI commands
    main.py        # App entry point
tests/             # Test cases
pyproject.toml     # Project configuration
```

## 资源链接

飞书多维表格模板：[点击访问](https://enjqkboeqf.feishu.cn/base/O94YbicNVapkVdsuzgIcojx3nWh?from=from_copylink)

验证码识别模型 captcha.onnx：请从 https://github.com/ARC-MX/sgcc_electricity_new 下载  
或使用以下命令直接下载：
```bash
curl -L -o captcha.onnx "https://github.com/ARC-MX/sgcc_electricity_new/raw/refs/heads/master/scripts/captcha.onnx"
```

讲解视频：（待补充）

## License

MIT

## 特别说明

本项目代码参考自 [https://github.com/ARC-MX/sgcc_electricity_new](https://github.com/ARC-MX/sgcc_electricity_new)。
如果遇到网络连接超时（RK001），请重试！
国网每天有登录限制，每天只能登录有限的几次，超过限制验证码识别成功也不会登录成功。


