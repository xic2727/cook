#!/usr/bin/env python3
"""
diagnose_epd.py
树莓派墨水屏驱动深度诊断与自愈脚本
用于快速定位为什么树莓派上依然提示【模拟模式 (Mock)】，并给出针对性修复方案。
"""

import sys
import os
import platform
import traceback

def print_header(title):
    print("\n" + "=" * 60)
    print(f"[{title}]")
    print("=" * 60)

def main():
    print_header("树莓派 7.5寸 (B) V2 墨水屏硬件环境诊断")
    
    issues = []
    fix_commands = []
    
    # 1. 检查操作系统与硬件型号
    print(f">> Python 版本: {sys.version.split()[0]} ({sys.executable})")
    print(f">> 操作系统: {platform.system()} {platform.release()}")
    
    pi_model = "未知 (可能不是树莓派)"
    if os.path.exists("/proc/device-tree/model"):
        try:
            with open("/proc/device-tree/model", "r", encoding="utf-8", errors="ignore") as f:
                pi_model = f.read().strip().replace('\x00', '')
        except Exception:
            pass
    print(f">> 设备型号: {pi_model}")
    
    is_pi_5 = "Raspberry Pi 5" in pi_model
    if is_pi_5:
        print("[!] 检测到 Raspberry Pi 5！注意：Pi 5 更改了 GPIO 架构，需使用 rpi-lgpio 替代传统 RPi.GPIO。")

    # 2. 检查 SPI 接口
    print_header("1. 检查 SPI 硬件总线")
    spi_dev0 = "/dev/spidev0.0"
    if os.path.exists(spi_dev0):
        print(f"[OK] {spi_dev0} 存在，硬件 SPI 已开启！")
    else:
        print(f"[FAIL] 未检测到 {spi_dev0}！")
        issues.append("SPI 接口未在树莓派系统配置中启用")
        fix_commands.append("sudo raspi-config nonint do_spi 0  # 启用硬件 SPI")

    # 3. 检查 spidev 库
    print_header("2. 检查 Python spidev 模块")
    try:
        import spidev
        print(f"[OK] spidev 导入成功")
    except Exception as e:
        print(f"[FAIL] 导入 spidev 失败: {e}")
        issues.append("缺少 spidev 库")
        fix_commands.append("sudo apt-get install -y python3-spidev || pip3 install spidev")

    # 4. 检查 GPIO 控制库 (RPi.GPIO 或 rpi-lgpio)
    print_header("3. 检查 GPIO 控制库 (RPi.GPIO / lgpio)")
    try:
        import RPi.GPIO as GPIO
        print("[OK] RPi.GPIO 导入成功")
    except Exception as e:
        print(f"[WARN] RPi.GPIO 导入异常: {e}")
        if is_pi_5 or "Bookworm" in platform.release() or "Cannot determine SOC" in str(e):
            print("[INFO] 树莓派 5 或 Debian 12 (Bookworm) 需要安装 rpi-lgpio 兼容层！")
            fix_commands.append("sudo apt-get remove -y python3-rpi.gpio && sudo apt-get install -y python3-rpi-lgpio")
        else:
            fix_commands.append("sudo apt-get install -y python3-rpi.gpio")
        issues.append(f"GPIO 库异常: {e}")

    # 5. 检查微雪官方驱动模块
    print_header("4. 检查 waveshare_epd 驱动模块")
    try:
        from waveshare_epd import epd7in5b_V2
        print("[OK] from waveshare_epd import epd7in5b_V2 成功！")
        try:
            epd = epd7in5b_V2.EPD()
            print("[OK] 成功创建 epd7in5b_V2.EPD() 实例！墨水屏驱动一切正常！")
        except Exception as e:
            print(f"[WARN] 实例化 epd7in5b_V2.EPD() 时发生异常: {e}")
            issues.append(f"驱动初始化异常: {e}")
    except Exception as e:
        print(f"[FAIL] 导入 waveshare_epd.epd7in5b_V2 失败！原因: {e}")
        issues.append(f"缺少或未正确安装微雪驱动: {e}")
        fix_commands.append(
            "git clone https://github.com/waveshare/e-Paper.git /tmp/e-Paper && "
            "cd /tmp/e-Paper/RaspberryPi_JetsonNano/python && sudo python3 setup.py install"
        )

    # 6. 总结诊断报告
    print_header("诊断结论与一键自愈指南")
    if not issues:
        print("[SUCCESS] 树莓派上的 SPI、GPIO 和微雪 7.5寸 V2 驱动全部就绪！")
        print("请在项目目录下重启服务: ./run.sh restart")
    else:
        print(f"[ALERT] 共发现 {len(issues)} 处问题导致进入【模拟模式 (Mock)】:")
        for idx, issue in enumerate(issues, 1):
            print(f"  {idx}. {issue}")
            
        print("\n[建议修复命令] 请复制以下命令在树莓派终端中执行 (或直接运行 sudo ./setup_epd.sh)：")
        print("-" * 60)
        print("sudo apt-get update")
        for cmd in fix_commands:
            print(cmd)
        print("-" * 60)
        print("修复完成后，重新运行: python3 diagnose_epd.py 验证。")

if __name__ == "__main__":
    main()
