import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Vehicle Daily Report Generator", page_icon="🚚")
st.title("🚚 Vehicle Daily Report Generator (with Route and Smart Save)")

uploaded_file = st.file_uploader("📤 Upload 'master_vehicle_database_alignment.xlsx'", type="xlsx")

# === Helper functions ===

def clean_license(license_number):
    if not isinstance(license_number, str):
        return license_number
    if license_number.endswith("C") or (license_number.endswith("T") and not license_number.endswith("THT")):
        return license_number[:-1]
    return license_number

def is_body(vehicle_id, license_number):
    if not isinstance(vehicle_id, str):
        return False
    return (
        vehicle_id.endswith("T") or
        vehicle_id.endswith("CHT") or
        vehicle_id.endswith("THT") or
        vehicle_id.startswith("DT")
    )

def clean_vehicle_id(vehicle_id, is_body_flag):
    if not isinstance(vehicle_id, str):
        return vehicle_id
    if is_body_flag and vehicle_id.endswith("T") and not vehicle_id.endswith("THT"):
        return vehicle_id[:-1]
    return vehicle_id

# === Core processing function ===

def generate_matched_df(master_df, branch_df):
    # Validate required columns
    if 'Vehicle#' not in master_df.columns or 'License' not in master_df.columns or 'Route' not in master_df.columns:
        raise ValueError("Sheet 'master vehicle list' must contain 'Vehicle#', 'License', and 'Route' columns.")
    if 'License' not in branch_df.columns:
        raise ValueError("Branch sheet must contain 'License' column.")

    # Process master vehicle list
    master_df['is_body'] = master_df.apply(lambda row: is_body(row['Vehicle#'], row['License']), axis=1)
    master_df['CleanLicense'] = master_df['License'].apply(clean_license)
    master_df['CleanVehicle#'] = master_df.apply(lambda row: clean_vehicle_id(row['Vehicle#'], row['is_body']), axis=1)

    # Separate tractors and bodies
    tractors = master_df[~master_df['is_body']].copy()
    bodies = master_df[master_df['is_body']].copy()

    # Clean branch license numbers
    branch_df['CleanLicense'] = branch_df['License'].apply(clean_license)

    # Merge tractors
    merged = pd.merge(
        branch_df[['CleanLicense']],
        tractors[['CleanLicense', 'CleanVehicle#', 'Route']],
        on='CleanLicense',
        how='left'
    ).rename(columns={'CleanVehicle#': 'Tractor'})

    if 'Tractor' not in merged.columns:
        merged['Tractor'] = None
    if 'Route' not in merged.columns:
        merged['Route'] = None

    # Merge bodies
    merged = pd.merge(
        merged,
        bodies[['CleanLicense', 'CleanVehicle#']],
        on='CleanLicense',
        how='left'
    ).rename(columns={'CleanVehicle#': 'Body'})

    if 'Body' not in merged.columns:
        merged['Body'] = None

    # Add status flags
    merged['has_both'] = merged['Tractor'].notna() & merged['Body'].notna()
    merged['only_tractor'] = merged['Tractor'].notna() & merged['Body'].isna()
    merged['only_body'] = merged['Tractor'].isna() & merged['Body'].notna()

    # Add final columns
    merged['Action'] = "Vehicle to be presented at Tyre-Bay"
    merged['Remark'] = "Vehicle not yet Presented"
    merged['Date Aligned'] = ""

    merged = merged[['Tractor', 'Body', 'CleanLicense', 'Route', 'Action', 'Remark', 'Date Aligned']]
    merged = merged.rename(columns={'CleanLicense': 'License'})

    # ✅ Sort result by condition
    if all(col in merged.columns for col in ['has_both', 'only_tractor', 'only_body']):
        return pd.concat([
            merged[merged['has_both']],
            merged[merged['only_tractor']],
            merged[merged['only_body']]
        ])
    else:
        return merged

# === Streamlit Interface ===

if uploaded_file:
    try:
        xl = pd.ExcelFile(uploaded_file)
        sheets_needed = ['master vehicle list', 'Obajana', 'Ibese']

        if not all(sheet in xl.sheet_names for sheet in sheets_needed):
            st.error("❌ One or more required sheets are missing: 'master vehicle list', 'Obajana', 'Ibese'")
        else:
            master_df = xl.parse('master vehicle list')
            obajana_df = xl.parse('Obajana')
            ibese_df = xl.parse('Ibese')

            obajana_result = generate_matched_df(master_df, obajana_df)
            ibese_result = generate_matched_df(master_df, ibese_df)

            # Write to Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                obajana_result.to_excel(writer, sheet_name='Obajana Result', index=False)
                ibese_result.to_excel(writer, sheet_name='Ibese Result', index=False)

                for sheet in writer.book.worksheets:
                    sheet.freeze_panes = "A2"

            st.success("✅ Report generated successfully!")

            st.download_button(
                label="📥 Download Result Excel",
                data=output.getvalue(),
                file_name=f"alignment_result_{datetime.now().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ An error occurred: {e}")