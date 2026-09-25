import os, json
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AI 小说工坊", layout="centered")

# 安全读取API Key（我们在下一步设置里填）
client = OpenAI(
    api_key=st.secrets.get("OPENAI_API_KEY", "缺Key"),
    base_url=st.secrets.get("OPENAI_BASE_URL", "https://api.deepseek.com"),
)

st.title("🎭 AI 小说工坊 (极简版)")
premise = st.text_input("故事前提", "一场暴雨困住了山间旅馆里的四个人，而其中一个人刚刚死了。")

if st.button("开始创作", type="primary"):
    with st.spinner("AI 正在架构世界观..."):
        try:
            r = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": f"根据这个前提写一段300字的世界观和角色设定：{premise}"}]
            )
            st.markdown("### 🌍 世界观与角色")
            st.write(r.choices[0].message.content)
        except Exception as e:
            st.error(f"出错了：{e}，请检查 API Key 是否填对。")
