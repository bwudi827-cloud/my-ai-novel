# -*- coding: utf-8 -*-
"""
AI 小说工坊 · 多智能体剧团版
==============================
一个"多 AI 独立记忆、自动演小说"的互动式写作平台。

用户 = 导演，AI = 演员。
  · 规划 AI   —— 生成世界观、大纲、人物骨架
  · 主角 AI   —— 独立人设、秘密、专属记忆
  · 配角 AI   —— 独立人设与记忆
  · 龙套 AI   —— 无名路人，台词超标自动升级为配角
  · 叙述者 AI —— 把对话与行动剪辑成文学化正文，禁止内心描写

核心机制：
  信息物理隔离 · 场外生活模拟 · 记忆压缩 · @唤醒 · 台词改写
  手动篡改记忆 · 章节确认 · 多项目管理 · 剧情推演 · 命运骰子
  双层 API 路由 · TXT / JSON 双导出
"""

import json
import re
import uuid
from datetime import datetime

import streamlit as st

# ============================================================
# 0. 页面配置
# ============================================================
st.set_page_config(
    page_title="AI 小说工坊",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display: none;}
        .block-container {padding-top: 1rem; padding-bottom: 4rem;}
        [data-testid="stChatMessage"] {padding: 0.5rem 0.2rem;}
        textarea {font-size: 16px !important;}
        .narration {
            color: #888;
            font-style: italic;
            padding: 6px 12px;
            border-left: 3px solid #ccc;
            margin: 6px 0;
        }
        .director {
            color: #b06;
            font-weight: 600;
            padding: 4px 0;
        }
        .chap {
            background: #f5f5f5;
            border-radius: 6px;
            padding: 8px 12px;
            margin: 8px 0;
            font-size: 0.9em;
            color: #666;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 1. 常量池
# ============================================================
COLOR_POOL = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#34495e",
]
EMOJI_POOL = ["🐉", "🦊", "🐺", "🐯", "🦁", "🐸", "🐼", "🦉",
              "🐙", "🦅", "🐍", "🐴", "🦌", "🐳", "🦋", "🐢"]

ROLE_ORDER = ["主角", "配角", "龙套"]
ROLE_TAG = {"主角": "⭐", "配角": "🎗️", "龙套": "👤"}


# ============================================================
# 2. 工具函数
# ============================================================
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def pick_color(existing: list) -> str:
    used = {c.get("color") for c in existing}
    for col in COLOR_POOL:
        if col not in used:
            return col
    return COLOR_POOL[len(existing) % len(COLOR_POOL)]


def pick_emoji(existing: list) -> str:
    used = {c.get("emoji") for c in existing}
    for e in EMOJI_POOL:
        if e not in used:
            return e
    return EMOJI_POOL[len(existing) % len(EMOJI_POOL)]


def get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return default


def count_sentences(text: str) -> int:
    """粗略统计句子数，用于龙套升级判断。"""
    return len([s for s in re.split(r"[。！？!?…]+", text) if s.strip()])


# ============================================================
# 3. 状态初始化
# ============================================================
def new_project(name: str = "新剧本") -> dict:
    return {
        "id": new_id(),
        "name": name,
        "created": now_str(),
        "world": {
            "title": "", "genre": "", "era": "",
            "places": "", "rules": "", "style": "",
        },
        "outline": "",        # 总大纲
        "sub_outline": "",    # 细纲
        "characters": [],     # 角色列表
        "chat": [],           # 聊天流
        "chapter_buffer": [], # 待确认的章节正文
    }


def init_state():
    if "projects" not in st.session_state:
        p = new_project("剧本一")
        st.session_state.projects = {p["id"]: p}
        st.session_state.current_pid = p["id"]

    if "api" not in st.session_state:
        st.session_state.api = {
            "api_key": get_secret("OPENAI_API_KEY", ""),
            "base_url": get_secret("OPENAI_BASE_URL", ""),
            "model": get_secret("OPENAI_MODEL", ""),
            "temperature": 0.85,
        }

    if "last_upload" not in st.session_state:
        st.session_state.last_upload = None

    if "pending_chapter" not in st.session_state:
        st.session_state.pending_chapter = None


init_state()


def P() -> dict:
    """当前项目。"""
    return st.session_state.projects[st.session_state.current_pid]


# ============================================================
# 4. 角色操作
# ============================================================
def add_character(name, role, desc="", secret="", status="存活") -> dict:
    p = P()
    ch = {
        "id": new_id(),
        "name": name,
        "role": role,
        "status": status,
        "desc": desc,
        "secret": secret,
        "memory": [],           # 私有长期记忆
        "offstage": "",         # 场外状态
        "speech_count": 0,      # 累计台词句数（龙套升级用）
        "color": pick_color(p["characters"]),
        "emoji": pick_emoji(p["characters"]),
        "api_override": None,   # 独立 API 配置（双层路由）
    }
    p["characters"].append(ch)
    return ch


def find_char(name: str):
    for c in P()["characters"]:
        if c["name"] == name:
            return c
    return None


def get_char(cid: str):
    for c in P()["characters"]:
        if c["id"] == cid:
            return c
    return None


# ============================================================
# 5. 聊天流操作
# ============================================================
def push_msg(mtype: str, content: str, speaker: str = "", cid: str = ""):
    """mtype: narration / character / director / chapter"""
    P()["chat"].append({
        "type": mtype,
        "speaker": speaker,
        "cid": cid,
        "content": content,
        "ts": now_str(),
    })


# ============================================================
# 6. 信息隔离：构建角色上下文
# ============================================================
def build_character_context(ch: dict) -> str:
    """
    信息隔离核心：
      · 共享：世界观、大纲、公开对话记录
      · 私有：该角色的秘密、私有记忆、场外状态
    """
    p = P()
    w = p["world"]

    parts = [
        f"你正在扮演角色「{ch['name']}」（{ch['role']}）。",
        "严格以该角色的立场、性格、认知发言。",
        "只输出该角色的动作与台词，不要写其他角色的内心。",
        "格式示例：（动作描写）台词内容。",
        "",
    ]

    # 世界观（共享）
    world_lines = []
    for k, label in [("title", "书名"), ("genre", "类型"), ("era", "背景"),
                     ("places", "地点"), ("rules", "规则"), ("style", "文风")]:
        if w.get(k):
            world_lines.append(f"{label}：{w[k]}")
    if world_lines:
        parts.append("===== 世界观 =====")
        parts.extend(world_lines)
        parts.append("")

    if p["outline"]:
        parts.append("===== 总大纲 =====")
        parts.append(p["outline"])
        parts.append("")
    if p["sub_outline"]:
        parts.append("===== 细纲 =====")
        parts.append(p["sub_outline"])
        parts.append("")

    # 该角色的人设与秘密（私有）
    parts.append(f"===== 你（{ch['name']}）的设定 =====")
    parts.append(f"身份：{ch['role']}")
    parts.append(f"状态：{ch.get('status','存活')}")
    if ch.get("desc"):
        parts.append(f"人设：{ch['desc']}")
    if ch.get("secret"):
        parts.append(f"你的秘密（绝不可直接说破）：{ch['secret']}")
    parts.append("")

    # 私有记忆
    if ch.get("memory"):
        parts.append("===== 你的私有记忆 =====")
        parts.extend(f"{i+1}. {m}" for i, m in enumerate(ch["memory"]))
        parts.append("")

    # 场外状态
    if ch.get("offstage"):
        parts.append("===== 你的场外近况 =====")
        parts.append(ch["offstage"])
        parts.append("")

    # 公开对话记录（共享）
    recent = p["chat"][-24:]
    if recent:
        parts.append("===== 公开对话记录 =====")
        for m in recent:
            if m["type"] == "character":
                parts.append(f"{m['speaker']}：{m['content']}")
            elif m["type"] == "director":
                parts.append(f"（导演指令）{m['content']}")
            elif m["type"] == "narration":
                parts.append(f"（旁白）{m['content']}")
        parts.append("")

    parts.append("请以该角色的身份续演，保持人设一致。")
    return "\n".join(parts)


def build_narrator_context() -> str:
    """叙述者 AI：只客观描述，禁止内心描写。"""
    p = P()
    w = p["world"]

    parts = [
        "你是小说旁白与剪辑师。你的任务是把角色的对话与行动，",
        "润色成文学化的小说正文段落。",
        "",
        "铁律：",
        "1. 绝对禁止描写任何角色的内心活动。",
        "   不得出现「他想」「她暗自」「心中一惊」「意识到」这类词。",
        "2. 只客观描述：动作、神态、对白、环境、声音、光影。",
        "3. 保持文风与世界观一致。",
        "4. 只输出正文，不要标题、序号或 Markdown 标记。",
        "",
    ]

    if w.get("style"):
        parts.append(f"文风要求：{w['style']}")
        parts.append("")
    if w.get("places"):
        parts.append(f"场景：{w['places']}")
        parts.append("")

    # 取最近一段对话作为素材
    recent = [m for m in p["chat"][-14:] if m["type"] in ("character", "director", "narration")]
    if recent:
        parts.append("===== 素材 =====")
        for m in recent:
            if m["type"] == "character":
                parts.append(f"{m['speaker']}：{m['content']}")
            elif m["type"] == "director":
                parts.append(f"（导演要求）{m['content']}")
            elif m["type"] == "narration":
                parts.append(f"（已有旁白）{m['content']}")
        parts.append("")
        parts.append("请把以上素材剪辑成一段连贯的小说正文。")

    return "\n".join(parts)


def build_planner_prompt(task: str) -> str:
    """规划 AI：世界观 / 大纲 / 人物骨架。"""
    p = P()
    w = p["world"]
    info = []
    if w.get("title"):
        info.append(f"书名：{w['title']}")
    if w.get("genre"):
        info.append(f"类型：{w['genre']}")
    if w.get("era"):
        info.append(f"背景：{w['era']}")
    if w.get("rules"):
        info.append(f"规则：{w['rules']}")
    if p.get("outline"):
        info.append(f"现有大纲：{p['outline']}")

    return (
        "你是剧本架构师。根据下面已有的设定，完成用户的规划请求。\n"
        "直接输出结果，不要客套话，不要 Markdown 标题符号。\n\n"
        + "\n".join(info)
        + f"\n\n用户的请求：{task}"
    )


# ============================================================
# 7. API 调用（双层路由）
# ============================================================
def get_client(ch: dict = None):
    from openai import OpenAI

    cfg = st.session_state.api
    api_key = cfg["api_key"]
    base_url = cfg["base_url"]
    model = cfg["model"]

    # 独立配置优先
    if ch and ch.get("api_override"):
        ov = ch["api_override"]
        api_key = ov.get("api_key") or api_key
        base_url = ov.get("base_url") or base_url
        model = ov.get("model") or model

    if not api_key:
        raise RuntimeError("未配置 API Key")

    return OpenAI(api_key=api_key, base_url=base_url or None, timeout=180.0), model


def call_ai(system: str, user: str, ch: dict = None, temperature=None) -> str:
    client, model = get_client(ch)
    temp = temperature if temperature is not None else float(
        st.session_state.api["temperature"]
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temp,
        max_tokens=1600,
    )
    return resp.choices[0].message.content


# ============================================================
# 8. 核心生成：角色发言 / 旁白
# ============================================================
def generate_speech(ch: dict, instruction: str) -> str:
    """让某个角色说台词、做动作。"""
    system = build_character_context(ch)
    user = instruction.strip() or "请自然接续当前场景，说一句台词并做一个动作。"
    return call_ai(system, user, ch=ch)


def generate_narration() -> str:
    system = build_narrator_context()
    user = "请生成旁白正文。"
    return call_ai(system, user, temperature=0.6)


# ============================================================
# 9. 龙套升级机制
# ============================================================
def check_rookie_upgrade(ch: dict):
    """龙套台词超过两句话，自动升级为配角并建档。"""
    if ch.get("role") != "龙套":
        return False
    if ch.get("speech_count", 0) >= 3:
        ch["role"] = "配角"
        # 自动生成人设与秘密
        if not ch.get("desc"):
            try:
                sys = (
                    f"根据下列小说片段，为临时角色「{ch['name']}」补一份简短人设：\n"
                    "一段 40 字内的性格 / 外貌描述，以及一句 30 字内的秘密。\n"
                    "输出格式：\n人设：xxx\n秘密：xxx"
                )
                snippet = "\n".join(
                    m["content"] for m in P()["chat"][-8:]
                    if m.get("cid") == ch["id"]
                )[:1200]
                raw = call_ai(sys, snippet or ch["name"])
                for line in raw.splitlines():
                    if line.startswith("人设："):
                        ch["desc"] = line.replace("人设：", "").strip()
                    elif line.startswith("秘密："):
                        ch["secret"] = line.replace("秘密：", "").strip()
            except Exception:
                pass
        push_msg("narration", f"※「{ch['name']}」的戏份增多，已正式建档为配角。")
        return True
    return False


# ============================================================
# 10. 记忆压缩
# ============================================================
def compress_memory():
    """把聊天流前段浓缩成摘要，存入相关角色的私有记忆。"""
    p = P()
    if len(p["chat"]) < 6:
        return False, "对话太短，无需压缩。"

    transcript = "\n".join(
        f"{m['speaker'] or '旁白'}：{m['content']}" if m["type"] == "character"
        else f"（{m['type']}）{m['content']}"
        for m in p["chat"]
    )[-12000:]

    sys = (
        "把下面这份剧本对话压缩成 5～8 条要点，按时间顺序，"
        "每条一句话，保留关键情节、人物状态变化与伏笔。"
        "每行输出一条，不要编号以外的多余文字。"
    )
    try:
        raw = call_ai(sys, transcript, temperature=0.3)
        lines = [ln.strip().lstrip("0123456789.、-· ") for ln in raw.splitlines() if ln.strip()]
        lines = [ln for ln in lines if len(ln) > 3][:8]
    except Exception as e:
        return False, f"压缩失败：{e}"

    # 存入所有主要角色的私有记忆
    for ch in p["characters"]:
        if ch["role"] in ("主角", "配角"):
            ch["memory"] = (ch["memory"] + lines)[-20:]

    # 保留最近 4 条聊天，其余清空（防止上下文过长）
    p["chat"] = p["chat"][-4:]
    push_msg("narration", f"※ 剧情已压缩为 {len(lines)} 条长期记忆。")
    return True, f"已生成 {len(lines)} 条记忆并写入各角色。"


# ============================================================
# 11. 剧情推演 & 命运骰子
# ============================================================
def plot_suggestions() -> str:
    p = P()
    recent = "\n".join(
        f"{m['speaker']}：{m['content']}" if m["type"] == "character"
        else f"（{m['type']}）{m['content']}"
        for m in p["chat"][-10:]
    )
    sys = "你是编剧。根据当前剧情，给出 3 个接下来可选的走向，每个 50 字内，用数字 1/2/3 开头。"
    return call_ai(sys, recent or "故事刚开始。", temperature=1.0)


def roll_dice() -> str:
    p = P()
    recent = "\n".join(
        m["content"] for m in p["chat"][-6:] if m["type"] in ("character", "narration")
    )
    sys = (
        "你是导演助手。根据当前剧情，随机丢出一个突发事件（如停电、巨响、匿名短信、"
        "陌生人闯入、天气骤变等），要求：\n"
        "1. 一句话描述事件本身；\n"
        "2. 一句话说明它如何打乱当前局面；\n"
        "3. 不要替角色做决定。"
    )
    return call_ai(sys, recent or "场景尚未开始。", temperature=1.2)


# ============================================================
# 12. 导出 / 导入
# ============================================================
def export_txt(kind: str) -> str:
    p = P()
    w = p["world"]
    if kind == "world":
        lines = [f"《{w.get('title','')}》", ""]
        for k, label in [("genre", "类型"), ("era", "背景"),
                         ("places", "地点"), ("rules", "规则"), ("style", "文风")]:
            if w.get(k):
                lines.append(f"{label}：{w[k]}")
        if p["outline"]:
            lines += ["", "【总大纲】", p["outline"]]
        if p["sub_outline"]:
            lines += ["", "【细纲】", p["sub_outline"]]
        return "\n".join(lines)

    if kind == "cast":
        lines = []
        for ch in p["characters"]:
            lines.append(f"{ROLE_TAG[ch['role']]} {ch['name']}（{ch['role']}·{ch.get('status','')}）")
            if ch.get("desc"):
                lines.append(f"  人设：{ch['desc']}")
            if ch.get("secret"):
                lines.append(f"  秘密：{ch['secret']}")
            if ch.get("memory"):
                lines.append("  记忆：")
                lines.extend(f"    - {m}" for m in ch["memory"])
            lines.append("")
        return "\n".join(lines) or "（暂无角色）"

    if kind == "novel":
        lines = [f"《{w.get('title','')}》", ""]
        for m in p["chat"]:
            if m["type"] == "character":
                lines.append(f"{m['speaker']}：{m['content']}")
            elif m["type"] == "narration":
                lines.append(m["content"])
            elif m["type"] == "chapter":
                lines.append(m["content"])
            lines.append("")
        return "\n".join(lines)

    return ""


def full_backup() -> dict:
    return {
        "version": 2,
        "exported_at": now_str(),
        "projects": st.session_state.projects,
        "current_pid": st.session_state.current_pid,
    }


# ============================================================
# 13. 侧边栏
# ============================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🎬 项目")

        # 切换项目
        pids = list(st.session_state.projects.keys())
        names = [st.session_state.projects[i]["name"] for i in pids]
        cur_idx = pids.index(st.session_state.current_pid)
        sel = st.selectbox("当前剧本", range(len(pids)),
                           format_func=lambda i: names[i], index=cur_idx)
        if pids[sel] != st.session_state.current_pid:
            st.session_state.current_pid = pids[sel]
            st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("＋ 新建", use_container_width=True):
                np_ = new_project(f"剧本{len(pids)+1}")
                st.session_state.projects[np_["id"]] = np_
                st.session_state.current_pid = np_["id"]
                st.rerun()
        with c2:
            if st.button("🗑 删除", use_container_width=True) and len(pids) > 1:
                del st.session_state.projects[st.session_state.current_pid]
                st.session_state.current_pid = list(st.session_state.projects.keys())[0]
                st.rerun()

        P()["name"] = st.text_input("剧本名称", P()["name"])

        st.divider()

        # ---------------- API 配置 ----------------
        st.markdown("## 🔌 接口")
        cfg = st.session_state.api
        cfg["api_key"] = st.text_input("API Key", cfg["api_key"], type="password")
        cfg["base_url"] = st.text_input("Base URL", cfg["base_url"])
        cfg["model"] = st.text_input("模型", cfg["model"])
        cfg["temperature"] = st.slider("创造力", 0.0, 1.5, float(cfg["temperature"]), 0.05)

        st.caption("以上为全局配置，所有 AI 默认使用。个别角色可在「剧组」单独配置。")

        st.divider()

        # ---------------- 工具 ----------------
        st.markdown("## 🛠 工具")

        if st.button("🎲 命运骰子", use_container_width=True):
            with st.spinner("投掷中…"):
                try:
                    ev = roll_dice()
                    push_msg("director", f"【突发事件】{ev}")
                    st.rerun()
                except Exception as e:
                    st.error(f"失败：{e}")

        if st.button("💡 剧情推演", use_container_width=True):
            with st.spinner("推演中…"):
                try:
                    sug = plot_suggestions()
                    push_msg("director", f"【剧情推演】\n{sug}")
                    st.rerun()
                except Exception as e:
                    st.error(f"失败：{e}")

        if st.button("🗜 压缩记忆", use_container_width=True):
            ok, msg = compress_memory()
            (st.success if ok else st.warning)(msg)
            if ok:
                st.rerun()

        st.divider()

        # ---------------- 导出 ----------------
        st.markdown("## 💾 导出")
        for label, kind in [("世界观 TXT", "world"), ("人物库 TXT", "cast"), ("小说正文 TXT", "novel")]:
            st.download_button(
                label,
                data=export_txt(kind),
                file_name=f"{P()['name']}_{kind}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        st.download_button(
            "全量 JSON 备份",
            data=json.dumps(full_backup(), ensure_ascii=False, indent=2),
            file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True,
        )

        up = st.file_uploader("导入 JSON 备份", type=["json"])
        if up is not None:
            tag = f"{up.name}_{up.size}"
            if st.session_state.last_upload != tag:
                try:
                    data = json.load(up)
                    if "projects" in data:
                        st.session_state.projects = data["projects"]
                        st.session_state.current_pid = data.get(
                            "current_pid", list(data["projects"].keys())[0]
                        )
                    st.session_state.last_upload = tag
                    st.success("已恢复备份")
                    st.rerun()
                except Exception as e:
                    st.error(f"导入失败：{e}")

        st.divider()
        st.caption(
            f"项目 {len(st.session_state.projects)} · "
            f"角色 {len(P()['characters'])} · "
            f"消息 {len(P()['chat'])}"
        )


# ============================================================
# 14. 剧组管理
# ============================================================
def render_cast_tab():
    st.subheader("🎭 剧组")
    st.caption("人物设定进入各自的信息隔离上下文。龙套台词超标将自动升级。")

    p = P()
    for role in ROLE_ORDER:
        group = [(i, c) for i, c in enumerate(p["characters"]) if c.get("role") == role]
        if not group:
            continue
        st.markdown(f"### {ROLE_TAG[role]} {role}（{len(group)}）")
        for i, ch in group:
            with st.expander(f"{ch['emoji']} {ch['name']}", expanded=False):
                ch["name"] = st.text_input("姓名", ch["name"], key=f"n_{ch['id']}")
                c1, c2 = st.columns(2)
                with c1:
                    ch["role"] = st.selectbox("定位", ROLE_ORDER,
                        index=ROLE_ORDER.index(ch["role"]), key=f"r_{ch['id']}")
                with c2:
                    ch["status"] = st.text_input("状态", ch.get("status", ""), key=f"st_{ch['id']}")

                ch["desc"] = st.text_area("人设", ch.get("desc", ""), height=80, key=f"d_{ch['id']}")
                ch["secret"] = st.text_area("秘密", ch.get("secret", ""), height=60, key=f"sc_{ch['id']}")
                ch["offstage"] = st.text_input("场外状态", ch.get("offstage", ""), key=f"of_{ch['id']}",
                    placeholder="不在场时他在做什么")

                # 私有记忆
                with st.popover("查看 / 修改私有记忆"):
                    mem_text = st.text_area(
                        "每行一条",
                        "\n".join(ch.get("memory", [])),
                        height=140,
                        key=f"mem_{ch['id']}",
                    )
                    if st.button("保存记忆", key=f"sm_{ch['id']}"):
                        ch["memory"] = [ln.strip() for ln in mem_text.splitlines() if ln.strip()]
                        st.success("已保存")
                        st.rerun()

                # 独立 API 配置（双层路由）
                with st.popover("独立模型配置（可选）"):
                    ov = ch.get("api_override") or {}
                    k = st.text_input("Key", ov.get("api_key", ""), type="password", key=f"ak_{ch['id']}")
                    b = st.text_input("Base URL", ov.get("base_url", ""), key=f"ab_{ch['id']}")
                    m = st.text_input("模型", ov.get("model", ""), key=f"am_{ch['id']}")
                    c1, c2 = st.columns(2)
                    if c1.button("保存", key=f"sv_{ch['id']}"):
                        ch["api_override"] = {"api_key": k, "base_url": b, "model": m} if (k or b or m) else None
                        st.success("已保存")
                    if c2.button("清除", key=f"cl_{ch['id']}"):
                        ch["api_override"] = None
                        st.rerun()

                b1, b2 = st.columns(2)
                if role == "龙套" and b1.button("升级为配角", key=f"up_{ch['id']}", use_container_width=True):
                    ch["role"] = "配角"
                    st.rerun()
                elif role == "配角" and b1.button("升级为主角", key=f"up_{ch['id']}", use_container_width=True):
                    ch["role"] = "主角"
                    st.rerun()
                if b2.button("删除", key=f"del_{ch['id']}", use_container_width=True):
                    p["characters"].pop(i)
                    st.rerun()

    st.divider()
    st.markdown("### ➕ 添加角色")
    with st.form("add_char", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        name = c1.text_input("姓名")
        role = c2.selectbox("定位", ROLE_ORDER, index=2)
        status = c3.text_input("状态", "存活")
        desc = st.text_area("人设", height=70)
        secret = st.text_area("秘密", height=60)
        if st.form_submit_button("添加", use_container_width=True):
            if name.strip():
                add_character(name.strip(), role, desc, secret, status)
                st.rerun()
            else:
                st.warning("姓名不能为空")


# ============================================================
# 15. 世界观 & 大纲
# ============================================================
def render_world_tab():
    st.subheader("🌍 世界观与大纲")
    p = P()
    w = p["world"]

    c1, c2 = st.columns(2)
    w["title"] = c1.text_input("书名", w.get("title", ""))
    w["genre"] = c2.text_input("类型", w.get("genre", ""))
    c3, c4 = st.columns(2)
    w["era"] = c3.text_input("背景", w.get("era", ""))
    w["places"] = c4.text_input("地点", w.get("places", ""))
    w["rules"] = st.text_area("规则", w.get("rules", ""), height=100)
    w["style"] = st.text_area("文风", w.get("style", ""), height=70)

    st.divider()
    st.markdown("### 📐 大纲")

    with st.form("plan_form"):
        task = st.text_area(
            "让规划 AI 帮你生成或补充大纲",
            height=80,
            placeholder="例：生成一个三幕式的故事大纲，主角是失忆的刺客。",
        )
        if st.form_submit_button("✨ 生成", use_container_width=True, type="primary"):
            if task.strip():
                with st.spinner("规划 AI 思考中…"):
                    try:
                        out = call_ai(build_planner_prompt(task), task)
                        p["outline"] = (p["outline"] + "\n" + out).strip()
                        st.rerun()
                    except Exception as e:
                        st.error(f"失败：{e}")

    p["outline"] = st.text_area("总大纲", p.get("outline", ""), height=160, key="outline_edit")
    p["sub_outline"] = st.text_area("细纲", p.get("sub_outline", ""), height=120, key="sub_edit")

    with st.expander("🔍 当前角色的信息隔离上下文预览"):
        if p["characters"]:
            sel = st.selectbox("查看角色", [c["name"] for c in p["characters"]], key="ctx_sel")
            ch = find_char(sel)
            if ch:
                st.code(build_character_context(ch), language="text")
        else:
            st.info("暂无角色。")


# ============================================================
# 16. 写作台（聊天流）
# ============================================================
def render_write_tab():
    p = P()

    if not p["chat"]:
        st.info(
            "**导演，可以开拍了。**\n\n"
            "· 在下方输入框 **@角色名** 唤醒对应 AI 发言；\n"
            "· 不 @ 人时，你输入的内容会作为**导演指令**记录；\n"
            "· 点侧边栏的「命运骰子」「剧情推演」可以搅动剧情；\n"
            "· 卡文时点「🗜 压缩记忆」，把前情凝练成长期记忆。"
        )

    # 渲染聊天流
    for idx, m in enumerate(p["chat"]):
        if m["type"] == "character":
            ch = get_char(m.get("cid", ""))
            color = ch["color"] if ch else "#333"
            emoji = ch["emoji"] if ch else "🎭"
            with st.chat_message("assistant"):
                st.markdown(
                    f"<span style='color:{color};font-weight:700'>{emoji} {m['speaker']}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(m["content"])
                # 改写台词
                if st.button("✏️ 改写", key=f"edit_{idx}"):
                    st.session_state[f"editing_{idx}"] = True
                if st.session_state.get(f"editing_{idx}"):
                    new = st.text_area("修改台词", m["content"], key=f"ta_{idx}", height=100)
                    if st.button("保存修改", key=f"save_{idx}"):
                        m["content"] = new
                        # 同步写入角色私有记忆
                        if ch:
                            ch["memory"] = (ch["memory"] + [f"我（{ch['name']}）说：{new[:60]}..."])[-20:]
                        st.session_state[f"editing_{idx}"] = False
                        st.rerun()
        elif m["type"] == "narration":
            st.markdown(f"<div class='narration'>📖 {m['content']}</div>", unsafe_allow_html=True)
        elif m["type"] == "director":
            st.markdown(f"<div class='director'>🎬 导演：{m['content']}</div>", unsafe_allow_html=True)
        elif m["type"] == "chapter":
            st.markdown(f"<div class='chap'>📄 正文：<br>{m['content']}</div>", unsafe_allow_html=True)

    st.divider()

    # 快捷指令栏
    if p["characters"]:
        st.caption("快捷 @ 唤醒：")
        cols = st.columns(min(len(p["characters"]), 5))
        for i, ch in enumerate(p["characters"][:5]):
            if cols[i].button(f"{ch['emoji']} {ch['name']}", key=f"quick_{ch['id']}", use_container_width=True):
                st.session_state.quick_input = f"@{ch['name']} "

    # 输入框
    default_text = st.session_state.pop("quick_input", "")
    with st.form("write_form", clear_on_submit=True):
        text = st.text_area(
            "输入",
            value=default_text,
            height=90,
            placeholder="@角色名 说点什么，或写下导演指令…",
            label_visibility="collapsed",
        )
        c1, c2, c3 = st.columns([2, 1, 1])
        go = c1.form_submit_button("▶ 发送", use_container_width=True, type="primary")
        do_narr = c2.form_submit_button("📖 让旁白剪辑", use_container_width=True)
        do_clear = c3.form_submit_button("🧹 清空", use_container_width=True)

    if do_clear:
        p["chat"] = []
        st.rerun()

    if do_narr:
        if not st.session_state.api["api_key"]:
            st.error("请先配置 API Key。")
        else:
            with st.spinner("叙述者剪辑中…"):
                try:
                    out = generate_narration()
                    push_msg("narration", out)
                    st.rerun()
                except Exception as e:
                    st.error(f"失败：{e}")

    if go and text.strip():
        handle_input(text.strip())


def handle_input(text: str):
    """处理导演输入：解析 @角色，唤醒对应 AI。"""
    p = P()
    if not st.session_state.api["api_key"]:
        st.error("请先在侧边栏配置 API Key。")
        return

    # 解析 @
    mentioned = re.findall(r"@([^\s@，,。！？!?]+)", text)
    targets = []
    for name in mentioned:
        ch = find_char(name)
        if ch and ch not in targets:
            targets.append(ch)

    if not targets:
        push_msg("director", text)
        st.rerun()
        return

    # 先记录导演的指令
    push_msg("director", text)

    # 依次唤醒（无状态框架下无法并行）
    for ch in targets:
        with st.spinner(f"{ch['name']} 正在表演…"):
            try:
                instruction = text
                out = generate_speech(ch, instruction)
                push_msg("character", out, speaker=ch["name"], cid=ch["id"])

                # 台词计数（龙套升级）
                ch["speech_count"] = ch.get("speech_count", 0) + count_sentences(out)
                check_rookie_upgrade(ch)
            except Exception as e:
                st.error(f"{ch['name']} 生成失败：{e}")

    st.rerun()


# ============================================================
# 17. 章节确认
# ============================================================
def render_chapter_bar():
    """当有新的角色发言时，提供"整章成文"的入口。"""
    p = P()
    if len(p["chat"]) < 3:
        return

    # 用 popover 收进侧边，避免干扰
    with st.sidebar:
        st.divider()
        st.markdown("## 📄 章节")
        if st.button("把当前对话剪辑成章", use_container_width=True):
            with st.spinner("叙述者剪辑中…"):
                try:
                    out = generate_narration()
                    st.session_state.pending_chapter = out
                except Exception as e:
                    st.error(f"失败：{e}")

        if st.session_state.pending_chapter:
            st.text_area("预览", st.session_state.pending_chapter, height=200, key="ch_prev")
            c1, c2, c3 = st.columns(3)
            if c1.button("保存", use_container_width=True):
                push_msg("chapter", st.session_state.pending_chapter)
                st.session_state.pending_chapter = None
                st.rerun()
            if c2.button("存记忆", use_container_width=True):
                for ch in p["characters"]:
                    if ch["role"] in ("主角", "配角"):
                        ch["memory"] = (ch["memory"] + [st.session_state.pending_chapter[:120]])[-20:]
                st.success("已写入各角色私有记忆")
            if c3.button("重写", use_container_width=True):
                st.session_state.pending_chapter = None
                st.rerun()


# ============================================================
# 18. 主界面
# ============================================================
render_sidebar()

# 顶部标题
head_l, head_r = st.columns([3, 1])
with head_l:
    title = P()["world"].get("title") or P()["name"]
    st.markdown(f"## 🎬 {title}")
with head_r:
    st.caption(
        f"角色 {len(P()['characters'])} · 消息 {len(P()['chat'])}"
    )

tab_write, tab_cast, tab_world = st.tabs(["✍️ 写作台", "🎭 剧组", "🌍 世界观"])

with tab_write:
    render_write_tab()

with tab_cast:
    render_cast_tab()

with tab_world:
    render_world_tab()

render_chapter_bar()
