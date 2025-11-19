# Contenu de app.py (ou 2.py)

import streamlit as st
import numpy as np
import plotly.graph_objects as go
import pandas as pd
import io
import datetime
import copy 
import json 
import openpyxl

# --- IMPORTATIONS DES LIBRAIRIES TIERCES (AUDIO) ---
try:
    from audiorecorder import audiorecorder
    import speech_recognition as sr
    from pydub import AudioSegment
    
    # MODIFIÉ: Tentative de chemins plus génériques
    try:
        ffmpeg_path = "ffmpeg"
        ffprobe_path = "ffprobe"
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffprobe = ffprobe_path
        empty_audio = AudioSegment.silent(duration=0)
        empty_audio.export(io.BytesIO(), format="wav")
    except Exception:
        # Si 'ffmpeg' n'est pas dans le PATH, tente le chemin anaconda
        ffmpeg_path = "/Applications/anaconda3/bin/ffmpeg"
        ffprobe_path = "/Applications/anaconda3/bin/ffprobe"
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffprobe = ffprobe_path
        empty_audio = AudioSegment.silent(duration=0)
        empty_audio.export(io.BytesIO(), format="wav")
except ImportError:
    st.error("Dépendances manquantes (audiorecorder, speech_recognition, pydub).")
    st.stop()
except Exception as e:
    if "ffmpeg" in str(e).lower() or "ffprobe" in str(e).lower():
         st.error(f"ERREUR FFMPEG : {e}. Assurez-vous que FFMPEG est installé et accessible (dans votre PATH ou via le chemin dans app.py).")
         st.stop()

# --- IMPORTATIONS DE VOS MODULES PERSONNALISÉS ---
from utils import (
    initialize_session_state, 
    parse_all_voice_commands, 
    calculate_hole_positions,
    get_default_debit_data,
    get_default_dims,
    get_default_door_props, 
    get_default_drawer_props,
    get_default_shelf_props,
    get_material_library 
)
from geometry_helpers import (
    validate_dims, inner_dims_from_thickness, 
    can_make_inner, cuboid_mesh_for,
    cylinder_mesh_for,
    rotation_matrix 
)
from drawing import draw_machining_view_professional
from excel_export import create_styled_excel

# --- Configuration et Initialisation ---
st.set_page_config(page_title="Caisson Designer", layout="wide")
initialize_session_state()

# --- Fonction de calcul récursif ---
def calculate_origins_recursively(scene_cabinets, unit_factor):
    calculated_origins = {}
    def get_absolute_origin(caisson_index):
        if caisson_index in calculated_origins: return calculated_origins[caisson_index]
        caisson = scene_cabinets[caisson_index]
        parent_idx = caisson['parent_index']
        if parent_idx is None:
            calculated_origins[caisson_index] = (0.0, 0.0, 0.0)
            return (0.0, 0.0, 0.0)
        if parent_idx >= len(scene_cabinets): # Orphelin (parent supprimé)
            calculated_origins[caisson_index] = (0.0, 0.0, 0.0)
            return (0.0, 0.0, 0.0)
        parent_origin = get_absolute_origin(parent_idx)
        parent_caisson = scene_cabinets[parent_idx]
        parent_L_m = parent_caisson['dims']['L_raw'] * unit_factor
        parent_H_m = parent_caisson['dims']['H_raw'] * unit_factor
        my_L_m = caisson['dims']['L_raw'] * unit_factor
        x, y, z = parent_origin
        direction = caisson['attachment_dir']
        if direction == 'right': x += parent_L_m
        elif direction == 'left': x -= my_L_m
        elif direction == 'up': z += parent_H_m
        my_origin = (x, y, z)
        calculated_origins[caisson_index] = my_origin
        return my_origin
    for i in range(len(scene_cabinets)): get_absolute_origin(i)
    return calculated_origins
# --- FIN DÉPLACEMENT ---

# ---------- INTERFACE UTILISATEUR (UI) ----------
st.title("🧰 Caisson Designer")
st.markdown("Assemblez votre scène en ajoutant et modifiant des caissons uniques.")

# --- Calcul des origines AVANT les colonnes ---
unit_factor = {"mm":0.001,"cm":0.01,"m":1.0}[st.session_state.unit_select]
absolute_origins = calculate_origins_recursively(st.session_state.scene_cabinets, unit_factor)
# --- FIN ---

col1, col2 = st.columns([1,2])

# --- Fonctions de Callback (Logique) ---
def add_cabinet(origin_type='central'):
    if origin_type == 'central':
        if st.session_state['scene_cabinets']:
            st.warning("Un caisson central existe déjà.")
            return
        new_cabinet = {
            'dims': get_default_dims(),
            'debit_data': get_default_debit_data(),
            'name': "Caisson 0 (Central)",
            'parent_index': None, 'attachment_dir': None,
            'door_props': get_default_door_props(),
            'drawer_props': get_default_drawer_props(),
            'shelves': [],
            'material_body': 'Blanc Mat' 
        }
        st.session_state['scene_cabinets'].append(new_cabinet)
        st.session_state['selected_cabinet_index'] = 0
        st.session_state['base_cabinet_index'] = 0
    else: 
        base_index = st.session_state.get('base_cabinet_index', 0)
        if base_index is None or base_index >= len(st.session_state['scene_cabinets']):
            st.error("Aucun caisson de base sélectionné pour l'ajout.")
            return
        base_caisson = st.session_state['scene_cabinets'][base_index]
        new_cabinet = {
            'dims': copy.deepcopy(base_caisson['dims']), 
            'debit_data': get_default_debit_data(),
            'parent_index': base_index, 'attachment_dir': origin_type,
            'door_props': get_default_door_props(),
            'drawer_props': get_default_drawer_props(),
            'shelves': [],
            'material_body': 'Blanc Mat' 
        }
        base_L_m = base_caisson['dims']['L_raw'] * unit_factor
        base_H_m = base_caisson['dims']['H_raw'] * unit_factor
        new_L_m = new_cabinet['dims']['L_raw'] * unit_factor
        if origin_type == 'right': new_name = f"D de {base_index}"
        elif origin_type == 'left': new_name = f"G de {base_index}"
        else: new_name = f"H de {base_index}"
        new_cabinet['name'] = f"Caisson {len(st.session_state['scene_cabinets'])} ({new_name})"
        st.session_state['scene_cabinets'].append(new_cabinet)
        new_index = len(st.session_state['scene_cabinets']) - 1
        st.session_state['selected_cabinet_index'] = new_index
        st.session_state['base_cabinet_index'] = new_index
def clear_scene():
    st.session_state['scene_cabinets'] = []
    st.session_state['selected_cabinet_index'] = None
    st.session_state['base_cabinet_index'] = 0
def delete_selected_cabinet():
    idx_to_delete = st.session_state.get('selected_cabinet_index')
    if idx_to_delete is None or idx_to_delete >= len(st.session_state['scene_cabinets']):
        st.warning("Aucun caisson sélectionné pour la suppression.")
        return
    indices_to_remove = set()
    queue = [idx_to_delete]
    while queue:
        current_idx = queue.pop()
        if current_idx not in indices_to_remove:
            indices_to_remove.add(current_idx)
            for i, caisson in enumerate(st.session_state['scene_cabinets']):
                if caisson['parent_index'] == current_idx:
                    queue.append(i)
    new_scene = []
    old_to_new_index_map = {}
    new_idx_counter = 0
    for i, caisson in enumerate(st.session_state['scene_cabinets']):
        if i not in indices_to_remove:
            old_to_new_index_map[i] = new_idx_counter
            new_scene.append(caisson)
            new_idx_counter += 1
    for caisson in new_scene:
        if caisson['parent_index'] is not None:
            caisson['parent_index'] = old_to_new_index_map.get(caisson['parent_index'], None) 
    st.session_state['scene_cabinets'] = new_scene
    if not st.session_state['scene_cabinets']:
        st.session_state['selected_cabinet_index'] = None
        st.session_state['base_cabinet_index'] = 0
    else:
        st.session_state['selected_cabinet_index'] = 0
        st.session_state['base_cabinet_index'] = 0
def get_selected_cabinet():
    idx = st.session_state.get('selected_cabinet_index')
    if idx is not None and idx < len(st.session_state['scene_cabinets']):
        return st.session_state['scene_cabinets'][idx]
    return None
def update_selected_cabinet_dim(key):
    cabinet = get_selected_cabinet()
    widget_key = f"{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state:
        cabinet['dims'][key] = st.session_state[widget_key]
def update_selected_cabinet_door(key):
    cabinet = get_selected_cabinet()
    widget_key = f"{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state:
        if 'door_props' not in cabinet:
             cabinet['door_props'] = get_default_door_props()
        new_value = st.session_state[widget_key]
        cabinet['door_props'][key] = new_value
        if key == 'has_door' and new_value is True:
            if 'drawer_props' in cabinet:
                cabinet['drawer_props']['has_drawer'] = False
def update_selected_cabinet_drawer(key):
    cabinet = get_selected_cabinet()
    widget_key = f"{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state:
        if 'drawer_props' not in cabinet:
             cabinet['drawer_props'] = get_default_drawer_props()
        new_value = st.session_state[widget_key]
        cabinet['drawer_props'][key] = new_value
        if key == 'has_drawer' and new_value is True:
            if 'door_props' in cabinet:
                cabinet['door_props']['has_door'] = False

# --- NOUVELLES FONCTIONS CALLBACK POUR LES ÉTAGÈRES ---
def add_shelf_callback():
    cabinet = get_selected_cabinet()
    if cabinet:
        if 'shelves' not in cabinet:
            cabinet['shelves'] = []
        cabinet['shelves'].append(get_default_shelf_props())

# --- CORRECTION DE LA CLÉ DE WIDGET ---
def update_shelf_prop(shelf_index, key):
    cabinet = get_selected_cabinet()
    
    if key == 'shelf_type':
         widget_key = f"shelf_t_{st.session_state.selected_cabinet_index}_{shelf_index}"
    elif key == 'height':
         widget_key = f"shelf_h_{st.session_state.selected_cabinet_index}_{shelf_index}"
    elif key == 'thickness':
         widget_key = f"shelf_e_{st.session_state.selected_cabinet_index}_{shelf_index}"
    else:
         widget_key = f"shelf_{key[0]}_{st.session_state.selected_cabinet_index}_{shelf_index}"
         
    if cabinet and widget_key in st.session_state:
        if 'shelves' in cabinet and shelf_index < len(cabinet['shelves']):
            cabinet['shelves'][shelf_index][key] = st.session_state[widget_key]
# --- FIN CORRECTION ---

def delete_shelf_callback(shelf_index):
    cabinet = get_selected_cabinet()
    if cabinet:
        if 'shelves' in cabinet and shelf_index < len(cabinet['shelves']):
            cabinet['shelves'].pop(shelf_index)
            st.rerun() # Forcer le rafraîchissement pour que la liste UI se mette à jour
# --- FIN NOUVELLES FONCTIONS ---

# --- NOUVELLES FONCTIONS CALLBACK (POUR LES MATIÈRES) ---
def update_selected_cabinet_material(key):
    """Callback pour la matière du corps du caisson."""
    cabinet = get_selected_cabinet()
    widget_key = f"{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state:
        cabinet[key] = st.session_state[widget_key]

def update_selected_cabinet_door_material(key):
    """Callback pour la matière de la porte."""
    cabinet = get_selected_cabinet()
    # CORRECTION: Le widget key est "door_material_X"
    widget_key = f"door_{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state:
        cabinet['door_props']['material'] = st.session_state[widget_key]

def update_selected_cabinet_drawer_material(key):
    """Callback pour la matière du tiroir."""
    cabinet = get_selected_cabinet()
    # CORRECTION: Le widget key est "drawer_material_X"
    widget_key = f"drawer_{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state:
        cabinet['drawer_props']['material'] = st.session_state[widget_key]

def update_shelf_material(shelf_index, key):
    """Callback pour la matière d'une étagère."""
    # NOTE: Ici la clé est 'material' et non 'm'
    widget_key = f"shelf_m_{st.session_state.selected_cabinet_index}_{shelf_index}"
    cabinet = get_selected_cabinet()
    if cabinet and widget_key in st.session_state:
        if 'shelves' in cabinet and shelf_index < len(cabinet['shelves']):
            cabinet['shelves'][shelf_index]['material'] = st.session_state[widget_key]
# --- FIN NOUVELLES FONCTIONS ---

def apply_voice_command(parsed_result):
    cabinet = get_selected_cabinet()
    if cabinet:
        for key, value in parsed_result.items():
            if key in cabinet['dims']:
                cabinet['dims'][key] = value
def load_save_state():
    """Charge l'état complet de l'application depuis un fichier XLSX."""
    uploaded_file = st.session_state.get("file_loader")
    if uploaded_file is None:
        return
    try:
        wb = openpyxl.load_workbook(uploaded_file, data_only=True)
        if "SaveData" not in wb.sheetnames:
            st.error("Ce fichier Excel n'est pas un fichier de projet valide (feuille 'SaveData' manquante).")
            return
        ws_data = wb["SaveData"]
        json_string = ws_data['A1'].value
        if not json_string:
            st.error("Le fichier de projet est corrompu (pas de données en A1).")
            return
        data = json.loads(json_string)
        st.session_state.project_name = data.get('project_name', 'Projet Chargé')
        st.session_state.client = data.get('client', '')
        st.session_state.ref_chantier = data.get('ref_chantier', '')
        st.session_state.telephone = data.get('telephone', '')
        st.session_state.panneau_decor = data.get('panneau_decor', '')
        st.session_state.chant_mm = data.get('chant_mm', '')
        st.session_state.decor_chant = data.get('decor_chant', '')
        date_str = data.get('date_souhaitee')
        if date_str:
            st.session_state.date_souhaitee = datetime.date.fromisoformat(date_str)
        else:
            st.session_state.date_souhaitee = datetime.date.today()
        st.session_state.scene_cabinets = data.get('scene_cabinets', [])
        
        # MODIFIÉ : Compatibilité des sauvegardes
        default_drawer_props = get_default_drawer_props() # Pour les nouvelles clés
        default_shelf_props = get_default_shelf_props() # Pour les nouvelles clés
        default_door_props = get_default_door_props() # Pour les nouvelles clés
        
        for cab in st.session_state.scene_cabinets:
            # --- NOUVEAU : Compatibilité matière corps ---
            if 'material_body' not in cab:
                cab['material_body'] = 'Blanc Mat'

            if 'door_props' not in cab:
                cab['door_props'] = default_door_props.copy()
            else:
                if 'door_type' not in cab['door_props']: cab['door_props']['door_type'] = 'single'
                if 'door_thickness' not in cab['door_props']: cab['door_props']['door_thickness'] = 18.0
                if 'door_model' not in cab['door_props']: cab['door_props']['door_model'] = 'standard' 
                if 'material' not in cab['door_props']:
                    cab['door_props']['material'] = default_door_props['material']
            
            if 'drawer_props' not in cab:
                cab['drawer_props'] = default_drawer_props.copy()
            else:
                if 'drawer_handle_type' not in cab['drawer_props']:
                    cab['drawer_props']['drawer_handle_type'] = default_drawer_props['drawer_handle_type']
                if 'drawer_handle_width' not in cab['drawer_props']:
                    cab['drawer_props']['drawer_handle_width'] = default_drawer_props['drawer_handle_width']
                if 'drawer_handle_height' not in cab['drawer_props']:
                    cab['drawer_props']['drawer_handle_height'] = default_drawer_props['drawer_handle_height']
                if 'drawer_handle_offset_top' not in cab['drawer_props']:
                    cab['drawer_props']['drawer_handle_offset_top'] = default_drawer_props['drawer_handle_offset_top']
                if 'material' not in cab['drawer_props']:
                    cab['drawer_props']['material'] = default_drawer_props['material']


            # Ajout de la compatibilité pour les étagères
            if 'shelves' not in cab:
                cab['shelves'] = []
            for shelf in cab['shelves']:
                if 'thickness' not in shelf:
                    shelf['thickness'] = default_shelf_props['thickness']
                if 'material' not in shelf: 
                    shelf['material'] = default_shelf_props['material']
                if 'shelf_type' not in shelf: # CORRECTION IMPORTANTE
                    shelf['shelf_type'] = default_shelf_props['shelf_type']
        
        if st.session_state.scene_cabinets:
            st.session_state.selected_cabinet_index = 0
            st.session_state.base_cabinet_index = 0
        else:
            st.session_state.selected_cabinet_index = None
            st.session_state.base_cabinet_index = 0
        st.success(f"Projet '{st.session_state.project_name}' chargé !")
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier Excel : {e}")

# --- NOUVELLE FONCTION UTILITAIRE : CALCUL DES POSITIONS DE CHARNIÈRES ---
def get_hinge_y_positions(door_height_raw):
    """
    Calcule les positions Y (depuis le bas) pour les charnières,
    en fonction de la hauteur de la porte.
    """
    if door_height_raw <= 1000:
        num_hinges = 2
    elif door_height_raw <= 1500:
        num_hinges = 3
    elif door_height_raw <= 2000:
        num_hinges = 4
    elif door_height_raw <= 2400:
        num_hinges = 5
    else:
        num_hinges = 6
        
    if num_hinges == 2:
        return [80.0, door_height_raw - 80.0]
    
    y_positions = [80.0]
    if num_hinges > 2:
        inner_space = (door_height_raw - 80.0) - 80.0
        num_intervals = num_hinges - 1
        spacing = inner_space / num_intervals
        for i in range(1, num_hinges - 1):
            y_positions.append(80.0 + (i * spacing))
            
    y_positions.append(door_height_raw - 80.0)
    return sorted(list(set(y_positions))) # Assure l'unicité et l'ordre
# --- FIN NOUVELLE FONCTION ---


# --- Colonne 1 : Éditeur ---
with col1:
    st.header("Éditeur de Scène")

    # --- Section Sauvegarder / Charger ---
    st.subheader("Fichier Projet")
    save_data = {}
    if st.session_state.scene_cabinets:
        save_data = {
            'project_name': st.session_state.project_name,
            'client': st.session_state.client,
            'ref_chantier': st.session_state.ref_chantier,
            'telephone': st.session_state.telephone,
            'date_souhaitee': st.session_state.date_souhaitee.isoformat(),
            'panneau_decor': st.session_state.panneau_decor,
            'chant_mm': st.session_state.chant_mm,
            'decor_chant': st.session_state.decor_chant,
            'scene_cabinets': st.session_state.scene_cabinets
        }
    st.info("La sauvegarde du projet est incluse dans le 'Télécharger la Feuille de Débit Globale (XLS)' dans la colonne de droite.")
    st.file_uploader(
        "Charger un Projet (Fichier .xlsx)", 
        type=["xlsx"],
        key="file_loader",
        on_change=load_save_state
    )
    st.markdown("---")
    
    # --- Section d'assemblage ---
    st.subheader("Assemblage")
    st.button(
        "1. Ajouter le Caisson Central", 
        on_click=add_cabinet, args=('central',), # CORRECTION: on_on_change remplacé par on_click
        disabled=bool(st.session_state['scene_cabinets']), 
        use_container_width=True
    )
    if st.session_state['scene_cabinets']:
        cabinet_options = [f"{i}: {cab['name']}" for i, cab in enumerate(st.session_state['scene_cabinets'])]
        st.selectbox(
            "Ajouter relatif à :", 
            options=range(len(cabinet_options)),
            format_func=lambda x: cabinet_options[x],
            key='base_cabinet_index'
        )
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        col_btn1.button("⬅️ Gauche", on_click=add_cabinet, args=('left',), use_container_width=True)
        col_btn2.button("➡️ Droite", on_click=add_cabinet, args=('right',), use_container_width=True)
        col_btn3.button("⬆️ Dessus", on_click=add_cabinet, args=('up',), use_container_width=True)
    st.button("Vider la scène 🗑️", on_click=clear_scene, use_container_width=True)
    
    st.markdown("---")
    st.subheader("Options des Pieds (Global)")
    st.toggle("Ajouter des pieds", key='has_feet')
    if st.session_state.has_feet:
        st.selectbox("Hauteur des pieds (mm)", options=[80.0, 100.0, 120.0, 150.0], key='foot_height') # Options étendues
        st.number_input("Diamètre des pieds (mm)", min_value=10.0, key='foot_diameter')
    
    st.markdown("---")

    # --- Section d'édition ---
    st.subheader("Éditeur de Caisson")
    if not st.session_state['scene_cabinets']:
        st.info("Ajoutez un caisson central pour commencer l'édition.")
    else:
        cabinet_options = [f"{i}: {cab['name']}" for i, cab in enumerate(st.session_state['scene_cabinets'])]
        current_sel_idx = st.session_state.get('selected_cabinet_index', 0)
        if current_sel_idx is None or current_sel_idx >= len(cabinet_options):
            st.session_state.selected_cabinet_index = 0
        st.selectbox(
            "Éditer le caisson :", 
            options=range(len(cabinet_options)),
            format_func=lambda x: cabinet_options[x],
            key='selected_cabinet_index'
        )
        st.button(
            f"Supprimer le Caisson {st.session_state.selected_cabinet_index} 🗑️",
            on_click=delete_selected_cabinet,
            use_container_width=True, type="primary",
            disabled=(get_selected_cabinet() is None)
        )
        st.markdown("---")
        
        selected_cab = get_selected_cabinet()
        unit = st.selectbox("Unité", ["mm","cm","m"], index=0, key='unit_select')
        
        if selected_cab:
            idx_key = st.session_state.selected_cabinet_index
            
            # --- NOUVEAU : Sélecteur de matière pour le corps ---
            material_lib = get_material_library()
            material_options = list(material_lib.keys())
            
            st.selectbox(
                f"Matière Corps (Caisson {idx_key})",
                options=material_options,
                index=material_options.index(selected_cab.get('material_body', 'Blanc Mat')),
                key=f"material_body_{idx_key}",
                on_change=update_selected_cabinet_material,
                args=('material_body',)
            )
            # --- FIN NOUVEAU ---
            
            st.markdown(f"**Dimensions (Caisson {idx_key})**")
            dims = selected_cab['dims']
            st.number_input("Longueur (X)", value=dims['L_raw'], key=f"L_raw_{idx_key}", min_value=1.0, format="%.3f", on_change=update_selected_cabinet_dim, args=('L_raw',))
            st.number_input("Largeur (Y)", value=dims['W_raw'], key=f"W_raw_{idx_key}", min_value=1.0, format="%.3f", on_change=update_selected_cabinet_dim, args=('W_raw',))
            st.number_input("Hauteur (Z)", value=dims['H_raw'], key=f"H_raw_{idx_key}", min_value=1.0, format="%.3f", on_change=update_selected_cabinet_dim, args=('H_raw',))
            st.markdown(f"**Épaisseurs (Caisson {idx_key})**")
            st.number_input("Parois latérales", value=dims['t_lr_raw'], key=f"t_lr_raw_{idx_key}", min_value=0.0, format="%.3f", on_change=update_selected_cabinet_dim, args=('t_lr_raw',))
            st.number_input("Arrière", value=dims['t_fb_raw'], key=f"t_fb_raw_{idx_key}", min_value=0.0, format="%.3f", on_change=update_selected_cabinet_dim, args=('t_fb_raw',))
            st.number_input("Haut/Bas", value=dims['t_tb_raw'], key=f"t_tb_raw_{idx_key}", min_value=0.0, format="%.3f", on_change=update_selected_cabinet_dim, args=('t_tb_raw',))

            # MODIFIÉ : Initialisation des nouvelles listes
            if 'door_props' not in selected_cab: selected_cab['door_props'] = get_default_door_props()
            if 'drawer_props' not in selected_cab: selected_cab['drawer_props'] = get_default_drawer_props()
            if 'shelves' not in selected_cab: selected_cab['shelves'] = [] # Ajout
            door_props = selected_cab['door_props']
            drawer_props = selected_cab['drawer_props']

            # --- Éditeur de Porte ---
            st.markdown("---")
            st.markdown(f"**Porte (Caisson {idx_key})**")
            st.toggle("Ajouter une porte", value=door_props['has_door'], key=f"has_door_{idx_key}", on_change=update_selected_cabinet_door, args=('has_door',), disabled=drawer_props['has_drawer'])
            if door_props['has_door']:
                
                is_base_cabinet = (absolute_origins[idx_key][2] == 0)
                
                if is_base_cabinet and st.session_state.has_feet:
                    st.selectbox(
                        "Modèle de porte",
                        options=['standard', 'floor_length'],
                        format_func=lambda x: "Standard" if x == 'standard' else "Cache-pieds (jusqu'au sol)",
                        index=0 if door_props.get('door_model', 'standard') == 'standard' else 1,
                        key=f"door_model_{idx_key}",
                        on_change=update_selected_cabinet_door,
                        args=('door_model',)
                    )
                else:
                    if door_props.get('door_model') == 'floor_length':
                        door_props['door_model'] = 'standard'
                
                st.selectbox("Type de porte", options=['single', 'double'], format_func=lambda x: "1 battant" if x == 'single' else "2 battants", index=0 if door_props.get('door_type', 'single') == 'single' else 1, key=f"door_type_{idx_key}", on_change=update_selected_cabinet_door, args=('door_type',))
                if door_props.get('door_type', 'single') == 'single':
                    st.selectbox("Sens d'ouverture", options=['right', 'left'], format_func=lambda x: "Charnières à Droite" if x == 'right' else "Charnières à Gauche", index=0 if door_props['door_opening'] == 'right' else 1, key=f"door_opening_{idx_key}", on_change=update_selected_cabinet_door, args=('door_opening',))
                st.selectbox("Jeu extérieur (mm)", options=[2.0, 4.0], format_func=lambda x: f"{x} mm", index=0 if door_props['door_gap'] == 2.0 else 1, key=f"door_gap_{idx_key}", on_change=update_selected_cabinet_door, args=('door_gap',))
                st.number_input("Épaisseur de la porte (mm)", value=door_props.get('door_thickness', 18.0), key=f"door_thickness_{idx_key}", min_value=1.0, format="%.1f", on_change=update_selected_cabinet_door, args=('door_thickness',))

                st.selectbox(
                    "Matière Porte",
                    options=material_options,
                    index=material_options.index(door_props.get('material', 'Chêne Naturel')),
                    key=f"door_material_{idx_key}",
                    on_change=update_selected_cabinet_door_material,
                    args=('material',)
                )

            # --- Éditeur de Tiroir ---
            st.markdown("---")
            st.markdown(f"**Tiroir Bloc (Caisson {idx_key})**")
            st.toggle("Ajouter un tiroir bloc", value=drawer_props['has_drawer'], key=f"has_drawer_{idx_key}", on_change=update_selected_cabinet_drawer, args=('has_drawer',), disabled=door_props['has_door'])
            if drawer_props['has_drawer']:
                st.number_input("Hauteur de la face (mm)", value=drawer_props['drawer_face_H_raw'], key=f"drawer_face_H_raw_{idx_key}", min_value=50.0, format="%.1f", on_change=update_selected_cabinet_drawer, args=('drawer_face_H_raw',))
                st.number_input("Position / bas caisson (mm)", value=drawer_props['drawer_bottom_offset'], key=f"drawer_bottom_offset_{idx_key}", min_value=0.0, format="%.1f", on_change=update_selected_cabinet_drawer, args=('drawer_bottom_offset',), help="Distance entre le bas du caisson et le bas de la face du tiroir.")
                st.number_input("Épaisseur de la face (mm)", value=drawer_props.get('drawer_face_thickness', 19.0), key=f"drawer_face_thickness_{idx_key}", min_value=1.0, format="%.1f", on_change=update_selected_cabinet_drawer, args=('drawer_face_thickness',))
                st.selectbox("Jeu extérieur (mm)", options=[2.0, 4.0], format_func=lambda x: f"{x} mm", index=0 if drawer_props['drawer_gap'] == 2.0 else 1, key=f"drawer_gap_{idx_key}", on_change=update_selected_cabinet_drawer, args=('drawer_gap',))
                
                st.selectbox(
                    "Type de Poignée", 
                    options=['none', 'integrated_cutout'], 
                    format_func=lambda x: "Aucune" if x == 'none' else "Poignée Intégrée (Découpe)", 
                    index=0 if drawer_props.get('drawer_handle_type', 'none') == 'none' else 1,
                    key=f"drawer_handle_type_{idx_key}", 
                    on_change=update_selected_cabinet_drawer, 
                    args=('drawer_handle_type',)
                )
                
                if drawer_props.get('drawer_handle_type') == 'integrated_cutout':
                    st.number_input(
                        "Largeur Poignée (mm)", 
                        value=drawer_props.get('drawer_handle_width', 150.0), 
                        key=f"drawer_handle_width_{idx_key}", 
                        min_value=10.0, 
                        format="%.1f", 
                        on_change=update_selected_cabinet_drawer, 
                        args=('drawer_handle_width',)
                    )
                    st.number_input(
                        "Hauteur Poignée (mm)", 
                        value=drawer_props.get('drawer_handle_height', 40.0), 
                        key=f"drawer_handle_height_{idx_key}", 
                        min_value=10.0, 
                        format="%.1f", 
                        on_change=update_selected_cabinet_drawer, 
                        args=('drawer_handle_height',)
                    )
                    st.number_input(
                        "Offset Haut Poignée (mm)", 
                        value=drawer_props.get('drawer_handle_offset_top', 10.0), 
                        key=f"drawer_handle_offset_top_{idx_key}", 
                        min_value=0.0, 
                        format="%.1f", 
                        on_change=update_selected_cabinet_drawer, 
                        args=('drawer_handle_offset_top',),
                        help="Distance entre le haut de la face et le haut de la découpe."
                    )
                
                st.selectbox(
                    "Matière Face Tiroir",
                    options=material_options,
                    index=material_options.index(drawer_props.get('material', 'Rouge Vif')),
                    key=f"drawer_material_{idx_key}",
                    on_change=update_selected_cabinet_drawer_material,
                    args=('material',)
                )

            # --- Éditeur d'Étagères (MODIFIÉ) ---
            st.markdown("---")
            st.markdown(f"**Étagères (Caisson {idx_key})**")
            
            shelf_disabled = drawer_props['has_drawer']
            if shelf_disabled:
                st.info("Les étagères sont désactivées si un 'Tiroir Bloc' est présent.")
            
            st.button(f"Ajouter une étagère au Caisson {idx_key}", 
                      key=f"add_shelf_{idx_key}", 
                      on_click=add_shelf_callback, 
                      disabled=shelf_disabled, 
                      use_container_width=True)
            
            if 'shelves' in selected_cab and selected_cab['shelves']:
                st.markdown("---")
                
                # --- MODIFIÉ : Titres des colonnes (Ajout du Type) ---
                cols_titles = st.columns([2, 2, 2, 2, 1])
                cols_titles[0].markdown("<small>Type</small>", unsafe_allow_html=True)
                cols_titles[1].markdown("<small>Position (Bas)</small>", unsafe_allow_html=True)
                cols_titles[2].markdown("<small>Épaisseur</small>", unsafe_allow_html=True)
                cols_titles[3].markdown("<small>Matière</small>", unsafe_allow_html=True)
                # --- FIN MODIFICATION ---

                shelves_copy = list(enumerate(selected_cab['shelves']))
                
                for s_idx, shelf in shelves_copy:
                    # --- MODIFIÉ : Ajout du sélecteur de type ---
                    cols_shelf = st.columns([2, 2, 2, 2, 1])
                    
                    # NOUVEAU : Sélecteur Type (Clé corrigée)
                    cols_shelf[0].selectbox(
                        f"Type Etagère {s_idx+1}",
                        options=['mobile', 'fixe'],
                        index=0 if shelf.get('shelf_type', 'mobile') == 'mobile' else 1,
                        key=f"shelf_t_{idx_key}_{s_idx}", 
                        on_change=update_shelf_prop,
                        args=(s_idx, 'shelf_type'),
                        label_visibility="collapsed"
                    )
                    
                    cols_shelf[1].number_input(
                        f"Hauteur Etagère {s_idx+1} (Bas)", 
                        value=shelf['height'], 
                        key=f"shelf_h_{idx_key}_{s_idx}", 
                        on_change=update_shelf_prop, 
                        args=(s_idx, 'height'),
                        min_value=0.0,
                        format="%.1f",
                        label_visibility="collapsed",
                        help="Position Y (depuis le bas intérieur du caisson) où le BAS de l'étagère sera positionné."
                    )
                    
                    cols_shelf[2].number_input(
                        f"Épaisseur Etagère {s_idx+1}", 
                        value=shelf['thickness'], 
                        key=f"shelf_e_{idx_key}_{s_idx}", 
                        on_change=update_shelf_prop, 
                        args=(s_idx, 'thickness'),
                        min_value=1.0,
                        format="%.1f",
                        label_visibility="collapsed"
                    )
                    
                    # --- Sélecteur matière étagère ---
                    cols_shelf[3].selectbox(
                        f"Matière Etagère {s_idx+1}",
                        options=material_options,
                        index=material_options.index(shelf.get('material', 'Blanc Mat')),
                        key=f"shelf_m_{idx_key}_{s_idx}",
                        on_change=update_shelf_material,
                        args=(s_idx, 'material'),
                        label_visibility="collapsed"
                    )
                    # --- FIN NOUVEAU ---
                    
                    cols_shelf[4].button(
                        "🗑️", 
                        key=f"del_shelf_{idx_key}_{s_idx}", 
                        on_click=delete_shelf_callback, 
                        args=(s_idx,)
                    )
            # --- FIN MODIFICATION ÉTAGÈRE UI ---

            # --- Commande vocale ---
            st.markdown("---")
            st.markdown("🎤 **Commande Vocale (pour Caisson SÉLECTIONNÉ)**")
            audio_data = audiorecorder("Enregistrer", "Transcrire...", key=st.session_state.audio_recorder_key)
            if len(audio_data) > 0:
                try:
                    wav_io = io.BytesIO()
                    audio_data.export(wav_io, format="wav")
                    r = sr.Recognizer()
                    with sr.AudioFile(wav_io) as source: audio = r.record(source)
                    voice_command = r.recognize_google(audio, language="fr-FR")
                    st.info(f"Transc.: {voice_command}")
                    unit_factor = {"mm":0.001,"cm":0.01,"m":1.0}[unit]
                    parsed_result, error = parse_all_voice_commands(voice_command, unit_factor)
                    if parsed_result:
                        apply_voice_command(parsed_result) 
                        st.success("✅ Cotes appliquées au caisson sélectionné.")
                        st.rerun() 
                    else:
                        st.error(f"❌ Commande non comprise: {error}")
                except Exception as e:
                    st.error(f"Erreur audio: {e}")
                finally:
                    idx = int(st.session_state.audio_recorder_key.split('_')[-1])
                    st.session_state.audio_recorder_key = f'audio_key_{idx+1}'
                    st.rerun()

            # --- Éditeur de Chants ---
            st.markdown("---")
            st.markdown(f"**Feuille de débit (pour Caisson {st.session_state.selected_cabinet_index})**")
            debit_data = selected_cab['debit_data']
            dims = selected_cab['dims']
            h_side_raw = dims['H_raw'] - 2 * dims['t_tb_raw']
            w_back_raw = dims['L_raw'] - 2 * dims['t_lr_raw']
            panel_dims = {
                "Traverse Bas (Tb)": (dims['L_raw'], dims['W_raw']),
                "Traverse Haut (Th)": (dims['L_raw'], dims['W_raw']),
                "Montant Gauche (Mg)": (h_side_raw, dims['W_raw']),
                "Montant Droit (Md)": (h_side_raw, dims['W_raw']),
                "Fond (F)": (w_back_raw, h_side_raw)
            }
            for row in debit_data:
                ref_piece = row["Référence Pièce"]
                if ref_piece in panel_dims:
                    row["Longueur (mm)"] = panel_dims[ref_piece][0]
                    row["Largeur (mm)"] = panel_dims[ref_piece][1]
            df_editor = pd.DataFrame(debit_data)
            edited_df = st.data_editor(
                df_editor,
                key=f"editor_{st.session_state.selected_cabinet_index}", 
                column_config={
                    "Lettre": st.column_config.TextColumn("N°", width="small", disabled=True),
                    "Référence Pièce": st.column_config.TextColumn("Référence Pièce", width="medium", disabled=True),
                    "Qté": st.column_config.NumberColumn("Qté", min_value=0, step=1),
                    "Longueur (mm)": st.column_config.NumberColumn("Longueur (mm)", format="%.2f", disabled=True),
                    "Chant Avant": st.column_config.CheckboxColumn("Avant", width="small"),
                    "Chant Arrière": st.column_config.CheckboxColumn("Arrière", width="small"),
                    "Largeur (mm)": st.column_config.NumberColumn("Largeur (mm)", format="%.2f", disabled=True),
                    "Chant Gauche": st.column_config.CheckboxColumn("Gauche", width="small"),
                    "Chant Droit": st.column_config.CheckboxColumn("Droit", width="small"),
                    "Usinage": st.column_config.TextColumn("Usinage (*)"),
                },
                column_order=[
                    "Lettre", "Référence Pièce", "Qté", 
                    "Longueur (mm)", "Chant Avant", "Chant Arrière", 
                    "Largeur (mm)", "Chant Gauche", "Chant Droit", 
                    "Usinage"
                ],
                hide_index=True,
                num_rows="dynamic" 
            )
            selected_cab['debit_data'] = edited_df.to_dict('records')

    # --- Infos Projet Globales (pour l'export) ---
    st.markdown("---")
    st.subheader("Informations Projet (Global)")
    with st.expander("Modifier les infos de l'export"):
        st.text_input("Nom du Projet", key='project_name')
        st.text_input("Corps du meuble", key='corps_meuble')
        st.text_input("Client", key='client')
        st.text_input("Réf. Chantier", key='ref_chantier')
        st.text_input("Téléphone / Mail", key='telephone')
        st.date_input("Date souhaitée", key='date_souhaitee')
        st.text_input("Panneau / Décor", key='panneau_decor')
        st.text_input("Chant (mm)", key='chant_mm')
        st.text_input("Décor Chant", key='decor_chant')


# --- Colonne 2 : Visualisation et Sorties ---
with col2:
    st.header("Prévisualisation 3D de la Scène")
    
    # --- Section 3D (inchangée) ---
    fig3d = go.Figure()
    if not st.session_state['scene_cabinets']:
        st.info("La scène est vide. Ajoutez un caisson central depuis la colonne de gauche.")
    else:
        material_lib = get_material_library()
        default_color = "#AAAAAA" 
        scene = st.session_state['scene_cabinets']
        all_L_coords, all_W_coords, all_H_coords = [0.0], [0.0], [0.0]

        for i, cabinet in enumerate(scene):
            dims = cabinet['dims']
            L, W, H = dims['L_raw'] * unit_factor, dims['W_raw'] * unit_factor, dims['H_raw'] * unit_factor
            t_lr, t_fb, t_tb = dims['t_lr_raw'] * unit_factor, dims['t_fb_raw'] * unit_factor, dims['t_tb_raw'] * unit_factor
            origin_plot = absolute_origins[i] 
            
            all_L_coords.extend([origin_plot[0], origin_plot[0] + L])
            all_W_coords.extend([origin_plot[1], origin_plot[1] + W])
            all_H_coords.extend([origin_plot[2], origin_plot[2] + H])

            body_material_name = cabinet.get('material_body', 'Blanc Mat')
            panel_color = material_lib.get(body_material_name, default_color)
            panel_opacity = 1.0
            
            h_side, w_back = H - 2 * t_tb, L - 2 * t_lr

            fig3d.add_trace(cuboid_mesh_for(L, W, t_tb, origin=origin_plot, name=cabinet['name'], color=panel_color, opacity=panel_opacity, showlegend=(i==0)))
            fig3d.add_trace(cuboid_mesh_for(L, W, t_tb, origin=(origin_plot[0], origin_plot[1], origin_plot[2] + H - t_tb), name=cabinet['name'], color=panel_color, opacity=panel_opacity, showlegend=False))
            fig3d.add_trace(cuboid_mesh_for(t_lr, W, h_side, origin=(origin_plot[0], origin_plot[1], origin_plot[2] + t_tb), name=cabinet['name'], color=panel_color, opacity=panel_opacity, showlegend=False))
            fig3d.add_trace(cuboid_mesh_for(t_lr, W, h_side, origin=(origin_plot[0] + L - t_lr, origin_plot[1], origin_plot[2] + t_tb), name=cabinet['name'], color=panel_color, opacity=panel_opacity, showlegend=False))
            fig3d.add_trace(cuboid_mesh_for(w_back, t_fb, h_side, origin=(origin_plot[0] + t_lr, origin_plot[1] + W - t_fb, origin_plot[2] + t_tb), name=cabinet['name'], color=panel_color, opacity=panel_opacity, showlegend=False))
            
            inner_L, inner_W, inner_H = L - (2 * t_lr), W - t_fb, H - (2 * t_tb)
            inner_origin = (origin_plot[0] + t_lr, origin_plot[1], origin_plot[2] + t_tb)
            if inner_L > 0 and inner_W > 0 and inner_H > 0:
                fig3d.add_trace(cuboid_mesh_for(inner_L, inner_W, inner_H, origin=inner_origin, name=f"Intérieur {i}", color='#ecf0f1', opacity=0.4, showlegend=False))
            
            if cabinet['door_props']['has_door']:
                door_props = cabinet['door_props']
                door_gap_m = door_props['door_gap'] * unit_factor 
                door_T_m = door_props.get('door_thickness', 18.0) * unit_factor
                
                door_origin_y = origin_plot[1] - door_T_m
                is_base_cabinet = (absolute_origins[i][2] == 0)
                door_material_name = door_props.get('material', 'Chêne Naturel')
                door_color = material_lib.get(door_material_name, default_color)
                door_opacity = 1.0
                
                if door_props.get('door_model') == 'floor_length' and is_base_cabinet and st.session_state.has_feet:
                    foot_height_m = st.session_state.foot_height * unit_factor
                    jeu_bas_sol_m = 10.0 * unit_factor
                    door_H_m = H + foot_height_m - door_gap_m - jeu_bas_sol_m
                    door_origin_z = origin_plot[2] - foot_height_m + jeu_bas_sol_m
                    door_color = "#636e72"
                else:
                    door_H_m = H - (2 * door_gap_m)
                    door_origin_z = origin_plot[2] + door_gap_m
                
                all_W_coords.append(door_origin_y) 
                angle_open = 50.0 
                
                if door_props.get('door_type', 'single') == 'single':
                    door_L_m = L - (2 * door_gap_m)
                    door_origin_x = origin_plot[0] + door_gap_m
                    door_origin = (door_origin_x, door_origin_y, door_origin_z)
                    if door_L_m > 0 and door_H_m > 0:
                        if door_props['door_opening'] == 'right':
                            pivot_point = (door_origin_x + door_L_m, door_origin_y, door_origin_z)
                            angle_to_apply = -angle_open
                        else:
                            pivot_point = door_origin
                            angle_to_apply = angle_open
                            
                        fig3d.add_trace(cuboid_mesh_for(
                            door_L_m, door_T_m, door_H_m, 
                            origin=door_origin, 
                            name=f"Porte {i}", 
                            color=door_color, 
                            opacity=door_opacity, showlegend=True,
                            rotation_angle=angle_to_apply,
                            rotation_axis='z',
                            rotation_pivot=pivot_point
                        ))
                else: 
                    middle_gap_m = 2.0 * unit_factor
                    battant_L_m = (L - (2 * door_gap_m) - middle_gap_m) / 2
                    battant1_origin_x = origin_plot[0] + door_gap_m
                    door_origin_G = (battant1_origin_x, door_origin_y, door_origin_z)
                    pivot_G = door_origin_G 
                    battant2_origin_x = battant1_origin_x + battant_L_m + middle_gap_m
                    door_origin_D = (battant2_origin_x, door_origin_y, door_origin_z)
                    pivot_D = (battant2_origin_x + battant_L_m, door_origin_y, door_origin_z) 
                    
                    if battant_L_m > 0 and door_H_m > 0:
                        fig3d.add_trace(cuboid_mesh_for(battant_L_m, door_T_m, door_H_m, origin=door_origin_G, name=f"Porte {i}-G", color=door_color, opacity=door_opacity, showlegend=True, rotation_angle=angle_open, rotation_axis='z', rotation_pivot=pivot_G))
                        fig3d.add_trace(cuboid_mesh_for(battant_L_m, door_T_m, door_H_m, origin=door_origin_D, name=f"Porte {i}-D", color=door_color, opacity=door_opacity, showlegend=False, rotation_angle=-angle_open, rotation_axis='z', rotation_pivot=pivot_D))
            
            if cabinet['drawer_props']['has_drawer']:
                drawer_props = cabinet['drawer_props']
                drawer_gap_m = drawer_props['drawer_gap'] * unit_factor
                drawer_T_m = drawer_props.get('drawer_face_thickness', 19.0) * unit_factor
                drawer_H_m = drawer_props['drawer_face_H_raw'] * unit_factor
                drawer_L_m = L - (2 * drawer_gap_m)
                drawer_origin_x = origin_plot[0] + drawer_gap_m
                drawer_origin_y = origin_plot[1] - drawer_T_m 
                drawer_origin_z = origin_plot[2] + (drawer_props['drawer_bottom_offset'] * unit_factor)
                all_W_coords.append(drawer_origin_y)
                drawer_material_name = drawer_props.get('material', 'Rouge Vif')
                drawer_color = material_lib.get(drawer_material_name, default_color)
                
                if drawer_L_m > 0 and drawer_H_m > 0:
                    fig3d.add_trace(cuboid_mesh_for(drawer_L_m, drawer_T_m, drawer_H_m, origin=(drawer_origin_x, drawer_origin_y, drawer_origin_z), name=f"Face Tiroir {i}", color=drawer_color, opacity=0.9, showlegend=True))
                
                if drawer_props.get('drawer_handle_type') == 'integrated_cutout':
                    cutout_W_m = drawer_props.get('drawer_handle_width', 150.0) * unit_factor
                    cutout_H_m = drawer_props.get('drawer_handle_height', 40.0) * unit_factor
                    cutout_offset_top_m = drawer_props.get('drawer_handle_offset_top', 10.0) * unit_factor
                    cutout_W_m = min(cutout_W_m, drawer_L_m * 0.9)
                    cutout_H_m = min(cutout_H_m, drawer_H_m * 0.9)
                    cutout_X = drawer_origin_x + (drawer_L_m - cutout_W_m) / 2
                    cutout_Y = drawer_origin_y - (0.001 * unit_factor) 
                    cutout_Z = drawer_origin_z + drawer_H_m - cutout_offset_top_m - cutout_H_m
                    cutout_T_m = drawer_T_m + (0.002 * unit_factor)
                    fig3d.add_trace(cuboid_mesh_for(cutout_W_m, cutout_T_m, cutout_H_m, origin=(cutout_X, cutout_Y, cutout_Z), name=f"Découpe Poignée {i}", color="#2c3e50", opacity=0.5, showlegend=False))

                jeu_coulisse_total_m = 49.0 * unit_factor
                drawer_inner_D_m = W - (20.0 * unit_factor) - t_fb
                drawer_inner_L_m = L - (2 * t_lr) - jeu_coulisse_total_m
                drawer_inner_H_m = drawer_H_m - (2 * drawer_gap_m) 
                drawer_inner_x = origin_plot[0] + t_lr + (jeu_coulisse_total_m / 2)
                drawer_inner_y = origin_plot[1] 
                drawer_inner_z = drawer_origin_z + drawer_gap_m
                if drawer_inner_L_m > 0 and drawer_inner_H_m > 0 and drawer_inner_D_m > 0:
                     fig3d.add_trace(cuboid_mesh_for(drawer_inner_L_m, drawer_inner_D_m, drawer_inner_H_m, origin=(drawer_inner_x, drawer_inner_y, drawer_inner_z), name=f"Bloc Tiroir {i}", color="#bdc3c7", opacity=0.3, showlegend=False))

            if 'shelves' in cabinet and cabinet['shelves']:
                inner_L_m = L - (2 * t_lr)
                inner_W_m = W - t_fb 
                inner_origin_x, inner_origin_y, inner_origin_z = (origin_plot[0] + t_lr, origin_plot[1], origin_plot[2] + t_tb)

                for s_idx, shelf in enumerate(cabinet['shelves']):
                    shelf_H_m = shelf['thickness'] * unit_factor
                    shelf_bottom_z_abs = inner_origin_z + (shelf['height'] * unit_factor)
                    shelf_origin = (inner_origin_x, inner_origin_y, shelf_bottom_z_abs)
                    shelf_material_name = shelf.get('material', 'Blanc Mat')
                    shelf_color = material_lib.get(shelf_material_name, default_color)
                    
                    if inner_L_m > 0 and inner_W_m > 0 and shelf_H_m > 0:
                        fig3d.add_trace(cuboid_mesh_for(
                            inner_L_m, inner_W_m, shelf_H_m, 
                            origin=shelf_origin, 
                            name=f"Etagère {i}-{s_idx}", 
                            color=shelf_color, 
                            opacity=0.9, 
                            showlegend=True
                        ))
            
        if st.session_state.has_feet:
            base_caissons_indices = [i for i, origin in absolute_origins.items() if origin[2] == 0]
            if base_caissons_indices:
                base_L_coords = []
                base_W_coords = []
                for i in base_caissons_indices:
                    origin = absolute_origins[i]
                    dims = scene[i]['dims']
                    L_m = dims['L_raw'] * unit_factor
                    W_m = dims['W_raw'] * unit_factor
                    base_L_coords.extend([origin[0], origin[0] + L_m])
                    base_W_coords.extend([origin[1], origin[1] + W_m])
                
                if base_L_coords:
                    min_L, max_L = min(base_L_coords), max(base_L_coords)
                    min_W, max_W = min(base_W_coords), max(base_W_coords)
                    foot_h_m = st.session_state.foot_height * unit_factor
                    foot_d_m = st.session_state.foot_diameter * unit_factor
                    foot_offset_m = 50.0 * unit_factor
                    z_origin = -foot_h_m 
                    foot_color = '#34495e'
                    pos1 = (min_L + foot_offset_m, min_W + foot_offset_m, z_origin)
                    pos2 = (max_L - foot_offset_m, min_W + foot_offset_m, z_origin)
                    pos3 = (min_L + foot_offset_m, max_W - foot_offset_m, z_origin)
                    pos4 = (max_L - foot_offset_m, max_W - foot_offset_m, z_origin)
                    fig3d.add_trace(cylinder_mesh_for(pos1, foot_h_m, foot_d_m / 2, color=foot_color, name="Pieds", showlegend=True))
                    fig3d.add_trace(cylinder_mesh_for(pos2, foot_h_m, foot_d_m / 2, color=foot_color, showlegend=False))
                    fig3d.add_trace(cylinder_mesh_for(pos3, foot_h_m, foot_d_m / 2, color=foot_color, showlegend=False))
                    fig3d.add_trace(cylinder_mesh_for(pos4, foot_h_m, foot_d_m / 2, color=foot_color, showlegend=False))
                    all_H_coords.append(-foot_h_m)

        # Dessin du Sol
        sol_z = min(all_H_coords) - 0.01 
        min_L, max_L = min(all_L_coords), max(all_L_coords)
        min_W, max_W = min(all_W_coords), max(all_W_coords)
        margin_L, margin_W = (max_L - min_L) * 0.5 + 1, (max_W - min_W) * 0.5 + 1
        sol = np.array([ [min_L - margin_L, min_W - margin_W, sol_z], [max_L + margin_L, min_W - margin_W, sol_z], [max_L + margin_L, max_W + margin_W, sol_z], [min_L - margin_L, max_W + margin_W, sol_z] ])
        fig3d.add_trace(go.Mesh3d(x=sol[:,0], y=sol[:,1], z=sol[:,2], i=[0], j=[1], k=[2], color="lightgray", opacity=0.8, flatshading=True, showscale=False, hoverinfo="skip"))
        fig3d.add_trace(go.Mesh3d(x=sol[:,0], y=sol[:,1], z=sol[:,2], i=[0], j=[2], k=[3], color="lightgray", opacity=0.8, flatshading=True, showscale=False, hoverinfo="skip"))

    fig3d.update_layout(scene=dict(aspectmode='data', camera=dict(eye=dict(x=1.5, y=-1.5, z=1.2))), margin=dict(l=0,r=0,t=0,b=0), showlegend=True)
    st.plotly_chart(fig3d, use_container_width=True)

    
    # --- Feuille de Débit Globale (inchangée) ---
    st.markdown("---")
    st.subheader("📋 Feuille de Débit Globale (Tous les caissons)")
    if not st.session_state['scene_cabinets']:
        st.info("Aucun caisson dans la scène. La feuille de débit est vide.")
    else:
        all_pieces = []
        lettre_code = 65 
        for i, cabinet in enumerate(st.session_state['scene_cabinets']):
            dims, debit_data = cabinet['dims'], cabinet['debit_data']
            
            body_material_name = cabinet.get('material_body', 'Blanc Mat')
            
            h_side_raw = dims['H_raw'] - 2 * dims['t_tb_raw']
            w_back_raw = dims['L_raw'] - 2 * dims['t_lr_raw']
            panel_dims = {
                "Traverse Bas (Tb)": (dims['L_raw'], dims['W_raw']), "Traverse Haut (Th)": (dims['L_raw'], dims['W_raw']),
                "Montant Gauche (Mg)": (h_side_raw, dims['W_raw']), "Montant Droit (Md)": (h_side_raw, dims['W_raw']),
                "Fond (F)": (w_back_raw, h_side_raw)
            }
            for piece in debit_data:
                new_piece = piece.copy()
                new_piece['Lettre'] = f"C{i}-{chr(lettre_code)}"
                lettre_code += 1
                
                ref = new_piece["Référence Pièce"]
                new_piece["Référence Pièce"] = f"{ref} ({body_material_name})"
                
                if ref.split(' (')[0] in panel_dims:
                    ref_key = ref.split(' (')[0]
                    new_piece["Longueur (mm)"] = panel_dims[ref_key][0]
                    new_piece["Largeur (mm)"] = panel_dims[ref_key][1]
                all_pieces.append(new_piece)
            
            if cabinet['door_props']['has_door']:
                door_props = cabinet['door_props']
                door_material_name = door_props.get('material', 'Chêne Naturel')
                
                door_gap_raw = door_props['door_gap']
                is_base_cabinet = (absolute_origins[i][2] == 0)
                if door_props.get('door_model') == 'floor_length' and is_base_cabinet and st.session_state.has_feet:
                    foot_height_raw = st.session_state.foot_height
                    door_H_raw_dim = dims['H_raw'] + foot_height_raw - door_gap_raw - 10.0
                else:
                    door_H_raw_dim = dims['H_raw'] - (2 * door_gap_raw)
                if door_props.get('door_type', 'single') == 'single':
                    door_W_raw_dim = dims['L_raw'] - (2 * door_gap_raw) 
                    opening_dir = "Gauche" if door_props['door_opening'] == 'left' else "Droite"
                    all_pieces.append({
                        "Lettre": f"C{i}-P", 
                        "Référence Pièce": f"Porte (Ch. {opening_dir}) ({door_material_name})", 
                        "Qté": 1, 
                        "Longueur (mm)": door_H_raw_dim, "Chant Avant": True, "Chant Arrière": True, 
                        "Largeur (mm)": door_W_raw_dim, "Chant Gauche": True, "Chant Droit": True, 
                        "Usinage": f"Perçages charnières Côté {opening_dir}"
                    })
                else: 
                    middle_gap_raw = 2.0
                    battant_W_raw_dim = (dims['L_raw'] - (2 * door_gap_raw) - middle_gap_raw) / 2
                    all_pieces.append({
                        "Lettre": f"C{i}-P", 
                        "Référence Pièce": f"Porte (2 battants) ({door_material_name})", 
                        "Qté": 2, 
                        "Longueur (mm)": door_H_raw_dim, "Chant Avant": True, "Chant Arrière": True, 
                        "Largeur (mm)": battant_W_raw_dim, "Chant Gauche": True, "Chant Droit": True, 
                        "Usinage": "Perçages charnières"
                    })
            
            if cabinet['drawer_props']['has_drawer']:
                drawer_props = cabinet['drawer_props']
                drawer_material_name = drawer_props.get('material', 'Rouge Vif')
                
                dims = cabinet['dims']
                jeu_coulisse_total_mm = 49.0
                face_L = dims['L_raw'] - (2 * drawer_props['drawer_gap'])
                face_H = drawer_props['drawer_face_H_raw']
                
                usinage_txt = "Perçages Tourillons (voir plan)"
                if drawer_props.get('drawer_handle_type') == 'integrated_cutout':
                    usinage_txt += " + Découpe Poignée (voir plan)"
                    
                all_pieces.append({
                    "Lettre": f"C{i}-TF", 
                    "Référence Pièce": f"Tiroir-Face ({drawer_material_name})", 
                    "Qté": 1,
                    "Longueur (mm)": face_H, "Chant Avant": True, "Chant Arrière": True,
                    "Largeur (mm)": face_L, "Chant Gauche": True, "Chant Droit": True,
                    "Usinage": usinage_txt
                })
                dos_L = dims['L_raw'] - (2 * dims['t_lr_raw']) - jeu_coulisse_total_mm
                dos_H = 151.0
                all_pieces.append({
                    "Lettre": f"C{i}-TD", 
                    "Référence Pièce": f"Tiroir-Dos ({body_material_name})", 
                    "Qté": 1,
                    "Longueur (mm)": dos_H, "Chant Avant": True, "Chant Arrière": False,
                    "Largeur (mm)": dos_L, "Chant Gauche": False, "Chant Droit": False,
                    "Usinage": "Perçages Vis (voir plan)"
                })
                fond_L = dims['W_raw'] - (20.0 + dims['t_fb_raw'])
                fond_W = dos_L
                all_pieces.append({
                    "Lettre": f"C{i}-TO", 
                    "Référence Pièce": f"Tiroir-Fond ({body_material_name})", 
                    "Qté": 1,
                    "Longueur (mm)": fond_L, "Chant Avant": False, "Chant Arrière": False,
                    "Largeur (mm)": fond_W, "Chant Gauche": False, "Chant Droit": False,
                    "Usinage": ""
                })

            if 'shelves' in cabinet and cabinet['shelves']:
                dims = cabinet['dims'] 
                shelf_L_dim = dims['L_raw'] - (2 * dims['t_lr_raw'])
                shelf_W_dim = dims['W_raw'] - dims['t_fb_raw']
                
                for s_idx, shelf in enumerate(cabinet['shelves']):
                    shelf_material_name = shelf.get('material', 'Blanc Mat')
                    shelf_T = shelf['thickness']
                    
                    type_str = "FIXE" if shelf.get('shelf_type') == 'fixe' else "MOBILE"
                    usinage_txt = "Vis/Tourillons Tranches Côtés" if shelf.get('shelf_type') == 'fixe' else "Aucun (Taquets mobiles)"

                    ref_piece_str = f"Etagère ({type_str}, Ep. {shelf_T:.1f}mm) ({shelf_material_name})"
                    all_pieces.append({
                        "Lettre": f"C{i}-E{s_idx+1}", 
                        "Référence Pièce": ref_piece_str, 
                        "Qté": 1,
                        "Longueur (mm)": shelf_L_dim, 
                        "Chant Avant": True, 
                        "Chant Arrière": False,
                        "Largeur (mm)": shelf_W_dim, 
                        "Chant Gauche": False, # FORCÉ À FALSE
                        "Chant Droit": False,  # FORCÉ À FALSE
                        "Usinage": usinage_txt
                    })
            
            lettre_code = 65
            
        df_global = pd.DataFrame(all_pieces)
        st.dataframe(df_global, hide_index=True)
        
        project_info = {
            "project_name": st.session_state.project_name, "corps_meuble": "Assemblage", "quantity": 1, 
            "date": datetime.date.today().strftime("%Y-%m-%d"), "client": st.session_state.client, 
            "ref_chantier": st.session_state.ref_chantier, "telephone": st.session_state.telephone, 
            "date_souhaitee": st.session_state.date_souhaitee.strftime("%d/%m/%Y"),
            "panneau_decor": st.session_state.panneau_decor, "chant_mm": st.session_state.chant_mm,
            "decor_chant": st.session_state.decor_chant
        }
        ref_t_tb = st.session_state.scene_cabinets[0]['dims']['t_tb_raw']
        
        save_data_for_excel = {
            'project_name': st.session_state.project_name,
            'client': st.session_state.client,
            'ref_chantier': st.session_state.ref_chantier,
            'telephone': st.session_state.telephone,
            'date_souhaitee': st.session_state.date_souhaitee.isoformat(),
            'panneau_decor': st.session_state.panneau_decor,
            'chant_mm': st.session_state.chant_mm,
            'decor_chant': st.session_state.decor_chant,
            'scene_cabinets': st.session_state.scene_cabinets
        }
        
        xls_data = create_styled_excel(
            project_info_dict=project_info, 
            df_data_edited=df_global, 
            t_tb_raw_val=ref_t_tb,
            save_data_dict=save_data_for_excel 
        ) 
        
        st.download_button(
            label="📥 Télécharger Fiche de Débit ET Projet (.xlsx)", 
            data=xls_data,
            file_name=f"Projet_{project_info['project_name'].replace(' ', '_')}.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            help="Ce fichier contient la feuille de débit ET les données de sauvegarde de votre projet."
        )

    # --- Feuilles d'usinage du caisson SÉLECTIONNÉ ---
    st.markdown("---")
    selected_cab_idx = st.session_state.get('selected_cabinet_index')
    st.subheader(f"📋 Feuilles d'usinage (Caisson {selected_cab_idx})")
    
    selected_cab = get_selected_cabinet()
    
    if not selected_cab:
        st.info("Sélectionnez un caisson dans la colonne de gauche pour voir ses plans d'usinage.")
    else:
        dims, debit_data = selected_cab['dims'], selected_cab['debit_data']
        unit_str = st.session_state.unit_select
        L_raw_val, W_raw_val, H_raw_val = dims['L_raw'], dims['W_raw'], dims['H_raw']
        t_lr_raw_val, t_fb_raw_val, t_tb_raw_val = dims['t_lr_raw'], dims['t_fb_raw'], dims['t_tb_raw']
        project_info = {
            "project_name": st.session_state.project_name, "corps_meuble": selected_cab['name'], "quantity": 1, 
            "date": datetime.date.today().strftime("%Y-%m-%d"), "client": st.session_state.client, 
            "ref_chantier": st.session_state.ref_chantier, "telephone": st.session_state.telephone, 
            "date_souhaitee": st.session_state.date_souhaitee.strftime("%d/%m/%Y"),
            "panneau_decor": st.session_state.panneau_decor, "chant_mm": st.session_state.chant_mm,
            "decor_chant": st.session_state.decor_chant
        }
        h_side_raw = H_raw_val - 2 * t_tb_raw_val
        w_back_raw = L_raw_val - 2 * t_lr_raw_val
        ys_vis, ys_dowel = calculate_hole_positions(W_raw_val) # Positions en profondeur
        
        face_holes_montants_g = [] 
        face_holes_montants_d = []
        
        # 1. Trous d'assemblage HAUT et BAS (Vis + Tourillons)
        for x in ys_vis:
            hole_top = {'type': 'vis', 'x': x, 'y': h_side_raw - (t_tb_raw_val / 2), 'diam_str': "⌀3"}
            hole_bot = {'type': 'vis', 'x': x, 'y': t_tb_raw_val / 2, 'diam_str': "⌀3"}
            face_holes_montants_g.extend([hole_bot, hole_top])
            face_holes_montants_d.extend([hole_bot, hole_top])
        for x in ys_dowel:
            hole_top = {'type': 'tourillon', 'x': x, 'y': h_side_raw - (t_tb_raw_val / 2), 'diam_str': "⌀8"}
            hole_bot = {'type': 'tourillon', 'x': x, 'y': t_tb_raw_val / 2, 'diam_str': "⌀8"}
            face_holes_montants_g.extend([hole_bot, hole_top])
            face_holes_montants_d.extend([hole_bot, hole_top])

        tranche_cote_holes_traverses = [ {'type': 'tourillon', 'x': t_tb_raw_val / 2, 'y': y, 'diam_str': "⌀8"} for y in ys_dowel ]
        
        # 2. Trous Charnières (inchangé)
        door_props = selected_cab['door_props']
        if door_props['has_door']:
            y_positions_montant = get_hinge_y_positions(h_side_raw) 
            
            if door_props.get('door_type', 'single') == 'single':
                if door_props['door_opening'] == 'left': # Charnières à gauche
                    for y in y_positions_montant:
                        face_holes_montants_g.extend([{'type': 'vis', 'x': 20.0, 'y': y, 'diam_str': "⌀5/11.5"}, {'type': 'vis', 'x': 52.0, 'y': y, 'diam_str': "⌀5/11.5"}])
                else: # Charnières à droite
                    for y in y_positions_montant:
                        face_holes_montants_d.extend([{'type': 'vis', 'x': 20.0, 'y': y, 'diam_str': "⌀5/11.5"}, {'type': 'vis', 'x': 52.0, 'y': y, 'diam_str': "⌀5/11.5"}])
            else: # 2 battants
                for y in y_positions_montant:
                    face_holes_montants_g.extend([{'type': 'vis', 'x': 20.0, 'y': y, 'diam_str': "⌀5/11.5"}, {'type': 'vis', 'x': 52.0, 'y': y, 'diam_str': "⌀5/11.5"}])
                    face_holes_montants_d.extend([{'type': 'vis', 'x': 20.0, 'y': y, 'diam_str': "⌀5/11.5"}, {'type': 'vis', 'x': 52.0, 'y': y, 'diam_str': "⌀5/11.5"}])

        # 3. GESTION DES ÉTAGÈRES (MODIFIÉ)
        fixed_shelf_tranche_holes = {}
        has_any_mobile_shelf = False
        
        if 'shelves' in selected_cab:
            has_any_mobile_shelf = any(s.get('shelf_type', 'mobile') == 'mobile' for s in selected_cab['shelves'])

        # A. Système 32 Mobile (colonne complète sur le Montant si au moins un mobile est présent)
        if has_any_mobile_shelf:
            diam_taquet = "⌀5/12"
            x_front = 37.0
            x_back = W_raw_val - 37.0
            
            start_offset = 50.0 
            current_y = t_tb_raw_val + start_offset
            end_y = h_side_raw - t_tb_raw_val - start_offset
            
            # Création de la grille (Système 32)
            while current_y <= end_y:
                hole_f = {'type': 'tourillon', 'x': x_front, 'y': current_y, 'diam_str': diam_taquet}
                hole_b = {'type': 'tourillon', 'x': x_back, 'y': current_y, 'diam_str': diam_taquet}
                
                face_holes_montants_g.extend([hole_f, hole_b])
                face_holes_montants_d.extend([hole_f, hole_b])
                current_y += 32.0

        # B. Étagères Fixes (Positions spécifiques + Trous Tranches)
        if 'shelves' in selected_cab:
            for s_idx, shelf in enumerate(selected_cab['shelves']):
                if shelf.get('shelf_type') == 'fixe':
                    y_shelf_bottom = t_tb_raw_val + shelf['height']
                    y_center_hole = y_shelf_bottom + (shelf['thickness'] / 2.0)
                    
                    # 1. Sur les Montants (Face) : Ligne Vis et Tourillons
                    for x in ys_vis:
                        hole = {'type': 'vis', 'x': x, 'y': y_center_hole, 'diam_str': "⌀3"}
                        face_holes_montants_g.append(hole)
                        face_holes_montants_d.append(hole)
                    for x in ys_dowel:
                        hole = {'type': 'tourillon', 'x': x, 'y': y_center_hole, 'diam_str': "⌀8"}
                        face_holes_montants_g.append(hole)
                        face_holes_montants_d.append(hole)
                    
                    # 2. Sur l'Étagère (Tranches G/D) : Vis et Tourillons
                    current_shelf_holes = []
                    for x_pos_depth in ys_vis:
                        current_shelf_holes.append({'type': 'vis', 'x': shelf['thickness']/2, 'y': x_pos_depth, 'diam_str': "⌀3"})
                    for x_pos_depth in ys_dowel:
                        current_shelf_holes.append({'type': 'tourillon', 'x': shelf['thickness']/2, 'y': x_pos_depth, 'diam_str': "⌀8"})
                        
                    fixed_shelf_tranche_holes[s_idx] = current_shelf_holes

        chant_data = {row['Référence Pièce'].split(' (')[0]: row for row in debit_data}

        # (Affichage des 5 feuilles de caisson)
        st.markdown("---")
        tb_chants = chant_data.get("Traverse Bas (Tb)", {})
        fig_tb = draw_machining_view_professional( "Traverse Bas (Tb)", L_raw_val, W_raw_val, t_tb_raw_val, unit_str, project_info, chants=tb_chants, face_holes_list=[], tranche_cote_holes_list=tranche_cote_holes_traverses )
        st.plotly_chart(fig_tb, use_container_width=True)
        st.markdown("---")
        th_chants = chant_data.get("Traverse Haut (Th)", {})
        fig_th = draw_machining_view_professional( "Traverse Haut (Th)", L_raw_val, W_raw_val, t_tb_raw_val, unit_str, project_info, chants=th_chants, face_holes_list=[], tranche_cote_holes_list=tranche_cote_holes_traverses )
        st.plotly_chart(fig_th, use_container_width=True)
        st.markdown("---")
        mg_chants = chant_data.get("Montant Gauche (Mg)", {})
        fig_mg = draw_machining_view_professional( "Montant Gauche (Mg)", W_raw_val, h_side_raw, t_lr_raw_val, unit_str, project_info, chants=mg_chants, face_holes_list=face_holes_montants_g, tranche_cote_holes_list=[] )
        st.plotly_chart(fig_mg, use_container_width=True)
        st.markdown("---")
        md_chants = chant_data.get("Montant Droit (Md)", {})
        fig_md = draw_machining_view_professional( "Montant Droit (Md)", W_raw_val, h_side_raw, t_lr_raw_val, unit_str, project_info, chants=md_chants, face_holes_list=face_holes_montants_d, tranche_cote_holes_list=[] )
        st.plotly_chart(fig_md, use_container_width=True)
        st.markdown("---")
        f_chants = chant_data.get("Fond (F)", {})
        fig_f = draw_machining_view_professional( "Panneau Arrière (F)", w_back_raw, h_side_raw, t_fb_raw_val, unit_str, project_info, chants=f_chants, face_holes_list=[], tranche_cote_holes_list=[] )
        st.plotly_chart(fig_f, use_container_width=True)

        # DESSIN DE LA FEUILLE D'USINAGE DE LA PORTE (RÉINTÉGRÉ)
        if selected_cab['door_props']['has_door']:
            door_props = selected_cab['door_props']
            door_gap_raw = door_props['door_gap']
            door_T_plot = door_props.get('door_thickness', 18.0)
            door_chants = {"Chant Avant": True, "Chant Arrière": True, "Chant Gauche": True, "Chant Droit": True}
            
            is_base_cabinet = (absolute_origins[selected_cab_idx][2] == 0)
            if door_props.get('door_model') == 'floor_length' and is_base_cabinet and st.session_state.has_feet:
                foot_height_raw = st.session_state.foot_height
                door_H_plot = H_raw_val + foot_height_raw - door_gap_raw - 10.0
            else:
                door_H_plot = H_raw_val - (2 * door_gap_raw) 
            
            y_positions = get_hinge_y_positions(door_H_plot)
            
            if door_props.get('door_type', 'single') == 'single':
                door_L_plot = L_raw_val - (2 * door_gap_raw)
                door_name = f"Porte (Caisson {selected_cab_idx})"
                door_holes = []
                
                if door_props['door_opening'] == 'left':
                    x_cup, x_dowel = 23.5, 33.0
                else: # 'right'
                    x_cup = door_L_plot - 23.5
                    x_dowel = door_L_plot - 33.0
                    
                for y in y_positions:
                    door_holes.append({'type': 'tourillon', 'x': x_cup, 'y': y, 'diam_str': "⌀35/13"}) 
                    door_holes.append({'type': 'vis', 'x': x_dowel, 'y': y - 22.5, 'diam_str': "⌀8/13"}) 
                    door_holes.append({'type': 'vis', 'x': x_dowel, 'y': y + 22.5, 'diam_str': "⌀8/13"})
                
                st.markdown("---")
                fig_p = draw_machining_view_professional( door_name, door_L_plot, door_H_plot, door_T_plot, unit_str, project_info, chants=door_chants, face_holes_list=door_holes )
                st.plotly_chart(fig_p, use_container_width=True)

            else: # Double
                middle_gap_raw = 2.0
                door_L_plot = (L_raw_val - (2 * door_gap_raw) - middle_gap_raw) / 2
                
                # Battant Gauche
                door_name_g = f"Porte (Battant G, C{selected_cab_idx})"
                x_cup_g, x_dowel_g = 23.5, 33.0
                holes_g = []
                for y in y_positions:
                    holes_g.append({'type': 'tourillon', 'x': x_cup_g, 'y': y, 'diam_str': "⌀35/13"})
                    holes_g.append({'type': 'vis', 'x': x_dowel_g, 'y': y - 22.5, 'diam_str': "⌀8/13"})
                    holes_g.append({'type': 'vis', 'x': x_dowel_g, 'y': y + 22.5, 'diam_str': "⌀8/13"})
                st.markdown("---")
                fig_pg = draw_machining_view_professional( door_name_g, door_L_plot, door_H_plot, door_T_plot, unit_str, project_info, chants=door_chants, face_holes_list=holes_g )
                st.plotly_chart(fig_pg, use_container_width=True)
                
                # Battant Droit
                door_name_d = f"Porte (Battant D, C{selected_cab_idx})"
                x_cup_d = door_L_plot - 23.5
                x_dowel_d = door_L_plot - 33.0
                holes_d = []
                for y in y_positions:
                    holes_d.append({'type': 'tourillon', 'x': x_cup_d, 'y': y, 'diam_str': "⌀35/13"})
                    holes_d.append({'type': 'vis', 'x': x_dowel_d, 'y': y - 22.5, 'diam_str': "⌀8/13"})
                    holes_d.append({'type': 'vis', 'x': x_dowel_d, 'y': y + 22.5, 'diam_str': "⌀8/13"})
                st.markdown("---")
                fig_pd = draw_machining_view_professional( door_name_d, door_L_plot, door_H_plot, door_T_plot, unit_str, project_info, chants=door_chants, face_holes_list=holes_d )
                st.plotly_chart(fig_pd, use_container_width=True)
                
        # DESSIN DES FEUILLES D'USINAGE DU TIROIR (inchangé)
        if selected_cab['drawer_props']['has_drawer']:
            drawer_props = selected_cab['drawer_props']
            dims = selected_cab['dims']
            jeu_coulisse_total_mm = 49.0
            
            # 1. Face Tiroir
            face_L = dims['L_raw'] - (2 * drawer_props['drawer_gap'])
            face_H = drawer_props['drawer_face_H_raw']
            face_T = drawer_props.get('drawer_face_thickness', 19.0)
            face_chants = {"Chant Avant": True, "Chant Arrière": True, "Chant Gauche": True, "Chant Droit": True}
            left_holes = [
                {'x': 32.5, 'y': 194.5, 'diam_str': "⌀10/12"},
                {'x': 32.5, 'y': 98.5, 'diam_str': "⌀10/12"},
                {'x': 32.5, 'y': 66.5, 'diam_str': "⌀10/12"},
                {'x': 137.5, 'y': 27.0, 'diam_str': "⌀10/10"},
                {'x': 169.5, 'y': 27.0, 'diam_str': "⌀10/10"}
            ]
            face_holes = []
            for hole in left_holes:
                if hole['y'] < face_H: 
                    face_holes.append({'type': 'tourillon', 'x': hole['x'], 'y': hole['y'], 'diam_str': hole['diam_str']})
                    x_sym = face_L - hole['x']
                    face_holes.append({'type': 'tourillon', 'x': x_sym, 'y': hole['y'], 'diam_str': hole['diam_str']})
            
            cutout_props_arg = None
            if drawer_props.get('drawer_handle_type') == 'integrated_cutout':
                cutout_props_arg = { 
                    'width': drawer_props.get('drawer_handle_width', 150.0), 
                    'height': drawer_props.get('drawer_handle_height', 40.0), 
                    'offset_top': drawer_props.get('drawer_handle_offset_top', 10.0)
                }
            
            st.markdown("---")
            fig_tf = draw_machining_view_professional(
                f"Tiroir-Face (C{selected_cab_idx})", 
                face_L, face_H, face_T, unit_str, project_info, 
                chants=face_chants, 
                face_holes_list=face_holes,
                center_cutout_props=cutout_props_arg
            )
            st.plotly_chart(fig_tf, use_container_width=True)

            # 2. Dos Tiroir
            dos_L = dims['L_raw'] - (2 * dims['t_lr_raw']) - jeu_coulisse_total_mm
            dos_H = 151.0
            dos_T = 16.0
            dos_chants = {"Chant Avant": True, "Chant Arrière": False, "Chant Gauche": False, "Chant Droit": False}
            dos_holes = []
            y_positions = [16.0, 48.0, 80.0, 112.0] 
            x_left = 9.0
            x_right = dos_L - 9.0
            if dos_H >= 112.0: 
                for y in y_positions:
                    dos_holes.append({'type': 'vis', 'x': x_left, 'y': y, 'diam_str': "⌀2.5/3"})
                    dos_holes.append({'type': 'vis', 'x': x_right, 'y': y, 'diam_str': "⌀2.5/3"})
            st.markdown("---")
            fig_td = draw_machining_view_professional(f"Tiroir-Dos (C{selected_cab_idx})", dos_L, dos_H, dos_T, unit_str, project_info, chants=dos_chants, face_holes_list=dos_holes)
            st.plotly_chart(fig_td, use_container_width=True)
            
            # 3. Fond Tiroir
            fond_L_dim = dims['W_raw'] - (20.0 + dims['t_fb_raw'])
            fond_W_dim = dos_L
            fond_T = 8.0
            fond_chants = {"Chant Avant": False, "Chant Arrière": False, "Chant Gauche": False, "Chant Droit": False}
            st.markdown("---")
            fig_to = draw_machining_view_professional(f"Tiroir-Fond (C{selected_cab_idx})", fond_W_dim, fond_L_dim, fond_T, unit_str, project_info, chants=fond_chants, face_holes_list=[])
            st.plotly_chart(fig_to, use_container_width=True)
            
        # DESSIN DES FEUILLES D'USINAGE DES ÉTAGÈRES (CORRIGÉ)
        if 'shelves' in selected_cab and selected_cab['shelves']:
            dims = selected_cab['dims'] 
            shelf_L_dim = dims['L_raw'] - (2 * dims['t_lr_raw'])
            shelf_W_dim = dims['W_raw'] - dims['t_fb_raw']
            
            # DÉFINITION UNIQUE ET FINALE : SEULEMENT CHANT AVANT
            shelf_chants_final = {"Chant Avant": True, "Chant Arrière": False, "Chant Gauche": False, "Chant Droit": False}
            
            for s_idx, shelf in enumerate(selected_cab['shelves']):
                shelf_T_dim = shelf['thickness']
                is_fixed = (shelf.get('shelf_type') == 'fixe')
                type_str = "FIXE" if is_fixed else "MOBILE"
                shelf_name = f"Etagère {s_idx+1} ({type_str}) (C{selected_cab_idx})"
                
                # Récupération des trous de tranche UNIQUEMENT si l'étagère est FIXE
                if is_fixed:
                    holes_tranche = fixed_shelf_tranche_holes.get(s_idx, [])
                else:
                    holes_tranche = []

                st.markdown("---")
                fig_shelf = draw_machining_view_professional(
                    shelf_name, 
                    shelf_L_dim, 
                    shelf_W_dim, 
                    shelf_T_dim, 
                    unit_str, 
                    project_info, 
                    chants=shelf_chants_final, # Chant Avant uniquement pour tous
                    face_holes_list=[], 
                    tranche_cote_holes_list=holes_tranche # Trous pour l'étagère fixe, aucun pour la mobile
                )
                st.plotly_chart(fig_shelf, use_container_width=True)