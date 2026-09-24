import os
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont

import config

def get_font(size: int = 16, bold: bool = False) -> ImageFont.FreeTypeFont:
    """跨平台字体选择器，按优先级寻找支持中文的字体"""
    font_candidates = [
        # 本地字体目录
        config.FONTS_DIR / "simhei.ttf",
        config.FONTS_DIR / "msyh.ttc",
        config.FONTS_DIR / "SourceHanSansCN-Regular.otf",
        config.FONTS_DIR / "wqy-microhei.ttc",
        # Windows 系统字体
        Path("C:/Windows/Fonts/msyhbd.ttc") if bold else Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        # Linux / 树莓派 系统字体
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
    ]
    
    for candidate in font_candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except Exception:
                continue
                
    # 兜底
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """文本自动按像素宽度折行（中文友好）"""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
    if current_line:
        lines.append(current_line)
    return lines

def get_weekday_cn(target_date: date) -> str:
    """获取中文星期"""
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return weekdays[target_date.weekday()]

def draw_heart(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 14, fill="red"):
    """使用贝塞尔多边形绘制实心红心"""
    # 简易而优雅的实心爱心坐标点
    half = size // 2
    pts = [
        (x, y + int(size * 0.3)),
        (x - half, y - int(size * 0.2)),
        (x - size, y + int(size * 0.1)),
        (x - size, y + int(size * 0.4)),
        (x, y + size),
        (x + size, y + int(size * 0.4)),
        (x + size, y + int(size * 0.1)),
        (x + half, y - int(size * 0.2)),
    ]
    draw.polygon(pts, fill=fill)

def render_eink_display(menu_data: Dict[str, Any], target_date: Optional[date] = None) -> Tuple[Image.Image, Image.Image, Image.Image]:
    """
    根据菜谱数据渲染 800x480 墨水屏画面
    返回 (preview_rgb_image, black_mono_image, red_mono_image)
    
    墨水屏单色位图规则 (Waveshare 规范):
    - 255: 白色 (背景/不着色)
    - 0:   着色 (黑色通道刷黑，红色通道刷红)
    """
    width, height = config.EPD_WIDTH, config.EPD_HEIGHT
    if not target_date:
        target_date = date.today()
        
    # 1. 建立图像通道
    # 预览图 (RGB)
    img_preview = Image.new("RGB", (width, height), (255, 255, 255))
    draw_prev = ImageDraw.Draw(img_preview)
    
    # 墨水屏黑白通道 (1-bit, '1'模式, 255为白, 0为黑)
    img_black = Image.new("1", (width, height), 255)
    draw_black = ImageDraw.Draw(img_black)
    
    # 墨水屏红色通道 (1-bit, '1'模式, 255为白, 0为红)
    img_red = Image.new("1", (width, height), 255)
    draw_red = ImageDraw.Draw(img_red)

    # 字体准备
    font_date = get_font(26, bold=True)
    font_badge = get_font(18, bold=True)
    font_title = get_font(21, bold=True)
    font_sub = get_font(15, bold=True)
    font_body = get_font(14, bold=False)
    font_tag = get_font(13, bold=False)
    font_small = get_font(12, bold=False)

    # 颜色常数 (用于RGB预览图)
    C_BLACK = (20, 20, 20)
    C_RED = (215, 30, 30)
    C_GRAY = (120, 120, 120)
    C_BG_CARD = (250, 250, 250)

    # ---------------- 1. 顶部 Header (日期 + 星期) ----------------
    date_str = f"{target_date.strftime('%Y年%m月%d日')}  {get_weekday_cn(target_date)}"
    draw_prev.text((28, 14), date_str, fill=C_BLACK, font=font_date)
    draw_black.text((28, 14), date_str, fill=0, font=font_date)

    # 右侧辅助标语 (优雅的五角星/纯文字，保证无乱码方块)
    sub_title = "★ 每日营养食谱"
    bbox_sub = draw_prev.textbbox((0, 0), sub_title, font=font_sub)
    sub_w = bbox_sub[2] - bbox_sub[0]
    draw_prev.text((width - 30 - sub_w, 20), sub_title, fill=C_RED, font=font_sub)
    draw_red.text((width - 30 - sub_w, 20), sub_title, fill=0, font=font_sub)

    # 顶部分隔双线 (上黑下红)
    draw_prev.line([(20, 52), (width - 20, 52)], fill=C_BLACK, width=2)
    draw_black.line([(20, 52), (width - 20, 52)], fill=0, width=2)
    
    draw_prev.line([(20, 56), (width - 20, 56)], fill=C_RED, width=1)
    draw_red.line([(20, 56), (width - 20, 56)], fill=0, width=1)

    # ---------------- 2. 中间纵向分割线 ----------------
    mid_x = width // 2
    for y in range(70, height - 20, 8):
        draw_prev.line([(mid_x, y), (mid_x, y + 4)], fill=C_RED, width=1)
        draw_red.line([(mid_x, y), (mid_x, y + 4)], fill=0, width=1)

    # ---------------- 3. 左右两栏内容绘制 ----------------
    cols = [
        {
            "meal_type": "breakfast",
            "name_label": "【 活力早餐 】",
            "data": menu_data.get("breakfast"),
            "x_start": 25,
            "x_end": mid_x - 18,
        },
        {
            "meal_type": "dinner",
            "name_label": "【 营养晚餐 】",
            "data": menu_data.get("dinner"),
            "x_start": mid_x + 18,
            "x_end": width - 25,
        }
    ]

    for col in cols:
        xs = col["x_start"]
        xe = col["x_end"]
        max_w = xe - xs
        data = col["data"] or {}

        # 3.1 餐别 Badge (动态自适应宽度，红底白字)
        badge_text = col["name_label"]
        bbox_b = draw_prev.textbbox((0, 0), badge_text, font=font_badge)
        badge_w = bbox_b[2] - bbox_b[0] + 16
        
        # 预览图: 红色背景 + 白色文字
        draw_prev.rectangle([(xs, 72), (xs + badge_w, 102)], fill=C_RED)
        draw_prev.text((xs + 8, 77), badge_text, fill=(255, 255, 255), font=font_badge)
        
        # 墨水屏红色通道: 红色背景 (0) + 白字镂空 (255)
        draw_red.rectangle([(xs, 72), (xs + badge_w, 102)], fill=0)
        draw_red.text((xs + 8, 77), badge_text, fill=255, font=font_badge)

        # 3.2 用时与红心
        prep_time = data.get("prep_time", "20分钟")
        time_text = f"用时: {prep_time}"
        draw_prev.text((xs + badge_w + 12, 80), time_text, fill=C_GRAY, font=font_tag)
        draw_black.text((xs + badge_w + 12, 80), time_text, fill=0, font=font_tag)

        # 红心标记 (仅保留纯粹的红色爱心图标)
        if data.get("is_favorite") == 1:
            draw_heart(draw_prev, xe - 18, 85, size=12, fill=C_RED)
            draw_heart(draw_red, xe - 18, 85, size=12, fill=0)

        # 3.3 菜谱大标题 (加粗黑字，自动折行)
        title = data.get("title", "未安排菜品")
        title_lines = wrap_text(title, font_title, max_w, draw_prev)
        cur_y = 112
        for line in title_lines[:2]:
            draw_prev.text((xs, cur_y), line, fill=C_BLACK, font=font_title)
            draw_black.text((xs, cur_y), line, fill=0, font=font_title)
            cur_y += 28

        # 3.4 营养重点标签
        nutrition = data.get("nutrition_tag", "均衡成长配方")
        nutri_text = f"● 营养重点: {nutrition}"
        draw_prev.text((xs, cur_y), nutri_text, fill=C_RED, font=font_tag)
        draw_red.text((xs, cur_y), nutri_text, fill=0, font=font_tag)
        cur_y += 24

        # 细虚线小分隔
        draw_prev.line([(xs, cur_y), (xe, cur_y)], fill=(220, 220, 220), width=1)
        draw_black.line([(xs, cur_y), (xe, cur_y)], fill=0, width=1)
        cur_y += 8

        # 3.5 食材清单
        ingredients = data.get("ingredients", [])
        if isinstance(ingredients, str):
            import json
            try:
                ingredients = json.loads(ingredients)
            except Exception:
                ingredients = [ingredients]
                
        draw_prev.text((xs, cur_y), "■ 食材准备:", fill=C_BLACK, font=font_sub)
        draw_black.text((xs, cur_y), "■ 食材准备:", fill=0, font=font_sub)
        cur_y += 22

        ing_text = " · ".join(ingredients[:6]) if ingredients else "常备家常食材"
        ing_lines = wrap_text(ing_text, font_body, max_w, draw_prev)
        for line in ing_lines[:2]:
            draw_prev.text((xs + 4, cur_y), line, fill=C_BLACK, font=font_body)
            draw_black.text((xs + 4, cur_y), line, fill=0, font=font_body)
            cur_y += 20
        cur_y += 6

        # 3.6 极简制作三步
        draw_prev.text((xs, cur_y), "■ 极简制作 (3步):", fill=C_BLACK, font=font_sub)
        draw_black.text((xs, cur_y), "■ 极简制作 (3步):", fill=0, font=font_sub)
        cur_y += 22

        steps = data.get("steps", [])
        if isinstance(steps, str):
            import json
            try:
                steps = json.loads(steps)
            except Exception:
                steps = [steps]

        for idx, step_str in enumerate(steps[:3]):
            step_clean = step_str.strip()
            # 剥离前面的 "1. " 或 "1、"
            if len(step_clean) >= 2 and step_clean[0].isdigit() and step_clean[1] in [".", "、", " "]:
                step_num = step_clean[0]
                step_body = step_clean[2:].strip()
            else:
                step_num = str(idx + 1)
                step_body = step_clean

            # 序号用红色高亮，醒目易读
            num_label = f"[{step_num}]"
            draw_prev.text((xs + 2, cur_y), num_label, fill=C_RED, font=font_tag)
            draw_red.text((xs + 2, cur_y), num_label, fill=0, font=font_tag)

            # 正文内容
            step_lines = wrap_text(step_body, font_body, max_w - 28, draw_prev)
            step_y = cur_y
            for s_line in step_lines[:2]:
                draw_prev.text((xs + 26, step_y), s_line, fill=C_BLACK, font=font_body)
                draw_black.text((xs + 26, step_y), s_line, fill=0, font=font_body)
                step_y += 20
            cur_y = step_y + 4

    # 4. 保存本地输出供调试与查看
    try:
        img_preview.save(str(config.PREVIEW_IMAGE_PATH), "PNG")
        img_black.save(str(config.EPD_BLACK_IMAGE_PATH), "BMP")
        img_red.save(str(config.EPD_RED_IMAGE_PATH), "BMP")
    except Exception as e:
        print(f"保存图像缓存失败: {e}")

    return img_preview, img_black, img_red
