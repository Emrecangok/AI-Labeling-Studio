import streamlit as st
import pandas as pd
import os
import json
import io
from openai import OpenAI
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Etiketleme Studio", layout="wide", page_icon="🔥")

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

# --- 1. FONKSİYONLAR ---
@st.cache_data(show_spinner=False)
def load_data(file):
    try:
        if file.name.endswith('.csv'): return pd.read_csv(file)
        elif file.name.endswith('.xlsx'): return pd.read_excel(file)
        elif file.name.endswith('.jsonl'): return pd.read_json(file, lines=True)
        elif file.name.endswith('.json'): return pd.read_json(file)
        return None
    except Exception as e:
        st.error(f"Dosya okuma hatası: {e}")
        return None

def get_project_list():
    if not os.path.exists(PROJECT_FOLDER): return ["➕ Yeni Proje"]
    files = [f.replace('.json', '') for f in os.listdir(PROJECT_FOLDER) if f.endswith('.json')]
    return ["➕ Yeni Proje"] + files

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
    status = st.status("Analiz Başladı...", expanded=True)
    p_bar = status.progress(0, text="Hazırlanıyor...")
    
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
            p_bar.progress(completed / len(df), text=f"İşlenen: {completed}/{len(df)}")
            
    status.update(label="Tamamlandı!", state="complete", expanded=False)
    return results

# --- ARAYÜZ (SIDEBAR) ---
with st.sidebar:
    st.header("Ayarlar")
    sel_proj = st.selectbox("Projeler", get_project_list())
    if sel_proj != "Yeni Proje":
        if st.button("Projeyi Yükle", type="primary", use_container_width=True):
            d = load_project_data(sel_proj)
            if d:
                for k, v in d.items(): st.session_state[k] = v
                st.toast(f"Yüklendi: {sel_proj}")
                st.rerun()

    st.markdown("---")
    prov = st.selectbox("API", ["OpenAI", "Gemini"], key="prov")
    
    current_mod = st.session_state["mod"]
    if prov == "OpenAI" and "gemini" in current_mod: st.session_state["mod"] = "gpt-4o-mini"
    elif prov == "Gemini" and "gpt" in current_mod: st.session_state["mod"] = "gemini-1.5-flash"
    
    model_name = st.text_input("Model", key="mod")
    api_key = st.text_input("API Key", type="password", key="key")
    concurrency = st.slider("İş Parçacığı(threads)", 1, 20, 5)

# --- ARAYÜZ (ANA EKRAN) ---
st.title("Etiketleme Ana Ekranı")

uploaded = st.file_uploader("Veri Seti (Excel/CSV)", type=["xlsx", "csv", "json", "jsonl"])
df = None
text_column = None

if uploaded:
    df = load_data(uploaded)
    c1, c2 = st.columns([3, 1])
    c1.success(f"Veri: {len(df)} Satır")
    text_column = c2.selectbox("Analiz Kolonu", df.columns)
    with st.expander("Veriyi Göster"): st.dataframe(df.head())
else:
    st.warning("Lütfen önce dosya yükleyin.")

st.divider()

# --- PROMPT FORMU ---
st.subheader("Prompt Tasarımı")

with st.form("main_form"):
    c_meta1, c_meta2 = st.columns(2)
    c_meta1.text_input("Marka Adı", key="brand", placeholder="Lipton")
    c_meta2.text_input("Proje Kayıt Adı", key="proj", placeholder="lipton_analiz_v1")
    
    st.markdown("---")
    
    with st.container(border=True):
        st.markdown("**1️⃣ Rol ve Giriş (Intro)**")
        st.caption("AI'ın kim olduğunu burada tanımla.")
        st.text_area("Role", key="p_role", height=100, label_visibility="collapsed", placeholder="You are an annotator...")

    with st.container(border=True):
        st.markdown("**2️⃣ Hangi Durumlar İLGİLİDİR? (Relevant if...)**")
        st.caption("Maddeler halinde '1' sayılacak durumları yaz.")
        st.text_area("Include", key="p_inc", height=150, label_visibility="collapsed", placeholder="1) Any consumer experience...")

    with st.container(border=True):
        st.markdown("**3️⃣ Hangi Durumlar HARİÇTİR? (Exclude as irrelevant...)**")
        st.caption("Maddeler halinde '0' sayılacak durumları yaz.")
        st.text_area("Exclude", key="p_exc", height=150, label_visibility="collapsed", placeholder="1) Texts not included...")

    with st.container(border=True):
        st.markdown("**4️⃣ Çıktı Formatı (Output)**")
        st.caption("AI nasıl cevap versin?")
        st.text_area("Format", key="p_out", height=70, label_visibility="collapsed", placeholder="Respond with ONLY one character...")

    st.markdown("---")
    col_lim, col_save, col_btn = st.columns([1, 1, 2])
    limit = col_lim.number_input("Test Limiti (0=Hepsi)", 0, value=5)
    save_chk = col_save.checkbox("Ayarları Kaydet", value=True)
    start = col_btn.form_submit_button("BAŞLAT", type="primary", use_container_width=True)

if start:
    if df is None: st.error("Dosya yok!")
    elif not api_key: st.error("API Key yok!")
    else:
        if save_chk and st.session_state["proj"]:
            save_data = {k: st.session_state[k] for k in ["brand", "proj", "p_role", "p_inc", "p_exc", "p_out", "prov", "mod"]}
            save_project(st.session_state["proj"] + ".json", save_data)
            st.toast("Ayarlar Kaydedildi")

        work_df = df.copy()
        if limit > 0: work_df = work_df.head(limit)
        
        results = run_process(
            work_df, text_column, 
            st.session_state["p_role"], st.session_state["p_inc"], st.session_state["p_exc"], st.session_state["p_out"], 
            api_key, prov, model_name, concurrency
        )
        
        work_df["AI_Response"] = results
        st.session_state["res"] = work_df

# --- GELİŞMİŞ SONUÇ EKRANI (FİLTRELEME & ARAMA EKLENDİ) ---
if st.session_state["res"] is not None:
    st.divider()
    st.header("🕵️‍♂️ Sonuç Kontrol Paneli")
    
    # 1. İSTATİSTİKLER (Veri genel özeti)
    df_res = st.session_state["res"]
    try:
        count_1 = df_res[df_res["AI_Response"].astype(str).str.contains("1")].shape[0]
        count_0 = df_res[df_res["AI_Response"].astype(str).str.contains("0")].shape[0]
    except: count_1, count_0 = 0, 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Toplam Satır", len(df_res), delta="Veri Seti")
    m2.metric("İlgili (1)", count_1, delta="Hedef")
    m3.metric("İlgisiz (0)", count_0, delta_color="inverse")
    
    st.markdown("---")

    # 2. FİLTRE VE ARAMA ALANI (YENİ)
    col_filter, col_search = st.columns([1, 2])
    
    with col_filter:
        filter_opt = st.radio(
            "Görünüm Filtresi:", 
            ["Tümü", "Sadece İlgili (1)", "Sadece İlgisiz (0)"], 
            horizontal=True
        )

    with col_search:
        search_term = st.text_input("Veri İçinde Ara:", placeholder="Kelime veya cümle yaz...")

    # 3. VERİYİ FİLTRELEME MANTIĞI
    # Orijinal verinin kopyası üzerinde işlem yapıyoruz ki asıl veriyi kaybetmeyelim
    df_display = df_res.copy()
    
    # Kategori Filtresi
    if filter_opt == "Sadece İlgili (1)":
        df_display = df_display[df_display["AI_Response"].astype(str).str.contains("1", na=False)]
    elif filter_opt == "Sadece İlgisiz (0)":
        df_display = df_display[df_display["AI_Response"].astype(str).str.contains("0", na=False)]
        
    # Arama Filtresi (Büyük/küçük harf duyarsız)
    if search_term:
        df_display = df_display[df_display[text_column].astype(str).str.contains(search_term, case=False, na=False)]

    st.caption(f"Şu an görüntülenen satır sayısı: **{len(df_display)}**")

    # 4. EDİTÖR (Filtrelenmiş Veriyi Gösterir)
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        num_rows="dynamic",
        key="editor",
        column_config={
            text_column: st.column_config.TextColumn("Analiz Edilen Metin", disabled=True),
            "AI_Response": st.column_config.TextColumn("llm_prediction", required=True, validate="^[01]$")
        }
    )

    # 5. KAYIT ve İNDİRME
    st.markdown("<br>", unsafe_allow_html=True)
    c_save, c_dl1, c_dl2 = st.columns([1, 1, 1])
    
    # AKILLI GÜNCELLEME BUTONU
    if c_save.button("💾 Filtrelenmiş Düzeltmeleri Ana Veriye İşle", type="secondary", use_container_width=True):
        # Pandas'ın update metodu index'leri kullanarak eşleştirme yapar.
        # Filtrelenmiş görünümde yapılan değişiklikleri ana (session_state) verisine aktarır.
        st.session_state["res"].update(edited_df)
        
        # Eğer satır silindiyse (index eşleşmesi yoksa), ana veriden de silmemiz lazım.
        # Bu biraz daha karmaşık ama basit update sadece değişen hücreleri günceller.
        # Tam senkronizasyon için index kontrolü:
        if len(edited_df) < len(df_display): # Eğer filtreli görünümden satır silindiyse
             # Silinen indexleri bul
             deleted_indices = set(df_display.index) - set(edited_df.index)
             # Ana veriden bu indexleri düş
             st.session_state["res"] = st.session_state["res"].drop(index=list(deleted_indices))
             
        st.toast("Ana Veri Tabanı Güncellendi!")
        st.rerun()

    # İNDİRME İŞLEMLERİ (ANA VERİYİ İNDİRİR - SON HALİYLE)
    # İpucu: Kullanıcı filtrelemiş olsa bile "Final" butonları her zaman TÜM verinin son halini indirir.
    final_df = st.session_state["res"]
    
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as w: final_df.to_excel(w, index=False)
    
    c_dl1.download_button("Tüm Veriyi Excel İndir", out.getvalue(), "sonuc_final.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
    
    json_str = final_df.to_json(orient="records", force_ascii=False, indent=4)
    c_dl2.download_button("Tüm Veriyi JSON İndir", json_str, "sonuc_final.json", "application/json", use_container_width=True)