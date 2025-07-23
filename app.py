import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="Vehicle Alignment Report", page_icon="🚚")
st.title("🚚 Vehicle Daily Report Generator (Web Version)")

uploaded_file = st.file_uploader("Upload master_vehicle_database_alignment.xlsx", type="xlsx")

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

def def generate_matched_df(master_df, branch_df):
    master_df['is_body'] = master_df.apply(lambda row: is_body(row['Vehicle#'], row['License']), axis=1)
    master_df['CleanLicense'] = master_df['License'].apply(clean_license)
    master_df['CleanVehicle#'] = master_df.apply(lambda row: clean_vehicle_id(row['Vehicle#'], row['is_body']), axis=1)

    tractors = master_df[~master_df['is_body']].copy()
    bodies = master_df[master_df['is_body']].copy()

    branch_df['CleanLicense'] = branch_df['License'].apply(clean_license)

    merged = pd.merge(
        tractors[['CleanLicense', 'CleanVehicle#', 'Route']],
        branch_df[['CleanLicense']],
        on='CleanLicense',
        how='right'
    ).rename(columns={'CleanVehicle#': 'Tractor', 'Route': 'Route'})

    if 'Tractor' not in merged.columns:
        merged['Tractor'] = None
    if 'Route' not in merged.columns:
        merged['Route'] = None

    merged = pd.merge(
        merged,
        bodies[['CleanLicense', 'CleanVehicle#']],
        on='CleanLicense',
        how='left'
    ).rename(columns={'CleanVehicle#': 'Body'})

    if 'Body' not in merged.columns:
        merged['Body'] = None

    # Safely create indicators
    merged['has_both'] = merged['Tractor'].notna() & merged['Body'].notna()
    merged['only_tractor'] = merged['Tractor'].notna() & merged['Body'].isna()
    merged['only_body'] = merged['Tractor'].isna() & merged['Body'].notna()

    merged['Action'] = "Vehicle to be presented at Tyre-Bay"
    merged['Remark'] = "Vehicle not yet Presented"
    merged['Date Aligned'] = ""

    merged = merged[['Tractor', 'Body', 'CleanLicense', 'Route', 'Action', 'Remark', 'Date Aligned']]
    merged = merged.rename(columns={'CleanLicense': 'License'})

    # Return in order: both → only tractor → only body
    return pd.concat([
        merged[merged['has_both']],
        merged[merged['only_tractor']],
        merged[merged['only_body']]
    ])

if uploaded_file:
    try:
        xl = pd.ExcelFile(uploaded_file)
        required_sheets = ['master vehicle list', 'Obajana', 'Ibese']

        if not all(sheet in xl.sheet_names for sheet in required_sheets):
            st.error("One or more required sheets are missing: 'master vehicle list', 'Obajana', 'Ibese'")
        else:
            master_df = xl.parse('master vehicle list')
            obajana_df = xl.parse('Obajana')
            ibese_df = xl.parse('Ibese')

            obajana_final = generate_matched_df(master_df.copy(), obajana_df.copy())
            ibese_final = generate_matched_df(master_df.copy(), ibese_df.copy())

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                obajana_final.to_excel(writer, sheet_name='Obajana Result', index=False)
                ibese_final.to_excel(writer, sheet_name='Ibese Result', index=False)

            st.success("✅ Report generated successfully!")

            st.download_button(
                label="🔹 Download Processed Report",
                data=output.getvalue(),
                file_name=f"daily_alignment_output_{datetime.today().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"An error occurred: {e}")