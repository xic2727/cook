import os
from pathlib import Path
from dotenv import load_dotenv

# 基础目录
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "output"

# 自动创建必要目录
DATA_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 加载环境变量
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)

# 数据库路径
DB_PATH = DATA_DIR / "kitchen.db"

# MiniMax / OpenAI 兼容配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-Text-01")

# 墨水屏硬件参数 (7.5寸 V2 黑白红)
EPD_WIDTH = int(os.getenv("EPD_WIDTH", 800))
EPD_HEIGHT = int(os.getenv("EPD_HEIGHT", 480))
EPD_MODE = os.getenv("EPD_MODE", "auto")

# 缓存的渲染图片路径
PREVIEW_IMAGE_PATH = OUTPUT_DIR / "eink_preview.png"
EPD_BLACK_IMAGE_PATH = OUTPUT_DIR / "eink_black.bmp"
EPD_RED_IMAGE_PATH = OUTPUT_DIR / "eink_red.bmp"

def save_api_config(api_key: str, base_url: str = None, model: str = None):
    """保存或更新 API 配置到 .env 文件"""
    global MINIMAX_API_KEY, MINIMAX_BASE_URL, MINIMAX_MODEL
    
    if api_key:
        MINIMAX_API_KEY = api_key
    if base_url:
        MINIMAX_BASE_URL = base_url
    if model:
        MINIMAX_MODEL = model
        
    lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    config_map = {
        "MINIMAX_API_KEY": MINIMAX_API_KEY,
        "MINIMAX_BASE_URL": MINIMAX_BASE_URL,
        "MINIMAX_MODEL": MINIMAX_MODEL,
        "EPD_WIDTH": str(EPD_WIDTH),
        "EPD_HEIGHT": str(EPD_HEIGHT),
        "EPD_MODE": EPD_MODE
    }
    
    written_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            k = stripped.split("=")[0].strip()
            if k in config_map:
                new_lines.append(f"{k}={config_map[k]}\n")
                written_keys.add(k)
                continue
        new_lines.append(line)
        
    for k, v in config_map.items():
        if k not in written_keys:
            new_lines.append(f"{k}={v}\n")
            
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
