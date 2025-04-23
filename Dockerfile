# 使用官方 Python 镜像
FROM python:3.12-slim-bookworm

# 环境变量设置
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8

# 设置工作目录
WORKDIR /app

# 复制必要文件
COPY ./src ./src
COPY ./pyproject.toml ./
COPY ./captcha.onnx ./
COPY ./README.md ./

# 安装必要软件（包括 tzdata）
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    tzdata \
    && ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

# 更新 pip 并安装项目
RUN pip install --upgrade pip \
    && pip install -e .

ENTRYPOINT ["sef", "schedule-daily"]