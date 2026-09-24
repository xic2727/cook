import os
import logging
from datetime import date
from typing import Tuple, Dict, Any, Optional
from PIL import Image

import config
import renderer

logger = logging.getLogger(__name__)

# 硬件状态与错误记录
HAS_HARDWARE_EPD = False
HARDWARE_ERROR_REASON = ""
epd_module = None

try:
    from waveshare_epd import epd7in5b_V2
    HAS_HARDWARE_EPD = True
    epd_module = epd7in5b_V2
except Exception as e_pkg:
    try:
        import epd7in5b_V2
        HAS_HARDWARE_EPD = True
        epd_module = epd7in5b_V2
    except Exception as e_local:
        HAS_HARDWARE_EPD = False
        HARDWARE_ERROR_REASON = f"未找到驱动包 waveshare_epd ({e_pkg}) 且无本地 epd7in5b_V2 ({e_local})"

def get_hardware_status() -> Dict[str, Any]:
    """获取墨水屏硬件加载状态与详情"""
    return {
        "available": is_hardware_available(),
        "error_reason": HARDWARE_ERROR_REASON,
        "mode": config.EPD_MODE,
        "spi_dev_exists": os.path.exists("/dev/spidev0.0")
    }

def is_hardware_available() -> bool:
    """检查是否可以直接驱动物理墨水屏"""
    return HAS_HARDWARE_EPD and (config.EPD_MODE in ["auto", "hardware"])

def display_on_eink(img_black: Image.Image, img_red: Image.Image) -> Tuple[bool, str]:
    """
    将黑白单色图和红色单色图推送到 7.5寸 V2 墨水屏
    """
    if not is_hardware_available():
        if HARDWARE_ERROR_REASON:
            msg = f"【模拟模式 (Mock)】检测到驱动加载受阻: {HARDWARE_ERROR_REASON}。请在树莓派终端运行: sudo ./setup_epd.sh 一键修复。"
        else:
            msg = "【模拟模式 (Mock)】检测到当前运行在 PC / 非树莓派 SPI 环境。已生成 800x480 位图并在界面预览展示。"
        logger.warning(msg)
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
