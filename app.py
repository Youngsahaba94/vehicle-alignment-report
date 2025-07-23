import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="🚚 Vehicle Daily Report Generator", page_icon="🚚")
st.title("🚚 Vehicle Daily Report Generator (Accurate Merge)")

uploaded_file = st.file_uploader("📤 Upload 'master_vehicle_database_alignment.xlsx'", type="xlsx")

# =====================
# Helper functions
# =====================

def clean_license(license_number):
    if not isinstance(license_number, str):
        return license_number
    if license_number.endswith("C") or (license_number.endswith("T") and not license_number.endswith("THT")):
        return license_number[:-1]
    return license_number

def is_body(vehicle_id):
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

# =====================
# Main processing
# =====================

def generate_matched_df(master_df, branch_df):
    required_cols = {'Vehicle#', 'License', 'Route'}
    if not required_cols.issubset(master_df.columns):
        raise ValueError("Missing required columns in 'master vehicle list' sheet.")
    if 'License' not in branch_df.columns:
        raise ValueError("Missing 'License' column in branch sheet.")

    # Process master data
    master_df['is_body'] = master_df['Vehicle#'].apply(is_body)
    master_df['CleanLicense'] = master_df['License'].apply(clean_license)
    master_df['CleanVehicle#'] = master_df.apply(lambda row: clean_vehicle_id(row['Vehicle#'], row['is_body']), axis=1)

    # Separate tractors and bodies
    tractors = master_df[~master_df['is_body']][['CleanLicense', 'CleanVehicle#', 'Route']].drop_duplicates()
    bodies = master_df[master_df['is_body']][['CleanLicense', 'CleanVehicle#']].drop_duplicates()

    # Clean branch license column
    branch_df = branch_df.copy()
    branch_df['CleanLicense'] = branch_df['License'].apply(clean_license)

    # Merge Tractors
    merged = pd.merge(
        branch_df[['License', 'CleanLicense']],
        tractors,
        on='CleanLicense',
        how='left'
    ).rename(columns={'CleanVehicle#': 'Tractor'})

    # Merge Bodies
    merged = pd.merge(
        merged,
        bodies,
        on='CleanLicense',
        how='left'
    ).rename(columns={'CleanVehicle#': 'Body'})

    # Add condition flags
    merged['has_both'] = merged['Tractor'].notna() & merged['Body'].notna()
    merged['only_tractor'] = merged['Tractor'].notna() & merged['Body'].isna()
    merged['only_body'] = merged['Tractor'].isna() & merged['Body'].notna()

    # Add default alignment fields
    merged['Action'] = "Vehicle to be presented at Tyre-Bay"
    merged['Remark'] = "Vehicle not yet Presented"
    merged['Date Aligned'] = ""

    # Arrange final columns
    final = merged[['Tractor', 'Body', 'License', 'Route', 'Action', 'Remark', 'Date Aligned']]

    # Reorder based on conditions
    if all(col in merged.columns for col in ['has_both', 'only_tractor', 'only_body']):
        final = pd.concat([
            final[merged['has_both']],
            final[merged['only_tractor']],
            final[merged['only_body']]
        ])
    
    return final.reset_index(drop=True)

# =====================
# Streamlit UI
# =====================

if uploaded_file:
    try:
        xl = pd.ExcelFile(uploaded_file)
        required_sheets = ['master vehicle list', 'Obajana', 'Ibese']
        
        if not all(sheet in xl.sheet_names for sheet in required_sheets):
            st.error("❌ The Excel file must contain: 'master vehicle list', 'Obajana', and 'Ibese' sheets.")
        else:
            master_df = xl.parse('master vehicle list')
            obajana_df = xl.parse('Obajana')
            ibese_df = xl.parse('Ibese')

            obajana_result = generate_matched_df(master_df, obajana_df)
            ibese_result = generate_matched_df(master_df, ibese_df)

            # Save results to Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                obajana_result.to_excel(writer, sheet_name='Obajana Result', index=False)
                ibese_result.to_excel(writer, sheet_name='Ibese Result', index=False)

                # Freeze top row
                for sheet in writer.book.worksheets:
                    sheet.freeze_panes = "A2"

            st.success("✅ Report generated successfully!")

            st.download_button(
                label="📥 Download Final Report",
                data=output.getvalue(),
                file_name=f"vehicle_alignment_report_{datetime.now().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ An error occurred: {e}")