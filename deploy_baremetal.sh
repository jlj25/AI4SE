#!/bin/bash
# 阿里云 ECS 裸机部署脚本（无需 Docker）
set -e

echo "===== 1. 安装 Python 3.12 ====="
if ! command -v python3.12 &> /dev/null; then
    yum install -y python3.12 python3.12-pip 2>/dev/null || apt install -y python3.12 python3.12-venv 2>/dev/null || {
        echo "系统源无 Python 3.12，从源码编译..."
        yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel make 2>/dev/null || apt install -y gcc libssl-dev libbz2-dev libffi-dev zlib1g-dev make 2>/dev/null
        cd /tmp
        curl -O https://www.python.org/ftp/python/3.12.7/Python-3.12.7.tgz
        tar xzf Python-3.12.7.tgz
        cd Python-3.12.7
        ./configure --enable-optimizations --prefix=/usr/local
        make -j2
        make install
        ln -sf /usr/local/bin/python3.12 /usr/bin/python3.12
        ln -sf /usr/local/bin/pip3.12 /usr/bin/pip3.12
    }
fi
python3.12 --version

echo ""
echo "===== 2. 安装 Node.js 20 ====="
if ! command -v node &> /dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]; then
    curl -fsSL https://rpm.nodesource.com/setup_20.x | bash - 2>/dev/null && yum install -y nodejs || {
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>/dev/null && apt install -y nodejs
    }
fi
node --version

echo ""
echo "===== 3. 安装 uv ====="
pip3.12 install uv || pip install uv

echo ""
echo "===== 4. 部署代码 ====="
cd /root/AI4SE

echo ""
echo "===== 5. 安装 Python 依赖 ====="
uv sync --extra dev

echo ""
echo "===== 6. 构建前端 ====="
cd frontend
npm install
npm run build
cd ..

echo ""
echo "===== 7. 停止旧进程（如有） ====="
pkill -f "uvicorn src.api.main" 2>/dev/null || true

echo ""
echo "===== 8. 启动服务 ====="
STATIC_DIR=frontend/dist nohup uv run uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8000 > /var/log/njuse.log 2>&1 &

echo ""
echo "===== 9. 等待启动 ====="
sleep 3
curl -s http://localhost:8000/api/health && echo "" || echo "服务尚未就绪，查看日志: tail -f /var/log/njuse.log"

echo ""
echo "===== 部署完成 ====="
echo "公网访问: http://<ECS公网IP>:8000"
echo "健康检查: http://<ECS公网IP>:8000/api/health"
echo "日志: tail -f /var/log/njuse.log"
echo ""
echo "注意：阿里云安全组需开放 TCP 8000 端口"
