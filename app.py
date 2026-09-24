import streamlit as st
from datetime import date, datetime
from pathlib import Path
import json

import config
import database
import llm_service
import epd_service
import renderer

# 页面基础配置
st.set_page_config(
    page_title="每日食谱 & 墨水屏",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化数据库
database.init_db()

# 自定义 CSS 样式提升视觉质感
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.8rem;
    }
    .card-box {
        background-color: #F8FAFC;
        border-radius: 10px;
        padding: 1.2rem;
        border: 1px solid #E2E8F0;
        margin-bottom: 1rem;
    }
    .badge-breakfast {
        background-color: #EF4444;
        color: white;
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-dinner {
        background-color: #DC2626;
        color: white;
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .heart-fav {
        color: #EF4444;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- 侧边栏：硬件与 API 设置 -----------------
with st.sidebar:
    st.image("https://img.icons8.com/parakeet/96/frying-pan.png", width=64)
    st.markdown("### ⚙️ 系统状态与设置")
    
    # 硬件状态
    hw_status = epd_service.get_hardware_status()
    if hw_status["available"]:
        st.success("🟢 **7.5寸墨水屏：硬件已就绪** (树莓派 SPI)")
    else:
        st.warning("🟡 **墨水屏模式：模拟预览模式**")
        with st.expander("🔧 硬件未识别诊断与排查", expanded=False):
            if hw_status["error_reason"]:
                st.caption("诊断原因:")
                st.code(hw_status["error_reason"], language="text")
            st.markdown("""
            **在树莓派终端运行一键修复：**
            ```bash
            sudo ./setup_epd.sh
            ```
            或运行深度诊断：
            ```bash
            python3 diagnose_epd.py
            ```
            """)
    st.caption("硬件型号: 微雪 7.5inch e-Paper (B) V2 (800×480 黑白红)")
    
    st.divider()
    
    # MiniMax API 配置
    st.markdown("#### 🤖 MiniMax AI 配置")
    current_key = config.MINIMAX_API_KEY
    api_key_input = st.text_input(
        "MiniMax API Key", 
        value=current_key, 
        type="password",
        help="输入你的 MiniMax 平台 API Key"
    )
    base_url_input = st.text_input("Base URL", value=config.MINIMAX_BASE_URL)
    model_input = st.text_input("模型名称", value=config.MINIMAX_MODEL)
    
    if st.button("💾 保存 API 配置", use_container_width=True):
        config.save_api_config(api_key_input, base_url_input, model_input)
        st.toast("✅ API 配置已更新并保存至 .env！", icon="🎉")
        st.rerun()
        
    if current_key:
        st.caption("🟢 已配置 API Key")
    else:
        st.caption("⚠️ 未配置 API Key，将自动使用内置优质儿童食谱库")
        
    st.divider()
    st.caption("💡 **树莓派部署小贴士**：\n在树莓派中运行 `sudo raspi-config` 开启 SPI 接口，即可将当前画面直连微雪墨水屏。")

# ----------------- 页面主体 -----------------
st.markdown('<div class="main-title">🍳 每日食谱</div>', unsafe_allow_html=True)

tab_menu, tab_inventory, tab_favorites = st.tabs([
    "🍽️ 今日食谱 & 墨水屏同步", 
    "🧊 冰箱食材管理", 
    "❤️ 红心菜谱库"
])

# =========================================================================
# TAB 1: 今日食谱 & 墨水屏同步工作台
# =========================================================================
with tab_menu:
    # 顶部工具栏
    col_date, col_action1, col_action2 = st.columns([2, 2.5, 2.5])
    with col_date:
        today = date.today()
        selected_date = st.date_input("选择日期", value=today)
        date_iso = selected_date.isoformat()
        
    # 读取所选日期的食谱
    daily_menu = database.get_daily_menu(date_iso)
    b_recipe = daily_menu.get("breakfast")
    d_recipe = daily_menu.get("dinner")

    with col_action1:
        st.write("") # 对齐
        if st.button("✨ 结合冰箱库存一键智能生成今日食谱", type="primary", use_container_width=True):
            with st.spinner("👩‍🍳 营养师爸爸正在结合冰箱食材规划科学菜谱..."):
                plan = llm_service.generate_full_day_plan()
                b_data = plan["breakfast"]
                d_data = plan["dinner"]
                
                # 存入数据库
                new_b_id = database.save_recipe(
                    title=b_data["title"],
                    meal_type="breakfast",
                    nutrition_tag=b_data.get("nutrition_tag", ""),
                    ingredients=b_data.get("ingredients", []),
                    steps=b_data.get("steps", []),
                    prep_time=b_data.get("prep_time", "15分钟"),
                    is_favorite=0,
                    daughter_notes=b_data.get("daughter_friendly_tip", "")
                )
                new_d_id = database.save_recipe(
                    title=d_data["title"],
                    meal_type="dinner",
                    nutrition_tag=d_data.get("nutrition_tag", ""),
                    ingredients=d_data.get("ingredients", []),
                    steps=d_data.get("steps", []),
                    prep_time=d_data.get("prep_time", "25分钟"),
                    is_favorite=0,
                    daughter_notes=d_data.get("daughter_friendly_tip", "")
                )
                database.set_daily_menu(date_iso, new_b_id, new_d_id)
                st.toast("今日早晚餐已生成！", icon="🍱")
                st.rerun()

    with col_action2:
        st.write("")
        if st.button("📺 立即同步到 7.5 寸墨水屏", type="secondary", use_container_width=True):
            with st.spinner("正在排版并推送到 800×480 墨水屏..."):
                success, msg, _ = epd_service.sync_menu_to_screen(daily_menu, selected_date)
                if success:
                    database.mark_daily_menu_synced(date_iso)
                    st.toast(msg, icon="🎉")
                else:
                    st.error(msg)
                st.rerun()

    st.markdown("---")

    # 左右两栏展示今日早餐与晚餐
    col_b, col_d = st.columns(2)

    # --- 左栏：活力早餐 ---
    with col_b:
        st.markdown('### ☀️ 活力早餐 <span class="badge-breakfast">控时 ≤ 20分钟</span>', unsafe_allow_html=True)
        if b_recipe:
            with st.container(border=True):
                # 标题栏与红心
                header_c1, header_c2 = st.columns([4, 1.2])
                with header_c1:
                    st.subheader(b_recipe["title"])
                with header_c2:
                    is_fav = b_recipe.get("is_favorite") == 1
                    btn_fav_label = "❤️ 喜欢" if is_fav else "🤍 收藏"
                    if st.button(btn_fav_label, key=f"fav_b_{b_recipe['id']}"):
                        new_fav = database.toggle_recipe_favorite(b_recipe["id"])
                        st.toast("已加入红心菜谱！" if new_fav else "已取消收藏", icon="❤️" if new_fav else "🤍")
                        st.rerun()

                st.markdown(f"**● 营养重点**：`:red[{b_recipe.get('nutrition_tag', '优质蛋白')}]` ｜ ⏱️ 预计用时: {b_recipe.get('prep_time', '15分钟')}")
                
                if b_recipe.get("daughter_notes"):
                    st.info(f"💡 **爸爸小贴士**：{b_recipe['daughter_notes']}")

                st.markdown("**■ 食材准备**")
                ing_list = b_recipe.get("ingredients", [])
                st.markdown(" • " + "   • ".join(ing_list))

                st.markdown("**■ 极简烹饪 (3步)**")
                for step in b_recipe.get("steps", []):
                    st.markdown(f"- {step}")

                # 早餐单独重抽 / 从红心库挑选
                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if st.button("🔄 单独换一道早餐", key="reroll_b"):
                        with st.spinner("正在重新为女儿生成早餐..."):
                            new_b = llm_service.generate_meal(meal_type="breakfast")
                            b_id = database.save_recipe(
                                title=new_b["title"],
                                meal_type="breakfast",
                                nutrition_tag=new_b.get("nutrition_tag", ""),
                                ingredients=new_b.get("ingredients", []),
                                steps=new_b.get("steps", []),
                                prep_time=new_b.get("prep_time", "15分钟"),
                                daughter_notes=new_b.get("daughter_friendly_tip", "")
                            )
                            database.set_daily_menu(date_iso, b_id, d_recipe["id"] if d_recipe else None)
                            st.rerun()
                with btn_c2:
                    fav_b_list = database.get_recipes(meal_type="breakfast", only_favorites=True)
                    if fav_b_list:
                        selected_fav_b = st.selectbox(
                            "从红心库选用", 
                            options=[f"{r['title']}" for r in fav_b_list],
                            key="select_fav_b"
                        )
                        if st.button("确定选用此红心早餐", key="apply_fav_b"):
                            chosen = next(r for r in fav_b_list if r['title'] == selected_fav_b)
                            database.set_daily_menu(date_iso, chosen["id"], d_recipe["id"] if d_recipe else None)
                            st.rerun()
                    else:
                        st.caption("暂无红心早餐，点红心收藏即可在此快速挑选")
        else:
            st.info("今日尚未安排早餐，请点击上方“智能生成”或从下方添加。")

    # --- 右栏：营养晚餐 ---
    with col_d:
        st.markdown('### 🌙 营养晚餐 <span class="badge-dinner">荤素全面搭配</span>', unsafe_allow_html=True)
        if d_recipe:
            with st.container(border=True):
                header_d1, header_d2 = st.columns([4, 1.2])
                with header_d1:
                    st.subheader(d_recipe["title"])
                with header_d2:
                    is_fav = d_recipe.get("is_favorite") == 1
                    btn_fav_label = "❤️ 喜欢" if is_fav else "🤍 收藏"
                    if st.button(btn_fav_label, key=f"fav_d_{d_recipe['id']}"):
                        new_fav = database.toggle_recipe_favorite(d_recipe["id"])
                        st.toast("已加入红心菜谱！" if new_fav else "已取消收藏", icon="❤️" if new_fav else "🤍")
                        st.rerun()

                st.markdown(f"**● 营养重点**：`:red[{d_recipe.get('nutrition_tag', '均衡膳食')}]` ｜ ⏱️ 预计用时: {d_recipe.get('prep_time', '25分钟')}")
                
                if d_recipe.get("daughter_notes"):
                    st.info(f"💡 **爸爸小贴士**：{d_recipe['daughter_notes']}")

                st.markdown("**■ 食材准备**")
                ing_list = d_recipe.get("ingredients", [])
                st.markdown(" • " + "   • ".join(ing_list))

                st.markdown("**■ 极简烹饪 (3步)**")
                for step in d_recipe.get("steps", []):
                    st.markdown(f"- {step}")

                # 晚餐单独重抽 / 从红心库挑选
                btn_d1, btn_d2 = st.columns(2)
                with btn_d1:
                    if st.button("🔄 单独换一道晚餐", key="reroll_d"):
                        with st.spinner("正在重新为女儿生成晚餐..."):
                            new_d = llm_service.generate_meal(meal_type="dinner")
                            d_id = database.save_recipe(
                                title=new_d["title"],
                                meal_type="dinner",
                                nutrition_tag=new_d.get("nutrition_tag", ""),
                                ingredients=new_d.get("ingredients", []),
                                steps=new_d.get("steps", []),
                                prep_time=new_d.get("prep_time", "25分钟"),
                                daughter_notes=new_d.get("daughter_friendly_tip", "")
                            )
                            database.set_daily_menu(date_iso, b_recipe["id"] if b_recipe else None, d_id)
                            st.rerun()
                with btn_d2:
                    fav_d_list = database.get_recipes(meal_type="dinner", only_favorites=True)
                    if fav_d_list:
                        selected_fav_d = st.selectbox(
                            "从红心库选用", 
                            options=[f"{r['title']}" for r in fav_d_list],
                            key="select_fav_d"
                        )
                        if st.button("确定选用此红心晚餐", key="apply_fav_d"):
                            chosen = next(r for r in fav_d_list if r['title'] == selected_fav_d)
                            database.set_daily_menu(date_iso, b_recipe["id"] if b_recipe else None, chosen["id"])
                            st.rerun()
                    else:
                        st.caption("暂无红心晚餐，点红心收藏即可在此快速挑选")
        else:
            st.info("今日尚未安排晚餐，请点击上方“智能生成”。")

    # --- 墨水屏 800x480 实时渲染预览 ---
    st.markdown("---")
    st.markdown("### 🖥️ 7.5 寸黑白红墨水屏 1:1 同步预览效果")
    
    # 动态渲染当前界面的预览图
    img_prev, _, _ = renderer.render_eink_display(daily_menu, selected_date)
    st.image(img_prev, caption="微雪 7.5inch e-Paper (B) V2 (800×480) 渲染预览", use_container_width=True)
    
    synced_at = daily_menu.get("synced_at")
    if synced_at:
        st.caption(f"🕒 上次成功同步到屏幕时间: {synced_at}")

# =========================================================================
# TAB 2: 冰箱食材管理
# =========================================================================
with tab_inventory:
    st.markdown("### 🧊 冰箱食材库存清单")
    st.caption("系统生成菜谱时，将优先消耗标记为“⚠️需优先消耗”的临期食材，并按现有食材做菜。")

    # 快捷添加食材表单
    with st.expander("➕ 添加新采购的食材 / 蔬菜肉类", expanded=True):
        with st.form("add_inventory_form", clear_on_submit=True):
            col_in1, col_in2, col_in3, col_in4 = st.columns([3, 2, 2, 2])
            with col_in1:
                item_name = st.text_input("食材名称 (如：西红柿、鲜虾仁、西兰花)")
            with col_in2:
                item_cat = st.selectbox(
                    "类别",
                    ["蔬菜瓜果", "肉禽水产", "豆蛋奶制品", "主食干货", "其他"]
                )
            with col_in3:
                item_qty = st.text_input("份量/数量 (如：2个、300g、1盒)", value="适量")
            with col_in4:
                item_urgent = st.checkbox("⚠️ 需优先消耗 (临期/开封)")
                
            submitted = st.form_submit_button("保存到冰箱", use_container_width=True, type="primary")
            if submitted:
                if item_name.strip():
                    database.add_inventory_item(
                        item_name.strip(),
                        item_cat,
                        item_qty.strip(),
                        1 if item_urgent else 0
                    )
                    st.toast(f"已录入食材：{item_name}", icon="🥗")
                    st.rerun()
                else:
                    st.warning("请输入食材名称")

    # 筛选类别
    cat_filter = st.radio(
        "分类筛选",
        ["全部", "蔬菜瓜果", "肉禽水产", "豆蛋奶制品", "主食干货"],
        horizontal=True
    )
    
    items = database.get_inventory(category=cat_filter)
    if items:
        # 表格化与操作列表
        st.write(f"当前共 **{len(items)}** 种食材：")
        for item in items:
            col_t1, col_t2, col_t3, col_t4 = st.columns([3, 2, 2, 1.5])
            with col_t1:
                urgent_badge = "⚠️ [优先吃] " if item['is_urgent'] else ""
                st.markdown(f"**{urgent_badge}{item['name']}**")
            with col_t2:
                st.caption(f"分类: {item['category']}")
            with col_t3:
                new_qty = st.text_input("数量", value=item['quantity'], key=f"qty_{item['id']}", label_visibility="collapsed")
            with col_t4:
                col_sub1, col_sub2 = st.columns(2)
                with col_sub1:
                    if st.button("更新", key=f"upd_{item['id']}"):
                        database.update_inventory_item(item['id'], new_qty, item['is_urgent'])
                        st.toast(f"已更新 {item['name']}", icon="✅")
                        st.rerun()
                with col_sub2:
                    if st.button("删除", key=f"del_{item['id']}"):
                        database.delete_inventory_item(item['id'])
                        st.toast(f"已从冰箱移除 {item['name']}", icon="🗑️")
                        st.rerun()
            st.divider()
    else:
        st.info("当前分类暂无食材，请在上方添加！")

# =========================================================================
# TAB 3: 红心菜谱库
# =========================================================================
with tab_favorites:
    st.markdown("### ❤️ 红心菜谱库")
    st.caption("这里是吃过且特别喜欢的菜品，打红心后永久留存。可一键安排到今日食谱，或写下口味偏好。")

    fav_filter = st.radio("筛选餐别", ["全部", "早餐", "晚餐"], horizontal=True)
    m_type = "breakfast" if fav_filter == "早餐" else ("dinner" if fav_filter == "晚餐" else None)
    
    fav_recipes = database.get_recipes(meal_type=m_type, only_favorites=True)

    if fav_recipes:
        for fav in fav_recipes:
            with st.container(border=True):
                f_col1, f_col2 = st.columns([4, 2])
                with f_col1:
                    tag_type = "【早餐】" if fav["meal_type"] == "breakfast" else "【晚餐】"
                    st.markdown(f"#### ❤️ {tag_type} {fav['title']}")
                    st.markdown(f"**● 营养要点**：`:red[{fav.get('nutrition_tag', '')}]` ｜ ⏱️ 用时: {fav.get('prep_time', '')}")
                    
                    st.markdown("**■ 食材**：" + " · ".join(fav.get("ingredients", [])))
                    st.markdown("**■ 做法**：")
                    for s in fav.get("steps", []):
                        st.markdown(f"  {s}")

                with f_col2:
                    st.markdown("##### 📝 口味偏好与烹饪笔记")
                    cur_notes = fav.get("daughter_notes", "")
                    new_notes = st.text_area("偏好备忘 (如：喜欢多加醋、切细丝)", value=cur_notes, key=f"notes_{fav['id']}", height=90)
                    if new_notes != cur_notes:
                        if st.button("保存笔记", key=f"save_notes_{fav['id']}"):
                            database.update_recipe_notes(fav["id"], new_notes)
                            st.toast("已保存专属笔记！", icon="📝")
                            st.rerun()

                    st.write("")
                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        target_label = "安排到今日早餐" if fav["meal_type"] == "breakfast" else "安排到今日晚餐"
                        if st.button(target_label, key=f"apply_today_{fav['id']}", type="primary"):
                            today_iso = date.today().isoformat()
                            if fav["meal_type"] == "breakfast":
                                database.set_daily_menu(today_iso, fav["id"], None)
                            else:
                                database.set_daily_menu(today_iso, None, fav["id"])
                            st.toast(f"已安排到今日{target_label[-2:]}！", icon="🍱")
                            st.rerun()
                    with col_act2:
                        if st.button("取消红心", key=f"unfav_{fav['id']}"):
                            database.toggle_recipe_favorite(fav["id"])
                            st.toast("已移出红心库", icon="🤍")
                            st.rerun()
    else:
        st.info("还没有收藏红心菜谱哦！在“今日食谱”中做完一道菜，点击 ❤️ 即可收录至此处。")
