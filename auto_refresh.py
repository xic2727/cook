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
import llm_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    logger.info("🌅 开始执行早晨墨水屏食谱定时自动刷新任务...")
    
    # 确保数据库存在与表字段就绪
    database.init_db()
    
    today = date.today()
    today_iso = today.isoformat()
    daily_menu = database.get_daily_menu(today_iso)
    
    b_candidates = daily_menu.get("breakfast_candidates", [])
    d_candidates = daily_menu.get("dinner_candidates", [])
    
    # 1. 如果今日尚未生成菜谱候选，自动调用 AI 生成各 3 套方案并入库
    if not b_candidates or not d_candidates:
        logger.info(f"今日 ({today_iso}) 尚未生成早晚餐候选，正在调用 AI 规划各 3 套方案...")
        try:
            plan = llm_service.generate_full_day_options()
            b_ids = []
            for b_item in plan.get("breakfasts", []):
                bid = database.save_recipe(
                    title=b_item["title"],
                    meal_type="breakfast",
                    nutrition_tag=b_item.get("nutrition_tag", ""),
                    ingredients=b_item.get("ingredients", []),
                    steps=b_item.get("steps", []),
                    prep_time=b_item.get("prep_time", "15分钟"),
                    is_favorite=0,
                    daughter_notes=b_item.get("cooking_tip") or ""
                )
                b_ids.append(bid)
                
            d_ids = []
            for d_item in plan.get("dinners", []):
                did = database.save_recipe(
                    title=d_item["title"],
                    meal_type="dinner",
                    nutrition_tag=d_item.get("nutrition_tag", ""),
                    ingredients=d_item.get("ingredients", []),
                    steps=d_item.get("steps", []),
                    prep_time=d_item.get("prep_time", "25分钟"),
                    is_favorite=0,
                    daughter_notes=d_item.get("cooking_tip") or ""
                )
                d_ids.append(did)
                
            # 默认选用第 1 个早餐和第 1 个晚餐
            database.save_daily_menu_candidates(
                today_iso, b_ids, d_ids,
                active_b_id=b_ids[0] if b_ids else None,
                active_d_id=d_ids[0] if d_ids else None
            )
            daily_menu = database.get_daily_menu(today_iso)
            logger.info("✅ 今日早晚各 3 套候选方案已自动生成并保存！")
        except Exception as e:
            logger.error(f"❌ 自动规划菜谱发生异常: {e}")
            return
    else:
        # 如果已有候选，默认确保选用第 1 个早餐和第 1 个晚餐
        if b_candidates:
            database.set_active_candidate(today_iso, "breakfast", b_candidates[0]["id"])
        if d_candidates:
            database.set_active_candidate(today_iso, "dinner", d_candidates[0]["id"])
        daily_menu = database.get_daily_menu(today_iso)
        logger.info(f"✅ 默认选用今日第 1 个早餐[{daily_menu['breakfast']['title']}]与第 1 个晚餐[{daily_menu['dinner']['title']}]")

    # 2. 推送到墨水屏
    if daily_menu.get("breakfast") and daily_menu.get("dinner"):
        logger.info("📺 正在排版并推送到 7.5 寸黑白红墨水屏...")
        success, msg, _ = epd_service.sync_menu_to_screen(daily_menu, today)
        if success:
            database.mark_daily_menu_synced(today_iso)
            logger.info(f"🎉 早晨定时自动刷屏成功: {msg}")
        else:
            logger.error(f"❌ 墨水屏同步失败: {msg}")
    else:
        logger.warning(f"今日 ({today_iso}) 菜谱数据不完整，无法刷屏。")

if __name__ == "__main__":
    main()
