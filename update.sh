#!/bin/bash
# 阿里云 ECS 一键更新部署脚本
# 用法：bash update.sh
set -e

DEPLOY_DIR="/root/AI4SE"
TARBALL="/root/deploy3.tar.gz"

echo "===== 1. 解压更新代码 ====="
cd "$DEPLOY_DIR"
if [ -f "$TARBALL" ]; then
    tar -xzf "$TARBALL"
    echo "代码已更新"
else
    echo "未找到 $TARBALL，跳过解压"
fi

echo ""
echo "===== 2. 配置 .env ====="
if [ ! -f .env ] || ! grep -q "OPENAI_API_KEY" .env 2>/dev/null; then
    echo "未检测到 API key 配置，需要手动输入"
    echo "（输入不可见，不会写入日志）"
    read -s -p "请输入 OPENAI_API_KEY: " API_KEY
    echo ""
    if [ -z "$API_KEY" ]; then
        echo "未输入 key，跳过。后续可手动创建 .env 文件"
    else
        read -p "请输入 OPENAI_BASE_URL（回车用默认 https://api.njusehub.ai/v1）: " BASE_URL
        BASE_URL=${BASE_URL:-https://api.njusehub.ai/v1}
        read -p "请输入 LLM_MODEL（回车用默认 njusehub/glm-5.2）: " MODEL
        MODEL=${MODEL:-njusehub/glm-5.2}

        cat > .env << EOF
OPENAI_API_KEY=$API_KEY
OPENAI_BASE_URL=$BASE_URL
LLM_MODEL=$MODEL
EOF
        chmod 600 .env
        echo ".env 已创建（权限 600，不公开）"
    fi
else
    echo ".env 已存在，跳过"
fi

echo ""
echo "===== 3. 构建前端 ====="
cd frontend
npm install 2>/dev/null
npm run build
cd ..

echo ""
echo "===== 4. 重启服务 ====="
pkill -f "uvicorn src.api.main" 2>/dev/null || true
sleep 1
STATIC_DIR=frontend/dist nohup uv run uvicorn src.api.main:create_app \
    --factory --host 0.0.0.0 --port 8000 > /var/log/njuse.log 2>&1 &
echo "服务已启动 (PID: $!)"

echo ""
echo "===== 5. 验证 ====="
sleep 3
if curl -s http://localhost:8000/api/health | grep -q "ok"; then
    echo "✓ 服务运行正常"
else
    echo "✗ 服务未就绪，查看日志："
    tail -20 /var/log/njuse.log
fi

echo ""
echo "===== 部署完成 ====="
echo "WebUI: http://$(curl -s ifconfig.me):8000"
echo "健康检查: http://$(curl -s ifconfig.me):8000/api/health"
echo "日志: tail -f /var/log/njuse.log"
