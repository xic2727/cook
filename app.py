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
    
    # 屏幕旋转设置
    current_rot = getattr(config, "EPD_ROTATION", 180)
    rot_options = [180, 0]
    selected_rot = st.radio(
        "墨水屏旋转方向",
        options=rot_options,
        index=0 if current_rot == 180 else 1,
        format_func=lambda x: f"{x}° (推荐/外壳倒装)" if x == 180 else f"{x}° (正向)",
        horizontal=True
    )
    if selected_rot != current_rot:
        config.save_epd_rotation(selected_rot)
        st.toast(f"已将墨水屏旋转角度更新为 {selected_rot}°", icon="🔄")
        st.rerun()
    
    st.divider()

    # 菜谱生成模式设置
    st.markdown("#### 🍲 菜谱生成模式")
    current_mode = getattr(config, "RECIPE_MODE", "free")
    if "sidebar_recipe_mode_radio" not in st.session_state:
        st.session_state["sidebar_recipe_mode_radio"] = current_mode
    if "tab_recipe_mode_radio" not in st.session_state:
        st.session_state["tab_recipe_mode_radio"] = current_mode

    mode_options = ["free", "inventory"]
    selected_mode_sidebar = st.radio(
        "默认生成模式",
        options=mode_options,
        index=0 if st.session_state["sidebar_recipe_mode_radio"] == "free" else 1,
        format_func=lambda x: "🌟 自由推荐 (不依赖库存，默认)" if x == "free" else "🧊 结合库存 (优先消耗冰箱食材)",
        key="sidebar_recipe_mode_radio"
    )
    if selected_mode_sidebar != current_mode:
        config.save_recipe_mode(selected_mode_sidebar)
        st.session_state["sidebar_recipe_mode_radio"] = selected_mode_sidebar
        st.session_state["tab_recipe_mode_radio"] = selected_mode_sidebar
        st.toast(f"已将菜谱生成模式更新为：{'🌟 自由推荐模式 (不依赖库存)' if selected_mode_sidebar == 'free' else '🧊 结合库存模式'}", icon="🍲")
        st.rerun()
    
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

tab_menu, tab_cuisine, tab_inventory, tab_favorites = st.tabs([
    "🍽️ 今日食谱 & 墨水屏同步", 
    "🏮 特色菜系点菜",
    "🧊 冰箱食材管理", 
    "❤️ 红心菜谱库"
])

# =========================================================================
# TAB 1: 今日食谱 & 墨水屏同步工作台
# =========================================================================
with tab_menu:
    current_mode = getattr(config, "RECIPE_MODE", "free")
    if "sidebar_recipe_mode_radio" not in st.session_state:
        st.session_state["sidebar_recipe_mode_radio"] = current_mode
    if "tab_recipe_mode_radio" not in st.session_state:
        st.session_state["tab_recipe_mode_radio"] = current_mode

    # 顶部工具栏：日期与菜谱生成模式
    col_date, col_mode = st.columns([2.5, 4.5])
    with col_date:
        today = date.today()
        selected_date = st.date_input("选择日期", value=today)
        date_iso = selected_date.isoformat()
    with col_mode:
        st.markdown("**菜谱生成模式：**")
        selected_mode_tab = st.radio(
            "选择生成模式",
            options=["free", "inventory"],
            index=0 if st.session_state["tab_recipe_mode_radio"] == "free" else 1,
            format_func=lambda x: "🌟 自由推荐模式 (不依赖库存，默认)" if x == "free" else "🧊 结合冰箱库存模式 (优先消耗临期)",
            horizontal=True,
            label_visibility="collapsed",
            key="tab_recipe_mode_radio"
        )
        if selected_mode_tab != current_mode:
            config.save_recipe_mode(selected_mode_tab)
            st.session_state["sidebar_recipe_mode_radio"] = selected_mode_tab
            st.session_state["tab_recipe_mode_radio"] = selected_mode_tab
            st.toast(f"已切换为：{'🌟 自由推荐模式 (不依赖库存)' if selected_mode_tab == 'free' else '🧊 结合冰箱库存模式'}", icon="🍲")
            st.rerun()
        active_mode = selected_mode_tab

    is_free = (active_mode == "free")

    # 读取所选日期的食谱及候选列表
    daily_menu = database.get_daily_menu(date_iso)
    b_recipe = daily_menu.get("breakfast")
    d_recipe = daily_menu.get("dinner")
    b_candidates = daily_menu.get("breakfast_candidates", [])
    d_candidates = daily_menu.get("dinner_candidates", [])

    col_action1, col_action2 = st.columns([1, 1])

    with col_action1:
        btn_label = "✨ 自由智能生成食谱 (早晚各3套候选)" if is_free else "✨ 结合库存智能生成食谱 (早晚各3套候选)"
        spinner_msg = "👩‍🍳 正在自由精选优质食材，规划早晚各 3 套候选方案..." if is_free else "👩‍🍳 正在结合冰箱食材规划早晚各 3 套候选方案..."
        if st.button(btn_label, type="primary", use_container_width=True):
            with st.spinner(spinner_msg):
                plan = llm_service.generate_full_day_options(use_inventory=(not is_free))
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
                    
                database.save_daily_menu_candidates(
                    date_iso, b_ids, d_ids,
                    active_b_id=b_ids[0] if b_ids else None,
                    active_d_id=d_ids[0] if d_ids else None
                )
                toast_msg = "已在自由推荐模式下生成早晚各 3 套候选方案！已默认展示第 1 套。" if is_free else "已结合冰箱食材生成早晚各 3 套候选方案！已默认展示第 1 套。"
                st.toast(toast_msg, icon="🍱")
                st.rerun()

    with col_action2:
        if st.button("📺 手动更新当前展示的菜谱到墨水屏", type="secondary", use_container_width=True):
            if not b_recipe and not d_recipe:
                st.warning("今日尚未安排菜谱，请先生成或选用菜谱。")
            else:
                with st.spinner("正在排版并推送到 800×480 墨水屏..."):
                    success, msg, _ = epd_service.sync_menu_to_screen(daily_menu, selected_date)
                    if success:
                        database.mark_daily_menu_synced(date_iso)
                        st.toast(msg, icon="🎉")
                    else:
                        st.error(msg)
                    st.rerun()

    mode_tip = "当前为【🌟 自由推荐模式 (不依赖库存)】" if is_free else "当前为【🧊 结合冰箱库存模式 (优先消耗临期)】"
    st.caption(f"💡 {mode_tip}。早晚各提供 3 个方案供挑选。点击下方【方案 ① / ② / ③】可实时切换查看；确认后点击上方「手动更新当前展示的菜谱到墨水屏」即可推送到屏幕。每天早晨系统默认自动更新第 1 个方案到墨水屏。")
    st.markdown("---")

    # 左右两栏展示今日早餐与晚餐
    col_b, col_d = st.columns(2)

    # --- 左栏：活力早餐 ---
    with col_b:
        st.markdown('### ☀️ 活力早餐 <span class="badge-breakfast">控时 ≤ 20分钟</span>', unsafe_allow_html=True)
        if b_candidates:
            # 找到当前激活早餐在候选中的索引
            current_b_idx = 0
            is_in_candidates_b = False
            for idx, c in enumerate(b_candidates):
                if b_recipe and c['id'] == b_recipe['id']:
                    current_b_idx = idx
                    is_in_candidates_b = True
                    break
            
            st.markdown("**选择候选方案：**")
            if hasattr(st, "pills"):
                sel_b = st.pills(
                    "选择早餐方案",
                    options=list(range(len(b_candidates))),
                    default=current_b_idx if is_in_candidates_b else 0,
                    format_func=lambda i: f"方案 {i+1} · {b_candidates[i]['title']}",
                    label_visibility="collapsed",
                    key=f"pill_b_{date_iso}"
                )
            else:
                sel_b = st.radio(
                    "选择早餐方案",
                    options=list(range(len(b_candidates))),
                    index=current_b_idx if is_in_candidates_b else 0,
                    format_func=lambda i: f"方案 {i+1} · {b_candidates[i]['title']}",
                    horizontal=True,
                    label_visibility="collapsed",
                    key=f"radio_b_{date_iso}"
                )
                
            if sel_b is not None and (not is_in_candidates_b or sel_b != current_b_idx):
                database.set_active_candidate(date_iso, "breakfast", b_candidates[sel_b]["id"])
                st.rerun()

            if not is_in_candidates_b and b_recipe:
                st.info(f"📌 当前选用了红心收藏菜品：**{b_recipe['title']}**（点击上方方案可随时切回候选方案）")

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
                    st.info(f"💡 **烹饪贴士**：{b_recipe['daughter_notes']}")

                st.markdown("**■ 食材准备**")
                ing_list = b_recipe.get("ingredients", [])
                st.markdown(" • " + "   • ".join(ing_list))

                st.markdown("**■ 极简烹饪 (3步)**")
                for step in b_recipe.get("steps", []):
                    st.markdown(f"- {step}")

                # 早餐重抽 3 套候选 / 从红心库挑选
                st.markdown("---")
                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    reroll_b_label = "🔄 重抽 3 套新早餐 (自由推荐)" if is_free else "🔄 重抽 3 套新早餐 (结合库存)"
                    reroll_b_spin = "正在自由规划 3 道早餐候选..." if is_free else "正在结合冰箱食材重新规划 3 道早餐候选..."
                    if st.button(reroll_b_label, key="reroll_b_3"):
                        with st.spinner(reroll_b_spin):
                            new_b_list = llm_service.generate_meal_options(meal_type="breakfast", count=3, use_inventory=(not is_free))
                            new_b_ids = []
                            for nb in new_b_list:
                                bid = database.save_recipe(
                                    title=nb["title"],
                                    meal_type="breakfast",
                                    nutrition_tag=nb.get("nutrition_tag", ""),
                                    ingredients=nb.get("ingredients", []),
                                    steps=nb.get("steps", []),
                                    prep_time=nb.get("prep_time", "15分钟"),
                                    daughter_notes=nb.get("cooking_tip") or ""
                                )
                                new_b_ids.append(bid)
                            database.update_meal_candidates(date_iso, "breakfast", new_b_ids, active_id=new_b_ids[0])
                            st.toast("已生成 3 套全新早餐方案！", icon="✨")
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
                            database.set_active_candidate(date_iso, "breakfast", chosen["id"])
                            st.rerun()
                    else:
                        st.caption("暂无红心早餐，点红心收藏即可在此快速挑选")
        else:
            st.info("今日尚未安排早餐，请点击上方“智能生成”一键规划 3 套方案。")

    # --- 右栏：营养晚餐 ---
    with col_d:
        st.markdown('### 🌙 营养晚餐 <span class="badge-dinner">荤素全面搭配</span>', unsafe_allow_html=True)
        if d_candidates:
            current_d_idx = 0
            is_in_candidates_d = False
            for idx, c in enumerate(d_candidates):
                if d_recipe and c['id'] == d_recipe['id']:
                    current_d_idx = idx
                    is_in_candidates_d = True
                    break
            
            st.markdown("**选择候选方案：**")
            if hasattr(st, "pills"):
                sel_d = st.pills(
                    "选择晚餐方案",
                    options=list(range(len(d_candidates))),
                    default=current_d_idx if is_in_candidates_d else 0,
                    format_func=lambda i: f"方案 {i+1} · {d_candidates[i]['title']}",
                    label_visibility="collapsed",
                    key=f"pill_d_{date_iso}"
                )
            else:
                sel_d = st.radio(
                    "选择晚餐方案",
                    options=list(range(len(d_candidates))),
                    index=current_d_idx if is_in_candidates_d else 0,
                    format_func=lambda i: f"方案 {i+1} · {d_candidates[i]['title']}",
                    horizontal=True,
                    label_visibility="collapsed",
                    key=f"radio_d_{date_iso}"
                )
                
            if sel_d is not None and (not is_in_candidates_d or sel_d != current_d_idx):
                database.set_active_candidate(date_iso, "dinner", d_candidates[sel_d]["id"])
                st.rerun()

            if not is_in_candidates_d and d_recipe:
                st.info(f"📌 当前选用了红心收藏菜品：**{d_recipe['title']}**（点击上方方案可随时切回候选方案）")

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
                    st.info(f"💡 **烹饪贴士**：{d_recipe['daughter_notes']}")

                st.markdown("**■ 食材准备**")
                ing_list = d_recipe.get("ingredients", [])
                st.markdown(" • " + "   • ".join(ing_list))

                st.markdown("**■ 极简烹饪 (3步)**")
                for step in d_recipe.get("steps", []):
                    st.markdown(f"- {step}")

                # 晚餐重抽 3 套候选 / 从红心库挑选
                st.markdown("---")
                btn_d1, btn_d2 = st.columns(2)
                with btn_d1:
                    reroll_d_label = "🔄 重抽 3 套新晚餐 (自由推荐)" if is_free else "🔄 重抽 3 套新晚餐 (结合库存)"
                    reroll_d_spin = "正在自由规划 3 道晚餐候选..." if is_free else "正在结合冰箱食材重新规划 3 道晚餐候选..."
                    if st.button(reroll_d_label, key="reroll_d_3"):
                        with st.spinner(reroll_d_spin):
                            new_d_list = llm_service.generate_meal_options(meal_type="dinner", count=3, use_inventory=(not is_free))
                            new_d_ids = []
                            for nd in new_d_list:
                                did = database.save_recipe(
                                    title=nd["title"],
                                    meal_type="dinner",
                                    nutrition_tag=nd.get("nutrition_tag", ""),
                                    ingredients=nd.get("ingredients", []),
                                    steps=nd.get("steps", []),
                                    prep_time=nd.get("prep_time", "25分钟"),
                                    daughter_notes=nd.get("cooking_tip") or ""
                                )
                                new_d_ids.append(did)
                            database.update_meal_candidates(date_iso, "dinner", new_d_ids, active_id=new_d_ids[0])
                            st.toast("已生成 3 套全新晚餐方案！", icon="✨")
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
                            database.set_active_candidate(date_iso, "dinner", chosen["id"])
                            st.rerun()
                    else:
                        st.caption("暂无红心晚餐，点红心收藏即可在此快速挑选")
        else:
            st.info("今日尚未安排晚餐，请点击上方“智能生成”一键规划 3 套方案。")

    # --- 墨水屏 800x480 实时渲染预览 ---
    st.markdown("---")
    st.markdown("### 🖥️ 7.5 寸黑白红墨水屏 1:1 同步预览效果")
    
    # 动态渲染当前界面的预览图
    img_prev, _, _ = renderer.render_eink_display(daily_menu, selected_date)
    
    col_prev_t1, col_prev_t2 = st.columns([4, 2])
    with col_prev_t2:
        show_rot = st.checkbox(f"🔄 预览 180° 物理旋转画面", value=False, help="勾选后在手机端查看物理墨水屏实际接收的倒置图层")
        
    display_img = img_prev.rotate(180) if show_rot else img_prev
    caption_text = f"微雪 7.5inch e-Paper (B) V2 (800×480) 渲染预览 {'[物理屏已启用 180° 旋转推送]' if config.EPD_ROTATION == 180 else ''}"
    try:
        st.image(display_img, caption=caption_text, width="stretch")
    except TypeError:
        st.image(display_img, caption=caption_text, use_container_width=True)
    
    synced_at = daily_menu.get("synced_at")
    if synced_at:
        st.caption(f"🕒 上次成功同步到屏幕时间: {synced_at}")

# =========================================================================
# TAB 2: 特色菜系点菜 & 墨水屏同步
# =========================================================================
with tab_cuisine:
    st.markdown("### 🏮 特色菜系点菜定制")
    st.caption("AI 专属大厨定制：探索川、粤、鲁、苏、浙、湘、闽、徽等传统名菜及特色佳肴，支持多道菜品定制与 800×480 墨水屏一键排版同步。")

    # 1. 定制参数配置
    with st.container(border=True):
        col_cui1, col_cui2 = st.columns([3, 2])
        with col_cui1:
            cuisine_presets = [
                "川菜 (麻辣鲜香 · 百菜百味)",
                "粤菜 (清鲜嫩滑 · 原汁原味)",
                "鲁菜 (咸鲜浓郁 · 葱香爆炒)",
                "苏菜 (咸甜适中 · 汤鲜软烂)",
                "浙菜 (清香脆嫩 · 时鲜精细)",
                "湘菜 (香辣酸辣 · 鲜浓开胃)",
                "闽菜 (鲜香脆爽 · 尤重糟香)",
                "徽菜 (原汁原味 · 擅长火腿烧炖)",
                "东北菜 (酱香浓郁 · 爽口实在)",
                "西北风味 (孜然喷香 · 面食牛羊)",
                "自定义菜系/特色风格"
            ]
            selected_preset = st.selectbox("选择目标菜系", options=cuisine_presets, index=0)
            if "自定义" in selected_preset:
                custom_cuisine_input = st.text_input("请输入自定义菜系或风格（如：潮汕风味、云南野生菌、日式家常等）", value="潮汕风味")
                actual_cuisine = custom_cuisine_input.strip() if custom_cuisine_input.strip() else "特色菜系"
            else:
                actual_cuisine = selected_preset.split(" ")[0]

        with col_cui2:
            dish_count_options = [2, 1, 3, 4]
            dish_count = st.selectbox(
                "定制菜品数量",
                options=dish_count_options,
                index=0,
                format_func=lambda x: f"{x} 道菜 (推荐一荤一素组合)" if x == 2 else (f"{x} 道菜 (招牌硬菜精做)" if x == 1 else (f"{x} 道菜 (两菜一汤标准席)" if x == 3 else f"{x} 道菜 (丰盛四菜套餐)"))
            )

        col_pref1, col_pref2 = st.columns([3, 3])
        with col_pref1:
            flavor_preference = st.selectbox(
                "口味偏好要求",
                options=[
                    "经典地道风味 (原汁原味/特色正宗)",
                    "温和微辣/少油少盐 (适合家庭与儿童)",
                    "清淡原汁原味 (少油低脂/轻负担)",
                    "酸辣鲜香浓郁 (超级开胃下饭)"
                ],
                index=0
            )
        with col_pref2:
            custom_dish_req = st.text_input(
                "指定食材或想吃的特定菜名（可选）",
                placeholder="例如：想吃牛肉和豆腐、水煮肉片、或多搭配菌菇等"
            )

        btn_gen_cuisine = st.button("🍳 AI 大厨开始定制菜系菜谱", type="primary", use_container_width=True)

    # 2. 触发生成
    if btn_gen_cuisine:
        with st.spinner(f"👩‍🍳 正在请教名厨，规划 {dish_count} 道地道【{actual_cuisine}】菜谱..."):
            dishes = llm_service.generate_cuisine_dishes(
                cuisine=actual_cuisine,
                count=dish_count,
                preference=flavor_preference,
                custom_prompt=custom_dish_req
            )
            st.session_state["cuisine_dishes"] = dishes
            st.session_state["current_cuisine_name"] = actual_cuisine
            st.toast(f"成功定制 {len(dishes)} 道地道【{actual_cuisine}】菜谱！", icon="🎉")
            st.rerun()

    # 3. 结果展示区
    generated_dishes = st.session_state.get("cuisine_dishes", [])
    active_cuisine_name = st.session_state.get("current_cuisine_name", "经典特色菜")

    if generated_dishes:
        st.markdown(f"#### 🥢 AI 大厨为您呈现：【{active_cuisine_name}】特选佳肴")
        
        # 逐道展示菜品卡片
        for idx, d in enumerate(generated_dishes):
            with st.container(border=True):
                c_head1, c_head2 = st.columns([4, 2])
                with c_head1:
                    st.subheader(f"#{idx+1} · {d.get('title', '特色名菜')}")
                    st.markdown(f"**● 菜系与风味**：`:red[{d.get('cuisine', active_cuisine_name)}]` · `:red[{d.get('nutrition_tag', '风味绝佳')}]` ｜ ⏱️ 预计用时: {d.get('prep_time', '20分钟')}")
                with c_head2:
                    col_btn_f1, col_btn_f2 = st.columns(2)
                    with col_btn_f1:
                        if st.button("❤️ 收藏", key=f"fav_cui_{idx}_{d.get('title')}", use_container_width=True):
                            database.save_recipe(
                                title=d["title"],
                                meal_type="cuisine",
                                nutrition_tag=d.get("nutrition_tag", ""),
                                ingredients=d.get("ingredients", []),
                                steps=d.get("steps", []),
                                prep_time=d.get("prep_time", "20分钟"),
                                is_favorite=1,
                                daughter_notes=f"【{d.get('cuisine', active_cuisine_name)}】{d.get('cooking_tip', '')}"
                            )
                            st.toast(f"已将【{d['title']}】存入红心菜谱库！", icon="❤️")
                    with col_btn_f2:
                        pop_menu = st.popover("🍱 设为今日...")
                        with pop_menu:
                            today_iso = date.today().isoformat()
                            if st.button("设为今日早餐", key=f"set_b_{idx}"):
                                bid = database.save_recipe(
                                    title=d["title"],
                                    meal_type="breakfast",
                                    nutrition_tag=d.get("nutrition_tag", ""),
                                    ingredients=d.get("ingredients", []),
                                    steps=d.get("steps", []),
                                    prep_time=d.get("prep_time", "15分钟"),
                                    is_favorite=0,
                                    daughter_notes=d.get("cooking_tip") or ""
                                )
                                database.set_daily_menu(today_iso, breakfast_id=bid, dinner_id=None)
                                st.toast(f"已将【{d['title']}】设为今日早餐！", icon="☀️")
                                st.rerun()
                            if st.button("设为今日晚餐", key=f"set_d_{idx}"):
                                did = database.save_recipe(
                                    title=d["title"],
                                    meal_type="dinner",
                                    nutrition_tag=d.get("nutrition_tag", ""),
                                    ingredients=d.get("ingredients", []),
                                    steps=d.get("steps", []),
                                    prep_time=d.get("prep_time", "25分钟"),
                                    is_favorite=0,
                                    daughter_notes=d.get("cooking_tip") or ""
                                )
                                database.set_daily_menu(today_iso, breakfast_id=None, dinner_id=did)
                                st.toast(f"已将【{d['title']}】设为今日晚餐！", icon="🌙")
                                st.rerun()

                if d.get("cooking_tip"):
                    st.info(f"💡 **大厨秘诀**：{d['cooking_tip']}")

                st.markdown("**■ 食材用量**")
                ing_list = d.get("ingredients", [])
                st.markdown(" • " + "   • ".join(ing_list))

                st.markdown("**■ 制作步骤 (极简)**")
                for s in d.get("steps", []):
                    st.markdown(f"- {s}")

        st.markdown("---")

        # 4. 墨水屏双栏排版与同步控制区
        st.markdown("### 🖥️ 同步到 7.5 寸黑白红墨水屏")
        st.caption("微雪 7.5寸 墨水屏（800×480）支持同屏并列展示两道菜品。你可以从上方生成的菜谱中任意指定左栏与右栏菜品，并一键推送到墨水屏！")

        dish_titles = [f"{i+1}. {item['title']}" for i, item in enumerate(generated_dishes)]

        col_sel_left, col_sel_right = st.columns(2)
        with col_sel_left:
            idx_left_default = 0
            sel_left_title = st.selectbox("选择【屏幕左栏】展示的菜品", options=dish_titles, index=idx_left_default, key="cui_screen_left")
            selected_left_dish = generated_dishes[dish_titles.index(sel_left_title)]

        with col_sel_right:
            idx_right_default = 1 if len(dish_titles) > 1 else 0
            options_right = ["(自动生成佐餐热汤搭配)"] + dish_titles if len(dish_titles) == 1 else dish_titles
            sel_right_title = st.selectbox(
                "选择【屏幕右栏】展示的菜品",
                options=options_right,
                index=idx_right_default if len(dish_titles) > 1 else 0,
                key="cui_screen_right"
            )
            if sel_right_title.startswith("(自动"):
                selected_right_dish = None
            else:
                selected_right_dish = generated_dishes[dish_titles.index(sel_right_title)]

        # 组装墨水屏所需数据
        cuisine_menu_data = {
            "header_title": f"★ {active_cuisine_name}精选美馔",
            "left_dish": selected_left_dish,
            "right_dish": selected_right_dish,
            "left_label": f"【 {selected_left_dish.get('cuisine', active_cuisine_name)} · 招牌 】",
            "right_label": f"【 {selected_right_dish.get('cuisine', active_cuisine_name) if selected_right_dish else '佐餐建议'} 】"
        }

        # 实时预览渲染图
        cui_img_prev, _, _ = renderer.render_eink_display(cuisine_menu_data, date.today())

        col_btn_sync, col_rot = st.columns([3, 2])
        with col_btn_sync:
            if st.button("📺 立即将所选菜谱推送到 7.5寸 墨水屏", type="primary", use_container_width=True):
                with st.spinner("正在排版并向 7.5寸 墨水屏推送菜系画面..."):
                    success, msg, _ = epd_service.sync_menu_to_screen(cuisine_menu_data, date.today())
                    if success:
                        st.toast(msg, icon="🎉")
                    else:
                        st.error(msg)
                    st.rerun()

        with col_rot:
            show_rot_cui = st.checkbox("🔄 预览 180° 物理旋转画面", value=False, key="cui_rot_preview")

        display_cui_img = cui_img_prev.rotate(180) if show_rot_cui else cui_img_prev
        st.image(display_cui_img, caption="微雪 7.5inch e-Paper (B) V2 墨水屏 1:1 菜系排版预览", use_container_width=True)

    else:
        st.info("💡 欢迎使用特色菜系定制功能！请在上方选择感兴趣的菜系风格（如川菜、粤菜、苏菜等），点击「AI 大厨开始定制菜谱」即可生成丰富做法与墨水屏专属排版。")

# =========================================================================
# TAB 3: 冰箱食材管理
# =========================================================================
with tab_inventory:
    st.markdown("### 🧊 冰箱食材库存清单")
    st.caption("💡 提示：在【结合冰箱库存模式】下，系统生成菜谱时将优先消耗标记为“⚠️需优先消耗”的临期食材；若处于【自由推荐模式】（默认），则不受库存限制自由规划推荐优质菜品。")

    # 1. AI 智能批量导入食材表单
    with st.expander("✨ 智能批量录入食材 (粘贴文本 / AI 自动识别并入库)", expanded=True):
        st.caption("直接粘贴买菜备忘录、语音录音文本、小票清单或一段口述，AI 自动提炼食材名称、类别、数量及临期状态。")
        batch_text = st.text_area(
            "输入食材清单文本",
            placeholder="例如：买了2斤排骨、1盒嫩豆腐、3个西红柿、一把菠菜、一盒鲜牛奶。西红柿快软了需要尽快吃掉...",
            height=90,
            key="batch_ingredient_input"
        )
        col_btn1, _ = st.columns([2, 5])
        with col_btn1:
            if st.button("🤖 AI 智能解析食材", type="primary", use_container_width=True):
                if batch_text.strip():
                    with st.spinner("正在通过 AI 提取并整理食材清单..."):
                        parsed_items = llm_service.parse_ingredients_from_text(batch_text)
                        if parsed_items:
                            st.session_state["parsed_batch_items"] = parsed_items
                            st.toast(f"成功识别到 {len(parsed_items)} 种食材！请在下方核对确认", icon="🔍")
                            st.rerun()
                        else:
                            st.warning("未能从文本中识别出有效食材，请检查输入内容。")
                else:
                    st.warning("请输入包含食材的文本内容。")

        # 若已解析出食材，展示交互式核对表单
        parsed = st.session_state.get("parsed_batch_items")
        if parsed:
            st.markdown("##### 📋 解析结果预览与确认 (支持直接在表格内修改与增删)：")
            import pandas as pd
            df = pd.DataFrame(parsed)
            # 重命名列名以优化显示
            df_display = df.rename(columns={
                "name": "食材名称",
                "category": "类别",
                "quantity": "数量/份量",
                "is_urgent": "优先消耗(临期)"
            })
            edited_df = st.data_editor(
                df_display, 
                use_container_width=True,
                column_config={
                    "类别": st.column_config.SelectboxColumn(
                        "类别",
                        options=["蔬菜瓜果", "肉禽水产", "豆蛋奶制品", "主食干货", "其他"],
                        required=True
                    ),
                    "优先消耗(临期)": st.column_config.CheckboxColumn(
                        "优先消耗(临期)",
                        default=False
                    )
                },
                num_rows="dynamic"
            )
            col_save, col_cancel = st.columns([2, 1])
            with col_save:
                if st.button("📥 确认一键保存入冰箱", type="primary", use_container_width=True):
                    items_to_save = []
                    for _, row in edited_df.iterrows():
                        name_val = str(row.get("食材名称", "")).strip()
                        if not name_val:
                            continue
                        items_to_save.append({
                            "name": name_val,
                            "category": str(row.get("类别", "蔬菜瓜果")).strip(),
                            "quantity": str(row.get("数量/份量", "适量")).strip(),
                            "is_urgent": 1 if row.get("优先消耗(临期)") else 0
                        })
                    cnt = database.batch_add_inventory_items(items_to_save)
                    st.session_state["parsed_batch_items"] = None
                    st.toast(f"已成功将 {cnt} 种食材存入冰箱库存！", icon="🎉")
                    st.rerun()
            with col_cancel:
                if st.button("❌ 放弃导入", use_container_width=True):
                    st.session_state["parsed_batch_items"] = None
                    st.rerun()

    # 2. 单个食材手动录入表单
    with st.expander("➕ 单个食材手动快速添加", expanded=False):
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
# TAB 4: 红心菜谱库
# =========================================================================
with tab_favorites:
    st.markdown("### ❤️ 红心菜谱库")
    st.caption("这里是吃过且特别喜欢的菜品，打红心后永久留存。可一键安排到今日食谱，或写下口味偏好。")

    fav_filter = st.radio("筛选餐别/品类", ["全部", "早餐", "晚餐", "特色菜系"], horizontal=True)
    m_type = "breakfast" if fav_filter == "早餐" else ("dinner" if fav_filter == "晚餐" else ("cuisine" if fav_filter == "特色菜系" else None))
    
    fav_recipes = database.get_recipes(meal_type=m_type, only_favorites=True)

    if fav_recipes:
        for fav in fav_recipes:
            with st.container(border=True):
                f_col1, f_col2 = st.columns([4, 2])
                with f_col1:
                    tag_type = "【早餐】" if fav["meal_type"] == "breakfast" else ("【晚餐】" if fav["meal_type"] == "dinner" else "【特色菜系】")
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
