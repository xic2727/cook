"""
auto_refresh.py
树莓派定时自动刷新脚本
可通过 crontab 定时在早晨和傍晚静默将今日菜谱刷到 7.5 寸墨水屏上。

示例 crontab 配置 (在树莓派中运行 crontab -e):
# 每天早上 06:30 自动刷屏为当日食谱
30 6 * * * /usr/bin/python3 /home/pi/cook/auto_refresh.py >> /home/pi/cook/cron.log 2>&1
"""

import sys
import logging
from datetime import date
from pathlib import Path

# 添加当前目录到 sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

import database
import epd_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    logger.info("开始执行定时墨水屏食谱刷新任务...")
    
    # 确保数据库存在
    database.init_db()
    
    today = date.today()
    today_iso = today.isoformat()
    daily_menu = database.get_daily_menu(today_iso)
    
    # 如果今天还没安排菜谱，提示跳过或使用默认
    if not daily_menu.get("breakfast") and not daily_menu.get("dinner"):
        logger.warning(f"今日 ({today_iso}) 尚未在 Web 端规划早晚餐，取消静默刷屏。")
        return
        
    success, msg, _ = epd_service.sync_menu_to_screen(daily_menu, today)
    if success:
        database.mark_daily_menu_synced(today_iso)
        logger.info(f"✅ 定时同步成功: {msg}")
    else:
        logger.error(f"❌ 同步失败: {msg}")

if __name__ == "__main__":
    main()
