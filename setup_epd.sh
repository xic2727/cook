#!/usr/bin/env bash
# ==============================================================================
# 🛠️ 树莓派微雪墨水屏一键环境安装与修复脚本
# ==============================================================================

set -e

# 确保以 root / sudo 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本: sudo ./setup_epd.sh"
    exit 1
fi

echo "======================================================"
echo "🚀 开始为树莓派配置微雪 7.5寸 (B) V2 墨水屏驱动环境..."
echo "======================================================"

# 1. 开启硬件 SPI
echo "▶ 步骤 1/4: 启用树莓派 SPI 接口..."
if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_spi 0
    echo "✅ SPI 接口已开启"
else
    echo "⚠️ 未找到 raspi-config，请确保 /boot/config.txt 或 /boot/firmware/config.txt 包含 dtparam=spi=on"
fi

# 2. 安装系统依赖库与中文字体
echo "▶ 步骤 2/4: 更新软件源并安装基础依赖 (spidev, Pillow, fonts)..."
apt-get update -y
apt-get install -y git python3-pip python3-pil python3-numpy python3-spidev fonts-wqy-microhei

# 3. 针对树莓派 5 / Bookworm 安装正确的 GPIO 库
echo "▶ 步骤 3/4: 适配 GPIO 库 (自动兼容树莓派 3/4/5 与 Bookworm)..."
MODEL=""
if [ -f /proc/device-tree/model ]; then
    MODEL=$(cat /proc/device-tree/model)
fi

if [[ "$MODEL" =~ "Raspberry Pi 5" ]] || grep -q "bookworm" /etc/os-release 2>/dev/null; then
    echo "💡 检测到树莓派 5 或 Debian 12 (Bookworm)，安装 python3-rpi-lgpio..."
    apt-get install -y python3-rpi-lgpio || true
else
    echo "💡 安装标准 python3-rpi.gpio..."
    apt-get install -y python3-rpi.gpio || true
fi

# 4. 下载并安装微雪官方 waveshare_epd 驱动
echo "▶ 步骤 4/4: 安装微雪官方 e-Paper 驱动包..."
TMP_DIR="/tmp/e-Paper-install"
rm -rf "$TMP_DIR"
git clone --depth 1 https://github.com/waveshare/e-Paper.git "$TMP_DIR"

cd "$TMP_DIR/RaspberryPi_JetsonNano/python"
python3 setup.py install

# 如果当前项目有虚拟环境 (.venv 或 venv)，也给虚拟环境安装一份
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$PROJECT_DIR/.venv" ]; then
    echo "💡 检测到项目虚拟环境 .venv，正在为虚拟环境同步安装驱动..."
    "$PROJECT_DIR/.venv/bin/python" setup.py install
elif [ -d "$PROJECT_DIR/venv" ]; then
    echo "💡 检测到项目虚拟环境 venv，正在为虚拟环境同步安装驱动..."
    "$PROJECT_DIR/venv/bin/python" setup.py install
fi

rm -rf "$TMP_DIR"

echo "======================================================"
echo "🎉 微雪墨水屏硬件环境配置完成！正在运行全面诊断..."
echo "======================================================"
cd "$PROJECT_DIR"
python3 diagnose_epd.py
