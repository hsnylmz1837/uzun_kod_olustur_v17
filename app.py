
import io, re, os, math
import pandas as pd
import numpy as np
import streamlit as st
import qrcode

st.set_page_config(page_title="Uzun Kod — v17 / Live", page_icon="🧩", layout="wide", initial_sidebar_state="collapsed")

# ==== Styles ====
st.markdown("""
<style>
[data-testid="stSidebar"]{display:none!important;}
[data-testid="collapsedControl"]{display:none!important;}
.block-container{padding-top:1.0rem;padding-bottom:2rem;}
.panel{background:#0f172a;color:#e5e7eb;padding:18px;border-radius:14px;border:1px solid #1f2937;box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02);margin-bottom:14px;}
.token{display:inline-block;background:#111827;border:1px solid #334155;color:#e5e7eb;padding:4px 8px;border-radius:999px;margin:2px;font-size:0.85rem;}
.token.new{background:#065f46;border-color:#064e3b;color:#ecfdf5;}
.stepbtns div[data-testid="column"] .stButton>button{width:100%;height:120px;padding:12px 16px;font-size:28px;font-weight:700;border-radius:18px;border:1px solid #334155;background:#0b1220;color:#e5e7eb;}
.stepbtns div[data-testid="column"] .stButton>button:hover{border-color:#22c55e;box-shadow:0 0 0 2px rgba(34,197,94,0.25) inset;}
</style>
""", unsafe_allow_html=True)

left, right = st.columns([6,1])
with left:
    st.title("Uzun Kod Oluşturma Programı - v17 / Statik")
    st.caption("Seçtikçe uzun kod otomatik oluşur.")
with right:
    st.image("data/coiltech_logo.png", use_container_width=True)

@st.cache_data
def read_schema(file)->dict:
    xls = pd.ExcelFile(file)
    dfs = {"products": pd.read_excel(xls,"products"),
           "sections": pd.read_excel(xls,"sections"),
           "fields": pd.read_excel(xls,"fields"),
           "options": pd.read_excel(xls,"options")}
    for col in ["PrereqFieldKey","PrereqAllowValues","SuffixKey","EncodeKey","Decimals","Widget","ShowType"]:
        if col not in dfs["fields"].columns:
            dfs["fields"][col] = "" if col!="Decimals" else np.nan
    for col in ["PrereqFieldKey","PrereqAllowValues"]:
        if col not in dfs["options"].columns:
            dfs["options"][col] = ""
    return dfs

schema = read_schema("data/schema.xlsx")

def clean_str(x):
    try:
        import math
        if x is None: return ""
        if isinstance(x,float) and math.isnan(x): return ""
        s=str(x);  return "" if s.lower()=="nan" else s
    except Exception: return ""

def sanitize_codes_only(s):
    import re
    return re.sub(r"[^A-Z0-9._-]","",str(s).upper()) if s is not None else ""

def norm(s): return str(s).strip().casefold()

def is_skip_valuecode(code):
    return norm(code) in {"yok","diger","diğer","var"}

def parse_allow_values(s):
    s=(s or "").strip()
    return [] if not s else [v.strip() for v in s.split(",") if v.strip()]

def prereq_ok(fk, allow)->bool:
    if fk is None: return True
    try:
        import math
        if isinstance(fk,float) and math.isnan(fk): return True
    except Exception: pass
    fk=str(fk).strip()
    if fk=="" or fk.lower() in {"nan","none"}: return True
    v=st.session_state["form_values"].get(fk)
    if v in (None,"",[]): return False
    allowset=set([sanitize_codes_only(a) for a in parse_allow_values(allow)])
    if not allowset: return True
    if isinstance(v,list): return any(sanitize_codes_only(x) in allowset for x in v)
    return sanitize_codes_only(v) in allowset

def prereq_message(fk, allow):
    if not fk: return ""
    try: flabel=schema["fields"].set_index("FieldKey").loc[fk,"FieldLabel"]
    except Exception: flabel=fk
    allow_list=parse_allow_values(allow)
    return (f"🔒 Bu alan, **{flabel}** alanında **{', '.join(allow_list)}** seçildiğinde aktif olur."
            if allow_list else f"🔒 Bu alan, **{flabel}** için seçim yapıldığında aktif olur.")

def option_filter(df):
    keep=[]
    for _,r in df.iterrows():
        keep.append(bool(prereq_ok(r.get("PrereqFieldKey",""), r.get("PrereqAllowValues",""))))
    return df[keep] if len(keep)==len(df) else df

def tr_norm(s):
    if s is None: return ""
    s=str(s)
    tr_map=str.maketrans({'İ':'I','I':'I','ı':'I','Ş':'S','ş':'S','Ğ':'G','ğ':'G','Ü':'U','ü':'U','Ö':'O','ö':'O','Ç':'C','ç':'C'})
    s=s.translate(tr_map)
    import unicodedata, re
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode('ascii')
    s=re.sub(r"[^A-Z0-9]+"," ", s.upper()).strip()
    return s

EMOJI_ASCII={"ELK":"⚡","ELEKTRIK":"⚡","MAKINA TIPI":"🛠️","UNITE TIPI":"🧩","CIFT KAFA":"🧲","ACICI TIPI":"🪛",
 "TAMBUR TIPI":"🎛️","TAMBUR HIZI":"🚀","TAMBUR HIZ":"🚀","SAC GENISLIGI":"📐","DIS CAP":"🧷","CAP":"🧷",
 "ACICI BASKI TIPI":"🧱","TAHRIK":"⚙️","MERKEZLEME":"🎯","YUKLEME ARABASI":"🛒","HIDROLIK UNITE":"💧",
 "LOOP KONTROL SISTEMI TIPI":"🔁","YON":"🧭","ENKODER":"📡","HAT HIZI":"⏱️"}
def emoji_for(section_key, section_label):
    for k in [section_key or "", section_label or ""]:
        key = tr_norm(k)
        if key in EMOJI_ASCII: return EMOJI_ASCII[key]
    return "•"

# ---- STATE ----
if "step" not in st.session_state: st.session_state["step"]=1
if "s1" not in st.session_state: st.session_state["s1"]=None
if "s2" not in st.session_state: st.session_state["s2"]=None
if "product_row" not in st.session_state: st.session_state["product_row"]=None
if "form_values" not in st.session_state: st.session_state["form_values"]={}
if "long_code_parts" not in st.session_state: st.session_state["long_code_parts"]=[]
if "long_code" not in st.session_state: st.session_state["long_code"]=""
if "last_added" not in st.session_state: st.session_state["last_added"]=[]

S1_ORDER=["Rulo Besleme","Plaka Besleme","Tamamlayıcı Ürünler"]

def big_buttons(options, cols=3, key_prefix="bb"):
    st.markdown('<div class="stepbtns">', unsafe_allow_html=True)
    cols_list=st.columns(cols); clicked=None
    for i,opt in enumerate(options):
        with cols_list[i%cols]:
            if st.button(opt, key=f"{key_prefix}_{opt}", use_container_width=True): clicked=opt
    st.markdown('</div>', unsafe_allow_html=True)
    return clicked

# ---- Steps ----
if st.session_state["step"]==1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.header("Aşama 1 — Ürün ve Detay ↪️")
    s1_candidates=[x for x in S1_ORDER if x in schema["products"]["Kategori1"].unique().tolist()]
    clicked=big_buttons(s1_candidates, cols=3, key_prefix="s1")
    st.markdown('</div>', unsafe_allow_html=True)
    if clicked:
        st.session_state.update({"s1":clicked,"s2":None,"product_row":None,"form_values":{},"long_code_parts":[],"long_code":"","last_added":[],"step":2})
        st.rerun()

elif st.session_state["step"]==2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.header("Aşama 2 — Alt Seçim")
    st.write(f"Seçimler: **{st.session_state['s1']}**")
    sub=schema["products"].query("Kategori1 == @st.session_state['s1']")["Kategori2"].dropna().unique().tolist()
    clicked=big_buttons(sub, cols=3, key_prefix="s2")
    col_back,_=st.columns([1,1])
    with col_back:
        if st.button("⬅️ Geri (Aşama 1)"): st.session_state["step"]=1; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    if clicked:
        st.session_state.update({"s2":clicked,"product_row":None,"form_values":{},"long_code_parts":[],"long_code":"","last_added":[],"step":3})
        st.rerun()

else:
    s1, s2 = st.session_state["s1"], st.session_state["s2"]
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.header("Aşama 3 — Ürün ve Detay 🔗")
    st.write(f"Seçimler: **{s1} → {s2}**")
    prods=schema["products"].query("Kategori1==@s1 and Kategori2==@s2")
    if prods.empty:
        st.warning("Bu seçim için 'products' sayfasında satır yok.")
    else:
        display=prods["UrunAdi"]+" — "+prods["MakineTipi"]
        choice=st.selectbox("Ürün", options=display.tolist(), placeholder="Seçiniz")
        if choice:
            idx=display.tolist().index(choice)
            st.session_state["product_row"]=prods.iloc[idx]

    row=st.session_state["product_row"]
    if row is not None:
        mk=row["MakineTipi"]
        st.info(f"Seçilen makine: **{mk}** — Kod: **{row['UrunKodu']}**")
        secs=schema["sections"].query("Kategori1==@s1 and Kategori2==@s2 and MakineTipi==@mk").sort_values("Order")
        if secs.empty:
            st.warning("Bu makine için 'sections' sayfasında kayıt yok.")
        else:
            tabs=st.tabs([f"{emoji_for(sec.SectionKey, sec.SectionLabel)} {sec.SectionLabel}" for _,sec in secs.iterrows()])
            fdf=schema["fields"]; optdf=schema["options"]
            for i,(_,sec) in enumerate(secs.iterrows()):
                with tabs[i]:
                    fields=fdf.query("SectionKey==@sec.SectionKey")
                    if fields.empty: st.write("Alan yok."); continue
                    for _,fld in fields.iterrows():
                        k=fld["FieldKey"]; label=fld["FieldLabel"]; typ=str(fld["Type"]).lower(); req=bool(fld["Required"]); default=fld.get("Default")
                        showtype=str(fld.get("ShowType") or "").strip().lower() or "lock"
                        en=prereq_ok(fld.get("PrereqFieldKey"), fld.get("PrereqAllowValues"))
                        if not en and showtype=="hide": continue
                        if not en and showtype=="lock": st.caption(prereq_message(fld.get("PrereqFieldKey"), fld.get("PrereqAllowValues")))
                        disabled=(not en)

                        widget=str(fld.get("Widget") or "").strip().lower()
                        if typ in ("select","multiselect"):
                            opts=optdf.query("OptionsKey==@fld.OptionsKey").sort_values("Order")
                            opts=option_filter(opts)
                            opts_codes=opts["ValueCode"].astype(str).tolist()
                            opts_labels=(opts["ValueCode"].astype(str)+" — "+opts["ValueLabel"].astype(str)).tolist()

                            if typ=="select":
                                if widget=="radio":
                                    sel=st.radio(label+(" *" if req else ""), options=opts_codes,
                                                 format_func=lambda c: opts_labels[opts_codes.index(c)], index=None,
                                                 key=f"k_{k}", disabled=disabled, horizontal=False)
                                else:
                                    sel=st.selectbox(label+(" *" if req else ""), options=opts_codes,
                                                     format_func=lambda c: opts_labels[opts_codes.index(c)], index=None,
                                                     key=f"k_{k}", disabled=disabled, placeholder="Seçiniz")
                                if en and sel is not None: st.session_state["form_values"][k]=sel
                                else: st.session_state["form_values"].pop(k, None)

                            else:  # multiselect
                                if widget=="checkboxes":
                                    selected=set(map(str, st.session_state["form_values"].get(k, [])))
                                    new_selected=[]
                                    for code,lbl in zip(opts_codes, opts_labels):
                                        chk=st.checkbox(lbl, key=f"chk_{k}_{code}", value=(code in selected), disabled=disabled)
                                        if chk: new_selected.append(code)
                                    if en and new_selected: st.session_state["form_values"][k]=new_selected
                                    else: st.session_state["form_values"].pop(k, None)
                                else:
                                    ms=st.multiselect(label+(" *" if req else ""), options=opts_codes, default=[],
                                                      format_func=lambda c: opts_labels[opts_codes.index(c)],
                                                      key=f"k_{k}", disabled=disabled, placeholder="Seçiniz")
                                    if en and ms: st.session_state["form_values"][k]=ms
                                    else: st.session_state["form_values"].pop(k, None)

                        elif typ=="number":
                            minv=fld.get("Min"); maxv=fld.get("Max"); step=fld.get("Step")
                            decimals=fld.get("Decimals"); d=int(decimals) if pd.notna(decimals) else 0
                            if pd.isna(step): step=1 if d==0 else 10**(-d)
                            if d==0:
                                minv_i=int(minv) if pd.notna(minv) else None
                                maxv_i=int(maxv) if pd.notna(maxv) else None
                                defv_i=int(default) if pd.notna(default) else (minv_i or 0)
                                step_i=int(step)
                                val=st.number_input(label+(" *" if req else ""), min_value=minv_i, max_value=maxv_i,
                                                    value=defv_i, step=step_i, format="%d", key=f"k_{k}", disabled=disabled)
                            else:
                                fmt=f"%.{d}f"
                                minv_f=float(minv) if pd.notna(minv) else None
                                maxv_f=float(maxv) if pd.notna(maxv) else None
                                defv_f=float(default) if pd.notna(default) else (minv_f or 0.0)
                                step_f=float(step) if pd.notna(step) else 10**(-d)
                                val=st.number_input(label+(" *" if req else ""), min_value=minv_f, max_value=maxv_f,
                                                    value=defv_f, step=step_f, format=fmt, key=f"k_{k}", disabled=disabled)
                            if en: st.session_state["form_values"][k]=val

                        else:
                            txt=st.text_input(label+(" *" if req else ""), value=clean_str(default),
                                              key=f"k_{k}", disabled=disabled, placeholder="Seçiniz")
                            if en and txt.strip()!="": st.session_state["form_values"][k]=txt
                            else: st.session_state["form_values"].pop(k, None)
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- Live long code ----
    st.markdown('<div class="panel">', unsafe_allow_html=True)

    def format_number_for_code(n, pad, decimals):
        if decimals is None or (isinstance(decimals,float) and math.isnan(decimals)): decimals=0
        try: nf=float(n)
        except Exception: return str(n)
        if int(decimals)==0:
            nv=int(round(nf))
            if not pad or (isinstance(pad,float) and math.isnan(pad)) or (isinstance(pad,str) and pad.strip()==""): return str(nv)
            if isinstance(pad,(int,float)) and not (isinstance(pad,float) and math.isnan(pad)): return f"{nv:0{int(pad)}d}"
            if isinstance(pad,str) and pad.isdigit(): return f"{nv:0{int(pad)}d}"
            if isinstance(pad,str) and "." in pad: return f"{nv:0{int(pad.split('.')[0])}d}"
            return str(nv)
        else:
            d=int(decimals); return f"{nf:.{d}f}"

    def build_parts(machine_type, schema, s1, s2):
        parts=[]
        m=sanitize_codes_only(machine_type) if machine_type else ""
        if m: parts.append(m)
        secs=schema["sections"].query("Kategori1==@s1 and Kategori2==@s2 and MakineTipi==@machine_type").sort_values("Order")
        fdf=schema["fields"]; optdf=schema["options"]
        for _,sec in secs.iterrows():
            fields=fdf.query("SectionKey==@sec.SectionKey")
            for _,fld in fields.iterrows():
                k=fld["FieldKey"]; typ=str(fld["Type"]).lower(); val=st.session_state['form_values'].get(k)
                if val in (None,"",[],0): continue
                if typ=="select":
                    if is_skip_valuecode(val): continue
                    parts.append(sanitize_codes_only(val))
                elif typ=="multiselect" and isinstance(val,list):
                    subset=optdf.query("OptionsKey==@fld.OptionsKey")
                    order_map={str(r["ValueCode"]): int(r["Order"]) for _, r in subset.iterrows()}
                    clean=[v for v in val if not is_skip_valuecode(v)]
                    ordered=sorted(clean, key=lambda v: order_map.get(str(v), 999999))
                    if ordered: parts.append("".join([sanitize_codes_only(v) for v in ordered]))
                elif typ=="number":
                    num=format_number_for_code(val, fld.get("Pad"), fld.get("Decimals"))
                    pre=clean_str(fld.get("EncodeKey")); suf=clean_str(fld.get("SuffixKey"))
                    parts.append(f"{pre}{num}{suf}" if (pre or suf) else f"{num}")
                else:
                    txt=clean_str(val); pre=clean_str(fld.get("EncodeKey")); suf=clean_str(fld.get("SuffixKey"))
                    piece=f"{pre}{txt}{suf}" if (pre or suf) else txt
                    if piece.strip(): parts.append(piece)
        return parts

    mk = st.session_state.get("product_row", {}).get("MakineTipi") if isinstance(st.session_state.get("product_row"), dict) else (st.session_state.get("product_row")["MakineTipi"] if st.session_state.get("product_row") is not None else None)
    s1, s2 = st.session_state.get("s1"), st.session_state.get("s2")
    new_parts = build_parts(mk, schema, s1, s2) if mk else []

    old = st.session_state["long_code_parts"]
    common=0
    for a,b in zip(old,new_parts):
        if a==b: common+=1
        else: break
    last_added=new_parts[common:]
    st.session_state["long_code_parts"]=new_parts
    st.session_state["last_added"]=last_added
    st.session_state["long_code"]=" ".join(new_parts)

    chips_html="".join([f'<span class="token{" new" if i>=common else ""}">{p}</span>' for i,p in enumerate(new_parts)])
    st.markdown(chips_html if chips_html else '<span class="smallmuted">Kod için seçim yapın…</span>', unsafe_allow_html=True)

    if st.session_state["long_code"]:
        st.code(st.session_state["long_code"], language="text")
        if last_added:
            st.markdown(f"**➕ Son eklenen:** {' , '.join(last_added)}")
            img=qrcode.make(st.session_state["long_code"]); buf=io.BytesIO(); img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption="QR", width=96)
        st.download_button("Kodu TXT indir", data=st.session_state["long_code"].encode("utf-8"), file_name="uzun_kod.txt")

    st.markdown('</div>', unsafe_allow_html=True)
