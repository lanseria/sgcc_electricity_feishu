# 使用官方 Python 镜像（建议3.12，确保与本地开发一致）
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV SET_CONTAINER_TIMEZONE=true
ENV CONTAINER_TIMEZONE=Asia/Shanghai
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8

# 设置工作目录
WORKDIR /app

# 复制项目文件到容器中
COPY ./src ./src
COPY ./pyproject.toml ./
COPY ./captcha.onnx ./
COPY ./README.md ./

# 安装构建工具（如有 C 扩展或依赖要求，可加 build-essential）
RUN apt-get --allow-releaseinfo-change update \
    && apt-get install -y --no-install-recommends jq chromium chromium-driver tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && dpkg-reconfigure --frontend noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*  \
    && apt-get clean

# 建议先安装 pipx 以便用 PEP 517/518 构建
RUN pip install --upgrade pip

# 安装项目依赖（推荐使用 PEP 517/518 标准，支持 pyproject.toml）
RUN pip install -e .

# 暴露 CLI 命令（可选，如通过 ENTRYPOINT 直接运行 sef main）
ENTRYPOINT ["sef", "main"]

# 或者如需进入交互式 shell，可使用如下命令（注释上一行 ENTRYPOINT）
# CMD ["/bin/bash"]