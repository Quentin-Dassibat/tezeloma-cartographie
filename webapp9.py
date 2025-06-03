############################################################################################################################
### Parameters
############################################################################################################################

#Synopsis
commune_nom = "Lyon-Villeurbanne"

#Libs
import os
import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import Geocoder
from shapely.geometry import shape
import ast
from io import BytesIO
import zipfile
import fiona

#Set directories
working_dir = os.getcwd()
output_dir = f"{working_dir}/outputs"
if os.path.exists(output_dir):
    pass
else:
    os.mkdir(output_dir)


############################################################################################################################
### Main
############################################################################################################################


# ---------------------------- SHARED FUNCTIONS --------------------------------------

@st.cache_data
def load_data_grouped(path,epsg_code):
    gdf = gpd.read_file(path)
    if epsg_code != 4326:
        gdf.to_crs(epsg=4326,inplace=True)
    return gdf

def load_data_detailed(path,epsg_code,subset_column,subset_values): #must a .gpkg file with one single layer
    layers = fiona.listlayers(path)
    layer = layers[0]
    value_str = ",".join([f"'{v}'" for v in subset_values])  #
    sql = f'SELECT * FROM "{layer}" WHERE "{subset_column}" IN ({value_str})'
    gdf = gpd.read_file(path, sql=sql)
    if epsg_code != 4326:
        gdf.to_crs(epsg=4326,inplace=True)
    return gdf

def dataframe2excel(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        dataframe.to_excel(writer, index=False, sheet_name='Data')
    xlsx_data = output.getvalue()
    return xlsx_data

def login_interface(USERS): #USERS is a dict with keys=usernames and values=passwords
    st.subheader("🔐 Connectez-vous pour continuer vers l'espace membre")
    username = st.text_input("Identifiant")
    password = st.text_input("Mot de passe", type="password")
    login_button = st.button("Se connecter")
    if login_button:
        if username in USERS and USERS[username] == password:
            #st.success("Connection réussie")
            st.session_state['authenticated'] = True
            st.session_state['username'] = username
            st.rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect")

# --------------------------------- USER INTERFACE ----------------------------------------------- 

# Preamble: app's logic

#st.session_state.space = 0 >> landing page 
#st.session_state.space = 1 >> DEMO space
#st.session_state.space = 2 >> TEZELOPA space

if 'space' in st.session_state and st.session_state['space'] == 2:

    if st.session_state['authenticated'] is False:

        login_interface({"tezelopa": "2025!Tezelopa"})

    else:

        st.success(f"Vous êtes connecté en tant que {st.session_state['username']}")

        # ------------------------- TEZELOPA SPACE ---------------------------------------

        #st.cache_data.clear()
    
        # Load data
        #gdf_detailed = load_data(f"{output_dir}/natprop2bdnb_{commune_nom}.gpkg",2154)
        gdf_grouped = load_data_grouped(f"{output_dir}/natprop2bdnb_{commune_nom}_grouped.gpkg",2154)
    
        # UI
        st.write("#### 🗂️ Bienvenue dans l'interface de visualisation de l'association TeZeLoPa.")
    
        st.write("Vous visualisez ici, en plus des données de la BDNB par défaut, les champs que vous ajoutez. Pour ajouter des champs, il suffit d'importer un tableur Excel comportant au moins une colonne appelée 'batiment_groupe_id'. Le programme va alors fusionner les données de la BDNB avec celles du tableur importé. Cette fusion permet ensuite d'afficher au format cartographique les données issues du travail de terrain, et de les superposer aux données initiales de la BDNB. Attention, il est nécessaire d'enregistrer la visualisation obtenue si vous souhaitez la conserver, car l'application la détruira une fois la page web fermée ou rafraîchie !")

        st.markdown("""
    Note pour l'utilisation de l'interface : tous les filtres fonctionnent de façon cumulative (opérateur logique "ET"). Par exemple, si l'on souhaite recenser tous les bâtiments du 1er arrondissement de Lyon dont le DPE représentatif est F **ou** G, on procède successivement :
    - Etape 1 : filtrez sur code postal = 69001 et DPE = F ; générez la carte ; téléchargez les données 
    - Etape 2 : filtrez sur code postal = 69001 et DPE = G ; générez la carte ; téléchargez les données 
    - Etape 3 : sous Excel (ou autre logiciel), collez bout-à-bout les deux tableurs obtenus ; sous Framacarte (ou autre logiciel), superposez les deux couches cartographiques obtenues
    """)
    
        if st.button("Se déconnecter"):
            st.session_state['authenticated'] = False
            st.session_state['space'] = False
            st.rerun()
    
        # File uploader
        
        user_file = st.file_uploader("Importez le fichier à utiliser (.xlsx) si nécessaire", type=["xlsx"])

        if user_file is not None:
            try:
                # Sheet to use
                excel_file = pd.ExcelFile(user_file)
                sheet_names = excel_file.sheet_names
                selected_sheet = st.selectbox("Choisir la feuille à utiliser dans le tableur importé", sheet_names, key='SHEET_KEY')
            except:
                pass
        
        if user_file is not None:
            try:
                #Read uploaded Excel file
                df_uploaded = pd.read_excel(user_file,sheet_name=selected_sheet)
                del st.session_state['SHEET_KEY']
                columns_uploaded = df_uploaded.columns.tolist()
                print("columns_uploaded",columns_uploaded)
                #Check for matching key column
                if "batiment_groupe_id" not in df_uploaded.columns:
                    st.error("Le champ 'batiment_groupe_id' n'existe pas dans le fichier importé. Fusion impossible.")
                else:
                    tmp = gdf_grouped.copy()
                    #Drop redundant columns
                    preserved_columns = {'batiment_groupe_id','geometry'}
                    redundant_columns = [col for col in df_uploaded.columns if col in tmp.columns and col not in preserved_columns]
                    tmp2 = tmp.drop(columns=redundant_columns)
                    #Merge
                    df_uploaded['batiment_groupe_id'] = df_uploaded['batiment_groupe_id'].astype('string')
                    tmp2['batiment_groupe_id'] = tmp2['batiment_groupe_id'].astype('string')
                    merged = pd.merge(tmp2, df_uploaded, on="batiment_groupe_id", how="left")
                    result_gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=tmp2.crs)
                    del gdf_grouped
                    gdf_grouped = result_gdf.copy()
                    st.success("Le fichier a bien été fusionné avec les données en ligne. Pensez à le sauvegarder avant de quitter la page.")
            except Exception as e:
                    st.error(f"Erreur interne d'importation des données : {e}. Veuillez contacter le support technique.")
        else:
            pass
    
        # Form
        
        with st.form("filter_form"):
        
        
            st.write("### 🔍 Ajustez les filtres pour générer une carte")
        
            # Permanent filters
    
            st.write("__Filtres permaments__")
            st.warning("Pour les filtres à curseur numérique, la valeur 0 indique que le filtre est laissé vierge. Le filtre est pris en compte à partir de la valeur 1.")
            
            ##Code postal
            cp_list = sorted([x for x in list(gdf_grouped['cp'].unique()) if x != ""])
            selected_cp = st.multiselect("Choisir un (ou plusieurs) code postal", cp_list, key='CP_KEY')
            ##DPE
            dpe_list = sorted([x for x in list(gdf_grouped['dpe'].unique()) if x != ""])
            selected_dpe = st.multiselect('Choisir un (ou plusieurs) DPE "représentatif du bâtiment"', dpe_list, key='DPE_KEY')
            selected_dpeA = st.slider("Pourcentage des logements d'un bâtiment avec une étiquette DPE A", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=100,
                                    step=1,
                                    key='DPEA_KEY')
            selected_dpeB = st.slider("Pourcentage des logements d'un bâtiment avec une étiquette DPE B", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=100,
                                    step=1,
                                    key='DPEB_KEY')
            selected_dpeC = st.slider("Pourcentage des logements d'un bâtiment avec une étiquette DPE C", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=100,
                                    step=1,
                                    key='DPEC_KEY')
            selected_dpeD = st.slider("Pourcentage des logements d'un bâtiment avec une étiquette DPE D", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=100,
                                    step=1,
                                    key='DPED_KEY')
            selected_dpeE = st.slider("Pourcentage des logements d'un bâtiment avec une étiquette DPE E", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=100,
                                    step=1,
                                    key='DPEE_KEY')
            selected_dpeF = st.slider("Pourcentage des logements d'un bâtiment avec une étiquette DPE F", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=100,
                                    step=1,
                                    key='DPEF_KEY')
            selected_dpeG = st.slider("Pourcentage des logements d'un bâtiment avec une étiquette DPE G", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=100,
                                    step=1,
                                    key='DPEG_KEY')
            selected_dpeNC = st.slider("Pourcentage des logements d'un bâtiment avec une étiquette DPE inconnue (non réalisé ou non communiqué)", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=100,
                                    step=1,
                                    key='DPENC_KEY')
            
            ##Forme juridique
            gdf_grouped['formes_juridiques'] = gdf_grouped['formes_juridiques'].apply(ast.literal_eval)
            all_formJur = sorted(set([formJur for sublist in list(gdf_grouped['formes_juridiques']) for formJur in sublist]))
            selected_formJur = st.multiselect("Choisir une (ou plusieurs) forme juridique de propriétaire", all_formJur, key='FORMJUR_KEY')
            filter_mode = st.radio("Mode de filtration pour la forme juridique", ["exclusif", "inclusif"])
            def filter_formJur(df, selection, mode):
                if not selection:
                    return df  # no filtering if nothing selected
                if mode == "exclusif":
                    df_filtered = df[df['formes_juridiques'].apply(lambda x: sorted(x) == sorted(selection))]
                    #df['formes_juridiques'] = df['formes_juridiques'].apply(lambda x: sorted(x) == sorted(selection))
                    return df_filtered
                elif mode == "inclusif":
                    df_filtered = df[df['formes_juridiques'].apply(lambda x: all(formJur in x for formJur in selection))]
                    #df['formes_juridiques'] = df['formes_juridiques'].apply(lambda x: all(formJur in x for formJur in selection))
                    return df_filtered
            
            ##Plus gros propriétaires
            bailleurs_list = sorted([x for x in list(gdf_grouped['concentration_prop_max_denomination'].unique()) if x != ""])
            selected_bailleur = st.multiselect('Choisir un (ou plusieurs) bailleur parmi les plus gros (/!/ ne signifie pas monopropriété)', bailleurs_list, key='BAILLEUR_KEY')
            
            ##Nombre de logements
            #range_nbLog = [int(x) for x in list(set(gdf_grouped['nb_log'])) if x != ''] 
            selected_nbLog = st.slider("Nombre de logements dans le bâtiment (logement != local)", 
                                    min_value=0, 
                                    #max_value=max(range_nbLog),
                                    max_value=50,
                                    step=1,
                                    key='LOG_KEY')
            ##Concentration propriété
            selected_concentration = st.slider("Pourcentage des logements d'un bâtiment détenus par un même propriétaire)", 
                                    min_value=0, 
                                    max_value=100, 
                                    step=5,
                                    key='CONC_KEY')
        
            # Dynamic filters (dfilters)
    
            st.write("__Filtres dynamiques (relatifs aux données importées le cas échéant)__")
    
            if user_file is None:

                st.error("Aucune donnée externe n'a été importée. Veuillez d'abord importer un fichier.")
                
                try:
                    
                    if "batiment_groupe_id" not in columns_uploaded:
                    
                        st.error("Le champ 'batiment_groupe_id' n'a pas été trouvé dans les données importées. La feuille de calcul à utiliser est-elle bien la bonne ?")
        
                    else:
        
                        selected_dfilterMode = st.radio("Mode d'ajout des filtres dynamiques aux filtres permanents", ["Lié", "Non-lié"], key='DFILTERMODE_KEY')
                        
                        st.session_state.dfilters_col = []
                        st.session_state.dfilters_val = []
                        st.session_state.dfilters_dtype = []
                            
                        #filter_id = -1
                        for col in [x for x in columns_uploaded if x != 'batiment_groupe_id']:
                            print(col)
                            #filter_id += 1
                            dtype = df_uploaded[col].dtype
                            if pd.api.types.is_numeric_dtype(dtype):
                                rng = [x for x in list(set(df_uploaded[col])) if x != '']
                                val = st.slider(f"Choisir une valeur minimum pour le champ {col}", 
                                                min_value=0, 
                                                max_value=max(rng),
                                                step=1,
                                                key=f"{col}_KEY")
                            else:
                                etiquettes = df_uploaded[col].dropna().unique().tolist()
                                val = st.multiselect(f"Choisir une (ou plusieurs) étiquettes pour le champ {col}", etiquettes, key=f"{col}_KEY")
                
                            st.session_state.dfilters_col.append(col)
                            st.session_state.dfilters_val.append(val)
                            st.session_state.dfilters_dtype.append(dtype)
                except:
                    pass
        
            ##Fond de carte
            st.write("__Choisissez un fond ce carte pour l'affichage__")
            selected_background = st.radio("Fond de carte", ["Couleur", "Noir et blanc"])
            
            
            # Define session states
            
            if 'CP_KEY' not in st.session_state:
                st.session_state['CP_KEY'] = selected_cp
            if 'DPE_KEY' not in st.session_state:
                st.session_state['DPE_KEY'] = selected_dpe
            if 'FORMJUR_KEY' not in st.session_state:
                st.session_state['FORMJUR_KEY'] = selected_formJur
            if 'LOG_KEY' not in st.session_state:
                st.session_state['LOG_KEY'] = selected_nbLog
            if 'CONC_KEY' not in st.session_state:
                st.session_state['CONC_KEY'] = selected_concentration
            try:
                if 'DFILTERMODE_KEY' not in st.session_state:
                    st.session_state['DFILTERMODE_KEY'] = selected_dfilterMode
            except:
                pass
            if 'DPEA_KEY' not in st.session_state:
                st.session_state[f'DPEA_KEY'] = selected_dpeA
            if 'DPEB_KEY' not in st.session_state:
                st.session_state[f'DPEB_KEY'] = selected_dpeB
            if 'DPEC_KEY' not in st.session_state:
                st.session_state[f'DPEC_KEY'] = selected_dpeC
            if 'DPED_KEY' not in st.session_state:
                st.session_state[f'DPED_KEY'] = selected_dpeD
            if 'DPEE_KEY' not in st.session_state:
                st.session_state[f'DPEE_KEY'] = selected_dpeE
            if 'DPEF_KEY' not in st.session_state:
                st.session_state[f'DPEF_KEY'] = selected_dpeF
            if 'DPEG_KEY' not in st.session_state:
                st.session_state[f'DPEG_KEY'] = selected_dpeG
            if 'DPENC_KEY' not in st.session_state:
                st.session_state[f'DPENC_KEY'] = selected_dpeNC
            if 'BAILLEUR_KEY' not in st.session_state:
                st.session_state[f'BAILLEUR_KEY'] = selected_bailleur
    
            
            submit = st.form_submit_button(label="Générez la carte")
    
        # Displaying
    
        if submit:

            #Clear load_data() function's cache
            #load_data.clear()
    
            # Filter dataframe for each permanent filter 
            ##forme juridique
            gdf_filtered = filter_formJur(gdf_grouped,selected_formJur,filter_mode) #returns gdf_grouped if no selection in filter
            
            ##code postal
            if not selected_cp:
                selected_cp = gdf_grouped['cp'].unique()
            gdf_filtered = gdf_filtered[gdf_filtered['cp'].isin(selected_cp)]
            
            ##dpe représentatif
            if not selected_dpe:
                selected_dpe = gdf_grouped['dpe'].unique()
            gdf_filtered = gdf_filtered[gdf_filtered['dpe'].isin(selected_dpe)]

            ##pourcentages dpe
            def filter_dpe(filter2apply,df,col_name):
                df[col_name] = df[col_name].astype('string')
                df = df.loc[df[col_name] != 'NC']
                df[col_name] = df[col_name].astype('float')
                if filter2apply and filter2apply >= 1:
                    df = df[df[col_name] >= int(filter2apply)]
                else:
                    filter2apply = ""
                return df
            gdf_filtered = filter_dpe(selected_dpeA,gdf_filtered,'pourcentage_dpe_a')
            gdf_filtered = filter_dpe(selected_dpeB,gdf_filtered,'pourcentage_dpe_b')
            gdf_filtered = filter_dpe(selected_dpeC,gdf_filtered,'pourcentage_dpe_c')
            gdf_filtered = filter_dpe(selected_dpeD,gdf_filtered,'pourcentage_dpe_d')
            gdf_filtered = filter_dpe(selected_dpeE,gdf_filtered,'pourcentage_dpe_e')
            gdf_filtered = filter_dpe(selected_dpeF,gdf_filtered,'pourcentage_dpe_f')
            gdf_filtered = filter_dpe(selected_dpeG,gdf_filtered,'pourcentage_dpe_g')
            gdf_filtered = filter_dpe(selected_dpeNC,gdf_filtered,'pourcentage_dpe_inconnu')
           
            ##concentration
            if "personne_physique" not in selected_formJur:
                if selected_concentration and selected_concentration >= 1:
                    gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].astype('string')
                    gdf_filtered = gdf_filtered.loc[gdf_filtered['concentration_prop_max'] != 'NC']
                    gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].astype(float)
                    gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].round(decimals=2)*100
                    gdf_filtered = gdf_filtered[gdf_filtered["concentration_prop_max"] >= float(selected_concentration)]
                else:
                    selected_concentration = ""
                    gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].astype('string')
                    gdf_filtered = gdf_filtered.loc[gdf_filtered['concentration_prop_max'] != 'NC']
                    gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].astype(float)
                    gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].round(decimals=2)*100
            else:
                pass

            ## Bailleurs
            if not selected_bailleur:
                selected_bailleur = gdf_grouped['concentration_prop_max_denomination'].unique()
            gdf_filtered = gdf_filtered[gdf_filtered['concentration_prop_max_denomination'].isin(selected_bailleur)]

            
            ## nbLog
            if selected_nbLog and selected_nbLog >= 1:
                gdf_filtered["nb_log"] = gdf_filtered["nb_log"].astype('string')
                gdf_filtered = gdf_filtered.loc[gdf_filtered['nb_log'] != 'NC']
                gdf_filtered["nb_log"] = gdf_filtered["nb_log"].astype('int32')
                gdf_filtered = gdf_filtered[gdf_filtered["nb_log"] >= int(selected_nbLog)]
            else:
                selected_nbLog = ""
                gdf_filtered["nb_log"] = gdf_filtered["nb_log"].astype('string')
                gdf_filtered = gdf_filtered.loc[gdf_filtered['nb_log'] != 'NC']
                gdf_filtered = gdf_filtered.loc[gdf_filtered['nb_log'] != '']
                gdf_filtered["nb_log"] = gdf_filtered["nb_log"].astype('int32')

            
            # Filter dataframe for each dynamic filter (dfilters)

            try:
                
                if selected_dfilterMode == "Lié":
    
                    #Dynamic filters adds up to the previous filtration
            
                    for i in range(len(st.session_state.dfilters_col)):
                        c = st.session_state.dfilters_col[i]
                        v = st.session_state.dfilters_val[i]
                        d = st.session_state.dfilters_dtype[i]
                        if c is not None and v is not None and d is not None:
                            if pd.api.types.is_numeric_dtype(d): 
                                if v != 0:
                                    gdf_filtered.dropna(axis=0,subset=[c],inplace=True)
                                    gdf_filtered = gdf_filtered[gdf_filtered[c] >= v]
                            else:
                                if v != []:
                                    gdf_filtered.dropna(axis=0,subset=[c],inplace=True)
                                    gdf_filtered = gdf_filtered[gdf_filtered[c] == v]
                        else:
                            pass
    
                else:
    
                    #Dynamic filters apply to the former, unfiltered gdf_grouped
                    
                    for i in range(len(st.session_state.dfilters_col)):
                        c = st.session_state.dfilters_col[i]
                        v = st.session_state.dfilters_val[i]
                        d = st.session_state.dfilters_dtype[i]
                        if c is not None and v is not None and d is not None:
                            gdf_filtered2 = gdf_grouped.copy()
                            if pd.api.types.is_numeric_dtype(d): 
                                if v != 0:
                                    gdf_filtered2.dropna(axis=0,subset=[c],inplace=True)
                                    gdf_filtered2 = gdf_filtered2[gdf_filtered2[c] >= v]
                                else:
                                    gdf_filtered2 = gdf_filtered2.loc[~gdf_filtered2[c].isna()]
                            else:
                                if v != []:
                                    gdf_filtered2.dropna(axis=0,subset=[c],inplace=True)
                                    gdf_filtered2 = gdf_filtered2[gdf_filtered2[c] == v]
                                else:
                                    gdf_filtered2 = gdf_filtered2.loc[~gdf_filtered2[c].isna()]
                        else:
                            pass

            except:
                pass
                
            # Create a Folium map
            
            if selected_background == "Couleur":
                m = folium.Map(location=[gdf_filtered.geometry.centroid.y.mean(), gdf_filtered.geometry.centroid.x.mean()],
                           zoom_start=14)
            else:
                m = folium.Map(location=[gdf_filtered.geometry.centroid.y.mean(), gdf_filtered.geometry.centroid.x.mean()],
                           zoom_start=14,tiles=f"CartoDB positron")
        
            # Add data from filters

            ## If mode = Lié, display one layer (gdf_filtered)

            try: #If data have been uploaded
                
                if selected_dfilterMode == "Lié":
        
                    popup = folium.GeoJsonPopup(
                                fields=["nb_log",
                                        "dpe",
                                        'pourcentage_dpe_a',
                                        'pourcentage_dpe_b',
                                        'pourcentage_dpe_c',
                                        'pourcentage_dpe_d',
                                        'pourcentage_dpe_e',
                                        'pourcentage_dpe_f',
                                        'pourcentage_dpe_g',
                                        'pourcentage_dpe_inconnu',
                                        "formes_juridiques",
                                        "concentration_prop_max",
                                        'concentration_prop_max_denomination',
                                        "adr",
                                        "batiment_groupe_id"
                                       ]+columns_uploaded,
                                aliases=["Nombre de logements",
                                         "DPE représentatif",
                                         "Formes juridiques des propriétaires",
                                         "Concentration de la propriété",
                                         "Plus gros propriétaire",
                                         "Adresse",
                                         "Identifiant"
                                        ]+columns_uploaded,
                                localize=True,
                                labels=True,
                                style="background-color: yellow; font-size: 12px;",
                            )
                
                    folium.GeoJson(
                        gdf_filtered,
                        popup=popup,
                    ).add_to(m)
                
                else:
        
                    ## If mode = non lié, display two layers (gdf_filtered and gdf_filtered2) 
        
                    popup = folium.GeoJsonPopup(
                                fields=["nb_log",
                                        "dpe",
                                        'pourcentage_dpe_a',
                                        'pourcentage_dpe_b',
                                        'pourcentage_dpe_c',
                                        'pourcentage_dpe_d',
                                        'pourcentage_dpe_e',
                                        'pourcentage_dpe_f',
                                        'pourcentage_dpe_g',
                                        'pourcentage_dpe_inconnu',
                                        "formes_juridiques",
                                        "concentration_prop_max",
                                        'concentration_prop_max_denomination',
                                        "adr",
                                        "batiment_groupe_id"],
                                aliases=["Nombre de logements",
                                         "DPE représentatif",
                                         "Part des DPE A (%)",
                                         "Part des DPE B (%)",
                                         "Part des DPE C (%)",
                                         "Part des DPE D (%)",
                                         "Part des DPE E (%)",
                                         "Part des DPE F (%)",
                                         "Part des DPE G (%)",
                                         "Part des DPE NC (%)",
                                         "Formes juridiques des propriétaires",
                                         "Concentration de la propriété (%)",
                                         "Plus gros propriétaire",
                                         "Adresse",
                                         "Identifiant"],
                                localize=True,
                                labels=True,
                                style="background-color: yellow; font-size: 12px;",
                            )
                    
                    folium.GeoJson(
                                    gdf_filtered,
                                    popup=popup,
                                    style_function=lambda feature: {
                                                        'fillColor': 'blue',
                                                        'color': 'black',
                                                        'weight': 1,
                                                        'fillOpacity': 0.6,
                                                        }
                    ).add_to(m)
        
                    popup2 = folium.GeoJsonPopup(
                                                fields=columns_uploaded,
                                                localize=True,
                                                labels=True,
                                                style="background-color: yellow; font-size: 12px;",
                                            )
                    folium.GeoJson(
                                    gdf_filtered2,
                                    popup=popup2,
                                    style_function=lambda feature: {
                                                        'fillColor': 'orange',
                                                        'color': 'black',
                                                        'weight': 1,
                                                        'fillOpacity': 0.9,
                                                        }
                    ).add_to(m) 
                    
            
            except: #If no data have been uploaded

                popup = folium.GeoJsonPopup(
                                fields=["nb_log", "dpe", "formes_juridiques", "concentration_prop_max", 'concentration_prop_max_denomination', "adr", "batiment_groupe_id"],
                                aliases=["Nombre de logements", "DPE représentatif", "Formes juridiques des propriétaires", "Concentration de la propriété", "Plus gros propriétaire", "Adresse", "Identifiant"],
                                localize=True,
                                labels=True,
                                style="background-color: yellow; font-size: 12px;",
                            )
        
                folium.GeoJson(
                    gdf_filtered,
                    popup=popup,
                ).add_to(m)
                
            # Add address search bar to the map
            Geocoder().add_to(m)
        
            # Display the map
            st.write("### 🗺️ Cartographie")
            try:
                if selected_dfilterMode == "Lié":
                    nbBat = int(len(gdf_filtered))
                else:
                    nbBat = int(len(gdf_filtered)+len(gdf_filtered2))
            except:
                nbBat = int(len(gdf_filtered))
            st.write(f"{nbBat} bâtiments correspondent à vos critères")
            st_data = st_folium(m, height=700, width=700, returned_objects=[])
    
            
            # Package data
    
            st.write("### 📥 Téléchargement des fichiers générés")


            try:
    
                if selected_dfilterMode == "Lié":
                    
                    #Filter gdf_detail with batiment_ids in the user's selection
                    filtered_batiment_ids = [f'{x}' for x in list(gdf_filtered['batiment_groupe_id'])]
                    export = load_data_detailed(f"{output_dir}/natprop2bdnb_{commune_nom}.gpkg",
                                                      2154,
                                                      "batiment_groupe_id",
                                                      filtered_batiment_ids)
                    export['batiment_groupe_id'] = export['batiment_groupe_id'].astype('string')
                    #gdf_detailed.clear()
                    
                    #Prepare zip archive
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        # Add Excel files
                        export_detailed = export.drop(columns=["geometry", "geom_groupe"])
                        xlsx_detailed = dataframe2excel(export_detailed)
                        zip_file.writestr(f"tableur_detaille_FPFD.xlsx", 
                                          xlsx_detailed)
                        export_grouped = gdf_filtered.drop(columns=["geometry"])
                        xlsx_grouped = dataframe2excel(export_grouped)
                        zip_file.writestr(f"tableur_groupe_FPFD.xlsx", xlsx_grouped)
                        # Add GeoJSON files
                        geojson_grouped = gdf_filtered.to_json()
                        zip_file.writestr(f"carte_groupee_FPFD.geojson", geojson_grouped)
            
                else:
        
                    #Filter gdf_detail with batiment_ids in the user's selection
                    ## For permament filters (FP)
                    filtered_batiment_ids = [f'{x}' for x in list(gdf_filtered['batiment_groupe_id'])]
                    export = load_data_detailed(f"{output_dir}/natprop2bdnb_{commune_nom}.gpkg",
                                                      2154,
                                                      "batiment_groupe_id",
                                                      filtered_batiment_ids)
                    export['batiment_groupe_id'] = export['batiment_groupe_id'].astype('string')
                    ## For dynamic filters (FD)
                    filtered_batiment_ids2 = [f'{x}' for x in list(gdf_filtered2['batiment_groupe_id'])]
                    export2 = load_data_detailed(f"{output_dir}/natprop2bdnb_{commune_nom}.gpkg",
                                                      2154,
                                                      "batiment_groupe_id",
                                                      filtered_batiment_ids2)
                    export2['batiment_groupe_id'] = export2['batiment_groupe_id'].astype('string')
                    #gdf_detailed.clear()
                    
                    #Prepare zip archive
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        # Add Excel files
                        ## For permament filters (FP)
                        export_detailed = export.drop(columns=["geometry", "geom_groupe"])
                        xlsx_detailed = dataframe2excel(export_detailed)
                        zip_file.writestr(f"tableur_detaille_FP.xlsx", 
                                          xlsx_detailed)
                        export_grouped = gdf_filtered.drop(columns=["geometry"])
                        xlsx_grouped = dataframe2excel(export_grouped)
                        zip_file.writestr(f"tableur_groupe_FP.xlsx", xlsx_grouped)
                        ## For dynamic filters (FD)
                        export_detailed2 = export2.drop(columns=["geometry", "geom_groupe"])
                        xlsx_detailed2 = dataframe2excel(export_detailed2)
                        zip_file.writestr(f"tableur_detaille_FD.xlsx", 
                                          xlsx_detailed2)
                        export_grouped2 = gdf_filtered2.drop(columns=["geometry"])
                        xlsx_grouped2 = dataframe2excel(export_grouped2)
                        zip_file.writestr(f"tableur_groupe_FD.xlsx", xlsx_grouped2)
                        # Add GeoJSON files
                        ## For permament filters (FP)
                        geojson_grouped = gdf_filtered.to_json()
                        zip_file.writestr(f"carte_groupee_FP.geojson", geojson_grouped)
                        ## For dynamic filters (FD)
                        geojson_grouped = gdf_filtered2.to_json()
                        zip_file.writestr(f"carte_groupee_FD.geojson", geojson_grouped2)

            except:

                #Filter gdf_detail with batiment_ids in the user's selection
                filtered_batiment_ids = [f'{x}' for x in list(gdf_filtered['batiment_groupe_id'])]
                export = load_data_detailed(f"{output_dir}/natprop2bdnb_{commune_nom}.gpkg",
                                                  2154,
                                                  "batiment_groupe_id",
                                                  filtered_batiment_ids)
                export['batiment_groupe_id'] = export['batiment_groupe_id'].astype('string')
                
                #Prepare zip archive
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    # Add Excel files
                    export_detailed = export.drop(columns=["geometry", "geom_groupe"])
                    xlsx_detailed = dataframe2excel(export_detailed)
                    zip_file.writestr(f"tableur_detaille_FP.xlsx", 
                                      xlsx_detailed)
                    export_grouped = gdf_filtered.drop(columns=["geometry"])
                    xlsx_grouped = dataframe2excel(export_grouped)
                    zip_file.writestr(f"tableur_groupe_FP.xlsx", xlsx_grouped)
                    # Add GeoJSON files
                    geojson_grouped = gdf_filtered.to_json()
                    zip_file.writestr(f"carte_groupee_FP.geojson", geojson_grouped)
                
            
            # Finalize ZIP
            zip_buffer.seek(0)
            
            st.download_button(
                                label="Téléchargez les fichiers générés (.zip)",
                                data=zip_buffer,
                                file_name="export.zip",
                                mime="application/zip"
                            )
            
            ## Reset filters session states
            del st.session_state['CP_KEY']
            del st.session_state['DPE_KEY']
            del st.session_state['FORMJUR_KEY']
            del st.session_state['LOG_KEY']
            del st.session_state['CONC_KEY']
            for l in ['A','B','C','D','E','F','G','NC']:
                del st.session_state[f'DPE{l}_KEY']
            del st.session_state['BAILLEUR_KEY']
            try:
                del st.session_state['dfilters_col']
                del st.session_state['dfilters_val']
                del st.session_state['dfilters_dtype']
            except:
                pass
            


elif 'space' in st.session_state and st.session_state['space'] == 1:

    # -------------------------- DEMO SPACE ----------------------------------------------

    st.write("#### 🗂️ Bienvenue dans l'interface de visualisation standard")

    st.markdown("""
    L'interface fonctionne en sélectionnant les bâtiments qui vous intéressent selon les caractéristiques proposées dans les options de filtres ci-dessous. L'application génère ensuite 1. la carte qui correspond à la sélection demandée et 2. les données téléchargeables associées. Les données téléchargeables sont de trois types :
    - un tableur dit "groupé" au format .xlsx : une ligne = un bâtiment, et les colonnes correspondent aux filtres proposés
    - un tableur dit "détaillé" au format .xlsx : une ligne = un propriétaire (personne morale), et les colonnes correspondent aux filtres proposés + aux attributs des propriétaires dans le fichier foncier
    - un couche cartographique vectorielle au format .geojson : cette couche est l'export direct de la carte qui a été générée. Elle peut être importée dans un logiciel cartographique (ex. en ligne, Framacrate) pour produire une mise en page. 
    """)

    st.markdown("""
    Note pour l'utilisation de l'interface : tous les filtres fonctionnent de façon cumulative (opérateur logique "ET"). Par exemple, si l'on souhaite recenser tous les bâtiments du 1er arrondissement de Lyon dont le DPE représentatif est F **ou** G, on procède successivement :
    - Etape 1 : filtrez sur code postal = 69001 et DPE = F ; générez la carte ; téléchargez les données 
    - Etape 2 : filtrez sur code postal = 69001 et DPE = G ; générez la carte ; téléchargez les données 
    - Etape 3 : sous Excel (ou autre logiciel), collez bout-à-bout les deux tableurs obtenus ; sous Framacarte (ou autre logiciel), superposez les deux couches cartographiques obtenues
    """)

    # Load data
    
    gdf_grouped = load_data_grouped(f"{output_dir}/natprop2bdnb_{commune_nom}_grouped.gpkg",2154)
    #gdf_detailed = load_data(f"{output_dir}/natprop2bdnb_{commune_nom}.gpkg",2154)
    
    # Form with edition mode
    
    with st.form("filter_form"):
    
    
        st.write("### 🔍 Ajustez les filtres pour générer une carte")
    
        # User's filters
        
        ##Code postal
        cp_list = sorted([x for x in list(gdf_grouped['cp'].unique()) if x != ""])
        selected_cp = st.multiselect("Choisir un (ou plusieurs) code postal", cp_list, key='CP_KEY')
        ##DPE
        dpe_list = sorted([x for x in list(gdf_grouped['dpe'].unique()) if x != ""])
        selected_dpe = st.multiselect("Choisir un (ou plusieurs) DPE", dpe_list, key='DPE_KEY')
        ##Forme juridique
        gdf_grouped['formes_juridiques'] = gdf_grouped['formes_juridiques'].apply(ast.literal_eval)
        all_formJur = sorted(set([formJur for sublist in list(gdf_grouped['formes_juridiques']) for formJur in sublist]))
        selected_formJur = st.multiselect("Choisir une (ou plusieurs) forme juridique de propriétaire", all_formJur, key='FORMJUR_KEY')
        filter_mode = st.radio("Mode de filtration pour la forme juridique", ["exclusif", "inclusif"])
        def filter_formJur(df, selection, mode):
            if not selection:
                return df  # no filtering if nothing selected
            if mode == "exclusif":
                df_filtered = df[df['formes_juridiques'].apply(lambda x: sorted(x) == sorted(selection))]
                #df['formes_juridiques'] = df['formes_juridiques'].apply(lambda x: sorted(x) == sorted(selection))
                return df_filtered
            elif mode == "inclusif":
                df_filtered = df[df['formes_juridiques'].apply(lambda x: all(formJur in x for formJur in selection))]
                #df['formes_juridiques'] = df['formes_juridiques'].apply(lambda x: all(formJur in x for formJur in selection))
                return df_filtered
        ##Nombre de logements
        #range_nbLog = [int(x) for x in list(set(gdf_grouped['nb_log'])) if x != ''] 
        selected_nbLog = st.slider("Nombre de logements dans le bâtiment (logement != local)", 
                                min_value=0, 
                                #max_value=max(range_nbLog),
                                max_value=50,
                                step=1,
                                key='LOG_KEY')
        ##Concentration propriété
        selected_concentration = st.slider("Pourcentage des logements d'un bâtiment détenus par un même propriétaire)", 
                                min_value=0, 
                                max_value=100, 
                                step=5,
                                key='CONC_KEY')            
        
    
        ##Fond de carte
        selected_background = st.radio("Fond de carte", ["Couleur", "Noir et blanc"])
        
        
        # Define session states
        
        if 'CP_KEY' not in st.session_state:
            st.session_state['CP_KEY'] = selected_cp
        if 'DPE_KEY' not in st.session_state:
            st.session_state['DPE_KEY'] = selected_dpe
        if 'FORMJUR_KEY' not in st.session_state:
            st.session_state['FORMJUR_KEY'] = selected_formJur
        if 'LOG_KEY' not in st.session_state:
            st.session_state['LOG_KEY'] = selected_nbLog
        if 'CONC_KEY' not in st.session_state:
            st.session_state['CONC_KEY'] = selected_concentration
        
        
        submit = st.form_submit_button(label="Générez la carte")

    # Displaying

    if submit:

        # Filter dataframe for each permanent filter 
        
        ##forme juridique
        gdf_filtered = filter_formJur(gdf_grouped,selected_formJur,filter_mode) #returns gdf_grouped if no selection in filter
        
        ##code postal
        if not selected_cp:
            selected_cp = gdf_grouped['cp'].unique()
        gdf_filtered = gdf_filtered[gdf_filtered['cp'].isin(selected_cp)]
        
        ##dpe
        if not selected_dpe:
            selected_dpe = gdf_grouped['dpe'].unique()
        gdf_filtered = gdf_filtered[gdf_filtered['dpe'].isin(selected_dpe)]
       
        ##concentration
        if "personne_physique" not in selected_formJur:
            if selected_concentration and selected_concentration >= 1:
                gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].astype('string')
                gdf_filtered = gdf_filtered.loc[gdf_filtered['concentration_prop_max'] != 'NC']
                gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].astype(float)
                gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].round(decimals=2)*100
                gdf_filtered = gdf_filtered[gdf_filtered["concentration_prop_max"] >= float(selected_concentration)]
            else:
                selected_concentration = ""
                gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].astype('string')
                gdf_filtered = gdf_filtered.loc[gdf_filtered['concentration_prop_max'] != 'NC']
                gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].astype(float)
                gdf_filtered["concentration_prop_max"] = gdf_filtered["concentration_prop_max"].round(decimals=2)*100
        else:
            pass
        
        ##nbLog
        if selected_nbLog and selected_nbLog >= 1:
            gdf_filtered["nb_log"] = gdf_filtered["nb_log"].astype('string')
            gdf_filtered = gdf_filtered.loc[gdf_filtered['nb_log'] != 'NC']
            gdf_filtered["nb_log"] = gdf_filtered["nb_log"].astype('int32')
            gdf_filtered = gdf_filtered[gdf_filtered["nb_log"] >= int(selected_nbLog)]
        else:
            selected_nbLog = ""
            gdf_filtered["nb_log"] = gdf_filtered["nb_log"].astype('string')
            gdf_filtered = gdf_filtered.loc[gdf_filtered['nb_log'] != 'NC']
            gdf_filtered = gdf_filtered.loc[gdf_filtered['nb_log'] != '']
            gdf_filtered["nb_log"] = gdf_filtered["nb_log"].astype('int32')
    
        # Create a Folium map
        if selected_background == "Couleur":
            m = folium.Map(location=[gdf_filtered.geometry.centroid.y.mean(), gdf_filtered.geometry.centroid.x.mean()],
                       zoom_start=14)
        else:
            m = folium.Map(location=[gdf_filtered.geometry.centroid.y.mean(), gdf_filtered.geometry.centroid.x.mean()],
                       zoom_start=14,tiles=f"CartoDB positron")
    
        # Add gdf_filtered to the map
        
        popup = folium.GeoJsonPopup(
                                fields=["nb_log", "dpe", "formes_juridiques", "concentration_prop_max", 'concentration_prop_max_denomination', "adr", "batiment_groupe_id"],
                                aliases=["Nombre de logements", "DPE représentatif", "Formes juridiques des propriétaires", "Concentration de la propriété", "Plus gros propriétaire", "Adresse", "Identifiant"],
                                localize=True,
                                labels=True,
                                style="background-color: yellow; font-size: 12px;",
                            )
    
        folium.GeoJson(
            gdf_filtered,
            popup=popup
        ).add_to(m)
        
        # Add address search bar to the map
        Geocoder().add_to(m)
    
        # Display the map
        st.write("### 🗺️ Cartographie")
        st.write(f"{int(len(gdf_filtered))} bâtiments correspondent à vos critères")
        st_data = st_folium(m, height=700, width=700, returned_objects=[])
    
        
        # Download button
        st.write("### 📥 Téléchargement des fichiers générés")

        #Filter gdf_detail with batiment_ids in the user's selection
        filtered_batiment_ids = [f'{x}' for x in list(gdf_filtered['batiment_groupe_id'])]
        export = load_data_detailed(f"{output_dir}/natprop2bdnb_{commune_nom}.gpkg",
                                          2154,
                                          "batiment_groupe_id",
                                          filtered_batiment_ids)
        export['batiment_groupe_id'] = export['batiment_groupe_id'].astype('string')
    
    
        #Prepare zip archive
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            _suffix = f"CP={','.join([str(x) for x in selected_cp])}:DPE={','.join(selected_dpe)}:formJur={','.join(selected_formJur)}:nbLog={str(selected_nbLog)}:concProp={str(selected_concentration)}"
            # Add Excel files
            export_detailed = export.drop(columns=["geometry", "geom_groupe"])
            xlsx_detailed = dataframe2excel(export_detailed)
            zip_file.writestr(f"tableur_detaille_filtres:{_suffix}.xlsx", 
                              xlsx_detailed)
            export_grouped = gdf_filtered.drop(columns=["geometry"])
            xlsx_grouped = dataframe2excel(export_grouped)
            zip_file.writestr(f"tableur_groupe_filtres:{_suffix}.xlsx", xlsx_grouped)
            # Add GeoJSON files
            geojson_grouped = gdf_filtered.to_json()
            zip_file.writestr(f"carte_groupee_filtres:{_suffix}.geojson", geojson_grouped)
            
        # Finalize ZIP
        zip_buffer.seek(0)
        
        st.download_button(
                            label="Téléchargez les fichiers générés (.zip)",
                            data=zip_buffer,
                            file_name="export.zip",
                            mime="application/zip"
                        )

            
        ## Reset filters session states
        del st.session_state['CP_KEY']
        del st.session_state['DPE_KEY']
        del st.session_state['FORMJUR_KEY']
        del st.session_state['LOG_KEY']
        del st.session_state['CONC_KEY']


else:
    
    # ------------------------- LANDING PAGE -------------------------------------
    
    st.title("Territoire Zéro Logement Mal Adaptés Climatiquement")
    
    st.write("#### Bienvenue sur l'interface en ligne TeZeLoMa ! Cette interface vous permet de visualiser et de télécharger une sélection des données cartographiques issues de la Base de Données Nationale du Bâtiment (version 2024) pour les villes de Lyon et Villeurbanne.")
    
    st.write("Si vous êtes membre de l'association TeZeLopa, veuillez vous connecter à l'espace de visualisation enrichi de l'association.")

    st.markdown("""
    Les données proposées sont issues d'un recoupement de bases différentes agrégées à la maille bâtiment :
    - le fichier foncier 2024 dit "fichier des locaux des personnes morales" (Trésor public) 
    - la base DPE 2024 (Ademe)
    - la base de données nationale du bâtiment 2024 (CSTB)
    Pour en savoir plus sur l'origine des données : [https://bdnb.io](https://bdnb.io/documentation/modele_donnees/)
    """)


    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.space = 0
    col1, col2 = st.columns(2)
    with col1:
        left, center, right = st.columns([1, 2, 1])
        with center:
            if st.button("Version DEMO"):
                st.session_state.space = 1
                st.rerun()
    with col2:
        left, center, right = st.columns([1, 2, 1])
        with center:
            if st.button("Version membre"):
                st.session_state.space = 2
                st.rerun()  




