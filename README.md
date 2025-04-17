# sgcc_electricity_feishu

国家电网飞书应用开发

## Features

- Basic CLI structure with Typer
- Rich console output
- Python project configuration (pyproject.toml)
- Test setup with pytest

## Installation

```bash
# Create virtual environment
python3 -m venv myenv
python3.12 -m venv myenv
source myenv/bin/activate  # macOS/Linux
# .\myenv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install -e .
```

## Usage

```bash
sef hello [name]
sef sgcc-login
sef bitable-list
sef main
```

## Development

Run tests:
```bash
pytest
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

## License

MIT

## 特别说明

本项目代码参考自 [https://github.com/ARC-MX/sgcc_electricity_new](https://github.com/ARC-MX/sgcc_electricity_new)。
如果遇到网络连接超时（RK001），请重试！
国网每天有登录限制，每天只能登录有限的几次，超过限制验证码识别成功也不会登录成功。


