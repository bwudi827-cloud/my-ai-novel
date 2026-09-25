import streamlit as st
from openai import OpenAI
import json
import time
import random
import datetime
from typing import Dict, Any, Tuple

# ==============================================================================
# 一、 全局配置与数据初始化
# ==============================================================================
st.set_page_config(page_title="AI导演终极工作台", layout="wide", initial_sidebar_state="expanded")
COLOR_PALETTE = ["#FF6B6B", "#FFA502", "#FFD32A", "#2ED573", "#00D2D3", "#1E90FF", "#A29BFE"]
EMOJI_POOL = ["🕵️", "👩‍🎨", "🧔", "👩‍🦰", "👨‍🔬", "👮", "👩‍🏫", "🧙", "🥷", "🤴", "👸", "🧛", "🧟", "🧝", "🧚", "👽", "🤖", "🧑‍🚀", "🥸", "🤠"]

API_PROVIDERS = {
    "DeepSeek (便宜聪明)": {"url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "Groq (免费极速)": {"url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "OpenRouter (免费聚合)": {"url": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "智谱GLM-4-Flash (完全免费)": {"url": "https://open.bigmodel.cn/api/paas/v4/", "model": "glm-4-flash"},
    "Kimi (月之暗面)": {"url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "通义千问 (阿里)": {"url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "ModelScope (魔搭)": {"url": "https://api-inference.modelscope.cn/v1", "model": "qwen-plus"},
    "自定义": {"url": "", "model": ""}
}

RANDOM_EVENTS = [
    "突然，整个房间陷入一片漆黑，停电了。", "一声极其刺耳的巨响从门外传来，像是什么东西砸在了墙上。",
    "你的手机突然震动，屏幕上显示一条匿名短信：『我知道你在哪。』", "窗外划过一道闪电，照亮了角落里一个你不曾注意到的黑影。",
    "空气中弥漫起一股奇怪的焦糊味，像是什么东西烧着了。", "有人重重地敲门，声音急促，带着明显的恐惧。",
    "地面突然开始剧烈震动，桌上的水杯掉在地上摔得粉碎。", "房间里的温度瞬间下降，你呼出的气变成了白雾。"
]

def init_system_state():
    defaults = {
        "projects": {"默认项目": {"worldview": "", "outline": "", "messages": [], "characters": {}, "novel_text": ""}},
        "current_project": "默认项目", "worldview": "", "outline": "", "messages": [], "characters": {},
        "novel_text": "", "user": "导演", "api_key": "", "base_url": "https://api.deepseek.com",
        "model_name": "deepseek-chat", "theme": "默认暗色", "font_size": 16, "current_input": "",
        "style_pool": [], "style_profile": "", "temperature": 0.9,
        "prompt_director": "你是一个导演，正在指挥演员表演。",
        "prompt_character": "请严格遵循你的人设和秘密回应，不要客套，直接输出台词。",
        "prompt_narrator": "第三人称，只写可观察到的动作、神态、对白和环境，绝对不写任何人的内心活动。",
        "custom_quick_commands": ["⚡ 突发事件", "👥 全员会议", "📦 压缩记忆", "🌧️ 下雨", "🌙 深夜"],
        "auto_save_time": "", "current_page": "chat", "pending_chapter": "", "edit_index": None, "edit_text": ""
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value
init_system_state()

def save_current_project():
    st.session_state.projects[st.session_state.current_project] = {
        "worldview": st.session_state.worldview, "outline": st.session_state.outline,
        "messages": st.session_state.messages, "characters": st.session_state.characters,
        "novel_text": st.session_state.novel_text
    }

def load_project(project_name):
    data = st.session_state.projects[project_name]
    st.session_state.current_project = project_name
    st.session_state.worldview = data.get("worldview", ""); st.session_state.outline = data.get("outline", "")
    st.session_state.messages = data.get("messages", []); st.session_state.characters = data.get("characters", {})
    st.session_state.novel_text = data.get("novel_text", "")

def get_ai_client(char_name: str = None) -> Tuple[OpenAI, str]:
    if char_name and char_name in st.session_state.characters:
        char = st.session_state.characters[char_name]
        if char.get('api_key') and char.get('base_url'): return OpenAI(api_key=char['api_key'], base_url=char['base_url']), char.get('model_name', 'deepseek-chat')
    return OpenAI(api_key=st.session_state.get("api_key", ""), base_url=st.session_state.get("base_url", "https://api.deepseek.com")), st.session_state.get("model_name", "deepseek-chat")

def get_char_color(name: str) -> str:
    if not name: return "#FFFFFF"
    names = list(st.session_state.characters.keys())
    return COLOR_PALETTE[names.index(name) % len(COLOR_PALETTE)] if name in names else "#FFFFFF"

def get_char_emoji(name: str) -> str:
    if not name: return "🎭"
    names = list(st.session_state.characters.keys())
    return EMOJI_POOL[names.index(name) % len(EMOJI_POOL)] if name in names else "🎭"

def typewriter_effect(placeholder, text: str, speed: float = 0.015):
    displayed = ""
    for char in text:
        displayed += char
        placeholder.markdown(displayed, unsafe_allow_html=True)
        time.sleep(speed)

def auto_save_snapshot():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.auto_save_time = now
    st.toast(f"💾 系统已自动快照保存于 {now}")

def map_reduce_style_distillation(raw_text: str, style_name: str, client, model: str) -> str:
    chunk_size = 4000
    chunks = [raw_text[i:i+chunk_size] for i in range(0, len(raw_text), chunk_size)]
    progress_text = st.empty(); progress_bar = st.progress(0); all_summaries = []
    for idx, chunk in enumerate(chunks):
        progress_text.text(f"正在分析第 {idx+1}/{len(chunks)} 个片段...")
        prompt = f"请阅读以下小说片段（第 {idx+1} 部分）。提取其叙事视角、语言节奏、人设特质、对话潜台词、爽点/糖点逻辑。只输出 JSON 格式：{{\"outline\": \"本段核心剧情\", \"style_analysis\": \"本段文风剖析\"}}\n片段内容：\n{chunk}"
        try:
            res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.6, response_format={"type": "json_object"})
            data = json.loads(res.choices[0].message.content.strip())
            all_summaries.append({"outline": data.get("outline", ""), "style": data.get("style_analysis", "")})
        except: pass
        progress_bar.progress((idx + 1) / len(chunks))
    progress_text.text("正在合并分析结果，生成最终风格指南...")
    combined_text = "\n".join([f"【片段 {i+1}】剧情：{s['outline']}\n文风：{s['style']}" for i, s in enumerate(all_summaries)])
    final_prompt = f"""你是一位精通网文市场的金牌编辑。请根据以下分块分析报告，提炼并生成一份极度详尽的【{style_name} 写作风格与套路指南】。
必须严格包含以下模块：
# {style_name} 写作风格指南
## 一、 风格定义与核心情绪
## 二、 核心驱动力（拉糖/虐点/升级爽点）
## 三、 叙事视角与信息差
## 四、 语言节奏与标点符号用法
## 五、 对话与潜台词公式
## 六、 人设配置与反差感
## 七、 情节编排与转场公式
## 八、 避坑指南与自检清单
分析报告：\n{combined_text}"""
    try:
        final_res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": final_prompt}], temperature=0.7)
        progress_text.empty(); progress_bar.empty()
        return final_res.choices[0].message.content.strip()
    except Exception as e:
        progress_text.empty(); progress_bar.empty()
        return f"合并失败：{e}"

def inject_theme_css(theme_mode, font_size):
    base_css = f"""<style>p,div,h1,h2,h3,label {{ font-size: {font_size}px !important; }} [data-testid="stChatMessage"] {{ padding: 15px; border-radius: 12px; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }} .stButton>button {{ width: 100%; border-radius: 8px; font-weight: 500; transition: all 0.2s; }} .stButton>button:hover {{ transform: scale(1.02); }}</style>"""
    if theme_mode == "纯黑极简": base_css += "<style>.stApp { background-color: #000; color: #fff; } [data-testid='stChatMessage'] { background-color: #1a1a1a; }</style>"
    elif theme_mode == "护眼浅色": base_css += "<style>.stApp { background-color: #f5f5dc; color: #333; } [data-testid='stChatMessage'] { background-color: #fff; }</style>"
    elif theme_mode == "赛博朋克紫": base_css += "<style>.stApp { background-color: #1a0b2e; color: #00ffff; } [data-testid='stChatMessage'] { background-color: #2d144b; border: 1px solid #00ffff; }</style>"
    else: base_css += "<style>[data-testid='stChatMessage'] { background-color: #262730; }</style>"
    st.markdown(base_css, unsafe_allow_html=True)
inject_theme_css(st.session_state.theme, st.session_state.font_size)

# ==============================================================================
# 二、 侧边栏（全局控制与备份）
# ==============================================================================
with st.sidebar:
    st.title("🎬 导演控制台")
    st.divider()
    st.subheader("🎛️ 导航与刷新")
    page_options = {"💬 导演聊天室": "chat", "📖 小说正文": "novel", "👥 角色管理": "cast", "🔬 风格蒸馏": "tools", "🕸️ 关系网": "relations"}
    selected_page = st.radio("页面切换", list(page_options.keys()), index=list(page_options.values()).index(st.session_state.current_page))
    st.session_state.current_page = page_options[selected_page]
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("↩️ 返回主页", use_container_width=True):
            st.session_state.current_page = "chat"; st.rerun()
    with col_act2:
        if st.button("🔄 安全刷新", use_container_width=True):
            st.toast("💾 数据已保存，正在刷新界面..."); time.sleep(0.5); st.rerun()

    st.divider()
    st.subheader("📂 项目/剧本管理")
    project_list = list(st.session_state.projects.keys())
    selected_proj = st.selectbox("当前剧本", project_list, index=project_list.index(st.session_state.current_project))
    if selected_proj != st.session_state.current_project: save_current_project(); load_project(selected_proj); st.rerun()
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("➕ 新建项目"):
            new_proj_name = f"新项目_{len(project_list)+1}"
            st.session_state.projects[new_proj_name] = {"worldview": "", "outline": "", "messages": [], "characters": {}, "novel_text": ""}
            save_current_project(); load_project(new_proj_name); st.rerun()
    with col_p2:
        if st.button("🗑️ 删除项目"):
            if len(project_list) > 1:
                del st.session_state.projects[st.session_state.current_project]; load_project(list(st.session_state.projects.keys())[0]); st.rerun()
            else: st.warning("至少保留一个项目。")

    st.divider()
    st.subheader("🤖 全局 API 路由")
    provider_name = st.selectbox("默认模型提供者", list(API_PROVIDERS.keys()), key="global_provider")
    st.session_state.api_key = st.text_input("全局 API Key", type="password", value=st.session_state.api_key)
    st.session_state.base_url = st.text_input("API 地址", value=st.session_state.base_url or API_PROVIDERS[provider_name]["url"])
    st.session_state.model_name = st.text_input("模型名称", value=st.session_state.model_name or API_PROVIDERS[provider_name]["model"])
    col_api1, col_api2 = st.columns(2)
    with col_api1:
        if st.button("🔌 测试连接", use_container_width=True):
            with st.spinner("测试中..."):
                try: get_ai_client()[0].models.list(); st.success("✅ 成功！")
                except Exception as e: st.error(f"❌ 失败：{e}")
    with col_api2: st.session_state.temperature = st.slider("🌡️ 温度", 0.0, 1.5, st.session_state.temperature, 0.1)

    st.divider()
    st.subheader("📖 共享剧本设定")
    st.session_state.worldview = st.text_area("世界观", value=st.session_state.worldview, height=80)
    st.session_state.outline = st.text_area("当前章节大纲", value=st.session_state.outline, height=80)

    st.divider()
    st.subheader("⚙️ 自定义快捷指令")
    new_cmd = st.text_input("添加自定义快捷指令")
    if st.button("➕ 添加快捷键"):
        if new_cmd and new_cmd not in st.session_state.custom_quick_commands:
            st.session_state.custom_quick_commands.append(new_cmd); st.rerun()
    if st.session_state.custom_quick_commands: st.caption(f"已有指令：{', '.join(st.session_state.custom_quick_commands[:3])}...")

    st.divider()
    st.subheader("📚 小说资料库 (独立导出)")
    if st.session_state.worldview: st.download_button("⬇️ 下载 世界观.txt", data=st.session_state.worldview.encode("utf-8"), file_name="世界观.txt", mime="text/plain", use_container_width=True)
    if st.session_state.outline: st.download_button("⬇️ 下载 大纲.txt", data=st.session_state.outline.encode("utf-8"), file_name="大纲.txt", mime="text/plain", use_container_width=True)
    if st.session_state.characters:
        char_txt = "========== 人物库与记忆 ==========\n\n"
        for name, char in st.session_state.characters.items():
            char_txt += f"【角色：{name}】\n【类型】{char.get('type', '龙套')}\n【人设】{char.get('persona', '')}\n【秘密】{char.get('secret', '')}\n【记忆】\n{char.get('memory', '')}\n--------------------\n\n"
        st.download_button("⬇️ 下载 人物库(含记忆).txt", data=char_txt.encode("utf-8"), file_name="人物库.txt", mime="text/plain", use_container_width=True)
    if st.session_state.novel_text: st.download_button("⬇️ 下载 小说正文.txt", data=st.session_state.novel_text.encode("utf-8"), file_name="小说正文.txt", mime="text/plain", use_container_width=True)

    st.divider()
    st.subheader("📦 全量备份与恢复")
    sync_ai = st.checkbox("导出时包含 AI 人设与记忆", value=True)
    if st.button("📥 导出 TXT 备份"):
        txt_content = "========== 🎬 AI导演工作台 备份文件 ==========\n\n========== 剧本设定 ==========\n"
        txt_content += f"【世界观】\n{st.session_state.worldview}\n\n【大纲】\n{st.session_state.outline}\n\n"
        if sync_ai:
            txt_content += "========== 角色档案 ==========\n"
            for name, char in st.session_state.characters.items():
                txt_content += f"【角色：{name}】\n【类型】{char.get('type', '龙套')}\n【人设】{char.get('persona', '')}\n【秘密】{char.get('secret', '')}\n【记忆】\n{char.get('memory', '')}\n---\n"
        txt_content += "\n========== 小说正文 ==========\n" + st.session_state.novel_text
        st.download_button("⬇️ 下载 .txt 备份", data=txt_content.encode("utf-8"), file_name="novel_backup.txt", mime="text/plain", use_container_width=True)

    uploaded_txt = st.file_uploader("📤 导入 TXT 备份", type=["txt"], label_visibility="collapsed")
    if uploaded_txt:
        try:
            content = uploaded_txt.read().decode("utf-8")
            if "【世界观】" in content:
                st.session_state.worldview = content.split("【世界观】")[1].split("【大纲】")[0].strip()
                st.session_state.outline = content.split("【大纲】")[1].split("========== 角色档案 ==========")[0].strip() if "========== 角色档案 ==========" in content else content.split("【大纲】")[1].split("========== 小说正文 ==========")[0].strip()
            if "========== 角色档案 ==========" in content and sync_ai:
                char_section = content.split("========== 角色档案 ==========")[1].split("========== 小说正文 ==========")[0]
                for block in char_section.split("---"):
                    if "【角色：" in block:
                        lines = block.strip().split("\n"); name = lines[0].replace("【角色：", "").replace("】", "").strip()
                        char = {"type": "龙套", "persona": "", "secret": "", "memory": "", "is_present": True, "dialogue_count": 0, "api_key": "", "model_name": ""}
                        for i, line in enumerate(lines):
                            if line.startswith("【类型】"): char['type'] = line.replace("【类型】", "").strip()
                            elif line.startswith("【人设】"): char['persona'] = line.replace("【人设】", "").strip()
                            elif line.startswith("【秘密】"): char['secret'] = line.replace("【秘密】", "").strip()
                            elif line.startswith("【记忆】"): char['memory'] = "\n".join(lines[i+1:]).strip()
                        st.session_state.characters[name] = char
            if "========== 小说正文 ==========" in content: st.session_state.novel_text = content.split("========== 小说正文 ==========")[1].strip()
            st.success("✅ TXT 数据解析成功！"); st.rerun()
        except Exception as e: st.error(f"解析失败: {e}")
    uploaded_json = st.file_uploader("📤 导入 JSON 备份", type=["json"], label_visibility="collapsed")
    if uploaded_json:
        try:
            data = json.loads(uploaded_json.read().decode("utf-8"))
            for key in ["worldview", "outline", "characters", "novel_text", "messages", "style_pool", "style_profile"]:
                if key in data: st.session_state[key] = data[key]
            st.success("✅ JSON 数据恢复成功！"); st.rerun()
        except Exception as e: st.error(f"JSON 文件损坏: {e}")
            # ==============================================================================
# 三、 主界面渲染（条件切换代替 Tabs）
# ==============================================================================

# ------------------------------------------------------------------------------
# 页面 1：导演聊天室
# ------------------------------------------------------------------------------
if st.session_state.current_page == "chat":
    if not st.session_state.characters: st.info("👈 请先去【角色管理】创建演员阵容。")
    else:
        st.markdown("### 🎭 演员在线状态（点击切换）")
        cols = st.columns(min(len(st.session_state.characters), 5))
        for idx, (name, char) in enumerate(st.session_state.characters.items()):
            with cols[idx % 5]:
                if st.button(f"{'🟢' if char.get('is_present') else '⚫'} {name}", use_container_width=True):
                    char['is_present'] = not char.get('is_present', True); st.rerun()

        for i, msg in enumerate(st.session_state.messages):
            if msg["role"] == "director":
                with st.chat_message("user", avatar="🎬"): st.markdown(f"**导演**：{msg['content']}")
            else:
                color = get_char_color(msg['name'])
                with st.chat_message("assistant", avatar=get_char_emoji(msg['name'])):
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>{msg['name']}</span>：{msg['content']}", unsafe_allow_html=True)
                    if i == len(st.session_state.messages) - 1:
                        col_edit, col_redo = st.columns([1, 1])
                        with col_edit:
                            if st.button("✏️ 修改这句", key=f"edit_{i}"): st.session_state.edit_index = i; st.session_state.edit_text = msg['content']
                        with col_redo:
                            if st.button("🔄 重说这句", key=f"redo_{i}"): st.session_state.messages.pop(); st.rerun()

        if st.session_state.edit_index is not None:
            with st.form("edit_form"):
                new_text = st.text_area("修改台词", value=st.session_state.edit_text)
                if st.form_submit_button("保存修改"):
                    idx = st.session_state.edit_index; name = st.session_state.messages[idx]['name']
                    st.session_state.messages[idx]['content'] = new_text
                    st.session_state.characters[name]['memory'] += f"\n[导演修改] {new_text}"
                    st.session_state.edit_index = None; st.rerun()

        st.markdown("---")
        st.caption("🎬 快捷指令控制台")
        active_chars = [n for n, c in st.session_state.characters.items() if c.get('is_present')]
        if active_chars:
            c_at = st.columns(min(len(active_chars), 5))
            for idx, name in enumerate(active_chars):
                with c_at[idx % 5]:
                    if st.button(f"@{name}", key=f"at_{name}"): st.session_state.current_input = f"@{name} "; st.rerun()

        c1, c2, c3, c4, c5 = st.columns(5)
        if c1.button("👥 全员会议"): st.session_state.current_input = "所有人都在场，请依次发表意见。"
        if c2.button("⚡ 突发事件"): st.session_state.current_input = random.choice(RANDOM_EVENTS)
        if c3.button("📦 强制压缩"): st.session_state.current_input = "导演指令：执行记忆压缩。"
        if c4.button("↩️ 撤销上一步"):
            if st.session_state.messages:
                st.session_state.messages.pop()
                if st.session_state.messages and st.session_state.messages[-1]["role"] == "director": st.session_state.messages.pop()
                st.rerun()
        with c5:
            with st.expander("💡 剧情推演"):
                if st.button("推演 3 个走向"):
                    if st.session_state.messages:
                        client, model = get_ai_client()
                        res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": f"根据大纲和最近对话，推演 3 个接下来的剧情走向建议。\n大纲：{st.session_state.outline}\n最近对话：{st.session_state.messages[-3:]}"}], temperature=0.9)
                        st.markdown(res.choices[0].message.content.strip())

        if st.session_state.current_input: st.rerun()
        user_input = st.chat_input("输入导演指令（@角色名 呼叫发言，不@人 作为旁白）...")
        if not user_input and st.session_state.current_input: user_input = st.session_state.current_input; st.session_state.current_input = ""
        if user_input:
            st.session_state.messages.append({"role": "director", "name": "导演", "content": user_input})
            with st.chat_message("user", avatar="🎬"): st.markdown(f"**导演**：{user_input}")
            targets = [name for name in st.session_state.characters.keys() if f"@{name}" in user_input]
            if not targets: st.toast("已记录旁白。")
            else:
                for target in targets:
                    char = st.session_state.characters[target]
                    prompt = f"【世界观】{st.session_state.worldview}\n【大纲】{st.session_state.outline}\n【名字】{target}\n【人设】{char.get('persona','')}\n【秘密】{char.get('secret','')}\n【记忆】{char.get('memory','')}\n【最近对话】\n"
                    for m in [x for x in st.session_state.messages if x['role'] != 'director'][-5:]: prompt += f"{m['name']}：{m['content']}\n"
                    prompt += f"\n导演：{user_input}\n{st.session_state.prompt_character}\n请以 JSON 输出：{{\"reply\": \"台词(100字内)\", \"new_memory\": \"记忆(50字内)\"}}"
                    client, model = get_ai_client(target)
                    with st.spinner(f"🎭 {target} 正在思考..."):
                        try:
                            res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=st.session_state.temperature, response_format={"type": "json_object"})
                            data = json.loads(res.choices[0].message.content.strip())
                            reply, new_mem = data.get("reply", "..."), data.get("new_memory", "")
                            with st.chat_message("assistant", avatar=get_char_emoji(target)): typewriter_effect(st.empty(), f"**{target}**：{reply}", 0.015)
                            st.session_state.messages.append({"role": "ai", "name": target, "content": reply})
                            if new_mem: char['memory'] = char.get('memory', '') + f"\n[新记忆] {new_mem}"
                            char['dialogue_count'] = char.get('dialogue_count', 0) + 1
                            if char.get('type') == '龙套' and char['dialogue_count'] >= 2:
                                char['type'] = '配角'; st.toast(f"⭐ 龙套【{target}】升级为配角！")
                            st.rerun()
                        except Exception as e: st.error(f"失败：{e}")

# ------------------------------------------------------------------------------
# 页面 2：小说正文（含章节确认流程）
# ------------------------------------------------------------------------------
elif st.session_state.current_page == "novel":
    st.subheader("📖 小说正文生成（绝对无内心戏）")
    col_nar, col_clr = st.columns([1, 1])
    with col_nar:
        if st.button("✨ 召唤旁白写小说", type="primary", use_container_width=True):
            if st.session_state.messages:
                with st.spinner("叙述者正在写正文..."):
                    style = st.session_state.get("style_profile", "")
                    nar = f"【风格】{style}\n\n" if style else ""
                    nar += f"【世界观】{st.session_state.worldview}\n【大纲】{st.session_state.outline}\n{st.session_state.prompt_narrator}\n"
                    nar += "\n".join([f"{m['name']}：{m['content']}" for m in st.session_state.messages])
                    try:
                        client, model = get_ai_client()
                        res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": nar}], temperature=st.session_state.temperature)
                        st.session_state.pending_chapter = res.choices[0].message.content.strip()
                        st.rerun()
                    except Exception as e: st.error(f"失败: {e}")
    with col_clr:
        if st.button("🗑️ 清空正文", use_container_width=True): st.session_state.novel_text = ""; st.rerun()

    if st.session_state.pending_chapter:
        st.info("📝 新章节已生成！请确认是否满意。")
        col_confirm1, col_confirm2, col_confirm3 = st.columns(3)
        with col_confirm1:
            if st.button("✅ 保存本章到正文", type="primary"):
                st.session_state.novel_text += "\n\n" + st.session_state.pending_chapter
                st.session_state.pending_chapter = ""; st.success("已保存！"); st.rerun()
        with col_confirm2:
            if st.button("🧠 保存正文并存入AI记忆"):
                st.session_state.novel_text += "\n\n" + st.session_state.pending_chapter
                summary_prompt = f"请把以下章节内容压缩成一段80字以内的摘要，用于存入角色的记忆：\n{st.session_state.pending_chapter}"
                try:
                    client, model = get_ai_client()
                    res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": summary_prompt}])
                    summary = res.choices[0].message.content.strip()
                    for name, char in st.session_state.characters.items():
                        if char.get('is_present'): char['memory'] += f"\n[本章记忆] {summary}"
                    st.session_state.pending_chapter = ""; st.success("已保存正文，且摘要已存入AI记忆！"); st.rerun()
                except Exception as e: st.error(f"记忆压缩失败：{e}")
        with col_confirm3:
            if st.button("🔄 重新生成本章"): st.session_state.pending_chapter = ""; st.rerun()
        
        with st.expander("👀 点击预览本章内容", expanded=True): st.markdown(st.session_state.pending_chapter)
    else:
        st.divider()
        st.markdown(st.session_state.novel_text if st.session_state.novel_text else "暂无正文，请点击上方按钮生成。")

# ------------------------------------------------------------------------------
# 页面 3：角色管理
# ------------------------------------------------------------------------------
elif st.session_state.current_page == "cast":
    st.subheader("👥 演员阵容管理")
    col_gen, col_batch = st.columns(2)
    with col_gen:
        st.markdown("**🤖 AI 自动生成阵容**")
        num_chars = st.number_input("生成数量", 1, 5, 3)
        if st.button("根据大纲一键生成角色", use_container_width=True):
            with st.spinner("AI 正在构思人设..."):
                client, model = get_ai_client()
                prompt = f"根据世界观和大致大纲，生成 {num_chars} 个角色。只输出 JSON: {{\"characters\": [{{\"name\": \"\", \"type\": \"主角/配角/龙套\", \"persona\": \"\", \"secret\": \"\"}}]}}\n世界观：{st.session_state.worldview}\n大纲：{st.session_state.outline}"
                try:
                    res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.8, response_format={"type": "json_object"})
                    for c in json.loads(res.choices[0].message.content.strip()).get("characters", []):
                        if c["name"] not in st.session_state.characters:
                            st.session_state.characters[c["name"]] = {"type": c.get("type", "配角"), "persona": c.get("persona", ""), "secret": c.get("secret", ""), "memory": "初始记忆。", "is_present": True, "dialogue_count": 0, "api_key": "", "model_name": ""}
                    st.rerun()
                except Exception as e: st.error(f"生成失败：{e}")
    with col_batch:
        st.markdown("**➕ 手动批量创建**")
        new_names = st.text_input("输入角色名（逗号隔开）", placeholder="林烨,苏婉,胖子")
        if st.button("批量创建角色", use_container_width=True):
            if new_names:
                for name in [n.strip() for n in new_names.split(",")]:
                    if name and name not in st.session_state.characters:
                        st.session_state.characters[name] = {"type": "龙套", "persona": "", "secret": "", "memory": "", "is_present": True, "dialogue_count": 0, "api_key": "", "model_name": ""}
                st.rerun()

    if st.button("🎬 为所有不在场角色生成场外生活"):
        with st.spinner("不在场的角色正在快进生活..."):
            client, model = get_ai_client()
            for name, char in st.session_state.characters.items():
                if not char.get('is_present'):
                    off_prompt = f"你是{name}。你现在不在主线剧情中。请用一句话（30字以内）快速记录你此刻的场外生活，写你正在做什么、想什么。不要推进主线。"
                    try:
                        res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": off_prompt}])
                        off_text = res.choices[0].message.content.strip()
                        char['memory'] += f"\n[场外生活] {off_text}"
                    except: pass
            st.success("✅ 所有不在场角色的场外生活已同步至他们的独立记忆！"); st.rerun()

    st.divider()
    for name, char in list(st.session_state.characters.items()):
        type_icon = "👑" if char.get('type') == "主角" else ("🎩" if char.get('type') == "配角" else "👤")
        with st.expander(f"{type_icon} {name} —— 点击展开详细档案", expanded=False):
            col_type, col_present, col_count = st.columns(3)
            with col_type: char['type'] = st.selectbox("角色定位", ["主角", "配角", "龙套"], index=["主角", "配角", "龙套"].index(char.get('type', '龙套')), key=f"t_{name}")
            with col_present: char['is_present'] = st.checkbox("当前在场（勾选才被调用）", value=char.get('is_present', True), key=f"p_{name}")
            with col_count: char['dialogue_count'] = st.number_input("累积台词句数", value=char.get('dialogue_count', 0), key=f"d_{name}")
            char['persona'] = st.text_area("📝 人物设定", value=char.get('persona', ''), key=f"per_{name}", height=60)
            char['secret'] = st.text_input("🤫 秘密", value=char.get('secret', ''), key=f"sec_{name}")
            char['memory'] = st.text_area("🧠 独立记忆（随时可手动篡改）", value=char.get('memory', ''), key=f"mem_{name}", height=80)
            st.caption("⚙️ 高级选项：独立 API 配置（留空则继承全局）")
            col_key, col_model = st.columns(2)
            with col_key: char['api_key'] = st.text_input("专属 API Key", value=char.get('api_key', ''), type="password", key=f"key_{name}")
            with col_model: char['model_name'] = st.text_input("专属模型名", value=char.get('model_name', ''), key=f"model_{name}")
            if st.button(f"🗑️ 彻底删除角色 {name}", key=f"del_{name}"): del st.session_state.characters[name]; st.rerun()
                # ------------------------------------------------------------------------------
# 页面 4：风格蒸馏与融合
# ------------------------------------------------------------------------------
elif st.session_state.current_page == "tools":
    st.subheader("🔬 风格蒸馏与融合控制台")
    st.markdown(f"### 📚 当前风格库（{len(st.session_state.style_pool)} 种风格）")
    if st.session_state.style_pool:
        for idx, style in enumerate(st.session_state.style_pool):
            with st.expander(f"风格 {idx+1}：{style['name']}"):
                st.markdown(style['content'])
                if st.button(f"删除此风格", key=f"del_style_{idx}"): st.session_state.style_pool.pop(idx); st.rerun()
        if st.button("🗑️ 清空整个风格库"): st.session_state.style_pool = []; st.session_state.style_profile = ""; st.rerun()
    st.divider()
    tool_mode = st.radio("操作类型：", ["🎨 风格蒸馏", "📖 小说拆解"], horizontal=True)
    uploaded_novel = st.file_uploader("📤 上传小说文本 (最大支持 10 万字)", type=["txt"])
    if uploaded_novel is not None:
        try:
            raw_text = uploaded_novel.read().decode("utf-8", errors="ignore")
            st.success(f"📊 文件已读取，总字数约：{len(raw_text)} 字")
            if tool_mode == "🎨 风格蒸馏":
                style_name = st.text_input("给这个风格起个名字", value=f"风格_{len(st.session_state.style_pool)+1}")
                if st.button("✨ 开始深度蒸馏（Map-Reduce引擎）", type="primary"):
                    with st.spinner("AI 正在深度拆解小说写作公式..."):
                        client, model = get_ai_client()
                        final_style_guide = map_reduce_style_distillation(raw_text, style_name, client, model)
                        if final_style_guide:
                            st.session_state.style_pool.append({"name": style_name, "content": final_style_guide})
                            st.success(f"✅ 风格【{style_name}】已完美存入风格库！"); st.rerun()
            elif tool_mode == "📖 小说拆解":
                if st.button("🔍 开始拆解并填入工作台", type="primary"):
                    with st.spinner("AI 正在拆解..."):
                        client, model = get_ai_client()
                        sample_text = raw_text[:6000] 
                        prompt = f"请深度拆解以下小说片段。只输出严格 JSON：{{\"worldview\": \"\", \"characters\": [{{\"name\":\"\",\"persona\":\"\",\"secret\":\"\"}}], \"outline\": \"\"}}\n片段：\n{sample_text}"
                        res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.7, response_format={"type": "json_object"})
                        data = json.loads(res.choices[0].message.content.strip())
                        st.session_state.worldview = data.get("worldview", ""); st.session_state.outline = data.get("outline", "")
                        for c in data.get("characters", []):
                            if c.get("name") and c["name"] not in st.session_state.characters:
                                st.session_state.characters[c["name"]] = {"type": "配角", "persona": c.get("persona", ""), "secret": c.get("secret", ""), "memory": "刚被拆解。", "is_present": True, "dialogue_count": 0, "api_key": "", "model_name": ""}
                        st.rerun()
        except Exception as e: st.error(f"读取失败：{e}")
    if len(st.session_state.style_pool) >= 2:
        if st.button("💥 开始融合所有风格"):
            with st.spinner("融合中..."):
                client, model = get_ai_client()
                pool = "\n\n---\n\n".join([f"【{s['name']}】\n{s['content']}" for s in st.session_state.style_pool])
                res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": f"融合以下风格为一份终极写作指南：\n{pool}"}])
                st.session_state.style_profile = f"【终极融合风格】\n{res.choices[0].message.content.strip()}"
                st.success("✅ 融合成功！已生效。")

# ------------------------------------------------------------------------------
# 页面 5：关系网与系统数据
# ------------------------------------------------------------------------------
elif st.session_state.current_page == "relations":
    st.subheader("🕸️ 角色关系网推演")
    if st.button("🔍 分析当前角色关系", type="primary"):
        if st.session_state.messages:
            with st.spinner("AI 正在推演..."):
                client, model = get_ai_client()
                recent = "\n".join([f"{m['name']}：{m['content']}" for m in st.session_state.messages[-10:]])
                prompt = f"根据对话，分析角色动态关系。输出格式：\n- A --> B : 怀疑\n- B --> C : 信任\n直接输出列表，不要客套。\n对话：\n{recent}"
                res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.7)
                st.markdown("### 📊 当前关系网")
                st.markdown(res.choices[0].message.content.strip())
        else: st.warning("还没有对话记录。")
    
    st.divider()
    st.subheader("📊 系统数据统计")
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    col_stat1.metric("角色总数", len(st.session_state.characters))
    col_stat2.metric("对话条数", len(st.session_state.messages))
    col_stat3.metric("正文字数", len(st.session_state.novel_text))
    st.caption(f"上次自动快照时间：{st.session_state.auto_save_time if st.session_state.auto_save_time else '暂无'}")
    if st.button("💾 立即执行快照保存"): auto_save_snapshot()
        "Aion-3.0 (专为小说优化)": {"url": "https://api.aionlabs.ai/v1", "model": "aion-labs/aion-3.0"},
"Aion-2.0 (专为小说优化)": {"url": "https://api.aionlabs.ai/v1", "model": "aion-labs/aion-2.0"},
"蚂蚁百灵 (长文本优化)": {"url": "https://api.lingyiwanwu.com/v1", "model": "ling-2.6-flash"},
