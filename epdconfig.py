"""
epdconfig.py
硬件底层适配器 (Hardware Abstraction Layer)
专门针对树莓派 3 / 4 / 5 以及 Debian Bookworm/Trixie 进行了兼容性增强。
采用纯净的轮询读取 (Polling)，杜绝 "Failed to add edge detection" 异常！
"""

import os
import sys
import time
import logging

# 强制避免 gpiozero 误用破损的旧 RPi.GPIO 边缘触发
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

logger = logging.getLogger(__name__)

# 微雪 7.5寸 墨水屏标准 BCM 引脚定义 (微雪官方 HAT 默认排线引脚)
RST_PIN  = 17
DC_PIN   = 25
CS_PIN   = 8
BUSY_PIN = 24

class RaspberryPi:
    def __init__(self):
        self.RST_PIN = RST_PIN
        self.DC_PIN = DC_PIN
        self.CS_PIN = CS_PIN
        self.BUSY_PIN = BUSY_PIN
        self.SPI = None
        self.gpio_mode = None

    def digital_write(self, pin, value):
        if self.gpio_mode == "RPi.GPIO":
            self.GPIO.output(pin, value)
        elif self.gpio_mode == "lgpio":
            self.sbc.gpio_write(self.chip, pin, 1 if value else 0)
        elif self.gpio_mode == "gpiozero":
            if pin == self.RST_PIN:
                self.rst_dev.value = 1 if value else 0
            elif pin == self.DC_PIN:
                self.dc_dev.value = 1 if value else 0
            elif pin == self.CS_PIN:
                self.cs_dev.value = 1 if value else 0

    def digital_read(self, pin):
        if self.gpio_mode == "RPi.GPIO":
            return self.GPIO.input(pin)
        elif self.gpio_mode == "lgpio":
            return self.sbc.gpio_read(self.chip, pin)
        elif self.gpio_mode == "gpiozero":
            if pin == self.BUSY_PIN:
                return 1 if self.busy_dev.is_active else 0
            return 0
        return 0

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        if self.SPI is not None:
            self.SPI.writebytes(data)

    def spi_writebyte2(self, data):
        if self.SPI is not None:
            self.SPI.writebytes2(data)

    def module_init(self, cleanup=False):
        # 1. 初始化 SPI 接口
        try:
            import spidev
            self.SPI = spidev.SpiDev()
            self.SPI.open(0, 0)
            self.SPI.max_speed_hz = 4000000
            self.SPI.mode = 0b00
        except Exception as e:
            logger.error(f"SPI 初始化失败: {e}")
            raise e

        # 2. 初始化 GPIO 控制器 (多重回退，完美兼容树莓派 3/4/5)
        # 方案 A: 尝试 RPi.GPIO / rpi-lgpio (纯输出与轮询输入，绝不加事件中断)
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setwarnings(False)
            self.GPIO.setup(self.RST_PIN, self.GPIO.OUT)
            self.GPIO.setup(self.DC_PIN, self.GPIO.OUT)
            self.GPIO.setup(self.CS_PIN, self.GPIO.OUT)
            self.GPIO.setup(self.BUSY_PIN, self.GPIO.IN) # 纯输入，无 edge detection
            self.gpio_mode = "RPi.GPIO"
            logger.info("已通过 RPi.GPIO/rpi-lgpio 模式初始化墨水屏 GPIO")
            return 0
        except Exception as e1:
            logger.warning(f"RPi.GPIO 模式不可用 ({e1})，尝试切换到原生 lgpio 驱动...")

        # 方案 B: 尝试树莓派 5 官方原生 lgpio
        try:
            import lgpio
            self.sbc = lgpio
            self.chip = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(self.chip, self.RST_PIN)
            lgpio.gpio_claim_output(self.chip, self.DC_PIN)
            lgpio.gpio_claim_output(self.chip, self.CS_PIN)
            lgpio.gpio_claim_input(self.chip, self.BUSY_PIN)
            self.gpio_mode = "lgpio"
            logger.info("已通过原生 lgpio (树莓派5标准) 初始化墨水屏 GPIO")
            return 0
        except Exception as e2:
            logger.warning(f"原生 lgpio 模式不可用 ({e2})，尝试切换到 gpiozero...")

        # 方案 C: 尝试 gpiozero
        try:
            from gpiozero import OutputDevice, InputDevice
            self.rst_dev = OutputDevice(self.RST_PIN, active_high=True, initial_value=False)
            self.dc_dev = OutputDevice(self.DC_PIN, active_high=True, initial_value=False)
            self.cs_dev = OutputDevice(self.CS_PIN, active_high=True, initial_value=True)
            self.busy_dev = InputDevice(self.BUSY_PIN, pull_up=False) # 纯电平读取
            self.gpio_mode = "gpiozero"
            logger.info("已通过 gpiozero 模式初始化墨水屏 GPIO")
            return 0
        except Exception as e3:
            raise RuntimeError(f"无法初始化任何树莓派 GPIO 驱动库: {e1} / {e2} / {e3}")

    def module_exit(self, cleanup=False):
        if self.SPI is not None:
            self.SPI.close()
            
        if self.gpio_mode == "RPi.GPIO":
            self.digital_write(self.RST_PIN, 0)
            self.digital_write(self.DC_PIN, 0)
            if cleanup:
                self.GPIO.cleanup()
        elif self.gpio_mode == "lgpio":
            self.digital_write(self.RST_PIN, 0)
            self.digital_write(self.DC_PIN, 0)
            if hasattr(self, 'chip'):
                self.sbc.gpiochip_close(self.chip)
        elif self.gpio_mode == "gpiozero":
            if hasattr(self, 'rst_dev'):
                self.rst_dev.close()
            if hasattr(self, 'dc_dev'):
                self.dc_dev.close()
            if hasattr(self, 'cs_dev'):
                self.cs_dev.close()
            if hasattr(self, 'busy_dev'):
                self.busy_dev.close()

# 实例化全局单例
implementation = RaspberryPi()

for attr in ["RST_PIN", "DC_PIN", "CS_PIN", "BUSY_PIN",
             "digital_write", "digital_read", "delay_ms", 
             "spi_writebyte", "spi_writebyte2", "module_init", "module_exit"]:
    globals()[attr] = getattr(implementation, attr)
