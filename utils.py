# Contenu de utils.py
import streamlit as st
import datetime
import re

def get_material_library():
    """Retourne une bibliothèque vide (l'utilisateur entre la matière manuellement)."""
    return {}

def get_default_debit_data():
    """Retourne la liste de pièces par défaut avec les CHANTS FORCÉS selon vos règles."""
    return [
        # Traverse : Avant/Arrière = True, Gauche/Droit = False (bouts usinés)
        {"Lettre": "A", "Référence Pièce": "Traverse Bas (Tb)", "Qté": 1, "Longueur (mm)": 0.0, "Chant Avant": True, "Chant Arrière": True, "Largeur (mm)": 0.0, "Chant Gauche": False, "Chant Droit": False, "Usinage": "Tourillons Tranches Côtés"},
        {"Lettre": "B", "Référence Pièce": "Traverse Haut (Th)", "Qté": 1, "Longueur (mm)": 0.0, "Chant Avant": True, "Chant Arrière": True, "Largeur (mm)": 0.0, "Chant Gauche": False, "Chant Droit": False, "Usinage": "Tourillons Tranches Côtés"},
        # Montants : Champs Partout (4 côtés)
        {"Lettre": "C", "Référence Pièce": "Montant Gauche (Mg)", "Qté": 1, "Longueur (mm)": 0.0, "Chant Avant": True, "Chant Arrière": True, "Largeur (mm)": 0.0, "Chant Gauche": True, "Chant Droit": True, "Usinage": "Vis/Tourillons Faces H&B"},
        {"Lettre": "D", "Référence Pièce": "Montant Droit (Md)", "Qté": 1, "Longueur (mm)": 0.0, "Chant Avant": True, "Chant Arrière": True, "Largeur (mm)": 0.0, "Chant Gauche": True, "Chant Droit": True, "Usinage": "Vis/Tourillons Faces H&B"},
        # Fond : Pas de chant par défaut
        {"Lettre": "E", "Référence Pièce": "Fond (F)", "Qté": 1, "Longueur (mm)": 0.0, "Chant Avant": False, "Chant Arrière": False, "Largeur (mm)": 0.0, "Chant Gauche": False, "Chant Droit": False, "Usinage": ""},
    ]

def get_default_dims():
    """Retourne les dimensions par défaut pour un NOUVEAU caisson."""
    return {
        'L_raw': 500.0, 'W_raw': 300.0, 'H_raw': 400.0,
        't_lr_raw': 18.0, 't_fb_raw': 18.0, 't_tb_raw': 18.0
    }

def get_default_door_props():
    """Retourne les propriétés de porte par défaut."""
    return {
        'has_door': False, 
        'door_type': 'single',
        'door_opening': 'right', 
        'door_gap': 2.0, 
        'door_thickness': 18.0,
        'door_model': 'standard',
        'material': 'Matière Porte'
    }

def get_default_drawer_props():
    """Retourne les propriétés de tiroir par défaut."""
    return {
        'has_drawer': False,
        'drawer_face_H_raw': 150.0, 
        'drawer_bottom_offset': 100.0,
        'drawer_face_thickness': 19.0,
        'drawer_gap': 2.0,
        'drawer_handle_type': 'none', 
        'drawer_handle_width': 150.0,
        'drawer_handle_height': 40.0,
        'drawer_handle_offset_top': 10.0,
        'material': 'Matière Tiroir'
    }

def get_default_shelf_props():
    """Retourne les propriétés par défaut pour une NOUVELLE étagère."""
    return {
        'height': 300.0, 
        'thickness': 19.0,
        'material': 'Matière Étagère',
        'shelf_type': 'mobile', 
        'mobile_machining_type': 'full_height', # 'full_height', '4_holes', 'custom'
        'custom_holes_above': 0,
        'custom_holes_below': 0
    }

def initialize_session_state():
    """Initialise l'état de session global."""
    st.session_state.setdefault('scene_cabinets', [])
    st.session_state.setdefault('selected_cabinet_index', None)
    st.session_state.setdefault('base_cabinet_index', 0)
    st.session_state.setdefault('audio_recorder_key', 'audio_key_1')
    st.session_state.setdefault('unit_select', 'mm')

    # Infos Globales du Projet
    st.session_state.setdefault('project_name', "Nouveau Projet")
    st.session_state.setdefault('corps_meuble', "Caisson 1")
    st.session_state.setdefault('quantity', 1)
    st.session_state.setdefault('client', "SYMETRY WHEELS")
    st.session_state.setdefault('ref_chantier', "Le Marec")
    st.session_state.setdefault('telephone', "06 42 89 98 58")
    st.session_state.setdefault('date_souhaitee', datetime.date.today())
    st.session_state.setdefault('panneau_decor', "ESSENTIAL OAK NATUREL")
    st.session_state.setdefault('chant_mm', "1mm")
    st.session_state.setdefault('decor_chant', "ESSENTIAL OAK NATUREL")
    
    # Propriétés des pieds
    st.session_state.setdefault('has_feet', False)
    st.session_state.setdefault('foot_height', 80.0) 
    st.session_state.setdefault('foot_diameter', 30.0)

def calculate_hole_positions(W_raw):
    screw_positions = []
    dowel_positions = []
    if 300 <= W_raw <= 400:
        v1_y = 25.0
        v3_y = W_raw - 25.0
        v2_y = W_raw / 2.0
        t1_y = v1_y + (v2_y - v1_y) / 2.0
        t2_y = v2_y + (v3_y - v2_y) / 2.0
        screw_positions = [v1_y, v2_y, v3_y]
        dowel_positions = [t1_y, t2_y]
    elif 400 < W_raw <= 600:
        v1_y = 25.0
        v4_y = W_raw - 25.0
        usable_width = v4_y - v1_y
        spacing = usable_width / 6.0
        screw_positions = [v1_y, v1_y + 2*spacing, v1_y + 4*spacing, v4_y]
        dowel_positions = [v1_y + spacing, v1_y + 3*spacing, v1_y + 5*spacing]
    elif W_raw > 60:
        v1_y = 25.0
        v2_y = W_raw - 25.0
        t1_y = W_raw / 2.0
        screw_positions = [v1_y, v2_y]
        dowel_positions = [t1_y]
    return screw_positions, dowel_positions

def parse_all_voice_commands(text, unit_factor):
    text = text.lower().replace(',', '.')
    result = {}
    factor_map = {"mm":0.001, "cm":0.01, "m":1.0}
    default_unit = st.session_state.unit_select
    default_factor = factor_map.get(default_unit, 0.001)
    matches_dims = re.findall(r"(longueur|largeur|hauteur|épaisseur|latérale|gache|droite|avant|arrière|top|bas|fond|haut)\D*([\d.,]+)\s*(mm|cm|m)?", text)
    if not matches_dims:
        return None, "Aucune dimension ou valeur numérique trouvée."
    for champ, valeur, unite in matches_dims:
        valeur_num = float(valeur)
        valeur_en_metres = valeur_num * factor_map.get(unite, default_factor)
        valeur_pour_input = valeur_en_metres / unit_factor
        if "longueur" in champ: result["L_raw"] = valeur_pour_input
        elif "largeur" in champ: result["W_raw"] = valeur_pour_input
        elif "hauteur" in champ: result["H_raw"] = valeur_pour_input
        elif "latérale" in champ or "gauche" in champ or "droite" in champ: result["t_lr_raw"] = valeur_pour_input
        elif "avant" in champ or "arrière" in champ: result["t_fb_raw"] = valeur_pour_input
        elif "top" in champ or "bas" in champ or "fond" in champ or "haut" in champ: result["t_tb_raw"] = valeur_pour_input
        elif "épaisseur" in champ:
             result["t_lr_raw"] = valeur_pour_input
             result["t_fb_raw"] = valeur_pour_input
             result["t_tb_raw"] = valeur_pour_input
    if not result:
         return None, "Aucune dimension clé reconnue (longueur, largeur, etc.)."
    return result, None
