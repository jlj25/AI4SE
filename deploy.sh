#!/bin/bash
# 阿里云 ECS 部署脚本
# 用法：在 ECS 上执行 bash deploy.sh
# 前提：已安装 git 和 docker

set -e

echo "===== 1. 检查 Docker ====="
if ! command -v docker &> /dev/null; then
    echo "Docker 未安装，开始安装..."
    curl -fsSL https://get.docker.com | sh
    systemctl start docker
    systemctl enable docker
    echo "Docker 安装完成"
else
    echo "Docker 已安装: $(docker --version)"
fi

echo ""
echo "===== 2. 克隆仓库 ====="
if [ -d "AI4SE" ]; then
    cd AI4SE && git pull origin main
    echo "仓库已更新"
else
    git clone https://github.com/jlj25/AI4SE.git
    cd AI4SE
fi

echo ""
echo "===== 3. 添加 swap（2G 内存防 OOM） ====="
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "Swap 已创建 (2G)"
else
    echo "Swap 已存在"
fi

echo ""
echo "===== 4. 构建 Docker 镜像 ====="
docker build -t njuse-agent .

echo ""
echo "===== 5. 停止旧容器（如有） ====="
docker rm -f njuse-agent 2>/dev/null || true

echo ""
echo "===== 6. 启动容器 ====="
docker run -d \
    --name njuse-agent \
    -p 8000:8000 \
    --restart unless-stopped \
    njuse-agent

echo ""
echo "===== 7. 等待启动 ====="
sleep 3
curl -s http://localhost:8000/api/health && echo "" || echo "服务尚未就绪，等待几秒后重试"

echo ""
echo "===== 部署完成 ====="
echo "公网访问地址: http://<你的ECS公网IP>:8000"
echo "健康检查: http://<你的ECS公网IP>:8000/api/health"
echo ""
echo "注意：请在阿里云控制台 -> 安全组 -> 添加入方向规则，开放 TCP 8000 端口"
