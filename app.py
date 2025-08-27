# app.py
import streamlit as st
import pandas as pd
import numpy as np
from math import isfinite

# ---------- Page ----------
st.set_page_config(page_title="Estimator Pro", layout="wide")
st.markdown(
    """
    <style>
      /* compact but readable */
      .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px;}
      .small-help {font-size: 0.85rem; color: #666;}
      div[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums;}
      /* snugger widgets */
      .stSelectbox, .stNumberInput, .stTextInput {margin-bottom: 0.25rem !important;}
      label.css-16idsys, label[data-testid="stWidgetLabel"] {font-size: 0.80rem; margin-bottom: 0.15rem;}
      .pill {background:#f6f9ff;border:1px solid #e3ecff;border-radius:8px;padding:10px 12px;margin-top:.25rem;}
      .mono {font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;}
      .tight {gap: .5rem;}
      .note {font-size:.9rem;color:#666;}
      .caption-tight {margin-top:-6px;color:#7a7a7a;}
      .hdr {font-weight:600;letter-spacing:.2px;color:#334;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Estimator Pro - Metal & Stones BBJ Bangkok Ltd")

st.caption(
    "Build center/side/accent stone lines with **cascading filters** (Gem → Shape → Size → Cut → Color → Country → Treatment), "
    "priced by **average per piece** or **per carat × weight** from your master sheet. Use the **Metal** tab for live per-gram rates."
)

# ---------- Data loading ----------
@st.cache_data
def load_master(xlsx_path="TEST.xlsx", sheet="MCGI_Master_Price"):
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    for c in [
        "Gemstone", "Shape", "Size", "Cut",
        "Color", "Country of Origin", "Stone Treatment",
        "Unit Of Measure", "Price Per Piece US$", "Price Per Carat US$", "Average Weight Per Piece"
    ]:
        if c in df.columns:
            if c in ("Price Per Piece US$", "Price Per Carat US$", "Average Weight Per Piece"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
            else:
                df[c] = df[c].astype(str).str.strip()
    return df

with st.sidebar:
    st.subheader("Data source")
    sheet_name = st.text_input(
        "Excel sheet name", "MCGI_Master_Price", help="Sheet inside TEST.xlsx", key="sheet_name"
    )
    st.caption("If you replace **TEST.xlsx**, the app will reload automatically on the next run.")
    try:
        df = load_master(sheet=sheet_name)
        st.success("Loaded data ✅")
    except Exception as e:
        st.error(f"Failed to load Excel: {e}")
        st.stop()

# ---------- Helpers ----------
def parse_size(s):
    if s is None:
        return None
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
        gem = st.selectbox(
            "Gemstone", gems, index=0,
            key=f"{key_prefix}_gem", help="Gemstone"
        )
    shapes, _, _, _, _, _ = cascade_options(df, gem=gem or None)
    with c2:
        shape = st.selectbox(
            "Shape", [""] + shapes, index=0,
            key=f"{key_prefix}_shape", help="Shape"
        )
    _, sizes, _, _, _, _ = cascade_options(df, gem=gem or None, shape=shape or None)
    with c3:
        size = st.selectbox(
            "Size", [""] + sizes, index=0,
            key=f"{key_prefix}_size", help="Size"
        )

    # Row 2: Cut, Color, Country, Treatment, Qty
    d1, d2, d3, d4, d5 = st.columns([1.2, 1.0, 1.2, 1.2, 0.7], gap="small")
    _, _, cuts, colors, countries, treatments = cascade_options(
        df, gem=gem or None, shape=shape or None, size=size or None
    )
    with d1:
        cut = st.selectbox(
            "Cut", [""] + cuts, index=0,
            key=f"{key_prefix}_cut", help="Cut"
        )
    with d2:
        color = st.selectbox(
            "Color (optional)", ["(any)"] + colors, index=0,
            key=f"{key_prefix}_color", help="Color (optional)"
        )
    with d3:
        country = st.selectbox(
            "Country (optional)", ["(any)"] + countries, index=0,
            key=f"{key_prefix}_country", help="Country of Origin (optional)"
        )
    with d4:
        treatment = st.selectbox(
            "Treatment (optional)", ["(any)"] + treatments, index=0,
            key=f"{key_prefix}_treat", help="Stone Treatment (optional)"
        )
    with d5:
        qty = st.number_input(
            "Pieces", min_value=0, value=1, step=1,
            key=f"{key_prefix}_qty", help="Pieces"
        )

    use_color = None if color == "(any)" else color
    use_country = None if country == "(any)" else country
    use_treat = None if treatment == "(any)" else treatment

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
            item_details["unit_cost"] = cost
            item_details["total_cost"] = total
            item_details["note"] = note
            line1 = (
                f"Price Per Piece: US${cost:,.4f} (Currency) · "
                f"Total Pieces: {qty} · "
                f"**Total Price: US${total:,.4f} (Currency)** "
                f"({note})"
            )
            bits = []
            if avg_row:
                if "Average Price Per Piece US$" in avg_row:
                    bits.append(f"Avg Price per Piece: US${avg_row['Average Price Per Piece US$']:.4f} (Currency)")
                if "Average Price Per Carat US$" in avg_row:
                    bits.append(f"Avg Price Carat: US${avg_row['Average Price Per Carat US$']:.4f} (Currency)")
                if "Average Weight Per Piece" in avg_row:
                    bits.append(f"Avg Wt/pc: {avg_row['Average Weight Per Piece']:.4f} Carats")
            line2 = " · ".join(bits)
            st.success(line1 + ("" if not line2 else "  \n" + line2))
            st.caption(f"Matched rows: {nmatch}")
            with st.expander(f"Preview matched rows ({min(len(preview), 50)} shown)"):
                st.dataframe(preview.head(50))
            return total, item_details
        else:
            st.error(note or "Could not price this line.")
            if len(preview) > 0:
                with st.expander("Matched rows we found (first 50)"):
                    st.dataframe(preview.head(50))
            return 0.0, None
    else:
        st.info("Pick Gemstone → Shape → Size (optional Cut/Color/Country/Treatment) and set Qty.")
        return 0.0, None

# ---------- TABS ----------
tab_center, tab_side, tab_acc, tab_metal, tab_summary = st.tabs(
    ["Center", "Side", "Accents", "Metal", "Summary"]
)

# Initialize session state for all item details
if 'center_details' not in st.session_state: st.session_state.center_details = None
if 'side_lines' not in st.session_state: st.session_state.side_lines = []
if 'acc_lines' not in st.session_state: st.session_state.acc_lines = []
if 'metal_details' not in st.session_state: st.session_state.metal_details = None

with tab_center:
    left, right = st.columns([1.0, 1.0])
    with left:
        center_total, center_meta = line_item(df, "Center Stone", key_prefix="center")
        st.session_state.center_details = center_meta
    with right:
        st.markdown("**Notes (optional, internal)**")
        st.text_area(
            "Notes",
            value="",
            key="notes_center",
            placeholder="Any memo about this center stone…",
            label_visibility="collapsed",
            height=96,
        )

with tab_side:
    st.subheader("Side Stones")
    side_count = st.number_input("How many side stone lines?", min_value=0, max_value=10, value=2, step=1, key="side_lines_count")
    side_tot = 0.0
    st.session_state.side_lines = []
    for i in range(int(side_count)):
        tot, meta = line_item(df, f"Side #{i+1}", key_prefix=f"side_{i+1}")
        side_tot += tot
        if meta:
            st.session_state.side_lines.append(meta)

with tab_acc:
    st.subheader("Accents")
    acc_count = st.number_input("How many accent lines?", min_value=0, max_value=20, value=1, step=1, key="acc_lines_count")
    acc_tot = 0.0
    st.session_state.acc_lines = []
    for i in range(int(acc_count)):
        tot, meta = line_item(df, f"Accent #{i+1}", key_prefix=f"acc_{i+1}")
        acc_tot += tot
        if meta:
            st.session_state.acc_lines.append(meta)

# ---------- METAL CALCULATOR (with optional live prices) ----------
with tab_metal:
    st.subheader("Metal Calculator")

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
                    info = t.fast_info if hasattr(t, "fast_info") else None
                    px = None
                    if info and "last_price" in info.__dict__:
                        px = float(info.last_price)
                    else:
                        hist = t.history(period="1d")
                        if not hist.empty and "Close" in hist.columns:
                            px = float(hist["Close"].iloc[-1])
                    if px and isfinite(px):
                        ounce_prices[m] = px
                live_note.success("Live ounce prices fetched ✅")
            except Exception as e:
                live_note.warning(f"Could not fetch live prices: {e}. You can enter ounce prices manually below.")

    # Main metal UI
    colA, colB = st.columns([1.2, 1.0])

    with colA:
        st.markdown("#### Inputs")
        prod = st.selectbox(
            "Product Type",
            ["Ring", "Earring", "Pendant", "Necklace", "Bracelet", "Bangle"],
            key="m_prod",
        )
        metal = st.selectbox(
            "Metal",
            ["Gold", "Silver", "Copper", "Steel", "Brass"],
            key="m_metal",
        )

        purity_options = []
        if metal == "Gold":
            purity_options = ["18K", "14K", "10K", "9K"]
        elif metal == "Silver":
            purity_options = ["SS925"]
        elif metal in ["Brass", "Copper", "Steel"]:
            purity_options = ["N.A"]

        purity_choice = st.selectbox(
            "Metal Purity",
            purity_options,
            key="m_purity",
        )
        
        if purity_choice == "N.A":
            st.caption("Purity is not applicable for this metal.")

        plating = st.selectbox(
            "Plating",
            ["(None)", "14KY Gold Plating over Silver", "18KY Gold Plating over Silver"],
            key="m_plating",
        )

        st.markdown("**Approximate Metal Weight**")
        approx_weight = st.number_input(
            "Approximate Weight (grams)", min_value=0.0, value=0.0, step=0.1, key="approx_weight"
        )
        
        st.markdown("**Ounce Prices (USD/oz)**")
        st.number_input(
            "Gold (USD/oz)",
            min_value=0.0, step=1.0,
            value=float(ounce_prices["Gold"]) if ounce_prices["Gold"] else 0.0,
            key="oz_gold",
            disabled=(metal != "Gold")
        )
        st.number_input(
            "Silver (USD/oz)",
            min_value=0.0, step=0.1,
            value=float(ounce_prices["Silver"]) if ounce_prices["Silver"] else 0.0,
            key="oz_silver",
            disabled=(metal != "Silver")
        )
        st.number_input(
            "Copper (USD/oz)",
            min_value=0.0, step=0.01,
            value=float(ounce_prices["Copper"]) if ounce_prices["Copper"] else 0.0,
            key="oz_copper",
            disabled=(metal not in ["Brass", "Copper", "Steel"])
        )

        st.markdown("**Factors (you can adjust)**")
        conv_oz_to_g = st.number_input("Ounce → gram factor", value=32.148, step=0.001, key="conv_oz_to_g", disabled=False)
        silver_yield = st.number_input("Silver yield factor", value=0.95, step=0.01, key="silver_yield", disabled=(metal != "Silver"))
        silver_finish = st.number_input("Silver finishing factor", value=1.15, step=0.01, key="silver_finish", disabled=(metal != "Silver"))
        gold_finish = st.number_input("Gold finishing factor", value=1.12, step=0.01, key="gold_finish", disabled=(metal != "Gold"))

        st.markdown("_Gold purities (fraction)_")
        st.number_input("9K purity", value=0.375, step=0.001, key="p9", disabled=(metal != "Gold"))
        st.number_input("10K purity", value=0.417, step=0.001, key="p10", disabled=(metal != "Gold"))
        st.number_input("14K purity", value=0.59, step=0.001, key="p14", disabled=(metal != "Gold"))
        st.number_input("18K purity", value=0.750, step=0.001, key="p18", disabled=(metal != "Gold"))

        st.markdown("_Other baselines_")
        st.number_input("Silver purity (SS925)", value=0.925, step=0.001, key="pss", disabled=(metal != "Silver"))
        brass_from_copper = st.checkbox("Derive Brass price from Copper (0.7 × Copper/gram)", value=True, key="brass_from_cu", disabled=(metal != "Brass"))
        steel_from_copper = st.checkbox("Derive Steel price from Copper (0.5 × Copper/gram)", value=True, key="steel_from_cu", disabled=(metal != "Steel"))

    with colB:
        st.markdown("#### Results")
        densities = {
            "18K": 15.5, "14K": 13.5, "10K": 11.5, "9K": 10.5, "SS925": 10.4,
            "Brass": 8.73, "Copper": 8.96
        }
        
        def per_gram_silver(oz_price, conv_oz_to_g, silver_yield, silver_finish):
            if oz_price <= 0: return None
            return (oz_price * conv_oz_to_g * silver_yield * silver_finish) / 1000.0

        def per_gram_gold(oz_price, conv_oz_to_g, purity, gold_finish):
            if oz_price <= 0: return None
            return (oz_price * conv_oz_to_g * purity * gold_finish) / 1000.0

        def per_gram_copper(oz_price, conv_oz_to_g):
            if oz_price <= 0: return None
            return (oz_price * conv_oz_to_g) / 1000.0
        
        oz_gold = st.session_state.get('oz_gold', 0.0)
        oz_silver = st.session_state.get('oz_silver', 0.0)
        oz_copper = st.session_state.get('oz_copper', 0.0)
        conv_oz_to_g = st.session_state.get('conv_oz_to_g', 32.148)
        silver_yield = st.session_state.get('silver_yield', 0.95)
        silver_finish = st.session_state.get('silver_finish', 1.15)
        gold_finish = st.session_state.get('gold_finish', 1.12)
        gold_p_9k = st.session_state.get('p9', 0.375)
        gold_p_10k = st.session_state.get('p10', 0.417)
        gold_p_14k = st.session_state.get('p14', 0.59)
        gold_p_18k = st.session_state.get('p18', 0.750)
        
        silver_g = per_gram_silver(oz_silver, conv_oz_to_g, silver_yield, silver_finish) if oz_silver else None
        gold_g_9 = per_gram_gold(oz_gold, conv_oz_to_g, gold_p_9k, gold_finish) if oz_gold else None
        gold_g_10 = per_gram_gold(oz_gold, conv_oz_to_g, gold_p_10k, gold_finish) if oz_gold else None
        gold_g_14 = per_gram_gold(oz_gold, conv_oz_to_g, gold_p_14k, gold_finish) if oz_gold else None
        gold_g_18 = per_gram_gold(oz_gold, conv_oz_to_g, gold_p_18k, gold_finish) if oz_gold else None
        copper_g = per_gram_copper(oz_copper, conv_oz_to_g) if oz_copper else None

        brass_from_copper = st.session_state.get("brass_from_cu", True)
        steel_from_copper = st.session_state.get("steel_from_cu", True)

        brass_g = None
        if metal == "Brass" and brass_from_copper and copper_g:
            brass_g = 0.70 * copper_g
        elif metal == "Brass":
            brass_g = st.number_input("Brass (USD/gram)", min_value=0.0, step=0.01, value=0.0, key="brass_manual")

        steel_g = None
        if metal == "Steel" and steel_from_copper and copper_g:
            steel_g = 0.50 * copper_g
        elif metal == "Steel":
            steel_g = st.number_input("Steel (USD/gram)", min_value=0.0, step=0.01, value=0.0, key="steel_manual")


        rows = []
        rows.append({"Metal": "Silver 925", "USD/gram": None if silver_g is None else round(silver_g, 4)})
        rows.append({"Metal": "Gold 9K", "USD/gram": None if gold_g_9 is None else round(gold_g_9, 4)})
        rows.append({"Metal": "Gold 10K", "USD/gram": None if gold_g_10 is None else round(gold_g_10, 4)})
        rows.append({"Metal": "Gold 14K", "USD/gram": None if gold_g_14 is None else round(gold_g_14, 4)})
        rows.append({"Metal": "Gold 18K", "USD/gram": None if gold_g_18 is None else round(gold_g_18, 4)})
        rows.append({"Metal": "Copper", "USD/gram": None if copper_g is None else round(copper_g, 4)})
        rows.append({"Metal": "Brass", "USD/gram": None if brass_g is None else round(brass_g, 4)})
        rows.append({"Metal": "Steel", "USD/gram": None if steel_g is None else round(steel_g, 4)})

        metal_df = pd.DataFrame(rows)
        st.dataframe(metal_df, use_container_width=True)

        st.caption(
            "Formulas: Silver = (oz × 32.148 × yield × finishing) / 1000 ; "
            "Gold = (oz × 32.148 × purity × finishing) / 1000 — defaults match your examples (14K purity 0.59, finishing 1.12; Silver yield 0.95, finishing 1.15)."
        )

        final_metal_cost = 0.0
        metal_details = {}
        if approx_weight > 0 and metal and purity_choice:
            current_metal_gram_cost = None
            if metal == "Gold":
                if purity_choice == "18K": current_metal_gram_cost = gold_g_18
                elif purity_choice == "14K": current_metal_gram_cost = gold_g_14
                elif purity_choice == "10K": current_metal_gram_cost = gold_g_10
                elif purity_choice == "9K": current_metal_gram_cost = gold_g_9
            elif metal == "Silver": current_metal_gram_cost = silver_g
            elif metal == "Brass": current_metal_gram_cost = brass_g
            elif metal == "Copper": current_metal_gram_cost = copper_g
            elif metal == "Steel": current_metal_gram_cost = steel_g

            if current_metal_gram_cost is not None:
                final_metal_cost = approx_weight * current_metal_gram_cost
                st.metric(f"Approximate Metal Cost ({metal}, {purity_choice})", f"US${final_metal_cost:,.2f}")
                metal_details = {
                    "Product Type": prod,
                    "Metal": metal,
                    "Purity": purity_choice,
                    "Weight (grams)": approx_weight,
                    "Unit Cost ($/g)": current_metal_gram_cost,
                    "Total Cost": final_metal_cost,
                }
            else:
                st.warning("Please provide a valid ounce price to calculate the metal cost.")

        st.session_state.metal_details = metal_details

        st.markdown("---")
        st.markdown("#### Relative Metal Weights")
        if approx_weight > 0 and metal and purity_choice:
            base_metal_key = purity_choice if metal in ["Gold", "Silver"] else metal
            base_density = densities.get(base_metal_key)
            if base_density is not None:
                volume = approx_weight / base_density
                weight_rows = []
                for m, density in densities.items():
                    relative_weight = volume * density
                    weight_rows.append({"Metal": m, "Approx. Weight (grams)": round(relative_weight, 2)})
                weight_df = pd.DataFrame(weight_rows)
                st.dataframe(weight_df, use_container_width=True)
            else:
                st.warning("Could not find density for selected base metal to calculate relative weights.")
        else:
            st.info("Enter an approximate weight to see relative weights in other metals.")

        st.download_button(
            "Download metal prices (CSV)",
            metal_df.to_csv(index=False).encode("utf-8"),
            "metal_prices_per_gram.csv",
            "text/csv",
            key="dl_metal_csv"
        )

# ---------- SUMMARY (Now the last tab) ----------
with tab_summary:
    grand_stone_total = 0.0
    
    st.subheader("Order Summary")

    # Display Center Stone Details
    if st.session_state.center_details and st.session_state.center_details["total_cost"] > 0:
        st.markdown("#### Center Stone")
        details = st.session_state.center_details
        st.write(f"**Gemstone:** {details['gem']}  \n**Shape:** {details['shape']}  \n**Size:** {details['size']}  \n**Pieces:** {details['qty']}  \n**Cost:** ${details['total_cost']:,.2f}")
        grand_stone_total += details['total_cost']
        st.markdown("---")

    # Display Side Stones Details
    if st.session_state.side_lines:
        st.markdown("#### Side Stones")
        for i, details in enumerate(st.session_state.side_lines):
            if details["total_cost"] > 0:
                st.write(f"**Side Stone #{i+1}**")
                st.write(f"**Gemstone:** {details['gem']}  \n**Shape:** {details['shape']}  \n**Size:** {details['size']}  \n**Pieces:** {details['qty']}  \n**Cost:** ${details['total_cost']:,.2f}")
                grand_stone_total += details['total_cost']
                if i < len(st.session_state.side_lines) - 1:
                    st.markdown("---")
        st.markdown("---")

    # Display Accent Details
    if st.session_state.acc_lines:
        st.markdown("#### Accents")
        for i, details in enumerate(st.session_state.acc_lines):
            if details["total_cost"] > 0:
                st.write(f"**Accent #{i+1}**")
                st.write(f"**Gemstone:** {details['gem']}  \n**Shape:** {details['shape']}  \n**Size:** {details['size']}  \n**Pieces:** {details['qty']}  \n**Cost:** ${details['total_cost']:,.2f}")
                grand_stone_total += details['total_cost']
                if i < len(st.session_state.acc_lines) - 1:
                    st.markdown("---")
        st.markdown("---")

    # Display Metal Details
    grand_metal_total = 0.0
    if st.session_state.metal_details and st.session_state.metal_details["Total Cost"] > 0:
        st.markdown("#### Metal")
        details = st.session_state.metal_details
        st.write(f"**Product Type:** {details['Product Type']}  \n**Metal:** {details['Metal']}  \n**Purity:** {details['Purity']}  \n**Weight:** {details['Weight (grams)']}g  \n**Cost:** ${details['Total Cost']:,.2f}")
        grand_metal_total = details['Total Cost']
        st.markdown("---")

    grand_total_unit_cost = grand_stone_total + grand_metal_total

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Stone Cost", f"${grand_stone_total:,.2f}")
    k2.metric("Total Metal Cost", f"${grand_metal_total:,.2f}")
    k3.metric("Approximate Total Unit Cost", f"${grand_total_unit_cost:,.2f}")

    st.markdown("---")
    st.info("Disclaimer: These are approximate base costs without markup, CPF, setting, and plating costs.")

    summary_data = {
        "Total_Stone_Cost": grand_stone_total,
        "Total_Metal_Cost": grand_metal_total,
        "Approximate_Total_Unit_Cost": grand_total_unit_cost,
    }

    # Add detailed breakdown to a DataFrame for download
    breakdown_rows = []
    if st.session_state.center_details and st.session_state.center_details["total_cost"] > 0:
        d = st.session_state.center_details
        breakdown_rows.append({
            "Category": "Center Stone",
            "Gemstone": d['gem'],
            "Shape": d['shape'],
            "Size": d['size'],
            "Qty": d['qty'],
            "Unit_Cost": d['unit_cost'],
            "Total_Cost": d['total_cost']
        })
    if st.session_state.side_lines:
        for d in st.session_state.side_lines:
            if d["total_cost"] > 0:
                breakdown_rows.append({
                    "Category": "Side Stone",
                    "Gemstone": d['gem'],
                    "Shape": d['shape'],
                    "Size": d['size'],
                    "Qty": d['qty'],
                    "Unit_Cost": d['unit_cost'],
                    "Total_Cost": d['total_cost']
                })
    if st.session_state.acc_lines:
        for d in st.session_state.acc_lines:
            if d["total_cost"] > 0:
                breakdown_rows.append({
                    "Category": "Accent",
                    "Gemstone": d['gem'],
                    "Shape": d['shape'],
                    "Size": d['size'],
                    "Qty": d['qty'],
                    "Unit_Cost": d['unit_cost'],
                    "Total_Cost": d['total_cost']
                })
    if st.session_state.metal_details and st.session_state.metal_details["Total Cost"] > 0:
        d = st.session_state.metal_details
        breakdown_rows.append({
            "Category": "Metal",
            "Metal": d['Metal'],
            "Purity": d['Purity'],
            "Weight": d['Weight (grams)'],
            "Unit_Cost_per_gram": d['Unit Cost ($/g)'],
            "Total_Cost": d['Total Cost']
        })

    if breakdown_rows:
        breakdown_df = pd.DataFrame(breakdown_rows)
        st.download_button(
            "Download detailed breakdown (CSV)",
            breakdown_df.to_csv(index=False).encode("utf-8"),
            "cost_breakdown.csv",
            "text/csv",
            key="dl_breakdown_csv"
        )

    summary_df = pd.DataFrame([summary_data])
    st.download_button(
        "Download summary (CSV)",
        summary_df.to_csv(index=False).encode("utf-8"),
        "total_cost_summary.csv",
        "text/csv",
        key="dl_summary_csv"
    )
