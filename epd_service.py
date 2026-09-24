import os
import logging
from datetime import date
from typing import Tuple, Dict, Any, Optional
from PIL import Image

import config
import renderer

logger = logging.getLogger(__name__)

# 尝试导入微雪官方驱动 (仅在树莓派且开启 SPI 环境下有效)
HAS_HARDWARE_EPD = False
epd_module = None

try:
    from waveshare_epd import epd7in5b_V2
    HAS_HARDWARE_EPD = True
    epd_module = epd7in5b_V2
except (ImportError, Exception):
    try:
        # 也可以支持把 epd7in5b_V2.py 直接放在项目根目录或 drivers/ 目录下
        import epd7in5b_V2
        HAS_HARDWARE_EPD = True
        epd_module = epd7in5b_V2
    except (ImportError, Exception):
        HAS_HARDWARE_EPD = False

def is_hardware_available() -> bool:
    """检查是否可以直接驱动物理墨水屏"""
    return HAS_HARDWARE_EPD and (config.EPD_MODE in ["auto", "hardware"])

def display_on_eink(img_black: Image.Image, img_red: Image.Image) -> Tuple[bool, str]:
    """
    将黑白单色图和红色单色图推送到 7.5寸 V2 墨水屏
    """
    if not is_hardware_available():
        msg = "【模拟模式 (Mock)】检测到当前运行在 PC / 非树莓派 SPI 环境。已成功生成 800x480 位图并在界面预览展示。"
        logger.info(msg)
        return True, msg
        
    try:
        logger.info("正在初始化微雪 7.5inch e-Paper (B) V2 硬件...")
        epd = epd_module.EPD()
        epd.init()
        logger.info("硬件初始化成功，正在刷新黑白红双通道图层 (全刷约需 15~20 秒)...")
        
        # 将 PIL 单色位图转为硬件缓冲区数组
        buf_black = epd.getbuffer(img_black)
        buf_red = epd.getbuffer(img_red)
        
        epd.display(buf_black, buf_red)
        logger.info("屏幕刷新完毕，进入休眠省电模式")
        epd.sleep()
        return True, "已成功刷新到 7.5 寸墨水屏！"
    except Exception as e:
        err_msg = f"物理墨水屏驱动刷新失败: {e}"
        logger.error(err_msg)
        return False, err_msg

def sync_menu_to_screen(menu_data: Dict[str, Any], target_date: Optional[date] = None) -> Tuple[bool, str, Image.Image]:
    """
    一键排版并同步当日菜单到墨水屏
    返回 (成功状态, 状态文本, 预览图对象)
    """
    if not target_date:
        target_date = date.today()
        
    # 1. 渲染出 800x480 的预览图、黑色通道、红色通道
    img_preview, img_black, img_red = renderer.render_eink_display(menu_data, target_date)
    
    # 2. 推送至硬件 (或模拟)
    success, message = display_on_eink(img_black, img_red)
    
    return success, message, img_preview
