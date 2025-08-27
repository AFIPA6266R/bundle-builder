# app.py
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="Gem Estimator Pro", layout="wide")

# ---------- Styles ----------
st.markdown(
    """
    <style>
      /* tighten vertical rhythm a bit */
      .block-container {padding-top: 1.25rem; padding-bottom: 2rem;}
      div[data-testid="stHorizontalBlock"] > div {padding-right: .5rem;}
      /* compact select/number widgets while still readable */
      .stSelectbox, .stNumberInput, .stTextInput {margin-bottom: .4rem;}
      label[for] {font-size: .80rem; color: #5b6770;}
      /* make inputs height compact */
      .stSelectbox div[role="combobox"], .stNumberInput input, .stTextInput input {
        min-height: 38px;
      }
      /* keep dropdowns wide enough to show long values */
      .auto-col {width: 100%;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Data loading ----------
@st.cache_data
def load_master(xlsx_path="TEST.xlsx", sheet="MCGI_Master_Price"):
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    for c in [
        "Gemstone", "Shape", "Size", "Cut",
        "Color", "Country of Origin", "Stone Treatment",
        "Unit Of Measure"
    ]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df

def parse_size(s):
    if s is None:
        return None
    s = str(s).strip().lower().replace(" ", "")
    return s.replace("mm","")

def uniq(series):
    return sorted([x for x in series.dropna().astype(str).unique() if str(x).strip() != ""])

def cascade_options(df, gem=None, shape=None, size=None, cut=None):
    base = df.copy()
    if gem:
        base = base[base["Gemstone"].str.lower() == gem.strip().lower()]
    shapes = uniq(base["Shape"]) if "Shape" in base.columns else []

    base2 = base.copy()
    if shape:
        base2 = base2[base2["Shape"].str.lower() == shape.strip().lower()]
    sizes = uniq(base2["Size"]) if "Size" in base2.columns else []

    base3 = base2.copy()
    if size:
        key = parse_size(size)
        base3 = base3[base3["Size"].map(parse_size) == key]
    cuts = uniq(base3["Cut"]) if "Cut" in base3.columns else []

    base4 = base3.copy()
    if cut and "Cut" in base4.columns:
        exact = base4[base4["Cut"].str.lower() == cut.strip().lower()]
        if len(exact) > 0:
            base4 = exact
    colors = uniq(base4["Color"]) if "Color" in base4.columns else []
    countries = uniq(base4["Country of Origin"]) if "Country of Origin" in base4.columns else []
    treatments = uniq(base4["Stone Treatment"]) if "Stone Treatment" in base4.columns else []
    return shapes, sizes, cuts, colors, countries, treatments

def avg_price_lookup(df, gem, shape, size, cut=None, color=None, country=None, treatment=None):
    q = df.copy()
    if gem:
        q = q[q["Gemstone"].str.lower() == str(gem).strip().lower()]
    if shape:
        q = q[q["Shape"].str.lower() == str(shape).strip().lower()]
    if size:
        key = parse_size(size)
        q = q[q["Size"].map(parse_size) == key]
    if cut and "Cut" in q.columns:
        qq = q[q["Cut"].str.lower() == str(cut).strip().lower()]
        if len(qq) > 0: q = qq
    if color and "Color" in q.columns:
        qq = q[q["Color"].str.lower() == str(color).strip().lower()]
        if len(qq) > 0: q = qq
    if country and "Country of Origin" in q.columns:
        qq = q[q["Country of Origin"].str.lower() == str(country).strip().lower()]
        if len(qq) > 0: q = qq
    if treatment and "Stone Treatment" in q.columns:
        qq = q[q["Stone Treatment"].str.lower() == str(treatment).strip().lower()]
        if len(qq) > 0: q = qq

    if len(q) == 0:
        return None, "No exact match. Adjust filters.", None, 0, q

    mean_ppp = q["Price Per Piece US$"].dropna().astype(float).mean() if "Price Per Piece US$" in q.columns else np.nan
    mean_ppc = q["Price Per Carat US$"].dropna().astype(float).mean() if "Price Per Carat US$" in q.columns else np.nan
    mean_awp = q["Average Weight Per Piece"].dropna().astype(float).mean() if "Average Weight Per Piece" in q.columns else np.nan

    avg_row = {}
    if pd.notna(mean_ppp): avg_row["Average Price Per Piece US$"] = float(mean_ppp)
    if pd.notna(mean_ppc): avg_row["Average Price Per Carat US$"] = float(mean_ppc)
    if pd.notna(mean_awp): avg_row["Average Weight Per Piece"] = float(mean_awp)

    if pd.notna(mean_ppp):
        unit_cost = float(mean_ppp)
        note = f"Used average Price/pc across {len(q)} match(es)"
    elif pd.notna(mean_ppc) and pd.notna(mean_awp):
        unit_cost = float(mean_ppc) * float(mean_awp)
        note = f"Used (avg Price/ct × avg Wt/pc) across {len(q)} match(es)"
    else:
        return None, "No usable pricing (need Price/pc OR (Price/ct & Avg Wt)).", (avg_row or None), len(q), q

    return unit_cost, note, (avg_row or None), len(q), q

# ---------- Sidebar: file controls ----------
with st.sidebar:
    st.subheader("Data Source")
    file_path = st.text_input(
        "Excel file path", value="TEST.xlsx", key="file_path_input"
    )
    sheet_name = st.text_input(
        "Sheet name", value="MCGI_Master_Price", key="sheet_name_input"
    )
    col1, col2 = st.columns([1,1])
    with col1:
        reloaded = st.button("Reload data", use_container_width=True)
    with col2:
        show_head = st.toggle("Preview 20 rows", value=False)

# Load data (reload when user clicks or path/sheet changes)
if reloaded:
    load_master.clear()

df = load_master(file_path, sheet_name)

if show_head:
    st.dataframe(df.head(20), use_container_width=True)

# ---------- Header ----------
st.title("💎 Gem Estimator Pro")
st.caption(
    "Cascading filters **(Gem → Shape → Size → Cut → Color → Country → Treatment)** with average pricing. "
    "Tabs keep scrolling minimal. Columns auto-size so longer fields (Country/Treatment) fit comfortably. "
    "Source: MCGI Shipment Invoices to BBJ."
)

# ---------- Line item UI ----------
def line_item(df, label, key_prefix):
    st.markdown(f"**{label}**")

    # Cascade lists
    shapes0, sizes0, cuts0, colors0, countries0, trts0 = cascade_options(df)

    # Row 1: Gem, Shape, Size, Cut, Color, Country, Treatment, Qty
    c1,c2,c3,c4,c5,c6,c7,c8 = st.columns([1.2,1.2,0.9,1.0,1.2,1.5,1.5,0.6])

    with c1:
        gem = st.selectbox(
            "Gem", [""] + uniq(df["Gemstone"]),
            index=0, key=f"{key_prefix}_gem", label_visibility="collapsed", help="Gemstone"
        )
    with c2:
        shapes,_,_,_,_,_ = cascade_options(df, gem=gem or None)
        shape = st.selectbox(
            "Shape", [""] + shapes,
            index=0, key=f"{key_prefix}_shape", label_visibility="collapsed", help="Shape"
        )
    with c3:
        _,sizes,_,_,_,_ = cascade_options(df, gem=gem or None, shape=shape or None)
        size = st.selectbox(
            "Size", [""] + sizes,
            index=0, key=f"{key_prefix}_size", label_visibility="collapsed", help="Size"
        )
    with c4:
        _,_,cuts,_,_,_ = cascade_options(df, gem=gem or None, shape=shape or None, size=size or None)
        cut = st.selectbox(
            "Cut", [""] + cuts,
            index=0, key=f"{key_prefix}_cut", label_visibility="collapsed", help="Cut"
        )
    with c5:
        _,_,_,colors,_,_ = cascade_options(df, gem=gem or None, shape=shape or None, size=size or None)
        color = st.selectbox(
            "Color (optional)", ["(any)"] + colors,
            index=0, key=f"{key_prefix}_color", label_visibility="collapsed", help="Color"
        )
    with c6:
        _,_,_,_,countries,_ = cascade_options(df, gem=gem or None, shape=shape or None, size=size or None, cut=cut or None)
        country = st.selectbox(
            "Country of Origin (optional)", ["(any)"] + countries,
            index=0, key=f"{key_prefix}_country", label_visibility="collapsed", help="Country"
        )
    with c7:
        _,_,_,_,_,treatments = cascade_options(df, gem=gem or None, shape=shape or None, size=size or None, cut=cut or None)
        treatment = st.selectbox(
            "Treatment (optional)", ["(any)"] + treatments,
            index=0, key=f"{key_prefix}_treat", label_visibility="collapsed", help="Treatment"
        )
    with c8:
        qty = st.number_input(
            "Qty", min_value=0, value=1, step=1,
            key=f"{key_prefix}_qty", label_visibility="collapsed", help="Pieces"
        )

    use_color = None if color == "(any)" else color
    use_country = None if country == "(any)" else country
    use_treat = None if treatment == "(any)" else treatment

    if qty > 0 and gem and shape and size:
        cost, note, avg_row, nmatch, preview = avg_price_lookup(
            df, gem, shape, size, cut or None, use_color, use_country, use_treat
        )
        if cost is not None:
            total = cost * qty
            line1 = (
                f"Price Per Piece: **US${cost:,.4f}** · Qty: **{qty}** · "
                f"**Line Total: US${total:,.4f}**  ({note})"
            )
            bits = []
            if avg_row:
                if "Average Price Per Piece US$" in avg_row:
                    bits.append(f"Avg/pc: US${avg_row['Average Price Per Piece US$']:.4f}")
                if "Average Price Per Carat US$" in avg_row:
                    bits.append(f"Avg/ct: US${avg_row['Average Price Per Carat US$']:.4f}")
                if "Average Weight Per Piece" in avg_row:
                    bits.append(f"Avg Wt/pc: {avg_row['Average Weight Per Piece']:.4f} ct")
            line2 = " · ".join(bits)
            st.success(line1 + ("" if not line2 else f"  \n{line2}"))

            with st.expander(f"Preview matched rows ({min(len(preview),50)} shown)"):
                st.dataframe(preview.head(50), use_container_width=True)

            return total, {
                "gem": gem, "shape": shape, "size": size, "cut": cut or "",
                "color": use_color, "country": use_country, "treatment": use_treat,
                "qty": qty, "unit_cost": cost, "note": note, "matches": nmatch
            }
        else:
            st.error(note or "Could not price this line.")
            if len(preview) > 0:
                with st.expander("Matched rows we found (first 50)"):
                    st.dataframe(preview.head(50), use_container_width=True)
            return 0.0, None
    else:
        st.info("Pick Gem → Shape → Size (then optional Cut/Color/Country/Treatment) and set Qty.")
        return 0.0, None

# ---------- Tabs ----------
tab_center, tab_side, tab_acc, tab_sum = st.tabs(["Center", "Side Stones", "Accents", "Summary"])

with tab_center:
    st.text_input(
        "Notes (optional)", "", placeholder="Notes (optional)…",
        key="notes_center", label_visibility="visible"
    )
    center_total, center_meta = line_item(df, "Line 1", key_prefix="center")

with tab_side:
    col = st.columns([1,7])[0]
    with col:
        side_lines_count = st.number_input("Number of side lines", 0, 10, 1, 1, key="side_count")
    side_tot = 0.0
    side_lines = []
    for i in range(int(side_lines_count)):
        tot, meta = line_item(df, f"Line {i+1}", key_prefix=f"side_{i+1}")
        side_tot += tot
        if meta: side_lines.append(meta)

with tab_acc:
    col = st.columns([1,7])[0]
    with col:
        acc_lines_count = st.number_input("Number of accent lines", 0, 20, 1, 1, key="acc_count")
    acc_tot = 0.0
    acc_lines = []
    for i in range(int(acc_lines_count)):
        tot, meta = line_item(df, f"Line {i+1}", key_prefix=f"acc_{i+1}")
        acc_tot += tot
        if meta: acc_lines.append(meta)

with tab_sum:
    # compute totals
    if "center_total" not in st.session_state:
        pass
    grand = (center_total or 0.0) + (side_tot if 'side_tot' in locals() else 0.0) + (acc_tot if 'acc_tot' in locals() else 0.0)

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Center Stones", f"${(center_total or 0.0):,.4f}")
    k2.metric("Side Stones", f"${(side_tot if 'side_tot' in locals() else 0.0):,.4f}")
    k3.metric("Accents", f"${(acc_tot if 'acc_tot' in locals() else 0.0):,.4f}")
    k4.metric("Total Stone Cost", f"${grand:,.4f}")

    # Download summary
    summary_df = pd.DataFrame([{
        "center_total": center_total or 0.0,
        "side_total": side_tot if 'side_tot' in locals() else 0.0,
        "acc_total": acc_tot if 'acc_tot' in locals() else 0.0,
        "grand_total": grand,
        "notes": st.session_state.get("notes_center",""),
        "source_file": str(Path(file_path).resolve()),
        "sheet": sheet_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }])
    st.download_button(
        "Download bundle breakdown (CSV)",
        summary_df.to_csv(index=False).encode("utf-8"),
        "bundle_cost_summary.csv",
        "text/csv",
        use_container_width=True,
    )
