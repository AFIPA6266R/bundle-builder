import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Bundle Builder – Stones Only (Cascade + Color + Origin)", layout="wide")
st.title("💎 Bundle Builder – Stones Only")
st.caption("Cascading filters (Gem → Shape → Size → Cut → Color → Country → Treatment) + averaging across all matched rows. The green line always shows Avg $/pc, Avg $/ct, and Avg Wt/pc when available.")

# ---------- Data loading ----------
@st.cache_data
def load_master(xlsx_path="TEST.xlsx", sheet="MCGI_Master_Price"):
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    # Normalize key text columns
    for c in [
        "Gemstone", "Shape", "Size", "Cut",
        "Color", "Country of Origin", "Stone Treatment",
        "Unit Of Measure"
    ]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df

df = load_master()

# ---------- Helpers ----------
def parse_size(s):
    if s is None:
        return None
    s = str(s).strip().lower().replace(" ", "")
    s = s.replace("mm", "")
    return s

def uniq(series):
    """Return sorted unique non-empty strings from a Series."""
    return sorted([x for x in series.dropna().astype(str).unique() if str(x).strip() != ""])

def cascade_options(df, gem=None, shape=None, size=None, cut=None):
    """
    Return cascaded option lists for size/cut/color/origin/treatment
    based on current selections (gem, shape, size, cut).
    """
    base = df.copy()

    if gem:
        base = base[base["Gemstone"].str.lower() == gem.strip().lower()]

    # Shapes available within selected gem (or whole set if no gem)
    shapes = uniq(base["Shape"]) if "Shape" in base.columns else []

    # Sizes depend on gem+shape
    base2 = base.copy()
    if shape:
        base2 = base2[base2["Shape"].str.lower() == shape.strip().lower()]
    sizes = uniq(base2["Size"]) if "Size" in base2.columns else []

    # Cuts depend on gem+shape+(size optional)
    base3 = base2.copy()
    if size:
        key = parse_size(size)
        base3 = base3[base3["Size"].map(parse_size) == key]
    cuts = uniq(base3["Cut"]) if "Cut" in base3.columns else []

    # Colors depend on gem+shape+size+cut(optional)
    base4 = base3.copy()
    if cut and "Cut" in base4.columns:
        base4_exact = base4[base4["Cut"].str.lower() == cut.strip().lower()]
        if len(base4_exact) > 0:
            base4 = base4_exact
    colors = uniq(base4["Color"]) if "Color" in base4.columns else []

    # Countries depend on gem+shape+size+cut+color(optional)
    base5 = base4.copy()
    countries = uniq(base5["Country of Origin"]) if "Country of Origin" in base5.columns else []
    treatments = uniq(base5["Stone Treatment"]) if "Stone Treatment" in base5.columns else []

    return shapes, sizes, cuts, colors, countries, treatments

def avg_price_lookup(df, gem, shape, size, cut=None, color=None, country=None, treatment=None):
    """
    Compute unit cost using either:
      - average Price Per Piece US$, or
      - (average Price Per Carat US$) × (average Average Weight Per Piece)
    across all matched rows after applying all selected filters.

    Returns: unit_cost, note, avg_row_dict (always includes any available averages),
             match_count, preview_df
    """
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
        if len(qq) > 0:
            q = qq
    if color and "Color" in q.columns:
        qq = q[q["Color"].str.lower() == str(color).strip().lower()]
        if len(qq) > 0:
            q = qq
    if country and "Country of Origin" in q.columns:
        qq = q[q["Country of Origin"].str.lower() == str(country).strip().lower()]
        if len(qq) > 0:
            q = qq
    if treatment and "Stone Treatment" in q.columns:
        qq = q[q["Stone Treatment"].str.lower() == str(treatment).strip().lower()]
        if len(qq) > 0:
            q = qq

    if len(q) == 0:
        return None, "No exact match. Adjust filters (Gem/Shape/Size/Cut/Color/Country/Treatment).", None, 0, q

    # Means (we'll report all available, regardless of which pricing mode is used)
    mean_ppp = q["Price Per Piece US$"].dropna().astype(float).mean() if "Price Per Piece US$" in q.columns else np.nan
    mean_ppc = q["Price Per Carat US$"].dropna().astype(float).mean() if "Price Per Carat US$" in q.columns else np.nan
    mean_awp = q["Average Weight Per Piece"].dropna().astype(float).mean() if "Average Weight Per Piece" in q.columns else np.nan

    avg_row = {}
    if pd.notna(mean_ppp):
        avg_row["Average Price Per Piece US$"] = float(mean_ppp)
    if pd.notna(mean_ppc):
        avg_row["Average Price Per Carat US$"] = float(mean_ppc)
    if pd.notna(mean_awp):
        avg_row["Average Weight Per Piece"] = float(mean_awp)

    # Decide pricing path
    if pd.notna(mean_ppp):
        unit_cost = float(mean_ppp)
        note = f"Used average Price Per Piece across {len(q)} match(es)"
    elif pd.notna(mean_ppc) and pd.notna(mean_awp):
        unit_cost = float(mean_ppc) * float(mean_awp)
        note = f"Used (average Price/ct × average Weight) across {len(q)} match(es)"
    else:
        return None, "No usable pricing (need Price/pc OR (Price/ct & Avg Weight)).", avg_row if avg_row else None, len(q), q

    return unit_cost, note, avg_row if avg_row else None, len(q), q

# ---------- UI ----------
def line_item(df, label):
    st.markdown(f"#### {label}")

    # Step 1: GEM
    gems = [""] + uniq(df["Gemstone"])
    gem = st.selectbox(f"{label} – Gemstone", gems, index=0, key=f"{label}_gem")

    # Step 2: SHAPE (depends on gem)
    shapes, sizes_all, cuts_all, colors_all, countries_all, trts_all = cascade_options(df, gem=gem or None)
    shapes = [""] + shapes
    shape = st.selectbox(f"{label} – Shape", shapes, index=0, key=f"{label}_shape")

    # Step 3: SIZE (depends on gem+shape)
    _, sizes, cuts_all2, colors_all2, countries_all2, trts_all2 = cascade_options(df, gem=gem or None, shape=shape or None)
    sizes = [""] + sizes
    size = st.selectbox(f"{label} – Size", sizes, index=0, key=f"{label}_size")

    # Step 4: CUT/COLOR/COUNTRY/TREATMENT (depend on gem+shape+size)
    _, _, cuts, colors, countries, treatments = cascade_options(df, gem=gem or None, shape=shape or None, size=size or None)
    cuts = [""] + cuts
    cut = st.selectbox(f"{label} – Cut", cuts, index=0, key=f"{label}_cut")

    color_choices = ["(any)"] + colors
    color = st.selectbox(f"{label} – Color (optional)", color_choices, index=0, key=f"{label}_color")

    country_choices = ["(any)"] + countries
    country = st.selectbox(f"{label} – Country of Origin (optional)", country_choices, index=0, key=f"{label}_country")

    trt_choices = ["(any)"] + treatments
    treatment = st.selectbox(f"{label} – Treatment (optional)", trt_choices, index=0, key=f"{label}_trt")

    qty = st.number_input(f"{label} – Pieces", min_value=0, value=1, step=1, key=f"{label}_qty")

    use_color = None if color == "(any)" else color
    use_country = None if country == "(any)" else country
    use_treat = None if treatment == "(any)" else treatment

    if qty > 0 and gem and shape and size:
        cost, note, avg_row, nmatch, preview = avg_price_lookup(
            df, gem, shape, size,
            cut or None, use_color, use_country, use_treat
        )
        if cost is not None:
            total = cost * qty
            details = f"Unit cost: ${cost:,.4f}  •  Qty: {qty}  •  **Total: ${total:,.4f}**  ({note})"

            # Always show any available averages (even if pricing used $/pc)
            extra_bits = []
            if avg_row:
                if "Average Price Per Piece US$" in avg_row:
                    extra_bits.append(f"Avg $/pc: {avg_row['Average Price Per Piece US$']:.4f}")
                if "Average Price Per Carat US$" in avg_row:
                    extra_bits.append(f"Avg $/ct: {avg_row['Average Price Per Carat US$']:.4f}")
                if "Average Weight Per Piece" in avg_row:
                    extra_bits.append(f"Avg Wt/pc: {avg_row['Average Weight Per Piece']:.4f}")
            if extra_bits:
                details += "  •  " + "  •  ".join(extra_bits)

            st.success(details)
            st.caption(f"Matched rows: {nmatch}")
            with st.expander(f"Preview matched rows ({min(len(preview), 50)} shown)"):
                st.dataframe(preview.head(50))

            return total, {
                "gem": gem, "shape": shape, "size": size, "cut": cut or "",
                "color": use_color, "country": use_country, "treatment": use_treat,
                "qty": qty, "unit_cost": cost, "note": note, "matches": nmatch
            }

        else:
            st.error(note or "Could not price this line.")
            if len(preview) > 0:
                with st.expander("Matched rows we found (first 50)"):
                    st.dataframe(preview.head(50))
            return 0.0, None
    else:
        st.info("Pick Gemstone → Shape → Size (then optional Cut/Color/Country/Treatment) and set Qty.")
        return 0.0, None

st.caption("Pricing source: MCGI_Master_Price (TEST.xlsx). Each dropdown narrows to valid choices from your data. Color & Country affect pricing when selected.")

# Center
center_total, center_meta = line_item(df, "Center Stone")

# Side stones
st.divider()
st.subheader("Side Stones")
side_count = st.number_input("How many side stone lines?", min_value=0, max_value=10, value=2, step=1)
side_tot = 0.0
side_lines = []
for i in range(int(side_count)):
    tot, meta = line_item(df, f"Side #{i+1}")
    side_tot += tot
    if meta:
        side_lines.append(meta)

# Accents
st.divider()
st.subheader("Accents")
acc_count = st.number_input("How many accent lines?", min_value=0, max_value=20, value=1, step=1)
acc_tot = 0.0
acc_lines = []
for i in range(int(acc_count)):
    tot, meta = line_item(df, f"Accent #{i+1}")
    acc_tot += tot
    if meta:
        acc_lines.append(meta)

# Summary
st.divider()
grand = center_total + side_tot + acc_tot
k1,k2,k3,k4 = st.columns(4)
k1.metric("Center Stones", f"${center_total:,.4f}")
k2.metric("Side Stones", f"${side_tot:,.4f}")
k3.metric("Accents", f"${acc_tot:,.4f}")
k4.metric("Total Stone Cost", f"${grand:,.4f}")

summary_df = pd.DataFrame([{
    "center_total": center_total,
    "side_total": side_tot,
    "acc_total": acc_tot,
    "grand_total": grand
}])
st.download_button(
    "Download bundle breakdown (CSV)",
    summary_df.to_csv(index=False).encode("utf-8"),
    "bundle_cost_summary.csv",
    "text/csv"
)