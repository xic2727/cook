import os
import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
import config
import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位经验丰富、注重营养均衡与健康烹饪的专业家庭营养师与生活助手。
你的任务是根据冰箱里的现有食材，规划健康美味、高效省时的家常菜谱。

【核心定制原则】：
1. 营养与口感：
   - 营养搭配均衡，富含优质蛋白、钙质、铁与维生素；
   - 食材处理偏向软嫩易嚼、清淡适口，少油少盐，避免重油重辣或过咸刺激；
   - 食材搭配丰富，色彩分明，开胃易消化。
2. 早晚餐场景要求：
   - 【早餐】：制作耗时严格控制在 15~20 分钟内！以“优质蛋白+温和复合碳水+暖胃饮品/汤水”为主（如蛋饼、软面条、馄饨、三明治、燕麦粥），营养快手，元气充沛。
   - 【晚餐】：耗时 25~35 分钟。注重荤素搭配（1荤1素或营养焖/炖/蒸），补足膳食纤维，清淡易消化，晚间不积食。
3. 食材利用：
   - 必须优先使用冰箱里标有“⚠️需优先消耗”的临期食材，最大化利用现有食材，油盐酱醋葱姜等基础佐料默认厨房常备。
4. 步骤精炼：
   - 步骤必须极简！严格提炼为清晰易懂的 3 步（每步不超过 35 个字），方便在墨水屏上一目了然。

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
  "cooking_tip": "一句实用的烹饪或风味贴士（如：切小丁更易嚼，酸甜开胃）"
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
        "cooking_tip": "饼煎得软软的，切成小三角更方便食用"
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
            "3. 盛入温热小碗，温度适中后即可趁热享用"
        ],
        "cooking_tip": "热腾腾的汤面早晨最养胃，面条稍剪短些更易吞咽"
    },
    {
        "title": "鲜肉小馄饨汤 + 水煮蛋",
        "meal_type": "breakfast",
        "nutrition_tag": "温热暖胃 · 优质蛋白",
        "prep_time": "15分钟",
        "ingredients": ["小馄饨10个", "鸡蛋1个", "紫菜少许", "虾皮1小勺"],
        "steps": [
            "1. 锅中水开下入洗净的小馄饨，中小火煮至浮起断生",
            "2. 碗底放入少许紫菜、虾皮、微量盐和香油，舀入两勺沸热原汤化开",
            "3. 盛入小馄饨与对半切开的水煮蛋，撒少许葱花趁热享用"
        ],
        "cooking_tip": "加少许虾皮紫菜提鲜又补钙，温热清润"
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
        "cooking_tip": "豆腐滑嫩易吞咽，肉末酱汁拌米饭特别香"
    },
    {
        "title": "彩椒玉米胡萝卜炒肉丁 + 番茄蛋汤",
        "meal_type": "dinner",
        "nutrition_tag": "全面营养 · 均衡膳食",
        "prep_time": "25分钟",
        "ingredients": ["瘦肉150g", "玉米粒半碗", "胡萝卜半根", "西红柿1个", "鸡蛋1个"],
        "steps": [
            "1. 肉切小丁少许淀粉抓匀，胡萝卜切小丁与玉米粒一起焯水备用",
            "2. 热锅下肉丁滑炒变色，倒入胡萝卜玉米粒大火翻炒2分钟加盐出锅",
            "3. 另起小锅番茄炒出红汁加水煮沸，淋入蛋花撒葱花煮成开胃汤"
        ],
        "cooking_tip": "色彩丰富鲜艳，有效提升用餐食欲"
    },
    {
        "title": "清蒸鲈鱼片 + 鲜菇冬瓜汤",
        "meal_type": "dinner",
        "nutrition_tag": "优质DHA · 清润低脂",
        "prep_time": "25分钟",
        "ingredients": ["鲈鱼肉200g", "冬瓜1块", "白玉菇半盒", "姜丝少许"],
        "steps": [
            "1. 鲈鱼片摆盘放姜丝，水开上汽大火蒸6分钟，出锅淋少许低钠蒸鱼豉油",
            "2. 冬瓜切薄片，白玉菇去根洗净备用",
            "3. 锅中加水煮沸下入菌菇与冬瓜片煮5分钟至透明，加少许盐和香油调味"
        ],
        "cooking_tip": "鱼肉无刺软嫩鲜美，搭配清甜冬瓜汤轻盈少负担"
    }
]

def extract_json_from_model_output(content: str) -> Any:
    """过滤思考链 <think>...</think> 与 Markdown 代码块，鲁棒提取 JSON"""
    import re
    if not content:
        raise ValueError("模型返回内容为空")
    # 1. 过滤掉 <think>...</think> 思考链内容
    cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    
    # 2. 提取 ```json ... ``` 块
    code_match = re.search(r'```(?:json)?\s*([\{\[].*?[\}\]])\s*```', cleaned, re.DOTALL)
    if code_match:
        return json.loads(code_match.group(1).strip())
        
    # 3. 寻找最外层的 { ... } 或 [ ... ]
    brace_match = re.search(r'([\{\[].*[\}\]])', cleaned, re.DOTALL)
    if brace_match:
        return json.loads(brace_match.group(1).strip())
        
    return json.loads(cleaned)

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

def generate_meal_options(meal_type: str = "breakfast", count: int = 3, custom_prompt: str = "") -> List[Dict[str, Any]]:
    """生成指定餐点类型的多套候选方案（默认3套）"""
    client = get_client()
    inventory_text = database.get_all_ingredients_text()
    recent_titles = database.get_recent_menu_titles(days=4)
    recent_text = f"最近几天已吃过的菜品（请避免重复）：{', '.join(recent_titles)}" if recent_titles else "暂无近期重复菜品"
    
    meal_desc = '活力早餐（耗时<=20分钟，营养快手暖胃）' if meal_type == 'breakfast' else '营养晚餐（耗时<=35分钟，荤素均衡清淡）'
    user_prompt = f"""
请为今日规划 {count} 道各不相同的【{meal_desc}】候选方案。

{inventory_text}
{recent_text}

特殊额外要求：{custom_prompt if custom_prompt else "请平衡营养与口感，严格满足3步极简烹饪。"}

严格输出 JSON 格式如下：
{{
  "options": [
    {{
      "title": "菜品名称",
      "meal_type": "{meal_type}",
      "nutrition_tag": "营养标签",
      "prep_time": "15分钟",
      "ingredients": ["食材1 数量", "食材2 数量"],
      "steps": ["1. 动作...", "2. 动作...", "3. 动作..."],
      "cooking_tip": "一句贴士"
    }}
  ]
}}
要求：options 数组恰好包含 {count} 个候选对象。
"""
    if not client:
        logger.warning(f"未配置 MINIMAX_API_KEY，使用兜底候选池")
        pool = FALLBACK_BREAKFASTS if meal_type == "breakfast" else FALLBACK_DINNERS
        return pool[:count]

    try:
        response = client.chat.completions.create(
            model=config.MINIMAX_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        content = response.choices[0].message.content
        data = extract_json_from_model_output(content)
        options = data.get("options", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for opt in options:
            opt["meal_type"] = meal_type
        if len(options) >= count:
            return options[:count]
        
        # 补全不足
        pool = FALLBACK_BREAKFASTS if meal_type == "breakfast" else FALLBACK_DINNERS
        for p in pool:
            if len(options) >= count:
                break
            if not any(o.get("title") == p["title"] for o in options):
                options.append(p)
        return options[:count]
    except Exception as e:
        logger.error(f"生成 {meal_type} 候选方案失败: {e}，启用兜底")
        pool = FALLBACK_BREAKFASTS if meal_type == "breakfast" else FALLBACK_DINNERS
        return pool[:count]

def generate_full_day_options(custom_prompt: str = "") -> Dict[str, List[Dict[str, Any]]]:
    """一次性生成今日 3 道候选早餐和 3 道候选晚餐"""
    client = get_client()
    inventory_text = database.get_all_ingredients_text()
    recent_titles = database.get_recent_menu_titles(days=4)
    recent_text = f"最近几天已吃过的菜品（请避免重复）：{', '.join(recent_titles)}" if recent_titles else "暂无近期重复菜品"

    user_prompt = f"""
请为今日规划 3 道不同的候选早餐（制作耗时<=20分钟，营养快手暖胃）和 3 道不同的候选晚餐（耗时<=35分钟，荤素均衡清淡），均严格满足3步极简烹饪。

{inventory_text}
{recent_text}

特殊额外要求：{custom_prompt if custom_prompt else "请平衡营养与口感，充分利用冰箱现有及临期食材。"}

请严格输出合法的 JSON 对象，格式如下：
{{
  "breakfasts": [
    {{
      "title": "菜品名称",
      "meal_type": "breakfast",
      "nutrition_tag": "营养标签",
      "prep_time": "15分钟",
      "ingredients": ["食材1 数量", "食材2 数量"],
      "steps": ["1. 动作...", "2. 动作...", "3. 动作..."],
      "cooking_tip": "一句贴士"
    }}
  ],
  "dinners": [
    {{
      "title": "菜品名称",
      "meal_type": "dinner",
      "nutrition_tag": "营养标签",
      "prep_time": "25分钟",
      "ingredients": ["食材1 数量", "食材2 数量"],
      "steps": ["1. 动作...", "2. 动作...", "3. 动作..."],
      "cooking_tip": "一句贴士"
    }}
  ]
}}
要求：breakfasts 包含恰好 3 个候选对象，dinners 包含恰好 3 个候选对象。
"""
    if not client:
        logger.warning("未配置 MINIMAX_API_KEY，使用兜底候选菜谱")
        return {
            "breakfasts": FALLBACK_BREAKFASTS[:3],
            "dinners": FALLBACK_DINNERS[:3]
        }

    try:
        response = client.chat.completions.create(
            model=config.MINIMAX_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        content = response.choices[0].message.content
        data = extract_json_from_model_output(content)
        breakfasts = data.get("breakfasts", [])
        dinners = data.get("dinners", [])

        for b in breakfasts:
            b["meal_type"] = "breakfast"
        for d in dinners:
            d["meal_type"] = "dinner"

        for fb in FALLBACK_BREAKFASTS:
            if len(breakfasts) >= 3:
                break
            if not any(b.get("title") == fb["title"] for b in breakfasts):
                breakfasts.append(fb)

        for fd in FALLBACK_DINNERS:
            if len(dinners) >= 3:
                break
            if not any(d.get("title") == fd["title"] for d in dinners):
                dinners.append(fd)

        return {
            "breakfasts": breakfasts[:3],
            "dinners": dinners[:3]
        }
    except Exception as e:
        logger.error(f"批量生成今日候选方案失败: {e}，启用兜底")
        return {
            "breakfasts": FALLBACK_BREAKFASTS[:3],
            "dinners": FALLBACK_DINNERS[:3]
        }

def generate_meal(meal_type: str = "breakfast", custom_prompt: str = "") -> Dict[str, Any]:
    """生成单道餐点（兼容旧调用）"""
    options = generate_meal_options(meal_type=meal_type, count=1, custom_prompt=custom_prompt)
    return options[0] if options else (FALLBACK_BREAKFASTS[0] if meal_type == "breakfast" else FALLBACK_DINNERS[0])

def generate_full_day_plan(custom_prompt: str = "") -> Dict[str, Any]:
    """生成今日一日两餐搭配（兼容旧调用）"""
    opts = generate_full_day_options(custom_prompt=custom_prompt)
    return {
        "breakfast": opts["breakfasts"][0],
        "dinner": opts["dinners"][0]
    }

# --- 批量食材智能提取 Prompt ---
BATCH_INGREDIENT_PROMPT = """你是一个专业的智能厨房库存助手。
用户会输入一段日常语言文本（例如买菜备忘、语音转写文本、小票清单等），请从中提取出所有食材，并结构化输出为 JSON 对象。

【分类规则】：
- "蔬菜瓜果": 西红柿、土豆、青菜、胡萝卜、西兰花、茄子、黄瓜、玉米、菌菇等
- "肉禽水产": 猪肉、牛肉、排骨、鸡肉、鸭肉、鱼、虾仁、鲜虾、肉馅、培根等
- "豆蛋奶制品": 鸡蛋、鲜牛奶、牛奶、豆腐、豆浆、内酯豆腐、奶酪等
- "主食干货": 面条、大米、面粉、挂面、粉丝、腐竹、杂粮等
- "其他": 调味品或其他无法归类的食材

【识别规则】：
1. name: 规范食材名称（如 "买了3个西红柿" -> name: "西红柿", quantity: "3个"）；
2. quantity: 份量或数量（如 "2斤"、"3个"、"1盒"，未提及则填 "适量"）；
3. is_urgent: 是否优先消耗（1 或 0）。如果文本提到"快坏了"、"尽快吃"、"先吃"、"临期"、"开封了"等，填 1，否则填 0；
4. 过滤掉非食材物品。

【输出格式要求】：
严格输出 JSON 对象，格式如下：
{
  "ingredients": [
    {"name": "西红柿", "category": "蔬菜瓜果", "quantity": "3个", "is_urgent": 1},
    {"name": "鲜排骨", "category": "肉禽水产", "quantity": "2斤", "is_urgent": 0}
  ]
}
"""

def parse_ingredients_from_text(raw_text: str) -> List[Dict[str, Any]]:
    """通过 AI 解析自然语言文本中的食材，返回结构化列表"""
    raw_text = raw_text.strip()
    if not raw_text:
        return []
        
    client = get_client()
    if not client:
        return _fallback_parse_ingredients(raw_text)
        
    user_prompt = f"请从以下文本中提取所有食材清单并返回 JSON：\n\n{raw_text}"
    try:
        response = client.chat.completions.create(
            model=config.MINIMAX_MODEL,
            messages=[
                {"role": "system", "content": BATCH_INGREDIENT_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = extract_json_from_model_output(content)
        if isinstance(data, dict):
            return data.get("ingredients", [])
        elif isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"AI 批量解析食材失败: {e}，启用规则提取兜底")
        return _fallback_parse_ingredients(raw_text)

def _fallback_parse_ingredients(text: str) -> List[Dict[str, Any]]:
    """当无 API Key 或网络异常时的规则分词提取兜底"""
    import re
    tokens = re.split(r'[,，、;；\n\r\t]+', text)
    results = []
    
    category_map = {
        "肉禽水产": ["肉", "排骨", "虾", "鱼", "鸡", "鸭", "牛", "羊", "肉馅", "培根", "香肠", "肋排"],
        "豆蛋奶制品": ["蛋", "奶", "豆腐", "豆浆", "干子", "奶酪"],
        "主食干货": ["面", "米", "粉", "燕麦", "粉丝", "腐竹", "年糕"],
        "蔬菜瓜果": ["菜", "西红柿", "番茄", "胡萝卜", "土豆", "黄瓜", "茄子", "玉米", "菇", "葱", "蒜", "姜", "莲藕"]
    }
    
    for t in tokens:
        t = t.strip()
        if not t or len(t) > 25:
            continue
        is_urgent = 1 if re.search(r'(快|急|先吃|临期|坏|早点)', t) else 0
        
        # 尝试提取数量与纯名称
        # 匹配诸如 "2斤排骨", "3个西红柿", "排骨500g"
        qty = "适量"
        m_qty = re.search(r'(\d+[\.\d]*\s*(?:斤|个|盒|把|条|包|袋|根|只|头|升|毫升|g|kg|克|两))', t, re.IGNORECASE)
        name = t
        if m_qty:
            qty = m_qty.group(1).strip()
            name = t.replace(qty, "").strip()
            
        # 清理多余语气词
        for kw in ["买了", "还有", "记得", "快坏了", "赶紧吃", "尽快吃", "需要"]:
            name = name.replace(kw, "")
        name = name.strip()
        if not name:
            continue
            
        # 匹配分类
        matched_cat = "蔬菜瓜果"
        for cat, kw_list in category_map.items():
            if any(kw in name for kw in kw_list):
                matched_cat = cat
                break
                
        results.append({
            "name": name,
            "category": matched_cat,
            "quantity": qty,
            "is_urgent": is_urgent
        })
    return results
