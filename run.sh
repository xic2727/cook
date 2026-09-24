#!/usr/bin/env bash
# ==============================================================================
# 🍳 树莓派管理与启动脚本 - 每日营养食谱 & 7.5寸墨水屏系统
# ==============================================================================
# 使用方式:
#   ./run.sh            # 前台启动 (默认，按 Ctrl+C 可退出)
#   ./run.sh start      # 后台启动 (守护进程，输出记录至 app.log)
#   ./run.sh stop       # 停止后台服务
#   ./run.sh restart    # 重启服务
#   ./run.sh status     # 查看当前运行状态
#   ./run.sh log        # 实时查看后台运行日志
# ==============================================================================

# 脚本所在绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PID_FILE="$SCRIPT_DIR/app.pid"
LOG_FILE="$SCRIPT_DIR/app.log"
PORT=8501

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. 查找 Python 与虚拟环境
PYTHON_CMD="python3"
if [ -d "$SCRIPT_DIR/.venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
    STREAMLIT_CMD="$SCRIPT_DIR/.venv/bin/streamlit"
elif [ -d "$SCRIPT_DIR/venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    STREAMLIT_CMD="$SCRIPT_DIR/venv/bin/streamlit"
else
    STREAMLIT_CMD="streamlit"
fi

# 2. 检查硬件 SPI 状态
check_spi() {
    if [ -e /dev/spidev0.0 ]; then
        echo -e "${GREEN}🟢 [硬件检测] 树莓派 SPI 接口已启用 (/dev/spidev0.0 就绪)${NC}"
    else
        echo -e "${YELLOW}⚠️  [硬件提示] 未检测到 SPI 接口 (/dev/spidev0.0)。${NC}"
        echo -e "${YELLOW}   若需连接 7.5 寸物理墨水屏，请在终端运行: sudo raspi-config -> Interface Options -> SPI -> Enable${NC}"
    fi
}

# 3. 获取本机局域网 IP
get_ip() {
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP="127.0.0.1"
    fi
    echo "$LOCAL_IP"
}

# 4. 打印欢迎访问信息
print_welcome() {
    LOCAL_IP=$(get_ip)
    echo -e "${BLUE}======================================================${NC}"
    echo -e "${GREEN}🍳 每日营养食谱 & 7.5寸墨水屏系统已就绪！${NC}"
    echo -e "📱 手机/电脑访问地址: ${GREEN}http://${LOCAL_IP}:${PORT}${NC}"
    echo -e "${BLUE}======================================================${NC}"
}

# 启动命令
start_foreground() {
    check_spi
    print_welcome
    echo -e "正在前台启动 Streamlit (按 Ctrl+C 可停止运行)..."
    $STREAMLIT_CMD run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
}

start_background() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo -e "${YELLOW}服务已在后台运行中，PID: $(cat "$PID_FILE")${NC}"
        print_welcome
        exit 0
    fi

    check_spi
    echo -e "正在启动后台服务..."
    nohup $STREAMLIT_CMD run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    sleep 2
    if kill -0 $PID 2>/dev/null; then
        echo -e "${GREEN}✅ 后台启动成功！PID: $PID${NC}"
        print_welcome
        echo -e "查看日志请运行: ${YELLOW}./run.sh log${NC}"
    else
        echo -e "${RED}❌ 启动失败，请检查日志:${NC}"
        tail -n 20 "$LOG_FILE"
    fi
}

stop_service() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "正在停止服务 (PID: $PID)..."
            kill "$PID"
            sleep 1
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID"
            fi
            echo -e "${GREEN}✅ 服务已停止${NC}"
        else
            echo -e "${YELLOW}进程 (PID: $PID) 不存在，清理残留 PID 文件${NC}"
        fi
        rm -f "$PID_FILE"
    else
        # 兜底通过进程名杀死
        PIDS=$(pgrep -f "streamlit run app.py")
        if [ -n "$PIDS" ]; then
            echo -e "正在终止正在运行的 Streamlit 实例: $PIDS"
            kill $PIDS
            echo -e "${GREEN}✅ 服务已停止${NC}"
        else
            echo -e "${YELLOW}未检测到正在运行的服务${NC}"
        fi
    fi
}

check_status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo -e "${GREEN}● 服务正在后台正常运行${NC} (PID: $(cat "$PID_FILE"))"
        print_welcome
    else
        PIDS=$(pgrep -f "streamlit run app.py")
        if [ -n "$PIDS" ]; then
            echo -e "${GREEN}● 检测到服务正在运行${NC} (PIDs: $PIDS)"
            print_welcome
        else
            echo -e "${RED}○ 服务未运行${NC}"
        fi
    fi
}

view_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}--- 实时输出日志 (Ctrl+C 退出) ---${NC}"
        tail -f -n 50 "$LOG_FILE"
    else
        echo -e "${YELLOW}暂无日志文件: $LOG_FILE${NC}"
    fi
}

# 命令分发
case "$1" in
    start)
        start_background
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 1
        start_background
        ;;
    status)
        check_status
        ;;
    log|logs)
        view_logs
        ;;
    fg|run|"")
        start_foreground
        ;;
    *)
        echo "使用方式: $0 {start|stop|restart|status|log|fg}"
        exit 1
        ;;
esac
