# 🍳 每日营养食谱 & 7.5寸墨水屏系统

专为儿童与家庭营养量身定制的食谱生成与管理系统。
支持结合冰箱库存通过 **MiniMax 大模型** 智能生成科学配餐，并通过 **树莓派 + 微雪 7.5寸三色墨水屏（黑白红）** 实时展示每日菜谱与极简做法。

---

## 🌟 核心特性

1. **科学营养与快手烹饪**：
   * **活力早餐（≤ 20分钟）**：高能量、优质蛋白、易消化吸收，助力晨间上学精神充沛。
   * **营养晚餐（25~35分钟）**：荤素均衡搭配，高钙富铁，补充膳食纤维，清淡不积食。
   * **食材吞咽考量**：提示切小丁或软嫩烹饪，避开坚硬整粒或刺激重辣。
2. **冰箱食材管理与防浪费**：
   * 支持分类登记（蔬菜、肉类、蛋奶、主食）。
   * 标注“⚠️ 需优先消耗”的临期食材，AI 生成时自动优先消耗。
3. **红心菜谱库 ❤️**：
   * 喜欢的菜一键打红心收录，可快速一键复用。
   * 支持记录个性化口味笔记（如“喜欢加番茄酱、不吃葱”）。
4. **微雪 7.5寸 e-Paper (B) V2 墨水屏深度适配**：
   * **800×480 分辨率**，方案 B（全天一日两餐同屏展示）。
   * **黑白红三色精心排版**：红心 ❤️、餐别标签、步骤序号使用纯正红色点缀。
   * **顶部极简**：仅显示日期与星期，纯本地渲染，稳定可靠。
   * **智能双模**：在 Windows 开发机上自动运行 **Mock 模拟模式**，在 Streamlit 页面 1:1 预览渲染效果；部署到树莓派后自动调用 SPI 硬件驱动刷屏。

---

## 📁 目录结构

```text
cook/
├── app.py                  # Streamlit 主交互页面 (工作台 / 冰箱管理 / 红心库)
├── renderer.py             # 800x480 黑白红单色位图与 RGB 预览渲染引擎
├── llm_service.py          # MiniMax (兼容 OpenAI 规范) 菜谱生成服务
├── database.py             # SQLite 本地轻量数据库模型 (自动初始化)
├── epd_service.py          # 微雪 7.5寸 V2 驱动适配与 Mock 硬件抽象层
├── auto_refresh.py         # 树莓派 Crontab 用的无头静默定时刷屏脚本
├── config.py               # 环境变量与配置管理器
├── requirements.txt        # Python 依赖清单
├── .env.example            # 配置项范例
├── data/                   # 存放 kitchen.db SQLite 数据库
└── output/                 # 存放渲染生成的墨水屏位图与预览图
```

---

## 🚀 快速上手 (Windows 本地测试)

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 MiniMax API Key
复制 `.env.example` 为 `.env`，填入你的 MiniMax 凭证：
```ini
MINIMAX_API_KEY=你的MiniMax_API_KEY
MINIMAX_BASE_URL=https://api.minimax.chat/v1
MINIMAX_MODEL=MiniMax-Text-01
```
*(注：你也可以直接在 Streamlit 页面左侧边栏中直接输入并点击保存)*

### 3. 启动 Web 页面
```bash
streamlit run app.py
```
在浏览器中打开 `http://localhost:8501` 即可体验。

---

## 🍓 树莓派部署与墨水屏接线指南

### 1. 硬件接线 (微雪 7.5寸 e-Paper HAT -> 树莓派 40Pin GPIO)
微雪 HAT 插板可直接插入树莓派 40Pin 引脚。如果采用杜邦线连接：
* `VCC` -> 3.3V (Pin 1 或 17)
* `GND` -> Ground (Pin 6 或 9 或 14)
* `DIN` -> MOSI (Pin 19)
* `CLK` -> SCLK (Pin 23)
* `CS`  -> CE0 (Pin 24)
* `DC`  -> Pin 22 (GPIO25)
* `RST` -> Pin 11 (GPIO17)
* `BUSY`-> Pin 18 (GPIO24)

### 2. 在树莓派上开启 SPI 接口
```bash
sudo raspi-config
# 选择 Interface Options -> SPI -> Enable -> Yes
```

### 3. 安装树莓派基础依赖与中文字体
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-numpy fonts-wqy-microhei
```

### 4. 安装微雪官方驱动
```bash
git clone https://github.com/waveshare/e-Paper.git
cd e-Paper/RaspberryPi_JetsonNano/python
sudo python3 setup.py install
```

### 5. 运行服务
```bash
cd /path/to/cook
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```
在手机或平板浏览器输入 `http://<树莓派IP>:8501` 即可随时随地管理冰箱、制定菜谱与一键推屏！

### 6. 配置早晚定时自动静默刷屏 (可选)
使用 `crontab -e` 添加定时任务：
```cron
# 每天早晨 06:30 自动刷屏今日菜单
30 6 * * * /usr/bin/python3 /home/pi/cook/auto_refresh.py >> /home/pi/cook/cron.log 2>&1
```
