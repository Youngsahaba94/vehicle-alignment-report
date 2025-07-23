import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="🚚 Vehicle Daily Report Generator", page_icon="🚚")
st.title("🚚 Vehicle Daily Report Generator (with Route and Smart Merge)")

uploaded_file = st.file_uploader("📤 Upload 'master_vehicle_database_alignment.xlsx'", type="xlsx")

# ============================
# Helper Functions
# ============================

def clean_license(license_number):
    if not isinstance(license_number, str):
        return license_number
    if license_number.endswith("C") or (license_number.endswith("T") and not license_number.endswith("THT")):
        return license_number[:-1]
    return license_number

def is_body_id(vehicle_id):
    if not isinstance(vehicle_id, str):
        return False
    return (
        vehicle_id.endswith("T") or
        vehicle_id.endswith("CHT") or
        vehicle_id.endswith("THT") or
        vehicle_id.startswith("DT")
    )

def clean_vehicle_id(vehicle_id):
    if not isinstance(vehicle_id, str):
        return vehicle_id
    if vehicle_id.endswith("T") and not vehicle_id.endswith("THT"):
        return vehicle_id[:-1]
    return vehicle_id

def generate_branch_output(master_df, branch_df):
    branch_df = branch_df.copy()
    branch_df['CleanLicense'] = branch_df['License'].apply(clean_license)
    unique_licenses = branch_df['CleanLicense'].dropna().unique()

    # Tag and clean master list
    master_df['is_body'] = master_df['Vehicle#'].apply(is_body_id)
    master_df['CleanLicense'] = master_df['License'].apply(clean_license)
    master_df['CleanVehicle'] = master_df.apply(lambda row: clean_vehicle_id(row['Vehicle#']) if row['is_body'] else row['Vehicle#'], axis=1)

    # Extract Tractor and Body data
    tractors = master_df[~master_df['is_body']][['CleanLicense', 'CleanVehicle', 'Route']].drop_duplicates()
    bodies = master_df[master_df['is_body']][['CleanLicense', 'CleanVehicle']].drop_duplicates()

    final_rows = []
    for lic in unique_licenses:
        tractor = tractors[tractors['CleanLicense'] == lic]
        body = bodies[bodies['CleanLicense'] == lic]

        tractor_id = tractor['CleanVehicle'].values[0] if not tractor.empty else ""
        body_id = body['CleanVehicle'].values[0] if not body.empty else ""
        route = tractor['Route'].values[0] if not tractor.empty else ""

        final_rows.append({
            "Tractor": tractor_id,
            "Body": body_id,
            "License": lic,
            "Route": route,
            "Action": "Vehicle to be presented at Tyre-Bay",
            "Remark": "Vehicle not yet Presented",
            "Date Aligned": ""
        })

    df_final = pd.DataFrame(final_rows)

    # Order: both → only Tractor → only Body
    df_final["has_both"] = df_final["Tractor"].ne("") & df_final["Body"].ne("")
    df_final["only_tractor"] = df_final["Tractor"].ne("") & df_final["Body"].eq("")
    df_final["only_body"] = df_final["Tractor"].eq("") & df_final["Body"].ne("")

    df_sorted = pd.concat([
        df_final[df_final["has_both"]],
        df_final[df_final["only_tractor"]],
        df_final[df_final["only_body"]]
    ])

    return df_sorted.drop(columns=["has_both", "only_tractor", "only_body"]).reset_index(drop=True)

# ============================
# Main App Logic
# ============================

if uploaded_file:
    try:
        xl = pd.ExcelFile(uploaded_file)
        required_sheets = ['master vehicle list', 'Obajana', 'Ibese']

        if not all(sheet in xl.sheet_names for sheet in required_sheets):
            st.error("❌ Missing required sheets: 'master vehicle list', 'Obajana', 'Ibese'.")
        else:
            master_df = xl.parse('master vehicle list')
            obajana_df = xl.parse('Obajana')
            ibese_df = xl.parse('Ibese')

            obajana_result = generate_branch_output(master_df, obajana_df)
            ibese_result = generate_branch_output(master_df, ibese_df)

            # Save to Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                obajana_result.to_excel(writer, sheet_name='Obajana Result', index=False)
                ibese_result.to_excel(writer, sheet_name='Ibese Result', index=False)

                # Freeze top rows
                for sheet in writer.book.worksheets:
                    sheet.freeze_panes = sheet["A2"]

            st.success("✅ Report generated successfully!")

            st.download_button(
                label="📥 Download Final Report",
                data=output.getvalue(),
                file_name=f"alignment_report_{datetime.now().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ An error occurred: {e}")