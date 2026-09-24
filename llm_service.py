import os
import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
import config
import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位深耕儿童营养学、非常懂7岁（小学二年级）小女孩成长需求的资深营养师兼温柔贴心的父亲生活助手。
你的任务是根据父亲冰箱里的现有食材，为他的女儿量身定制每日健康美味家常菜谱。

【核心定制原则】：
1. 7岁儿童成长特点：
   - 处于换牙期与身体骨骼快速发育期，需要充足的高蛋白、高钙、富铁与维生素A/D；
   - 咀嚼吞咽特点：食材切小丁/小块/薄片，口感偏软嫩多汁，绝不可有整颗硬坚果或带刺危险，避免重油重辣或过咸刺激；
   - 克服挑食：将蔬菜巧妙融入（如西红柿汁、胡萝卜丁、肉末混合）。
2. 早晚餐场景要求：
   - 【早餐】：制作耗时严格控制在 15~20 分钟内！以“优质蛋白+温和复合碳水+暖胃饮品/汤水”为主（如蛋饼、软面条、馄饨、三明治、燕麦粥），让孩子清晨胃口大开且有饱腹感去上学。
   - 【晚餐】：耗时 25~35 分钟。注重荤素搭配（1荤1素或营养焖/炖/蒸），补足膳食纤维，清淡易消化，睡前不积食。
3. 食材利用：
   - 必须优先使用父亲冰箱里标有“⚠️需优先消耗”的临期食材，最大化利用现有食材，油盐酱醋葱姜等基础佐料默认厨房常备。
4. 步骤精炼：
   - 步骤必须极简！严格提炼为清晰易懂的 3 步（每步不超过 35 个字），方便爸爸在厨房墨水屏上一目了然。

【输出格式要求】：
必须严格且只返回合法的 JSON 对象，不要添加任何 markdown 代码块外部的闲聊。
JSON 字段定义：
{
  "title": "菜品名称（如：西红柿牛肉碎焖饭 / 鲜虾蛋饼+温牛奶）",
  "meal_type": "breakfast 或 dinner",
  "nutrition_tag": "营养标签（如：高蛋白 · 护眼维A · 补钙）",
  "prep_time": "用时（如：15分钟）",
  "ingredients": ["食材1 数量", "食材2 数量", "..."],
  "steps": [
    "1. 第一步动作...",
    "2. 第二步动作...",
    "3. 第三步动作..."
  ],
  "daughter_friendly_tip": "一句适合7岁女儿的小建议（如：切小丁更易嚼，酸甜开胃）"
}
"""

# 内置兜底示例菜谱池（当 API Key 未配置或网络不通时无缝应急）
FALLBACK_BREAKFASTS = [
    {
        "title": "西红柿鸡蛋软饼 + 鲜牛奶",
        "meal_type": "breakfast",
        "nutrition_tag": "优质蛋白 · 补钙护眼",
        "prep_time": "15分钟",
        "ingredients": ["鸡蛋2个", "西红柿1个", "面粉半碗", "鲜牛奶1杯"],
        "steps": [
            "1. 西红柿去皮切细丁，与鸡蛋、少许盐和面粉调成均匀面糊",
            "2. 平底锅刷油，倒入面糊中小火两面各煎2分钟至微黄金黄",
            "3. 软饼切三角小块方便手抓，搭配一杯温热鲜牛奶即可"
        ],
        "daughter_friendly_tip": "饼煎得软软的，切成小角更讨女儿喜欢"
    },
    {
        "title": "鲜虾滑蛋热汤挂面",
        "meal_type": "breakfast",
        "nutrition_tag": "高钙暖胃 · 易消化",
        "prep_time": "15分钟",
        "ingredients": ["鲜虾仁6只", "鸡蛋1个", "挂面1小把", "青菜叶适量"],
        "steps": [
            "1. 水开下入挂面煮软，放入虾仁和青菜叶煮至断生变色",
            "2. 碗中打散蛋液淋入锅中形成嫩滑蛋花，滴入几滴香油生抽",
            "3. 盛入温热小碗，温度适中后即可让女儿开动"
        ],
        "daughter_friendly_tip": "热腾腾的汤面早晨最养胃，面条稍剪短些"
    }
]

FALLBACK_DINNERS = [
    {
        "title": "肉末滑豆腐 + 清炒西兰花",
        "meal_type": "dinner",
        "nutrition_tag": "高钙富铁 · 膳食纤维",
        "prep_time": "25分钟",
        "ingredients": ["猪肉馅100g", "内酯豆腐1盒", "西兰花半朵", "蒜末适量"],
        "steps": [
            "1. 豆腐切小块焯水沥干，油锅炒散肉末加生抽微调勾芡浇在豆腐上",
            "2. 西兰花洗净切小朵焯水30秒断生捞出",
            "3. 热锅下蒜末快炒西兰花1分钟加微盐出锅，荤素搭配上桌"
        ],
        "daughter_friendly_tip": "豆腐滑嫩易吞咽，肉末酱汁拌米饭特别香"
    },
    {
        "title": "彩椒玉米胡萝卜炒肉丁 + 番茄蛋汤",
        "meal_type": "dinner",
        "nutrition_tag": "全面营养 · 促进骨骼发育",
        "prep_time": "25分钟",
        "ingredients": ["瘦肉150g", "玉米粒半碗", "胡萝卜半根", "西红柿1个", "鸡蛋1个"],
        "steps": [
            "1. 肉切小丁少许淀粉抓匀，胡萝卜切小丁与玉米粒一起焯水备用",
            "2. 热锅下肉丁滑炒变色，倒入胡萝卜玉米粒大火翻炒2分钟加盐出锅",
            "3. 另起小锅番茄炒出红汁加水煮沸，淋入蛋花撒葱花煮成开胃汤"
        ],
        "daughter_friendly_tip": "色彩丰富像彩虹，有效激发孩子的吃饭兴趣"
    }
]

def get_client() -> Optional[OpenAI]:
    """获取 OpenAI 兼容客户端（适配 MiniMax）"""
    api_key = config.MINIMAX_API_KEY or os.getenv("MINIMAX_API_KEY", "")
    base_url = config.MINIMAX_BASE_URL or os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
    
    if not api_key:
        return None
        
    return OpenAI(
        api_key=api_key,
        base_url=base_url
    )

def generate_meal(meal_type: str = "breakfast", custom_prompt: str = "") -> Dict[str, Any]:
    """生成单道餐点（breakfast 或 dinner）"""
    client = get_client()
    inventory_text = database.get_all_ingredients_text()
    recent_titles = database.get_recent_menu_titles(days=4)
    recent_text = f"最近几天已吃过的菜品（请避免重复）：{', '.join(recent_titles)}" if recent_titles else "暂无近期重复菜品"
    
    user_prompt = f"""
请为我的7岁小学二年级女儿设计一份【{'活力早餐' if meal_type == 'breakfast' else '营养晚餐'}】。

{inventory_text}
{recent_text}

特殊额外要求：{custom_prompt if custom_prompt else "请平衡营养与口感，步骤控制在极简3步以内。"}
请严格以 JSON 格式输出该餐点。
"""

    if not client:
        logger.warning("未配置 MINIMAX_API_KEY，使用智能兜底儿童菜谱")
        pool = FALLBACK_BREAKFASTS if meal_type == "breakfast" else FALLBACK_DINNERS
        import random
        return random.choice(pool)

    try:
        response = client.chat.completions.create(
            model=config.MINIMAX_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        data['meal_type'] = meal_type
        return data
    except Exception as e:
        logger.error(f"调用 MiniMax 生成菜谱失败: {e}，启用兜底方案")
        pool = FALLBACK_BREAKFASTS if meal_type == "breakfast" else FALLBACK_DINNERS
        import random
        return random.choice(pool)

def generate_full_day_plan(custom_prompt: str = "") -> Dict[str, Any]:
    """生成今日一日两餐搭配"""
    breakfast = generate_meal(meal_type="breakfast", custom_prompt=custom_prompt)
    dinner = generate_meal(meal_type="dinner", custom_prompt=custom_prompt)
    return {
        "breakfast": breakfast,
        "dinner": dinner
    }
