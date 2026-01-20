import streamlit as st
import pandas as pd
import os
import json
import io
from openai import OpenAI
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential

# --- PAGE SETTINGS ---
st.set_page_config(page_title="Labeling Studio", layout="wide", page_icon="🔥")

PROJECT_FOLDER = "projects"
if not os.path.exists(PROJECT_FOLDER): os.makedirs(PROJECT_FOLDER)

# --- 0. SESSION STATE ---
defaults = {
    "brand": "", "proj": "", "prov": "OpenAI", "mod": "gpt-4o-mini", 
    "res": None, "key": "",
    "p_role": "", "p_inc": "", "p_exc": "", "p_out": ""
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 1. FUNCTIONS ---
@st.cache_data(show_spinner=False)
def load_data(file):
    try:
        if file.name.endswith('.csv'): return pd.read_csv(file)
        elif file.name.endswith('.xlsx'): return pd.read_excel(file)
        elif file.name.endswith('.jsonl'): return pd.read_json(file, lines=True)
        elif file.name.endswith('.json'): return pd.read_json(file)
        return None
    except Exception as e:
        st.error(f"File reading error: {e}")
        return None

def get_project_list():
    if not os.path.exists(PROJECT_FOLDER): return ["➕ New Project"]
    files = [f.replace('.json', '') for f in os.listdir(PROJECT_FOLDER) if f.endswith('.json')]
    return ["➕ New Project"] + files

def save_project(filename, data):
    safe_data = {k: v for k, v in data.items() if k != "key"} 
    with open(os.path.join(PROJECT_FOLDER, filename), 'w', encoding='utf-8') as f:
        json.dump(safe_data, f, ensure_ascii=False, indent=4)

def load_project_data(filename):
    path = os.path.join(PROJECT_FOLDER, filename + ".json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_api_safe(provider, api_key, prompt, model):
    if provider == "OpenAI":
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model, messages=[{"role":"user","content":prompt}], temperature=0, max_tokens=10
        )
        return resp.choices[0].message.content.strip()
    elif provider == "Gemini":
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model)
        return m.generate_content(prompt).text.strip()

def call_api_wrapper(provider, api_key, role, inc, exc, out, text, model):
    full_prompt = f"""
{role}

Relevant if the text includes:
{inc}

Exclude as irrelevant:
{exc}

{out}

Text:
---
{text}
---
"""
    try:
        return call_api_safe(provider, api_key, full_prompt, model)
    except Exception as e:
        return f"ERR: {str(e)[:50]}"

def run_process(df, col, role, inc, exc, out, key, prov, model, workers):
    results = [None] * len(df)
    status = st.status("Analysis Started...", expanded=True)
    p_bar = status.progress(0, text="Preparing...")
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_index = {
            executor.submit(call_api_wrapper, prov, key, role, inc, exc, out, row[col], model): i 
            for i, row in df.iterrows()
        }
        completed = 0
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            results[idx] = future.result()
            completed += 1
            p_bar.progress(completed / len(df), text=f"Processed: {completed}/{len(df)}")
            
    status.update(label="Completed!", state="complete", expanded=False)
    return results

# --- INTERFACE (SIDEBAR) ---
with st.sidebar:
    st.header("Settings")
    sel_proj = st.selectbox("Projects", get_project_list())
    if sel_proj != "New Project":
        if st.button("Load Project", type="primary", use_container_width=True):
            d = load_project_data(sel_proj)
            if d:
                for k, v in d.items(): st.session_state[k] = v
                st.toast(f"Loaded: {sel_proj}")
                st.rerun()

    st.markdown("---")
    prov = st.selectbox("API", ["OpenAI", "Gemini"], key="prov")
    
    current_mod = st.session_state["mod"]
    if prov == "OpenAI" and "gemini" in current_mod: st.session_state["mod"] = "gpt-4o-mini"
    elif prov == "Gemini" and "gpt" in current_mod: st.session_state["mod"] = "gemini-1.5-flash"
    
    model_name = st.text_input("Model", key="mod")
    api_key = st.text_input("API Key", type="password", key="key")
    concurrency = st.slider("Threads", 1, 20, 5)

# --- INTERFACE (MAIN SCREEN) ---
st.title("Labeling Main Screen")

uploaded = st.file_uploader("Dataset (Excel/CSV)", type=["xlsx", "csv", "json", "jsonl"])
df = None
text_column = None

if uploaded:
    df = load_data(uploaded)
    c1, c2 = st.columns([3, 1])
    c1.success(f"Data: {len(df)} Rows")
    text_column = c2.selectbox("Analysis Column", df.columns)
    with st.expander("Show Data"): st.dataframe(df.head())
else:
    st.warning("Please upload a file first.")

st.divider()

# --- PROMPT FORM ---
st.subheader("Prompt Design")

with st.form("main_form"):
    c_meta1, c_meta2 = st.columns(2)
    c_meta1.text_input("Brand Name", key="brand", placeholder="Lipton")
    c_meta2.text_input("Project Save Name", key="proj", placeholder="lipton_analysis_v1")
    
    st.markdown("---")
    
    with st.container(border=True):
        st.markdown("**1️⃣ Role and Intro**")
        st.caption("Define who the AI is here.")
        st.text_area("Role", key="p_role", height=100, label_visibility="collapsed", placeholder="You are an annotator...")

    with st.container(border=True):
        st.markdown("**2️⃣ What is RELEVANT? (Relevant if...)**")
        st.caption("List situations that should be marked as '1'.")
        st.text_area("Include", key="p_inc", height=150, label_visibility="collapsed", placeholder="1) Any consumer experience...")

    with st.container(border=True):
        st.markdown("**3️⃣ What is EXCLUDED? (Exclude as irrelevant...)**")
        st.caption("List situations that should be marked as '0'.")
        st.text_area("Exclude", key="p_exc", height=150, label_visibility="collapsed", placeholder="1) Texts not included...")

    with st.container(border=True):
        st.markdown("**4️⃣ Output Format**")
        st.caption("How should AI respond?")
        st.text_area("Format", key="p_out", height=70, label_visibility="collapsed", placeholder="Respond with ONLY one character...")

    st.markdown("---")
    col_lim, col_save, col_btn = st.columns([1, 1, 2])
    limit = col_lim.number_input("Test Limit (0=All)", 0, value=5)
    save_chk = col_save.checkbox("Save Settings", value=True)
    start = col_btn.form_submit_button("START", type="primary", use_container_width=True)

if start:
    if df is None: st.error("No file!")
    elif not api_key: st.error("No API Key!")
    else:
        if save_chk and st.session_state["proj"]:
            save_data = {k: st.session_state[k] for k in ["brand", "proj", "p_role", "p_inc", "p_exc", "p_out", "prov", "mod"]}
            save_project(st.session_state["proj"] + ".json", save_data)
            st.toast("Settings Saved")

        work_df = df.copy()
        if limit > 0: work_df = work_df.head(limit)
        
        results = run_process(
            work_df, text_column, 
            st.session_state["p_role"], st.session_state["p_inc"], st.session_state["p_exc"], st.session_state["p_out"], 
            api_key, prov, model_name, concurrency
        )
        
        work_df["AI_Response"] = results
        st.session_state["res"] = work_df

# --- ADVANCED RESULTS SCREEN (FILTERING & SEARCH ADDED) ---
if st.session_state["res"] is not None:
    st.divider()
    st.header("Results Control Panel")
    
    # 1. STATISTICS (Data overview)
    df_res = st.session_state["res"]
    try:
        count_1 = df_res[df_res["AI_Response"].astype(str).str.contains("1")].shape[0]
        count_0 = df_res[df_res["AI_Response"].astype(str).str.contains("0")].shape[0]
    except: count_1, count_0 = 0, 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Rows", len(df_res), delta="Dataset")
    m2.metric("Relevant (1)", count_1, delta="Target")
    m3.metric("Irrelevant (0)", count_0, delta_color="inverse")
    
    st.markdown("---")

    # 2. FILTER AND SEARCH AREA
    col_filter, col_search = st.columns([1, 2])
    
    with col_filter:
        filter_opt = st.radio(
            "View Filter:", 
            ["All", "Only Relevant (1)", "Only Irrelevant (0)"], 
            horizontal=True
        )

    with col_search:
        search_term = st.text_input("Search in Data:", placeholder="Type word or phrase...")

    # 3. DATA FILTERING LOGIC
    df_display = df_res.copy()
    
    # Category Filter
    if filter_opt == "Only Relevant (1)":
        df_display = df_display[df_display["AI_Response"].astype(str).str.contains("1", na=False)]
    elif filter_opt == "Only Irrelevant (0)":
        df_display = df_display[df_display["AI_Response"].astype(str).str.contains("0", na=False)]
        
    # Search Filter (Case insensitive)
    if search_term:
        df_display = df_display[df_display[text_column].astype(str).str.contains(search_term, case=False, na=False)]

    st.caption(f"Currently displayed rows: **{len(df_display)}**")

    # 4. EDITOR (Shows filtered data)
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        num_rows="dynamic",
        key="editor",
        column_config={
            text_column: st.column_config.TextColumn("Analyzed Text", disabled=True),
            "AI_Response": st.column_config.TextColumn("llm_prediction", required=True, validate="^[01]$")
        }
    )

    # 5. SAVE and DOWNLOAD
    st.markdown("<br>", unsafe_allow_html=True)
    c_save, c_dl1, c_dl2 = st.columns([1, 1, 1])
    
    # SMART UPDATE BUTTON
    if c_save.button("💾 Apply Filtered Corrections to Main Data", type="secondary", use_container_width=True):
        st.session_state["res"].update(edited_df)
        
        if len(edited_df) < len(df_display):
             deleted_indices = set(df_display.index) - set(edited_df.index)
             st.session_state["res"] = st.session_state["res"].drop(index=list(deleted_indices))
             
        st.toast("Main Database Updated!")
        st.rerun()

    # DOWNLOAD OPERATIONS
    final_df = st.session_state["res"]
    
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as w: final_df.to_excel(w, index=False)
    
    c_dl1.download_button("Download All Data as Excel", out.getvalue(), "result_final.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
    
    json_str = final_df.to_json(orient="records", force_ascii=False, indent=4)
    c_dl2.download_button("Download All Data as JSON", json_str, "result_final.json", "application/json", use_container_width=True)