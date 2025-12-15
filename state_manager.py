# Contenu de state_manager.py
# Gestion des callbacks et de l'état de session

import streamlit as st
import openpyxl
import json
import datetime
import copy
from utils import get_default_debit_data, get_default_shelf_props, get_default_door_props, get_default_drawer_props
from project_definitions import get_default_dims_19, get_default_door_props_19, get_default_drawer_props_19

def get_selected_cabinet():
    idx = st.session_state.get('selected_cabinet_index')
    if idx is not None and idx < len(st.session_state['scene_cabinets']): return st.session_state['scene_cabinets'][idx]
    return None

def initialize_session_state():
    """Initialise l'état de session global."""
    st.session_state.setdefault('scene_cabinets', [])
    st.session_state.setdefault('selected_cabinet_index', None)
    st.session_state.setdefault('base_cabinet_index', 0)
    st.session_state.setdefault('unit_select', 'mm')

    # Infos Globales du Projet
    st.session_state.setdefault('project_name', "Nouveau Projet")
    st.session_state.setdefault('corps_meuble', "Caisson 1")
    st.session_state.setdefault('quantity', 1)
    st.session_state.setdefault('client', "CLIENT NOM")
    st.session_state.setdefault('adresse_chantier', "") # AJOUTÉ
    st.session_state.setdefault('ref_chantier', "")
    st.session_state.setdefault('telephone', "")
    st.session_state.setdefault('date_souhaitee', datetime.date.today())
    st.session_state.setdefault('panneau_decor', "BLANC")
    st.session_state.setdefault('chant_mm', "1mm")
    st.session_state.setdefault('decor_chant', "BLANC")
    
    # Propriétés des pieds
    st.session_state.setdefault('has_feet', False)
    st.session_state.setdefault('foot_height', 80.0) 
    st.session_state.setdefault('foot_diameter', 30.0)

def load_save_state():
    if 'file_loader' in st.session_state and st.session_state.file_loader is not None:
        uploaded_file = st.session_state.file_loader
        try:
            workbook = openpyxl.load_workbook(uploaded_file)
            if 'SaveData' in workbook.sheetnames:
                save_sheet = workbook['SaveData']
                json_data_str = save_sheet['A1'].value 
                if json_data_str:
                    loaded_data = json.loads(json_data_str)
                    st.session_state['project_name'] = loaded_data.get('project_name', 'Nouveau Projet')
                    st.session_state['client'] = loaded_data.get('client', '')
                    st.session_state['adresse_chantier'] = loaded_data.get('adresse_chantier', '') # AJOUTÉ
                    st.session_state['ref_chantier'] = loaded_data.get('ref_chantier', '')
                    st.session_state['telephone'] = loaded_data.get('telephone', '')
                    if 'date_souhaitee' in loaded_data:
                         st.session_state['date_souhaitee'] = datetime.date.fromisoformat(loaded_data['date_souhaitee'])
                    st.session_state['panneau_decor'] = loaded_data.get('panneau_decor', '')
                    st.session_state['chant_mm'] = loaded_data.get('chant_mm', '')
                    st.session_state['decor_chant'] = loaded_data.get('decor_chant', '')
                    st.session_state['has_feet'] = loaded_data.get('has_feet', False)
                    st.session_state['foot_height'] = loaded_data.get('foot_height', 80.0)
                    st.session_state['foot_diameter'] = loaded_data.get('foot_diameter', 50.0)
                    st.session_state['scene_cabinets'] = loaded_data.get('scene_cabinets', [])
                    if st.session_state['scene_cabinets']:
                        st.session_state['selected_cabinet_index'] = 0
                        st.session_state['base_cabinet_index'] = 0
                    else:
                        st.session_state['selected_cabinet_index'] = None
                        st.session_state['base_cabinet_index'] = 0
                    st.success("Projet chargé.")
                    st.rerun()
        except Exception as e:
            st.error(f"Erreur chargement : {e}")

# Callbacks
def update_selected_cabinet_dim(key):
    cabinet = get_selected_cabinet()
    widget_key = f"{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state: cabinet['dims'][key] = st.session_state[widget_key]

def update_selected_cabinet_door(key):
    cabinet = get_selected_cabinet()
    widget_key = f"{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state:
        if 'door_props' not in cabinet: cabinet['door_props'] = get_default_door_props_19()
        cabinet['door_props'][key] = st.session_state[widget_key]
        if key == 'has_door' and st.session_state[widget_key] is True:
            if 'drawer_props' in cabinet: cabinet['drawer_props']['has_drawer'] = False

def update_selected_cabinet_drawer(key):
    cabinet = get_selected_cabinet()
    widget_key = f"{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state:
        if 'drawer_props' not in cabinet: cabinet['drawer_props'] = get_default_drawer_props_19()
        cabinet['drawer_props'][key] = st.session_state[widget_key]
        if key == 'has_drawer' and st.session_state[widget_key] is True:
            if 'door_props' in cabinet: cabinet['door_props']['has_drawer'] = False

def add_shelf_callback():
    cabinet = get_selected_cabinet()
    if cabinet:
        if 'shelves' not in cabinet: cabinet['shelves'] = []
        cabinet['shelves'].append(get_default_shelf_props())

def update_shelf_prop(shelf_index, key):
    cabinet = get_selected_cabinet()
    if key == 'shelf_type': widget_key = f"shelf_t_{st.session_state.selected_cabinet_index}_{shelf_index}"
    elif key == 'height': widget_key = f"shelf_h_{st.session_state.selected_cabinet_index}_{shelf_index}"
    elif key == 'thickness': widget_key = f"shelf_e_{st.session_state.selected_cabinet_index}_{shelf_index}"
    elif key == 'mobile_machining_type': widget_key = f"shelf_m_type_{st.session_state.selected_cabinet_index}_{shelf_index}"
    elif key == 'custom_holes_above': widget_key = f"shelf_c_above_{st.session_state.selected_cabinet_index}_{shelf_index}"
    elif key == 'custom_holes_below': widget_key = f"shelf_c_below_{st.session_state.selected_cabinet_index}_{shelf_index}"
    else: widget_key = f"shelf_{key[0]}_{st.session_state.selected_cabinet_index}_{shelf_index}"
    if cabinet and widget_key in st.session_state:
        if 'shelves' in cabinet and shelf_index < len(cabinet['shelves']): cabinet['shelves'][shelf_index][key] = st.session_state[widget_key]

def delete_shelf_callback(shelf_index):
    cabinet = get_selected_cabinet()
    if cabinet:
        if 'shelves' in cabinet and shelf_index < len(cabinet['shelves']):
            cabinet['shelves'].pop(shelf_index)
            st.rerun()

def update_selected_cabinet_material(key):
    cabinet = get_selected_cabinet()
    widget_key = f"{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state: cabinet[key] = st.session_state[widget_key]
def update_selected_cabinet_door_material(key):
    cabinet = get_selected_cabinet()
    widget_key = f"door_{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state: cabinet['door_props']['material'] = st.session_state[widget_key]
def update_selected_cabinet_drawer_material(key):
    cabinet = get_selected_cabinet()
    widget_key = f"drawer_{key}_{st.session_state.selected_cabinet_index}"
    if cabinet and widget_key in st.session_state: cabinet['drawer_props']['material'] = st.session_state[widget_key]
def update_shelf_material(shelf_index, key):
    widget_key = f"shelf_m_{st.session_state.selected_cabinet_index}_{shelf_index}"
    cabinet = get_selected_cabinet()
    if cabinet and widget_key in st.session_state:
        if 'shelves' in cabinet and shelf_index < len(cabinet['shelves']): cabinet['shelves'][shelf_index]['material'] = st.session_state[widget_key]

def add_cabinet(origin_type='central'):
    if origin_type == 'central':
        if st.session_state['scene_cabinets']: return
        new_cabinet = {
            'dims': get_default_dims_19(), 'debit_data': get_default_debit_data(), 'name': "Caisson 0 (Central)",
            'parent_index': None, 'attachment_dir': None, 'door_props': get_default_door_props_19(),
            'drawer_props': get_default_drawer_props_19(), 'shelves': [], 'material_body': 'Matière Corps' 
        }
        st.session_state['scene_cabinets'].append(new_cabinet)
        st.session_state['selected_cabinet_index'] = 0
        st.session_state['base_cabinet_index'] = 0
    else: 
        base_index = st.session_state.get('base_cabinet_index', 0)
        if base_index is None or base_index >= len(st.session_state['scene_cabinets']):
            st.error("Aucun caisson de base sélectionné.")
            return
        base_caisson = st.session_state['scene_cabinets'][base_index]
        new_cabinet = {
            'dims': copy.deepcopy(base_caisson['dims']), 'debit_data': get_default_debit_data(),
            'parent_index': base_index, 'attachment_dir': origin_type, 'door_props': get_default_door_props_19(),
            'drawer_props': get_default_drawer_props_19(), 'shelves': [], 'material_body': 'Matière Corps' 
        }
        if origin_type == 'right': new_name = f"D de {base_index}"
        elif origin_type == 'left': new_name = f"G de {base_index}"
        else: new_name = f"H de {base_index}"
        new_cabinet['name'] = f"Caisson {len(st.session_state['scene_cabinets'])} ({new_name})"
        st.session_state['scene_cabinets'].append(new_cabinet)
        new_index = len(st.session_state['scene_cabinets']) - 1
        st.session_state['selected_cabinet_index'] = new_index
        st.session_state['base_cabinet_index'] = st.session_state['selected_cabinet_index']

def clear_scene():
    st.session_state['scene_cabinets'] = []
    st.session_state['selected_cabinet_index'] = None
    st.session_state['base_cabinet_index'] = 0

def delete_selected_cabinet():
    idx = st.session_state.get('selected_cabinet_index')
    if idx is None or idx >= len(st.session_state['scene_cabinets']): return
    indices_to_remove = set()
    queue = [idx]
    while queue:
        curr = queue.pop()
        if curr not in indices_to_remove:
            indices_to_remove.add(curr)
            for i, c in enumerate(st.session_state['scene_cabinets']):
                if c['parent_index'] == curr: queue.append(i)
    new_scene = []
    map_old_new = {}
    counter = 0
    for i, c in enumerate(st.session_state['scene_cabinets']):
        if i not in indices_to_remove:
            map_old_new[i] = counter
            new_scene.append(c)
            counter += 1
    for c in new_scene:
        if c['parent_index'] is not None: c['parent_index'] = map_old_new.get(c['parent_index'], None) 
    st.session_state['scene_cabinets'] = new_scene
    st.session_state['selected_cabinet_index'] = 0 if new_scene else None
    st.session_state['base_cabinet_index'] = 0
