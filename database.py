import sqlite3
import json
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表结构并插入初始示例数据"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. 冰箱库存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                quantity TEXT DEFAULT '适量',
                is_urgent INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. 菜谱库
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                meal_type TEXT NOT NULL, -- 'breakfast' or 'dinner'
                nutrition_tag TEXT,      -- 如 '优质蛋白 · 补钙护眼'
                ingredients TEXT,        -- JSON 字符串: ["西红柿 1个", "鸡蛋 2个"]
                steps TEXT,              -- JSON 字符串: ["切块", "翻炒", "装盘"]
                prep_time TEXT,          -- 如 '15分钟'
                is_favorite INTEGER DEFAULT 0, -- 1: ❤️, 0: 普通
                daughter_notes TEXT DEFAULT '', -- 烹饪笔记/风味反馈
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. 每日菜单记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_menu (
                date TEXT PRIMARY KEY,   -- 'YYYY-MM-DD'
                breakfast_id INTEGER,
                dinner_id INTEGER,
                breakfast_ids TEXT,      -- JSON 数组，如 "[1, 2, 3]" 候选方案
                dinner_ids TEXT,         -- JSON 数组，如 "[4, 5, 6]" 候选方案
                synced_at TIMESTAMP,
                FOREIGN KEY (breakfast_id) REFERENCES recipes(id),
                FOREIGN KEY (dinner_id) REFERENCES recipes(id)
            )
        """)
        
        # 兼容已有数据库迁移 breakfast_ids 和 dinner_ids
        cursor.execute("PRAGMA table_info(daily_menu)")
        dm_columns = [row[1] for row in cursor.fetchall()]
        if "breakfast_ids" not in dm_columns:
            cursor.execute("ALTER TABLE daily_menu ADD COLUMN breakfast_ids TEXT")
        if "dinner_ids" not in dm_columns:
            cursor.execute("ALTER TABLE daily_menu ADD COLUMN dinner_ids TEXT")
        
        # 检查是否需要插入初始示例数据
        cursor.execute("SELECT COUNT(*) FROM inventory")
        if cursor.fetchone()[0] == 0:
            initial_inventory = [
                ("鸡蛋", "豆蛋奶制品", "8个", 0),
                ("鲜牛奶", "豆蛋奶制品", "2盒", 0),
                ("西红柿", "蔬菜瓜果", "2个", 1), # 临期优先
                ("西兰花", "蔬菜瓜果", "半朵", 0),
                ("胡萝卜", "蔬菜瓜果", "1根", 0),
                ("猪肉馅", "肉禽水产", "200g", 1), # 临期优先
                ("鲜虾仁", "肉禽水产", "150g", 0),
                ("嫩豆腐", "豆蛋奶制品", "1盒", 1),
                ("挂面/面粉", "主食干货", "充足", 0),
                ("玉米粒", "蔬菜瓜果", "1包", 0),
            ]
            cursor.executemany(
                "INSERT INTO inventory (name, category, quantity, is_urgent) VALUES (?, ?, ?, ?)",
                initial_inventory
            )
            
        cursor.execute("SELECT COUNT(*) FROM recipes")
        if cursor.fetchone()[0] == 0:
            sample_breakfast = (
                "西红柿鸡蛋软饼 + 温牛奶",
                "breakfast",
                "优质蛋白 · 补钙护眼",
                json.dumps(["鸡蛋2个", "西红柿1个", "面粉半碗", "鲜牛奶1杯"], ensure_ascii=False),
                json.dumps([
                    "西红柿烫皮切小丁，打入鸡蛋搅散，加少许盐和面粉调成均匀面糊",
                    "平底锅刷薄油，舀入面糊摊平，中小火煎至两面金黄微凝固",
                    "切扇形小块方便抓握，搭配一杯温热鲜牛奶即可上桌"
                ], ensure_ascii=False),
                "15分钟",
                1, # 默认红心
                "煎得软软的，切成小三角口感很好"
            )
            sample_dinner = (
                "肉末滑嫩豆腐 + 清炒西兰花",
                "dinner",
                "高钙高铁 · 丰富膳食纤维",
                json.dumps(["猪肉馅100g", "内酯豆腐1盒", "西兰花半朵", "蒜末适量"], ensure_ascii=False),
                json.dumps([
                    "豆腐切小方块焯水沥干装盘，锅中少许油将肉末炒散变色",
                    "肉末加入少许低钠生抽调味，加水淀粉勾薄芡后淋在热豆腐上",
                    "西兰花焯水30秒，热锅蒜末快炒1分钟加少许盐出锅"
                ], ensure_ascii=False),
                "25分钟",
                1,
                "豆腐拌米饭吃光了一大碗！"
            )
            cursor.execute("""
                INSERT INTO recipes (title, meal_type, nutrition_tag, ingredients, steps, prep_time, is_favorite, daughter_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_breakfast)
            b_id = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO recipes (title, meal_type, nutrition_tag, ingredients, steps, prep_time, is_favorite, daughter_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_dinner)
            d_id = cursor.lastrowid
            
            # 设置今天默认菜单
            today_str = date.today().isoformat()
            cursor.execute("""
                INSERT OR IGNORE INTO daily_menu (date, breakfast_id, dinner_id)
                VALUES (?, ?, ?)
            """, (today_str, b_id, d_id))
            
        conn.commit()

# --- 冰箱库存管理 ---

def get_inventory(category: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if category and category != "全部":
            cursor.execute("SELECT * FROM inventory WHERE category = ? ORDER BY is_urgent DESC, updated_at DESC", (category,))
        else:
            cursor.execute("SELECT * FROM inventory ORDER BY is_urgent DESC, updated_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def add_inventory_item(name: str, category: str, quantity: str = "适量", is_urgent: int = 0) -> bool:
    name = name.strip()
    if not name:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO inventory (name, category, quantity, is_urgent, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                category=excluded.category,
                quantity=excluded.quantity,
                is_urgent=excluded.is_urgent,
                updated_at=CURRENT_TIMESTAMP
        """, (name, category, quantity, is_urgent))
        conn.commit()
    return True

def batch_add_inventory_items(items: List[Dict[str, Any]]) -> int:
    """批量新增或更新食材，返回成功处理条数"""
    if not items:
        return 0
    count = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for item in items:
            name = item.get("name", "").strip()
            if not name:
                continue
            category = item.get("category", "蔬菜瓜果")
            quantity = item.get("quantity", "适量")
            is_urgent = 1 if item.get("is_urgent") else 0
            cursor.execute("""
                INSERT INTO inventory (name, category, quantity, is_urgent, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    category=excluded.category,
                    quantity=excluded.quantity,
                    is_urgent=excluded.is_urgent,
                    updated_at=CURRENT_TIMESTAMP
            """, (name, category, quantity, is_urgent))
            count += 1
        conn.commit()
    return count

def update_inventory_item(item_id: int, quantity: str, is_urgent: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE inventory 
            SET quantity = ?, is_urgent = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (quantity, is_urgent, item_id))
        conn.commit()

def delete_inventory_item(item_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        conn.commit()

def get_all_ingredients_text() -> str:
    """提取冰箱所有食材描述，格式化给大模型Prompt"""
    items = get_inventory()
    if not items:
        return "冰箱暂无登记食材，请按常见家常蔬菜、鸡蛋肉类推荐。"
    
    urgent_items = [item['name'] for item in items if item['is_urgent']]
    normal_items = [f"{item['name']}({item['quantity']})" for item in items if not item['is_urgent']]
    
    text = "【当前冰箱食材】\n"
    if urgent_items:
        text += f"⚠️ 需优先消耗的临期食材: {', '.join(urgent_items)}\n"
    text += f"常备或充足食材: {', '.join(normal_items)}\n"
    return text

# --- 菜谱库管理 ---

def get_recipes(meal_type: Optional[str] = None, only_favorites: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        conditions = []
        params = []
        if meal_type:
            conditions.append("meal_type = ?")
            params.append(meal_type)
        if only_favorites:
            conditions.append("is_favorite = 1")
            
        sql = "SELECT * FROM recipes"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY is_favorite DESC, created_at DESC"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d['ingredients'] = json.loads(d['ingredients']) if isinstance(d['ingredients'], str) else d['ingredients']
            except Exception:
                d['ingredients'] = [d['ingredients']] if d['ingredients'] else []
            try:
                d['steps'] = json.loads(d['steps']) if isinstance(d['steps'], str) else d['steps']
            except Exception:
                d['steps'] = [d['steps']] if d['steps'] else []
            result.append(d)
        return result

def get_recipe_by_id(recipe_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['ingredients'] = json.loads(d['ingredients']) if isinstance(d['ingredients'], str) else d['ingredients']
        except Exception:
            d['ingredients'] = [d['ingredients']] if d['ingredients'] else []
        try:
            d['steps'] = json.loads(d['steps']) if isinstance(d['steps'], str) else d['steps']
        except Exception:
            d['steps'] = [d['steps']] if d['steps'] else []
        return d

def save_recipe(title: str, meal_type: str, nutrition_tag: str, 
                ingredients: list, steps: list, prep_time: str = "20分钟", 
                is_favorite: int = 0, daughter_notes: str = "") -> int:
    """保存或新增菜谱，返回 recipe_id"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recipes (title, meal_type, nutrition_tag, ingredients, steps, prep_time, is_favorite, daughter_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            meal_type,
            nutrition_tag,
            json.dumps(ingredients, ensure_ascii=False),
            json.dumps(steps, ensure_ascii=False),
            prep_time,
            is_favorite,
            daughter_notes
        ))
        conn.commit()
        return cursor.lastrowid

def toggle_recipe_favorite(recipe_id: int) -> int:
    """切换菜谱的红心状态，返回切换后的状态 (0 或 1)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_favorite FROM recipes WHERE id = ?", (recipe_id,))
        row = cursor.fetchone()
        if not row:
            return 0
        new_val = 0 if row['is_favorite'] == 1 else 1
        cursor.execute("UPDATE recipes SET is_favorite = ? WHERE id = ?", (new_val, recipe_id))
        conn.commit()
        return new_val

def update_recipe_notes(recipe_id: int, notes: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE recipes SET daughter_notes = ? WHERE id = ?", (notes, recipe_id))
        conn.commit()

# --- 每日食谱管理 ---

def get_daily_menu(date_str: Optional[str] = None) -> Dict[str, Any]:
    if not date_str:
        date_str = date.today().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_menu WHERE date = ?", (date_str,))
        row = cursor.fetchone()
        if not row:
            return {
                "date": date_str,
                "breakfast": None,
                "dinner": None,
                "breakfast_id": None,
                "dinner_id": None,
                "breakfast_candidates": [],
                "dinner_candidates": [],
                "breakfast_ids": [],
                "dinner_ids": [],
                "synced_at": None
            }
        
        row_dict = dict(row)
        b_id = row_dict.get('breakfast_id')
        d_id = row_dict.get('dinner_id')
        
        # 解析 breakfast_ids
        raw_b_ids = row_dict.get('breakfast_ids')
        b_ids = []
        if raw_b_ids:
            try:
                b_ids = json.loads(raw_b_ids) if isinstance(raw_b_ids, str) else raw_b_ids
            except Exception:
                b_ids = []
        if not b_ids and b_id:
            b_ids = [b_id]
            
        # 解析 dinner_ids
        raw_d_ids = row_dict.get('dinner_ids')
        d_ids = []
        if raw_d_ids:
            try:
                d_ids = json.loads(raw_d_ids) if isinstance(raw_d_ids, str) else raw_d_ids
            except Exception:
                d_ids = []
        if not d_ids and d_id:
            d_ids = [d_id]
            
        b_candidates = [get_recipe_by_id(rid) for rid in b_ids]
        b_candidates = [c for c in b_candidates if c is not None]
        
        d_candidates = [get_recipe_by_id(rid) for rid in d_ids]
        d_candidates = [c for c in d_candidates if c is not None]
        
        if not b_id and b_candidates:
            b_id = b_candidates[0]['id']
        if not d_id and d_candidates:
            d_id = d_candidates[0]['id']
            
        active_b = get_recipe_by_id(b_id) if b_id else (b_candidates[0] if b_candidates else None)
        active_d = get_recipe_by_id(d_id) if d_id else (d_candidates[0] if d_candidates else None)
        
        return {
            "date": date_str,
            "breakfast": active_b,
            "dinner": active_d,
            "breakfast_id": active_b['id'] if active_b else None,
            "dinner_id": active_d['id'] if active_d else None,
            "breakfast_candidates": b_candidates,
            "dinner_candidates": d_candidates,
            "breakfast_ids": [c['id'] for c in b_candidates],
            "dinner_ids": [c['id'] for c in d_candidates],
            "synced_at": row_dict.get('synced_at')
        }

def save_daily_menu_candidates(date_str: str, b_ids: List[int], d_ids: List[int], 
                               active_b_id: Optional[int] = None, active_d_id: Optional[int] = None):
    """保存当天的早晚各3套候选菜谱，并设置当前激活的菜谱（默认各取第1个）"""
    if active_b_id is None and b_ids:
        active_b_id = b_ids[0]
    if active_d_id is None and d_ids:
        active_d_id = d_ids[0]
        
    b_json = json.dumps(b_ids)
    d_json = json.dumps(d_ids)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_menu (date, breakfast_id, dinner_id, breakfast_ids, dinner_ids)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                breakfast_id = excluded.breakfast_id,
                dinner_id = excluded.dinner_id,
                breakfast_ids = excluded.breakfast_ids,
                dinner_ids = excluded.dinner_ids
        """, (date_str, active_b_id, active_d_id, b_json, d_json))
        conn.commit()

def set_active_candidate(date_str: str, meal_type: str, recipe_id: int):
    """在 Streamlit 页面上切换某餐当前展示与同步的菜谱"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if meal_type == "breakfast":
            cursor.execute("""
                INSERT INTO daily_menu (date, breakfast_id) VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET breakfast_id = excluded.breakfast_id
            """, (date_str, recipe_id))
        else:
            cursor.execute("""
                INSERT INTO daily_menu (date, dinner_id) VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET dinner_id = excluded.dinner_id
            """, (date_str, recipe_id))
        conn.commit()

def update_meal_candidates(date_str: str, meal_type: str, candidate_ids: List[int], active_id: Optional[int] = None):
    """单独重新生成某餐的 3 套候选方案"""
    if active_id is None and candidate_ids:
        active_id = candidate_ids[0]
    c_json = json.dumps(candidate_ids)
    with get_connection() as conn:
        cursor = conn.cursor()
        if meal_type == "breakfast":
            cursor.execute("""
                INSERT INTO daily_menu (date, breakfast_id, breakfast_ids) VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET breakfast_id = excluded.breakfast_id, breakfast_ids = excluded.breakfast_ids
            """, (date_str, active_id, c_json))
        else:
            cursor.execute("""
                INSERT INTO daily_menu (date, dinner_id, dinner_ids) VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET dinner_id = excluded.dinner_id, dinner_ids = excluded.dinner_ids
            """, (date_str, active_id, c_json))
        conn.commit()

def set_daily_menu(date_str: str, breakfast_id: Optional[int], dinner_id: Optional[int]):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_menu (date, breakfast_id, dinner_id)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                breakfast_id = COALESCE(excluded.breakfast_id, daily_menu.breakfast_id),
                dinner_id = COALESCE(excluded.dinner_id, daily_menu.dinner_id)
        """, (date_str, breakfast_id, dinner_id))
        conn.commit()

def mark_daily_menu_synced(date_str: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE daily_menu SET synced_at = CURRENT_TIMESTAMP WHERE date = ?
        """, (date_str,))
        conn.commit()

def get_recent_menu_titles(days: int = 5) -> List[str]:
    """获取最近几天的菜谱标题，供大模型去重"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.title as b_title, d.title as d_title
            FROM daily_menu m
            LEFT JOIN recipes b ON m.breakfast_id = b.id
            LEFT JOIN recipes d ON m.dinner_id = d.id
            ORDER BY m.date DESC LIMIT ?
        """, (days,))
        titles = []
        for row in cursor.fetchall():
            if row['b_title']:
                titles.append(row['b_title'])
            if row['d_title']:
                titles.append(row['d_title'])
        return titles
