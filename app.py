# app.py
import streamlit as st          # Streamlit: easy web apps in Python
import pandas as pd             # pandas: table (CSV) handling
import numpy as np              # numpy: math functions
import glob, os                 # glob & os: find files in folders
from PIL import Image

# 1) Load every CSV in your data/ folder into a dict of DataFrames
@st.cache_data
def load_normative_tables():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    tables = {}
    for path in csv_files:
        name = os.path.splitext(os.path.basename(path))[0]
        # e.g. "right_kidney_length" → DataFrame from that CSV
        tables[name] = pd.read_csv(path)
    return tables

# 2) Call the function once (cached) so we can reuse it
norms = load_normative_tables()

# --- UI: select organ, enter age & measurement, then compute z-score ---

st.title("Pediatric Organ Size Calculator")

# — Center all buttons below images —
st.markdown(
    """
    <style>
    div.stButton > button {
        margin: auto;
        display: block;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Organ selector via images + button below (reordered & relabeled) ---
# Ensure a default organ is selected
if "selected_organ" not in st.session_state:
    st.session_state.selected_organ = "right_lobe_liver_length"

def select_organ(name):
    st.session_state.selected_organ = name

# 1) Define the exact order and display labels you want:
ordered_organs = [
    "right_lobe_liver_length",
    "spleen_length",
    "right_kidney_length",
    "left_kidney_length"
]
display_names = {
    "right_kidney_length": "Right Kidney",
    "left_kidney_length": "Left Kidney",
    "right_lobe_liver_length": "Liver",
    "spleen_length": "Spleen"
}

st.write("## Select an organ:")
image_dir = os.path.join(os.path.dirname(__file__), "images")
cols = st.columns(len(ordered_organs))

# 2) Loop through your ordered list instead of norms.keys()
for idx, key in enumerate(ordered_organs):
    with cols[idx]:
        img_path = os.path.join(image_dir, f"{key}.png")
        if os.path.exists(img_path):
            img = Image.open(img_path)
            st.image(img, use_container_width=True)
        # Use your short label under each image
        if st.button(display_names[key], key=f"btn_{key}"):
            select_organ(key)

# 3) Show the chosen organ with its clean label
organ_key = st.session_state.selected_organ
st.write(f"**Selected organ:** {display_names[organ_key]}")

# --- Optional: Patient sex ---
sex = st.selectbox(
    "Patient sex (optional):",
    options=["Unknown", "Male", "Female"]
)

# --- Optional: Calculate BSA (Mosteller) in an expander ---
with st.expander("Optional: Body Surface Area (BSA)", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        height_val = st.number_input(
            "Height", min_value=0.0, step=0.1,
            help="Enter height as a number"
        )
        height_unit = st.radio("Height unit:", ("cm", "m"), horizontal=True)
    with col2:
        weight_val = st.number_input(
            "Weight", min_value=0.0, step=0.1,
            help="Enter weight as a number"
        )
        weight_unit = st.radio("Weight unit:", ("kg", "g"), horizontal=True)

    # convert to cm/kg
    if height_unit == "m":
        height_cm = height_val * 100
    else:
        height_cm = height_val

    if weight_unit == "g":
        weight_kg = weight_val / 1000
    else:
        weight_kg = weight_val

    # compute & display BSA
    if height_cm > 0 and weight_kg > 0:
        bsa = np.sqrt((height_cm * weight_kg) / 3600)
        st.write(f"**Body Surface Area:** {bsa:.2f} m²")

# 2) Age input
age_input = st.text_input(
    "Enter patient age (e.g. 2y3m or 27m or 1.5y):",
    value=""
)

# 3) Measurement input
measurement_value = st.number_input(
    "Enter dimension value:",
    min_value=0.0,
    step=0.1
)
unit = st.radio("Unit:", ("cm", "mm"))

# 4) Helper: convert any cm→mm
def to_mm(val, unit):
    return val * 10 if unit == "cm" else val

# 5) Helper: parse age string into a single number of months
def parse_age_to_months(s):
    s = s.strip().lower()
    years = 0.0
    months = 0.0
    if "y" in s:
        parts = s.split("y", 1)
        try:
            years = float(parts[0])
        except:
            years = 0.0
        s = parts[1]
    if "m" in s:
        parts = s.split("m", 1)
        try:
            months = float(parts[0])
        except:
            months = 0.0
    # if no “y” or “m”, assume the whole is months
    if years == 0 and months == 0:
        try:
            months = float(s)
        except:
            months = 0.0
    return years * 12 + months

def format_age_range(min_mo, max_mo):
    """
    Return a human-readable age range:
    - if min_mo >= 24, show in years (e.g. "15.0–16.7 yrs")
    - otherwise, show in months (e.g. "1–3 mo")
    """
    if min_mo >= 24:
        min_yr = min_mo / 12
        max_yr = max_mo / 12
        # one decimal place, drop trailing .0 if you like
        return f"{min_yr:.1f}–{max_yr:.1f} yrs"
    else:
        return f"{int(min_mo)}–{int(max_mo)} mo"

# 6) When user clicks, do the calculation
# --- Compute Z-Score block ---
if st.button("Compute Z-Score"):
    # 1) Parse inputs
    age_months = parse_age_to_months(age_input)
    meas_mm    = to_mm(measurement_value, unit)
    key        = organ_key
    table      = norms[key]

    # 2) Find matching row or fallback
    match = table[
        (table.age_min_months <= age_months) &
        (age_months <= table.age_max_months)
    ]
    if match.empty:
        row = table.iloc[0] if age_months < table.age_min_months.min() else table.iloc[-1]
        st.warning(
            f"Age ({age_input}) out of range. Using data for "
            f"{format_age_range(row.age_min_months, row.age_max_months)}."
        )
    else:
        row = match.iloc[0]

    # 3) Compute and show z-score
    z = (meas_mm - row.mean_mm) / row.sd_mm
    st.write(f"**Z-score:** {z:.2f}")

    # 4) Verdict based on suggested limits
    lower = row.lower_mm
    upper = row.upper_mm

    if meas_mm < lower:
        verdict = "Too small"
    elif meas_mm > upper:
        verdict = "Too large"
    else:
        verdict = "Within normal limits"

    st.write(f"**Interpretation:** {verdict}")

    # 5) (Optional) Show reference stats and limits in chosen unit
    age_label = format_age_range(row.age_min_months, row.age_max_months)
    if unit == "cm":
        mean_disp  = row.mean_mm / 10
        sd_disp    = row.sd_mm   / 10
        lower_disp = lower       / 10
        upper_disp = upper       / 10
    else:
        mean_disp  = row.mean_mm
        sd_disp    = row.sd_mm
        lower_disp = lower
        upper_disp = upper

    # display reference stats
    st.write(
        f"Reference (ages {age_label}): mean = {mean_disp:.2f} {unit}, "
        f"SD = {sd_disp:.2f} {unit}"
    )

    # display the age‐specific suggested limits
    st.write(
        f"**Suggested limits for age {age_input} ({age_label}):** "
        f"{lower_disp:.2f}–{upper_disp:.2f} {unit}"
    )

# — Reference at bottom —
st.markdown("---")  # horizontal rule
st.caption(
    "Normative data from Konus OL et al. AJR. 1998;171(6):984–991. "
    "[Link to article](https://ajronline.org/doi/10.2214/ajr.171.6.9843315)"
)    
