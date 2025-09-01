# app.py
import streamlit as st
import pandas as pd
import numpy as np
from math import isfinite

# ---------------- Page & CSS ----------------
st.set_page_config(page_title="Estimator Pro", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px;}
      .small-help {font-size: 0.85rem; color: #666;}
      div[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
      .stSelectbox, .stNumberInput, .stTextInput, .stTextArea {margin-bottom: 0.35rem !important;}
      label[data-testid="stWidgetLabel"] {font-size: 0.85rem; margin-bottom: 0.15rem;}
      .pill {background:#f6f9ff;border:1px solid #e3ecff;border-radius:8px;padding:10px 12px;margin-top:.25rem;}
      .mono {font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;}
      .caption-tight {margin-top:-6px;color:#7a7a7a;}
      /* Prevent clipped cell text in dataframes */
      .stDataFrame td div { white-space: nowrap; overflow: visible; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Estimator Pro – Metal & Stones · BBJ Bangkok Ltd")
st.caption(
    "Build center/side/accent stone lines with *cascading filters* (Gem → Shape → Size → Cut → Color → Country → Treatment), "
    "priced by *average per piece* or *per carat × weight* from your master sheet. "
    "Use the *Metal* tab for live per-gram rates and *Labor* to estimate CPF/setting/plating. "
    "Finish in *Summary* and export."
)

# ---------------- Sidebar: data controls ----------------
st.sidebar.header("Data Source")
xlsx_path = st.sidebar.text_input("Excel file path or name", value="TEST.xlsx", help="Example: TEST.xlsx (must be in working directory)")
sheet_name = st.sidebar.text_input("Sheet name", value="MCGI_Master_Price")
reload_now = st.sidebar.button("Reload data")

# ---------------- Data loading ----------------
@st.cache_data(show_spinner=False)
def load_master(xlsx_path:str, sheet:str):
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    # normalize key columns
    text_cols = [
        "Gemstone","Shape","Size","Cut","Color","Country of Origin","Stone Treatment","Unit Of Measure"
    ]
    num_cols = ["Price Per Piece US$","Price Per Carat US$","Average Weight Per Piece"]
    for c in text_cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

if reload_now:
    load_master.clear()

try:
    df = load_master(xlsx_path, sheet_name)
except Exception as e:
    st.error(f"Failed to load Excel → {e}")
    st.stop()

# ---------------- Helpers ----------------
def parse_size(s):
    if s is None: return None
    s = str(s).strip().lower().replace(" ", "").replace("mm", "")
    return s

def uniq(series):
    return sorted([x for x in series.dropna().astype(str).unique() if str(x).strip() != ""])

def cascade_options(df, gem=None, shape=None, size=None, cut=None):
    base = df
    if gem:
        base = base[base["Gemstone"].str.lower() == gem.strip().lower()]

    shapes = uniq(base["Shape"]) if "Shape" in base.columns else []

    base2 = base
    if shape:
        base2 = base2[base2["Shape"].str.lower() == shape.strip().lower()]
    sizes = uniq(base2["Size"]) if "Size" in base2.columns else []

    base3 = base2
    if size:
        key = parse_size(size)
        base3 = base3[base3["Size"].map(parse_size) == key]
    cuts = uniq(base3["Cut"]) if "Cut" in base3.columns else []

    base4 = base3
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
    if gem:    q = q[q["Gemstone"].str.lower() == str(gem).strip().lower()]
    if shape:  q = q[q["Shape"].str.lower() == str(shape).strip().lower()]
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
        note = f"Used average Price Per Piece across {len(q)} match(es)"
    elif pd.notna(mean_ppc) and pd.notna(mean_awp):
        unit_cost = float(mean_ppc) * float(mean_awp)
        note = f"Used (average Price/ct × average Weight) across {len(q)} match(es)"
    else:
        return None, "No usable pricing (need Price/pc OR (Price/ct & Avg Weight)).", (avg_row or None), len(q), q

    return unit_cost, note, (avg_row or None), len(q), q

def line_item(df, header, key_prefix):
    st.markdown(f"#### {header}")

    # Row 1: Gem, Shape, Size
    c1, c2, c3 = st.columns([1.1, 1.0, 1.2], gap="small")
    with c1:
        gems = [""] + uniq(df["Gemstone"])
        gem = st.selectbox("Gemstone", gems, index=0, key=f"{key_prefix}_gem", help="Pick a gemstone")
    shapes, _, _, _, _, _ = cascade_options(df, gem=gem or None)
    with c2:
        shape = st.selectbox("Shape", [""] + shapes, index=0, key=f"{key_prefix}_shape", help="Pick a shape")
    _, sizes, _, _, _, _ = cascade_options(df, gem=gem or None, shape=shape or None)
    with c3:
        size = st.selectbox("Size", [""] + sizes, index=0, key=f"{key_prefix}_size", help="Pick a size")

    # Row 2: Cut, Color, Country, Treatment, Qty
    d1, d2, d3, d4, d5 = st.columns([1.2, 1.0, 1.2, 1.2, 0.8], gap="small")
    _, _, cuts, colors, countries, treatments = cascade_options(
        df, gem=gem or None, shape=shape or None, size=size or None
    )
    with d1:
        cut = st.selectbox("Cut", [""] + cuts, index=0, key=f"{key_prefix}_cut", help="Optional")
    with d2:
        color = st.selectbox("Color (optional)", ["(any)"] + colors, index=0, key=f"{key_prefix}_color")
    with d3:
        country = st.selectbox("Country (optional)", ["(any)"] + countries, index=0, key=f"{key_prefix}_country")
    with d4:
        treatment = st.selectbox("Treatment (optional)", ["(any)"] + treatments, index=0, key=f"{key_prefix}_treat")
    with d5:
        qty = st.number_input("Pieces", min_value=0, value=1, step=1, key=f"{key_prefix}_qty")

    use_color    = None if color == "(any)" else color
    use_country  = None if country == "(any)" else country
    use_treat    = None if treatment == "(any)" else treatment

    item_details = {
        "gem": gem or "",
        "shape": shape or "",
        "size": size or "",
        "cut": cut or "",
        "color": use_color or "",
        "country": use_country or "",
        "treatment": use_treat or "",
        "qty": qty,
        "unit_cost": 0.0,
        "total_cost": 0.0,
        "note": ""
    }

    if qty > 0 and gem and shape and size:
        cost, note, avg_row, nmatch, preview = avg_price_lookup(
            df, gem, shape, size, cut or None, use_color, use_country, use_treat
        )
        if cost is not None:
            total = cost * qty
            item_details.update({"unit_cost": cost, "total_cost": total, "note": note})
            line1 = (
                f"Price Per Piece: US${cost:,.4f} · "
                f"Total Pieces: {qty} · "
                f"*Total: US${total:,.4f}* "
                f"({note})"
            )
            bits = []
            if avg_row:
                if "Average Price Per Piece US$" in avg_row:
                    bits.append(f"Avg Price/pc: US${avg_row['Average Price Per Piece US$']:.4f}")
                if "Average Price Per Carat US$" in avg_row:
                    bits.append(f"Avg Price/ct: US${avg_row['Average Price Per Carat US$']:.4f}")
                if "Average Weight Per Piece" in avg_row:
                    bits.append(f"Avg Wt/pc: {avg_row['Average Weight Per Piece']:.4f} ct")
            line2 = " · ".join(bits)
            st.success(line1 + ("" if not line2 else "  \n" + line2))
            st.caption(f"Matched rows: {nmatch}")
            with st.expander(f"Preview matched rows ({min(len(preview), 50)} shown)"):
                st.dataframe(preview.head(50), use_container_width=True, hide_index=True)
            return total, item_details
        else:
            st.error(note or "Could not price this line.")
            if len(preview) > 0:
                with st.expander("Matched rows we found (first 50)"):
                    st.dataframe(preview.head(50), use_container_width=True, hide_index=True)
            return 0.0, None
    else:
        st.info("Pick Gemstone → Shape → Size (then optional Cut/Color/Country/Treatment) and set Pieces.")
        return 0.0, None

# ---------------- TABS ----------------
tab_center, tab_side, tab_acc, tab_metal, tab_labor, tab_summary = st.tabs(
    ["Center", "Side", "Accents", "Metal", "Labor", "Summary"]
)

# Session state buckets
if 'center_details' not in st.session_state: st.session_state.center_details = None
if 'side_lines' not in st.session_state: st.session_state.side_lines = []
if 'acc_lines' not in st.session_state:  st.session_state.acc_lines = []
if 'metal_details' not in st.session_state: st.session_state.metal_details = None
if 'labor_totals' not in st.session_state:  st.session_state.labor_totals = {}

# -------- Center --------
with tab_center:
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        center_total, center_meta = line_item(df, "Center Stone", key_prefix="center")
        st.session_state.center_details = center_meta
    with right:
        st.markdown("*Notes (optional, internal)*")
        st.text_area(
            "Center Notes",
            value="",
            key="notes_center",
            placeholder="Any memo about this center stone…",
            height=96,
        )

# -------- Side --------
with tab_side:
    st.subheader("Side Stones")
    side_count = st.number_input("Number of side stone lines", min_value=0, max_value=10, value=2, step=1, key="side_lines_count")
    side_tot = 0.0
    st.session_state.side_lines = []
    for i in range(int(side_count)):
        tot, meta = line_item(df, f"Side #{i+1}", key_prefix=f"side_{i+1}")
        side_tot += tot
        if meta: st.session_state.side_lines.append(meta)

# -------- Accents --------
with tab_acc:
    st.subheader("Accents")
    acc_count = st.number_input("Number of accent lines", min_value=0, max_value=20, value=1, step=1, key="acc_lines_count")
    acc_tot = 0.0
    st.session_state.acc_lines = []
    for i in range(int(acc_count)):
        tot, meta = line_item(df, f"Accent #{i+1}", key_prefix=f"acc_{i+1}")
        acc_tot += tot
        if meta: st.session_state.acc_lines.append(meta)

# -------- Metal Calculator --------
with tab_metal:
    st.subheader("Metal Calculator")

    # Optional live prices in the sidebar
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Live metal prices (optional)")
        use_live = st.checkbox("Fetch live ounce prices (Yahoo Finance)", value=False, key="use_live")
        live_note = st.empty()
        ounce_prices = {"Gold": None, "Silver": None, "Copper": None}
        if use_live:
            try:
                import yfinance as yf
                tickers = {"Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F"}
                for m, tkr in tickers.items():
                    t = yf.Ticker(tkr)
                    px = None
                    # Try fast_info.last_price first
                    info = getattr(t, "fast_info", None)
                    if info is not None and hasattr(info, "last_price"):
                        px = float(info.last_price)
                    # Fallback to last close
                    if px is None:
                        hist = t.history(period="1d")
                        if not hist.empty and "Close" in hist.columns:
                            px = float(hist["Close"].iloc[-1])
                    if px and isfinite(px):
                        ounce_prices[m] = px
                live_note.success("Live ounce prices fetched ✅")
            except Exception as e:
                live_note.warning(f"Could not fetch live prices: {e}. Enter ounce prices manually in Metal tab.")

    colA, colB = st.columns([1.2, 1.0])
    with colA:
        st.markdown("#### Inputs")
        prod = st.selectbox("Product Type", ["Ring","Earring","Pendant","Necklace","Bracelet","Bangle"], key="m_prod")
        metal = st.selectbox("Metal", ["Gold","Silver","Copper","Steel","Brass"], key="m_metal")

        if metal == "Gold":
            purity_options = ["18K","14K","10K","9K"]
        elif metal == "Silver":
            purity_options = ["SS925"]
        else:
            purity_options = ["N.A"]

        purity_choice = st.selectbox("Metal Purity", purity_options, key="m_purity")
        plating = st.selectbox("Plating", ["(None)","14KY Gold Plating over Silver","18KY Gold Plating over Silver"], key="m_plating")

        approx_weight = st.number_input("Approximate Metal Weight (grams)", min_value=0.0, value=0.0, step=0.1, key="approx_weight")

        st.markdown("*Ounce Prices (USD/oz)*")
        st.number_input("Gold (USD/oz)",   min_value=0.0, step=1.0,  value=float(ounce_prices["Gold"])   if ounce_prices["Gold"]   else 0.0, key="oz_gold")
        st.number_input("Silver (USD/oz)", min_value=0.0, step=0.1,  value=float(ounce_prices["Silver"]) if ounce_prices["Silver"] else 0.0, key="oz_silver")
        st.number_input("Copper (USD/oz)", min_value=0.0, step=0.01, value=float(ounce_prices["Copper"]) if ounce_prices["Copper"] else 0.0, key="oz_copper")

        st.markdown("*Factors (editable)*")
        st.number_input("Ounce → gram factor", value=32.148, step=0.001, key="conv_oz_to_g")
        st.number_input("Silver yield factor", value=0.95, step=0.01, key="silver_yield")
        st.number_input("Silver finishing factor", value=1.15, step=0.01, key="silver_finish")
        st.number_input("Gold finishing factor", value=1.12, step=0.01, key="gold_finish")

        st.markdown("Gold purities (fraction)")
        st.number_input("9K purity fraction",  value=0.375, step=0.001, key="p9")
        st.number_input("10K purity fraction", value=0.417, step=0.001, key="p10")
        st.number_input("14K purity fraction", value=0.59,  step=0.001, key="p14")
        st.number_input("18K purity fraction", value=0.750, step=0.001, key="p18")

        st.markdown("Other baselines")
        st.number_input("Silver purity (SS925 fraction)", value=0.925, step=0.001, key="pss")
        st.checkbox("Derive Brass price from Copper (0.7 × Copper/gram)", value=True, key="brass_from_cu")
        st.checkbox("Derive Steel price from Copper (0.5 × Copper/gram)", value=True, key="steel_from_cu")

    with colB:
        st.markdown("#### Results")
        densities = { "18K": 15.5, "14K": 13.5, "10K": 11.5, "9K": 10.5, "SS925": 10.4, "Brass": 8.73, "Copper": 8.96 }

        def per_gram_silver(oz_price, conv_oz_to_g, silver_yield, silver_finish):
            if oz_price <= 0: return None
            return (oz_price * conv_oz_to_g * silver_yield * silver_finish) / 1000.0

        def per_gram_gold(oz_price, conv_oz_to_g, purity, gold_finish):
            if oz_price <= 0: return None
            return (oz_price * conv_oz_to_g * purity * gold_finish) / 1000.0

        def per_gram_copper(oz_price, conv_oz_to_g):
            if oz_price <= 0: return None
            return (oz_price * conv_oz_to_g) / 1000.0

        oz_gold   = st.session_state.get('oz_gold', 0.0)
        oz_silver = st.session_state.get('oz_silver', 0.0)
        oz_copper = st.session_state.get('oz_copper', 0.0)
        conv      = st.session_state.get('conv_oz_to_g', 32.148)
        sy        = st.session_state.get('silver_yield', 0.95)
        sf        = st.session_state.get('silver_finish', 1.15)
        gf        = st.session_state.get('gold_finish', 1.12)
        p9        = st.session_state.get('p9', 0.375)
        p10       = st.session_state.get('p10', 0.417)
        p14       = st.session_state.get('p14', 0.59)
        p18       = st.session_state.get('p18', 0.750)

        silver_g = per_gram_silver(oz_silver, conv, sy, sf) if oz_silver else None
        gold_g_9  = per_gram_gold(oz_gold, conv, p9,  gf) if oz_gold else None
        gold_g_10 = per_gram_gold(oz_gold, conv, p10, gf) if oz_gold else None
        gold_g_14 = per_gram_gold(oz_gold, conv, p14, gf) if oz_gold else None
        gold_g_18 = per_gram_gold(oz_gold, conv, p18, gf) if oz_gold else None
        copper_g  = per_gram_copper(oz_copper, conv) if oz_copper else None

        brass_g = (0.70 * copper_g) if st.session_state.get("brass_from_cu", True) and copper_g else None
        steel_g = (0.50 * copper_g) if st.session_state.get("steel_from_cu", True)  and copper_g else None
        if brass_g is None:
            brass_g = 0.0
        if steel_g is None:
            steel_g = 0.0

        rows = [
            {"Metal": "Silver 925", "USD/gram": None if silver_g is None else round(silver_g, 4)},
            {"Metal": "Gold 9K",   "USD/gram": None if gold_g_9  is None else round(gold_g_9, 4)},
            {"Metal": "Gold 10K",  "USD/gram": None if gold_g_10 is None else round(gold_g_10, 4)},
            {"Metal": "Gold 14K",  "USD/gram": None if gold_g_14 is None else round(gold_g_14, 4)},
            {"Metal": "Gold 18K",  "USD/gram": None if gold_g_18 is None else round(gold_g_18, 4)},
            {"Metal": "Copper",    "USD/gram": None if copper_g  is None else round(copper_g, 4)},
            {"Metal": "Brass",     "USD/gram": round(brass_g, 4)},
            {"Metal": "Steel",     "USD/gram": round(steel_g, 4)},
        ]
        metal_df = pd.DataFrame(rows)
        st.dataframe(metal_df, use_container_width=True, hide_index=True)

        st.caption("Formulas: Silver = (oz × 32.148 × yield × finishing)/1000; Gold = (oz × 32.148 × purity × finishing)/1000. Defaults match your examples.")

        # Compute final metal cost if weight + chosen metal/purity available
        final_metal_cost = 0.0
        metal_details = {}
        selected_unit_cost = None
        if approx_weight > 0:
            if metal == "Gold":
                if purity_choice == "18K": selected_unit_cost = gold_g_18
                elif purity_choice == "14K": selected_unit_cost = gold_g_14
                elif purity_choice == "10K": selected_unit_cost = gold_g_10
                elif purity_choice == "9K":  selected_unit_cost = gold_g_9
            elif metal == "Silver":
                selected_unit_cost = silver_g
            elif metal == "Brass":
                selected_unit_cost = brass_g
            elif metal == "Copper":
                selected_unit_cost = copper_g
            elif metal == "Steel":
                selected_unit_cost = steel_g

            if selected_unit_cost is not None and selected_unit_cost > 0:
                final_metal_cost = approx_weight * selected_unit_cost
                st.metric(f"Approx. Metal Cost ({metal} {purity_choice})", f"US${final_metal_cost:,.2f}")
                metal_details = {
                    "Product Type": prod,
                    "Metal": metal,
                    "Purity": purity_choice,
                    "Plating": plating,
                    "Weight (grams)": approx_weight,
                    "Unit Cost ($/g)": selected_unit_cost,
                    "Total Cost": final_metal_cost,
                }
            else:
                st.warning("Enter valid ounce price(s) to calculate the per-gram cost for the selected metal/purity.")

        st.session_state.metal_details = metal_details

        st.markdown("---")
        st.markdown("#### Relative Metal Weights (same volume)")
        if approx_weight > 0:
            # choose base density key
            base_key = purity_choice if metal in ["Gold","Silver"] else metal
            base_density = densities.get(base_key)
            if base_density:
                volume = approx_weight / base_density
                weight_rows = []
                for m, density in densities.items():
                    relative_weight = volume * density
                    weight_rows.append({"Metal": m, "Approx. Weight (grams)": round(relative_weight, 2)})
                weight_df = pd.DataFrame(weight_rows)
                st.dataframe(weight_df, use_container_width=True, hide_index=True)
            else:
                st.info("Select a metal/purity that has a known density to see relative weights.")
        else:
            st.info("Enter approximate weight to see relative weights in other metals.")

        st.download_button(
            "Download metal prices (CSV)",
            metal_df.to_csv(index=False).encode("utf-8"),
            "metal_prices_per_gram.csv",
            "text/csv",
            key="dl_metal_csv"
        )

# -------- Labor (CPF / Setting / Plating) --------
with tab_labor:
    st.subheader("Labor (CPF, Setting & Plating)")
    st.caption("Rates sourced from Standard Labor for JTV – Aug. 2025.")

    # derive counts from selections
    center_qty = (st.session_state.center_details or {}).get("qty", 0) or 0
    side_qty   = sum((d.get("qty",0) for d in st.session_state.side_lines), 0)
    acc_qty    = sum((d.get("qty",0) for d in st.session_state.acc_lines), 0)

    colL, colR = st.columns([1.2, 1.0], gap="large")

    with colL:
        st.markdown("#### Inputs")
        labor_prod = st.selectbox("Product Type for Labor", ["Ring","Earring","Pendant","Necklace","Bracelet","Bangle"], key="lab_prod")

        st.markdown("*CPF (Casting / Polish / Finish)*")
        cpf_base = st.number_input("CPF base (USD per unit)", min_value=0.0, value=0.0, step=0.5, key="cpf_base")
        cpf_weight_factor = st.number_input("CPF weight adder (USD per gram)", min_value=0.0, value=0.0, step=0.1, key="cpf_wt")

        st.markdown("*Setting Costs*")
        set_center = st.number_input("Setting per Center (USD/stone)", min_value=0.0, value=0.0, step=0.5, key="set_center")
        set_side   = st.number_input("Setting per Side (USD/stone)",   min_value=0.0, value=0.0, step=0.25, key="set_side")
        set_acc    = st.number_input("Setting per Accent (USD/stone)", min_value=0.0, value=0.0, step=0.10, key="set_acc")

        st.markdown("*Plating / Misc*")
        plating_flat = st.number_input("Plating flat (USD/unit)", min_value=0.0, value=0.0, step=0.5, key="plating_flat")
        misc_labor   = st.number_input("Misc. labor (USD/unit)", min_value=0.0, value=0.0, step=0.5, key="misc_labor")

        approx_weight_for_labor = st.number_input(
            "Approximate metal weight for labor calc (grams)", min_value=0.0, value=st.session_state.get("approx_weight", 0.0), step=0.1, key="labor_weight"
        )

    with colR:
        st.markdown("#### Derived Counts")
        st.write(f"Center stones: *{center_qty}*")
        st.write(f"Side stones: *{side_qty}*")
        st.write(f"Accents: *{acc_qty}*")

        cpf_total = cpf_base + (cpf_weight_factor * approx_weight_for_labor)
        set_total = (center_qty * set_center) + (side_qty * set_side) + (acc_qty * set_acc)
        labor_total = cpf_total + set_total + plating_flat + misc_labor

        st.metric("CPF Total", f"US${cpf_total:,.2f}")
        st.metric("Setting Total", f"US${set_total:,.2f}")
        st.metric("Plating + Misc", f"US${(plating_flat + misc_labor):,.2f}")
        st.metric("Labor Total", f"US${labor_total:,.2f}")

        st.session_state.labor_totals = {
            "Product": labor_prod,
            "CPF Total": cpf_total,
            "Setting Total": set_total,
            "Plating + Misc": plating_flat + misc_labor,
            "Labor Total": labor_total
        }

# -------- Summary --------
with tab_summary:
    st.subheader("Order Summary")

    # Stone rows
    stone_rows = []
    grand_stone_total = 0.0
    if st.session_state.center_details and st.session_state.center_details["total_cost"] > 0:
        d = st.session_state.center_details
        stone_rows.append({
            "Category": "Center",
            "Stone": d['gem'],
            "Cut": d['cut'],
            "Shape": d['shape'],
            "Size": d['size'],
            "Color": d['color'],
            "Origin": d['country'],
            "Treatment": d['treatment'],
            "Pieces": d['qty'],
            "Unit Price ($)": d['unit_cost'],
            "Total Stone ($)": d['total_cost'],
        })
        grand_stone_total += d['total_cost']

    for d in st.session_state.side_lines:
        if d["total_cost"] > 0:
            stone_rows.append({
                "Category": "Side",
                "Stone": d['gem'],
                "Cut": d['cut'],
                "Shape": d['shape'],
                "Size": d['size'],
                "Color": d['color'],
                "Origin": d['country'],
                "Treatment": d['treatment'],
                "Pieces": d['qty'],
                "Unit Price ($)": d['unit_cost'],
                "Total Stone ($)": d['total_cost'],
            })
            grand_stone_total += d['total_cost']

    for d in st.session_state.acc_lines:
        if d["total_cost"] > 0:
            stone_rows.append({
                "Category": "Accent",
                "Stone": d['gem'],
                "Cut": d['cut'],
                "Shape": d['shape'],
                "Size": d['size'],
                "Color": d['color'],
                "Origin": d['country'],
                "Treatment": d['treatment'],
                "Pieces": d['qty'],
                "Unit Price ($)": d['unit_cost'],
                "Total Stone ($)": d['total_cost'],
            })
            grand_stone_total += d['total_cost']

    if stone_rows:
        stone_df = pd.DataFrame(stone_rows)
        st.markdown("### Stone Summary")
        st.dataframe(stone_df, use_container_width=True, hide_index=True)
    else:
        st.info("No stones have been selected yet.")

    st.markdown("---")

    # Metal summary
    metal_rows = []
    grand_metal_total = 0.0
    if st.session_state.metal_details and st.session_state.metal_details.get("Total Cost", 0) > 0:
        d = st.session_state.metal_details
        metal_rows.append({
            "Category": "Metal",
            "Product": d['Product Type'],
            "Metal": d['Metal'],
            "Purity": d['Purity'],
            "Plating": d['Plating'],
            "Weight (g)": d['Weight (grams)'],
            "Unit Price ($/g)": d['Unit Cost ($/g)'],
            "Total Metal ($)": d['Total Cost'],
        })
        grand_metal_total += d['Total Cost']

    if metal_rows:
        metal_df = pd.DataFrame(metal_rows)
        st.markdown("### Metal Summary")
        st.dataframe(metal_df, use_container_width=True, hide_index=True)
    else:
        st.info("No metal has been calculated yet.")

    st.markdown("---")

    # Labor summary
    labor_rows = []
    grand_labor_total = 0.0
    if st.session_state.labor_totals and st.session_state.labor_totals.get("Labor Total", 0) >= 0:
        lt = st.session_state.labor_totals
        labor_rows.append({
            "Category": "Labor",
            "Product": lt.get("Product",""),
            "CPF Total": lt.get("CPF Total",0.0),
            "Setting Total": lt.get("Setting Total",0.0),
            "Plating + Misc": lt.get("Plating + Misc",0.0),
            "Labor Total": lt.get("Labor Total",0.0)
        })
        grand_labor_total = lt.get("Labor Total",0.0)

    if labor_rows:
        labor_df = pd.DataFrame(labor_rows)
        st.markdown("### Labor Summary")
        st.dataframe(labor_df, use_container_width=True, hide_index=True)
        st.caption("Labor rates per JTV sheet.")
    else:
        st.info("No labor has been entered yet.")

    st.markdown("---")

    # Totals
    grand_total_unit_cost = grand_stone_total + grand_metal_total + grand_labor_total
    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Total Stone Cost", f"${grand_stone_total:,.2f}")
    k2.metric("Total Metal Cost", f"${grand_metal_total:,.2f}")
    k3.metric("Total Labor Cost", f"${grand_labor_total:,.2f}")
    k4.metric("Approx. Total Unit Cost", f"${grand_total_unit_cost:,.2f}")

    st.markdown("---")
    st.info("Disclaimer: These are approximate base costs without selling markup and exclude taxes, freight, and other commercial terms.")

    # Downloads (Excel)
    if stone_rows or metal_rows or labor_rows:
        import io
        @st.cache_data
        def create_xlsx_for_download(stone_df, metal_df, labor_df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                if not stone_df.empty: stone_df.to_excel(writer, sheet_name='Stone Summary', index=False)
                if not metal_df.empty: metal_df.to_excel(writer, sheet_name='Metal Summary', index=False)
                if not labor_df.empty: labor_df.to_excel(writer, sheet_name='Labor Summary', index=False)
            return output.getvalue()

        out_stone = pd.DataFrame(stone_rows)
        out_metal = pd.DataFrame(metal_rows)
        out_labor = pd.DataFrame(labor_rows)
        xlsx_data = create_xlsx_for_download(out_stone, out_metal, out_labor)
        st.download_button(
            label="Download All Summaries (Excel)",
            data=xlsx_data,
            file_name="jewelry_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_all_xlsx"
        )
