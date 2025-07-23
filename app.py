def generate_branch_output(master_df, branch_df):
    # Clean and prepare master list
    master_df['License'] = master_df['License'].astype(str).str.upper().str.strip()
    master_df['Vehicle#'] = master_df['Vehicle#'].astype(str).str.upper().str.strip()

    master_df['is_body'] = master_df['Vehicle#'].apply(is_body_id)
    master_df['CleanLicense'] = master_df['License'].apply(clean_license)
    master_df['CleanVehicle'] = master_df.apply(lambda row: clean_vehicle_id(row['Vehicle#']) if row['is_body'] else row['Vehicle#'], axis=1)

    # Use Vehicle# from branch (Obajana/Ibese)
    branch_df = branch_df.copy()
    branch_df['Vehicle#'] = branch_df['Vehicle#'].astype(str).str.upper().str.strip()

    # Match branch vehicles to master to get License
    matched_branch = pd.merge(branch_df, master_df[['Vehicle#', 'License']], on='Vehicle#', how='left')
    matched_branch['CleanLicense'] = matched_branch['License'].apply(clean_license)
    unique_licenses = matched_branch['CleanLicense'].dropna().unique()

    # Get Tractor and Body sets
    tractors = master_df[~master_df['is_body']][['CleanLicense', 'CleanVehicle', 'Route']].drop_duplicates()
    bodies = master_df[master_df['is_body']][['CleanLicense', 'CleanVehicle']].drop_duplicates()

    # Generate final output
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

    # Sort
    df_final["has_both"] = df_final["Tractor"].ne("") & df_final["Body"].ne("")
    df_final["only_tractor"] = df_final["Tractor"].ne("") & df_final["Body"].eq("")
    df_final["only_body"] = df_final["Tractor"].eq("") & df_final["Body"].ne("")

    df_sorted = pd.concat([
        df_final[df_final["has_both"]],
        df_final[df_final["only_tractor"]],
        df_final[df_final["only_body"]]
    ])

    return df_sorted.drop(columns=["has_both", "only_tractor", "only_body"]).reset_index(drop=True)