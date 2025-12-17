# Contenu de app.py (anciennement 2.py)
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import datetime
from io import BytesIO 
import math
import copy
import hashlib 

# --- IMPORTATIONS MODULAIRES ---
from utils import initialize_session_state, calculate_hole_positions
from geometry_helpers import cuboid_mesh_for, cylinder_mesh_for
from excel_export import create_styled_excel
from project_definitions import get_default_dims_19, get_default_door_props_19, get_default_drawer_props_19
from machining_logic import calculate_origins_recursively, get_hinge_y_positions, get_mobile_shelf_holes, calculate_back_panel_holes, detect_collisions
from drawing_interface import draw_machining_view_pro_final
from state_manager import (
    get_selected_cabinet, load_save_state, add_cabinet, clear_scene, delete_selected_cabinet,
    update_selected_cabinet_dim, update_selected_cabinet_door, update_selected_cabinet_drawer,
    add_shelf_callback, update_shelf_prop, delete_shelf_callback,
    update_selected_cabinet_material, update_selected_cabinet_door_material, 
    update_selected_cabinet_drawer_material, update_shelf_material
)
from export_manager import generate_stacked_html_plans

# --- CONFIGURATION ---
st.set_page_config(page_title="Caisson Designer", layout="wide")
initialize_session_state()

# ==============================================================================
# LOGIQUE MÉTIER CHANTS
# ==============================================================================
def get_automatic_edge_banding(part_name):
    name = part_name.lower()
    if "etagère" in name or "etagere" in name: return True, False, False, False
    elif "fond" in name or "dos" in name:
        if "façade" in name or "face" in name: return True, True, True, True
        return False, False, False, False
    elif "traverse" in name: return True, True, False, False
    else: return True, True, True, True

# ==============================================================================
# LOGIQUE DE CALCUL CENTRALISÉE (CORRIGÉE POUR ÉTAGÈRES)
# ==============================================================================
def calculate_all_project_parts():
    all_parts = []
    lettre_code = 65 
    shelf_dims_cache = {} 

    for i, cabinet in enumerate(st.session_state['scene_cabinets']):
        dims = cabinet['dims']
        debit_data = cabinet['debit_data']
        
        t_lr, t_tb, t_fb = dims['t_lr_raw'], dims['t_tb_raw'], dims['t_fb_raw']
        h_side = dims['H_raw'] 
        L_traverse = dims['L_raw'] - 2 * t_lr 
        dim_fond_vertical = dims['H_raw'] - 2.0; dim_fond_horizontal = dims['L_raw'] - 2.0
        
        panel_dims = {
            "Traverse Bas": (L_traverse, dims['W_raw'], t_tb),
            "Traverse Haut": (L_traverse, dims['W_raw'], t_tb),
            "Montant Gauche": (h_side, dims['W_raw'], t_lr),
            "Montant Droit": (h_side, dims['W_raw'], t_lr),
            "Fond": (dim_fond_vertical, dim_fond_horizontal, t_fb)
        }
        
        # 1. Structure
        for piece in debit_data:
            new_piece = piece.copy()
            new_piece['Lettre'] = f"C{i}-{chr(lettre_code)}"
            lettre_code += 1
            ref_full = new_piece["Référence Pièce"]
            ref_key = ref_full.split(' (')[0].strip()
            new_piece["Référence Pièce"] = ref_full 
            new_piece["Matière"] = cabinet.get('material_body', 'Matière Corps')
            new_piece["Caisson"] = f"C{i}"
            new_piece["Usinage"] = "CF plan" if new_piece.get("Usinage", "") else ""
            cav, car, cg, cd = get_automatic_edge_banding(ref_key)
            new_piece["Chant Avant"] = cav; new_piece["Chant Arrière"] = car; new_piece["Chant Gauche"] = cg; new_piece["Chant Droit"] = cd

            match_found = False
            for key, dims_tuple in panel_dims.items():
                if key in ref_key:
                    new_piece["Longueur (mm)"] = dims_tuple[0]; new_piece["Largeur (mm)"] = dims_tuple[1]; new_piece["Epaisseur"] = dims_tuple[2]
                    match_found = True; break
            if not match_found and "Fond" in ref_key:
                    new_piece["Longueur (mm)"] = dim_fond_vertical; new_piece["Largeur (mm)"] = dim_fond_horizontal; new_piece["Epaisseur"] = t_fb
            all_parts.append(new_piece)
        
        # 2. Porte
        if cabinet['door_props']['has_door']:
            dp = cabinet['door_props']
            dH = dims['H_raw'] - (2 * dp['door_gap']) 
            if dp.get('door_model') == 'floor_length': dH += st.session_state.foot_height 
            dW = dims['L_raw'] - (2 * dp['door_gap']) if dp.get('door_type') == 'single' else (dims['L_raw'] - 2*dp['door_gap'])/2
            cav, car, cg, cd = get_automatic_edge_banding("Porte")
            all_parts.append({"Lettre": f"C{i}-P", "Référence Pièce": f"Porte (C{i})", "Matière": dp.get('material', 'Matière Porte'), "Caisson": f"C{i}", "Qté": 1 if dp.get('door_type')=='single' else 2, "Longueur (mm)": dH, "Largeur (mm)": dW, "Epaisseur": dp.get('door_thickness', 19.0), "Chant Avant": cav, "Chant Arrière": car, "Chant Gauche": cg, "Chant Droit": cd, "Usinage": "CF plan"})

        # 3. Tiroir
        if cabinet['drawer_props']['has_drawer']:
            drp = cabinet['drawer_props']
            
            # Gestion des types N, M, K, D
            tech_type = drp.get('drawer_tech_type', 'K')
            back_height_map = {'N': 69.0, 'M': 84.0, 'K': 116.0, 'D': 199.0}
            fixed_back_h = back_height_map.get(tech_type, 116.0)
            
            cav, car, cg, cd = get_automatic_edge_banding("Façade")
            all_parts.append({"Lettre": f"C{i}-TF", "Référence Pièce": f"Façade Tiroir (C{i})", "Matière": drp.get('material', 'Matière Tiroir'), "Caisson": f"C{i}", "Qté": 1, "Longueur (mm)": drp['drawer_face_H_raw'], "Largeur (mm)": dims['L_raw'] - (2 * drp['drawer_gap']), "Epaisseur": drp.get('drawer_face_thickness', 19.0), "Chant Avant": cav, "Chant Arrière": car, "Chant Gauche": cg, "Chant Droit": cd, "Usinage": "CF plan"})
            
            cav, car, cg, cd = get_automatic_edge_banding("Tiroir Dos")
            # Épaisseur forcée à 16mm pour Dos
            all_parts.append({"Lettre": f"C{i}-TD", "Référence Pièce": f"Tiroir Dos (C{i})", "Matière": cabinet.get('material_body', 'Matière Corps'), "Caisson": f"C{i}", "Qté": 1, "Longueur (mm)": fixed_back_h, "Largeur (mm)": dims['L_raw']-2*t_lr-40, "Epaisseur": 16.0, "Chant Avant": cav, "Chant Arrière": car, "Chant Gauche": cg, "Chant Droit": cd, "Usinage": ""})
            
        # 4. Étagères (Correction ici : Ajout au tableau et calcul des dimensions)
        if 'shelves' in cabinet:
            for s_idx, s in enumerate(cabinet['shelves']):
                s_type = s.get('shelf_type', 'mobile')
                s_th = float(s.get('thickness', 19.0))
                
                # Calcul Dimensions
                # Profondeur : Retrait standard de 10mm pour portes/devanture
                dim_W = dims['W_raw'] - 10.0
                
                # Longueur (Largeur dans le meuble)
                if s_type == 'fixe':
                    # Fixe : Doit faire exactement la largeur interne (assemblage structurel)
                    dim_L = L_traverse 
                else:
                    # Mobile : Doit avoir du jeu (2mm total -> 1mm par coté)
                    dim_L = L_traverse - 2.0
                
                # **CRUCIAL**: Remplir le cache pour que l'affichage des plans (plus bas) ne prenne pas (100,100)
                shelf_dims_cache[f"C{i}_S{s_idx}"] = (dim_L, dim_W)
                
                cav, car, cg, cd = get_automatic_edge_banding("Etagère")
                all_parts.append({
                    "Lettre": f"C{i}-E{s_idx+1}",
                    "Référence Pièce": f"Etagère {s_type.capitalize()} (C{i})",
                    "Matière": s.get('material', 'Matière Étagère'),
                    "Caisson": f"C{i}",
                    "Qté": 1,
                    "Longueur (mm)": dim_L,
                    "Largeur (mm)": dim_W,
                    "Epaisseur": s_th,
                    "Chant Avant": cav, "Chant Arrière": car, "Chant Gauche": cg, "Chant Droit": cd,
                    "Usinage": "Taquets" if s_type == 'mobile' else "Fixe"
                })
            
    return all_parts, shelf_dims_cache

# ==============================================================================
# INTERFACE UTILISATEUR
# ==============================================================================

st.title("Caisson Designer 🛠️")
col1, col2 = st.columns([1, 2])
selected_cab = get_selected_cabinet()

# --- COLONNE 1 ---
with col1:
    st.header("Éditeur de Scène")
    tab_assembly, tab_edit = st.tabs(["🏗️ Assemblage & Fichiers", "✏️ Éditeur de Caisson"])

    with tab_assembly:
        st.subheader("Fichier Projet")
        c1, c2 = st.columns(2)
        st.text_input("Nom du Projet", key='project_name')
        with c2:
            st.markdown("Date souhaitée")
            st.date_input("Date souhaitée", key='date_souhaitee', value=datetime.date.today(), label_visibility="collapsed")
        st.text_input("Client", key='client')
        st.text_input("Adresse Chantier", key='adresse_chantier')
        st.text_input("Réf. Chantier", key='ref_chantier')
        st.text_input("Téléphone / Mail", key='telephone')
        st.markdown("##### Matériaux (Défaut)")
        st.text_input("Panneau / Décor", key='panneau_decor')
        c1, c2 = st.columns(2)
        st.text_input("Chant (mm)", key='chant_mm')
        st.text_input("Décor Chant", key='decor_chant')
        st.markdown("---")
        st.info("La sauvegarde est incluse dans le téléchargement XLS.")
        st.file_uploader("Charger un Projet (.xlsx)", type=["xlsx"], key="file_loader", on_change=load_save_state)
        st.markdown("---")
        st.subheader("Assemblage de la Scène")
        st.button("1. Ajouter le Caisson Central", on_click=add_cabinet, args=('central',), disabled=bool(st.session_state['scene_cabinets']), use_container_width=True)
        if st.session_state['scene_cabinets']:
            opts = [f"{i}: {c['name']}" for i, c in enumerate(st.session_state['scene_cabinets'])]
            st.selectbox("Ajouter relatif à :", options=range(len(opts)), format_func=lambda x: opts[x], key='base_cabinet_index')
            c1, c2, c3 = st.columns(3)
            c1.button("⬅️ Gauche", on_click=add_cabinet, args=('left',), use_container_width=True)
            c2.button("➡️ Droite", on_click=add_cabinet, args=('right',), use_container_width=True)
            c3.button("⬆️ Dessus", on_click=add_cabinet, args=('up',), use_container_width=True)
        st.button("Vider la scène 🗑️", on_click=clear_scene, use_container_width=True)
        st.markdown("---")
        st.subheader("Options des Pieds (Global)")
        st.toggle("Ajouter des pieds", key='has_feet')
        if st.session_state.has_feet:
            feet_map = {"20": 20.0, "80-100": 100.0, "110-120": 120.0}
            sel_feet = st.selectbox("Hauteur (mm)", options=["20", "80-100", "110-120"], index=1)
            st.session_state.foot_height = feet_map[sel_feet]
            st.number_input("Diamètre pieds (mm)", min_value=10.0, key='foot_diameter', value=50.0, format="%.0f", step=1.0)

    with tab_edit:
        st.subheader("Sélection et Suppression")
        if not st.session_state['scene_cabinets']:
            st.info("Ajoutez un caisson central pour commencer l'édition.")
        else:
            opts = [f"{i}: {c['name']}" for i, c in enumerate(st.session_state['scene_cabinets'])]
            st.selectbox("Éditer le caisson :", options=range(len(opts)), format_func=lambda x: opts[x], key='selected_cabinet_index')
            st.button("Supprimer le Caisson", on_click=delete_selected_cabinet, use_container_width=True, type="primary")
            
            if selected_cab:
                idx = st.session_state.selected_cabinet_index
                t_dims, t_acc, t_sh, t_deb = st.tabs(["Dimensions", "Porte/Tiroir", "Étagères", "Feuille de Débit"])
                with t_dims:
                    st.markdown(f"#### Matières et Dimensions du Corps")
                    st.text_input(f"Matière Corps", value=selected_cab.get('material_body', 'Matière Corps'), key=f"material_body_{idx}", on_change=lambda: update_selected_cabinet_material('material_body'))
                    st.markdown("##### Dimensions Externes")
                    dims = selected_cab['dims']
                    st.number_input("Longueur (X)", value=dims['L_raw'], key=f"L_raw_{idx}", on_change=lambda: update_selected_cabinet_dim('L_raw'), format="%.0f", step=1.0)
                    st.number_input("Largeur (Y - Profondeur)", value=dims['W_raw'], key=f"W_raw_{idx}", on_change=lambda: update_selected_cabinet_dim('W_raw'), format="%.0f", step=1.0)
                    st.number_input("Hauteur (Z)", value=dims['H_raw'], key=f"H_raw_{idx}", on_change=lambda: update_selected_cabinet_dim('H_raw'), format="%.0f", step=1.0)
                    st.markdown("##### Épaisseurs des Panneaux")
                    st.number_input("Parois latérales (Montants)", value=dims['t_lr_raw'], key=f"t_lr_raw_{idx}", on_change=lambda: update_selected_cabinet_dim('t_lr_raw'), format="%.0f", step=1.0)
                    st.number_input("Arrière (Fond)", value=dims['t_fb_raw'], key=f"t_fb_raw_{idx}", on_change=lambda: update_selected_cabinet_dim('t_fb_raw'), format="%.0f", step=1.0)
                    st.number_input("Haut/Bas (Traverses)", value=dims['t_tb_raw'], key=f"t_tb_raw_{idx}", on_change=lambda: update_selected_cabinet_dim('t_tb_raw'), format="%.0f", step=1.0)

                with t_acc:
                    d_p = selected_cab['door_props']; dr_p = selected_cab['drawer_props']
                    st.markdown("#### Porte (Façade)")
                    st.toggle("Ajouter une porte", value=d_p['has_door'], key=f"has_door_{idx}", on_change=lambda: update_selected_cabinet_door('has_door'))
                    if d_p['has_door']:
                        st.selectbox("Type de porte", options=['single', 'double'], index=0 if d_p.get('door_type')=='single' else 1, format_func=lambda x: 'Simple' if x=='single' else 'Double', key=f"door_type_{idx}", on_change=lambda: update_selected_cabinet_door('door_type'))
                        if d_p.get('door_type')=='single': st.selectbox("Sens d'ouverture", options=['right', 'left'], index=0 if d_p.get('door_opening')=='right' else 1, format_func=lambda x: 'Droite' if x=='right' else 'Gauche', key=f"door_opening_{idx}", on_change=lambda: update_selected_cabinet_door('door_opening'))
                        st.number_input("Épaisseur (mm)", value=d_p.get('door_thickness', 19.0), key=f"door_thickness_{idx}", on_change=lambda: update_selected_cabinet_door('door_thickness'), format="%.0f", step=1.0)
                        st.selectbox("Modèle", options=['standard', 'floor_length'], index=0 if d_p.get('door_model')=='standard' else 1, format_func=lambda x: 'Standard' if x=='standard' else 'Cache-pied', key=f"door_model_{idx}", on_change=lambda: update_selected_cabinet_door('door_model'))
                        st.number_input("Jeu extérieur (mm)", value=d_p.get('door_gap', 2.0), key=f"door_gap_{idx}", on_change=lambda: update_selected_cabinet_door('door_gap'), format="%.1f", step=0.1)
                        st.text_input("Matière Porte", value=d_p.get('material', 'Matière Porte'), key=f"door_material_{idx}", on_change=lambda: update_selected_cabinet_door_material('material'))

                    st.markdown("#### Tiroir Bloc (Façade)")
                    st.toggle("Ajouter un tiroir bloc", value=dr_p['has_drawer'], key=f"has_drawer_{idx}", on_change=lambda: update_selected_cabinet_drawer('has_drawer'))
                    if dr_p['has_drawer']:
                        tech_opts = ['K', 'M', 'N', 'D']
                        curr_tech = dr_p.get('drawer_tech_type', 'K')
                        idx_tech = tech_opts.index(curr_tech) if curr_tech in tech_opts else 0
                        st.selectbox("Type de Tiroir (Système)", options=tech_opts, index=idx_tech, key=f"drawer_tech_type_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_tech_type'))
                        
                        st.number_input("Hauteur Face (mm)", value=dr_p['drawer_face_H_raw'], key=f"drawer_face_H_raw_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_face_H_raw'), format="%.0f", step=1.0)
                        st.number_input("Offset / bas caisson (mm)", value=dr_p['drawer_bottom_offset'], key=f"drawer_bottom_offset_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_bottom_offset'), format="%.0f", step=1.0)
                        st.number_input("Épaisseur Face (mm)", value=dr_p.get('drawer_face_thickness', 19.0), key=f"drawer_face_thickness_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_face_thickness'), format="%.0f", step=1.0)
                        st.number_input("Jeu extérieur (mm)", value=dr_p.get('drawer_gap', 2.0), key=f"drawer_gap_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_gap'), format="%.1f", step=0.1)
                        st.selectbox("Poignée", options=['none', 'integrated_cutout'], index=['none', 'integrated_cutout'].index(dr_p.get('drawer_handle_type', 'none')), format_func=lambda x: 'Aucune' if x=='none' else 'Intégrée (Découpe)', key=f"drawer_handle_type_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_handle_type'))
                        if dr_p.get('drawer_handle_type') == 'integrated_cutout':
                            st.number_input("Largeur Poignée", value=dr_p.get('drawer_handle_width', 150.0), key=f"drawer_handle_width_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_handle_width'), format="%.0f", step=1.0)
                            st.number_input("Hauteur Poignée", value=dr_p.get('drawer_handle_height', 40.0), key=f"drawer_handle_height_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_handle_height'), format="%.0f", step=1.0)
                            st.number_input("Offset Haut", value=dr_p.get('drawer_handle_offset_top', 10.0), key=f"drawer_handle_offset_top_{idx}", on_change=lambda: update_selected_cabinet_drawer('drawer_handle_offset_top'), format="%.0f", step=1.0)
                        st.text_input("Matière Face Tiroir", value=dr_p.get('material', 'Matière Tiroir'), key=f"drawer_material_{idx}", on_change=lambda: update_selected_cabinet_drawer_material('material'))

                with t_sh:
                    st.markdown("#### Configuration des Étagères")
                    st.button("Ajouter une étagère au Caisson", key=f"add_shelf_{idx}", on_click=add_shelf_callback)
                    if 'shelves' in selected_cab:
                        for i, s in enumerate(selected_cab['shelves']):
                            # SÉCURITÉ ICI : .get
                            s_type = s.get('shelf_type', 'mobile')
                            with st.expander(f"⚙️ Étagère {i+1} ({'Mobile' if s_type=='mobile' else 'Fixe'})"):
                                st.selectbox("Type", options=['mobile', 'fixe'], index=0 if s_type=='mobile' else 1, format_func=lambda x: 'Mobile (Taquets)' if x=='mobile' else 'Fixe', key=f"shelf_t_{idx}_{i}", on_change=lambda x=i: update_shelf_prop(x, 'shelf_type'))
                                st.number_input("Position Y (mm)", value=s['height'], key=f"shelf_h_{idx}_{i}", on_change=lambda x=i: update_shelf_prop(x, 'height'), format="%.0f", step=1.0)
                                st.number_input("Épaisseur (mm)", value=s['thickness'], key=f"shelf_e_{idx}_{i}", on_change=lambda x=i: update_shelf_prop(x, 'thickness'), format="%.0f", step=1.0)
                                st.text_input("Matière", value=s.get('material', 'Matière Étagère'), key=f"shelf_m_{idx}_{i}", on_change=lambda x=i: update_shelf_material(x, 'material'))
                                if s_type == 'mobile':
                                    st.selectbox("Motif Trous", options=['full_height', '5_holes_centered', 'custom_n_m'], index=['full_height', '5_holes_centered', 'custom_n_m'].index(s.get('mobile_machining_type', 'full_height')), format_func=lambda x: {'full_height':'Toute hauteur', '5_holes_centered':'5 Trous Centrés', 'custom_n_m':'Personnalisé'}.get(x, x), key=f"shelf_m_type_{idx}_{i}", on_change=lambda x=i: update_shelf_prop(x, 'mobile_machining_type'))
                                    if s.get('mobile_machining_type') == 'custom_n_m':
                                        st.number_input("Trous au-dessus (N)", value=s.get('custom_holes_above', 0), key=f"shelf_c_above_{idx}_{i}", on_change=lambda x=i: update_shelf_prop(x, 'custom_holes_above'), step=1)
                                        st.number_input("Trous en-dessous (M)", value=s.get('custom_holes_below', 0), key=f"shelf_c_below_{idx}_{i}", on_change=lambda x=i: update_shelf_prop(x, 'custom_holes_below'), step=1)
                                st.button("Supprimer cette étagère 🗑️", key=f"del_shelf_{idx}_{i}", on_click=lambda x=i: delete_shelf_callback(x))

                with t_deb:
                    st.markdown(f"#### Feuille de Débit (Caisson {idx})")
                    df = pd.DataFrame(selected_cab['debit_data'])
                    st.data_editor(df, key=f"editor_{idx}", hide_index=True)

# --- CALCUL CENTRALISÉ ---
all_calculated_parts, shelf_dims_cache = calculate_all_project_parts()

# --- COLONNE 2 ---
with col2:
    
    # A. DÉTECTION DE COLLISIONS
    sel_idx = st.session_state.get('selected_cabinet_index')
    if sel_idx is None and st.session_state['scene_cabinets']: sel_idx = 0
    cab_for_check = st.session_state['scene_cabinets'][sel_idx] if sel_idx is not None and 0 <= sel_idx < len(st.session_state['scene_cabinets']) else None
    
    # 1. Effectuer la détection
    collisions = []
    if cab_for_check:
        dims = cab_for_check['dims']
        t_tb = dims['t_tb_raw']; h_side = dims['H_raw']; W_raw = dims['W_raw']; t_lr = dims['t_lr_raw']
        ys_vis, ys_dowel = calculate_hole_positions(W_raw)
        check_holes_mg = []
        for x in ys_vis: check_holes_mg.extend([{'y': t_tb/2, 'x':x, 'source':'structure'}, {'y': h_side - t_tb/2, 'x':x, 'source':'structure'}])
        
        if selected_cab['door_props']['has_door']:
            for y in get_hinge_y_positions(h_side): 
                check_holes_mg.append({'y': y, 'x':20.0, 'source': 'charniere_vis1'})
                check_holes_mg.append({'y': y, 'x':52.0, 'source': 'charniere_vis2'})
        
        if 'shelves' in selected_cab:
            for s in selected_cab['shelves']:
                # SÉCURITÉ ICI : .get
                s_type = s.get('shelf_type', 'mobile')
                if s_type == 'fixe':
                    yc_val = t_tb + s['height'] + s['thickness']/2.0 
                    check_holes_mg.append({'y': yc_val, 'x':0, 'source': 'shelf_fixe'})
                else:
                    for h in get_mobile_shelf_holes(h_side, t_tb, s, W_raw):
                        h['source'] = 'shelf_mobile'
                        check_holes_mg.append(h)
        
        collisions = detect_collisions(check_holes_mg, selected_cab.get('shelves', []), panel_name=f"Caisson {sel_idx}")

    # 2. Affichage de l'alerte/popup
    collision_state_key = f'ignore_collision_state_{sel_idx}'

    import hashlib
    cab_hash = hashlib.sha256(str(selected_cab).encode()).hexdigest() if selected_cab else ""
    if 'last_cab_hash' not in st.session_state or st.session_state['last_cab_hash'] != cab_hash:
        st.session_state[collision_state_key] = False
        st.session_state['last_cab_hash'] = cab_hash

    if collisions and not st.session_state.get(collision_state_key, False):
        st.toast(f"⚠️ CONFLIT DÉTECTÉ !", icon="🚨")
        
        # ALERTE "EXPANDER" FLOTTANTE ROUGE
        with st.expander("🚨 PROBLÈME D'USINAGE (Action requise)", expanded=True):
            st.error("Chevauchement d'usinage détecté.")
            
            # Affichage simplifié (juste le premier conflit pour ne pas saturer)
            if collisions:
                 st.caption(f"📍 {collisions[0]['msg']}")
            
            c1, c2, c3 = st.columns(3)
            
            # FONCTION DE DÉPLACEMENT INTELLIGENT (Calcul de la distance de saut)
            def move_shelf_smart(direction_mult):
                if 'shelves' in st.session_state['scene_cabinets'][sel_idx] and st.session_state['scene_cabinets'][sel_idx]['shelves']:
                    # On détermine la hauteur du bloc à sauter
                    # Par défaut pour 5 trous : ~128mm + marge = 150mm
                    # Pour custom : (N+M)*32 + marge
                    # Pour full_height : On ne peut pas vraiment sauter, on décale de 32mm
                    
                    shelf = st.session_state['scene_cabinets'][sel_idx]['shelves'][0]
                    
                    # Calcul de la hauteur du pattern
                    pattern_height = 32.0 
                    # SÉCURITÉ ICI
                    s_type = shelf.get('shelf_type', 'mobile')
                    if s_type == 'mobile':
                        m_type = shelf.get('mobile_machining_type', 'full_height')
                        if m_type == '5_holes_centered':
                            pattern_height = 128.0 # 4 entraxes de 32
                        elif m_type == 'custom_n_m':
                            n = shelf.get('custom_holes_above', 0)
                            m = shelf.get('custom_holes_below', 0)
                            pattern_height = (n + m) * 32.0
                    
                    # Distance de saut = Hauteur du pattern + Marge de sécurité (32mm)
                    jump_dist = pattern_height + 32.0
                    
                    st.session_state['scene_cabinets'][sel_idx]['shelves'][0]['height'] += (jump_dist * direction_mult)
                    st.session_state[collision_state_key] = False 
            
            c1.button("⬆️", on_click=move_shelf_smart, args=(1.0,), use_container_width=True, help="Déplacer au-dessus de la zone de conflit")
            c2.button("⬇️", on_click=move_shelf_smart, args=(-1.0,), use_container_width=True, help="Déplacer au-dessous de la zone de conflit")
            
            if c3.button("Ignorer", use_container_width=True, type="primary"):
                st.session_state[collision_state_key] = True
                st.rerun()
        
        st.stop()


    # B. 3D VIEW
    st.header("Prévisualisation 3D")
    fig3d = go.Figure()
    scene = st.session_state['scene_cabinets']
    unit_factor = {"mm":0.001,"cm":0.01,"m":1.0}[st.session_state.unit_select]
    abs_origins = calculate_origins_recursively(st.session_state.scene_cabinets, unit_factor)
    
    # COULEURS 3D (Beige Bois & Contraste)
    BODY_COLOR = "#D6C098"      # Bois Clair
    ACCESSORY_COLOR = "#B8A078" # Beige plus foncé (Portes/Tiroirs)
    BODY_OPACITY = 1.0          # Opaque
    ACCESSORY_OPACITY = 1.0     # Opaque
    
    if not st.session_state['scene_cabinets']:
        st.info("La scène est vide.")
    else:
        for i, cab in enumerate(st.session_state['scene_cabinets']):
            o = abs_origins[i]; d = cab['dims']; L, W, H = d['L_raw']*unit_factor, d['W_raw']*unit_factor, d['H_raw']*unit_factor
            tl, tb, tt = d['t_lr_raw']*unit_factor, d['t_fb_raw']*unit_factor, d['t_tb_raw']*unit_factor
            
            # Corps
            fig3d.add_trace(cuboid_mesh_for(L-2*tl, W, tt, (o[0]+tl, o[1], o[2]), color=BODY_COLOR, opacity=BODY_OPACITY, showlegend=False))
            fig3d.add_trace(cuboid_mesh_for(L-2*tl, W, tt, (o[0]+tl, o[1], o[2]+H-tt), color=BODY_COLOR, opacity=BODY_OPACITY, showlegend=False))
            fig3d.add_trace(cuboid_mesh_for(tl, W, H, (o[0], o[1], o[2]), color=BODY_COLOR, opacity=BODY_OPACITY, showlegend=False))
            fig3d.add_trace(cuboid_mesh_for(tl, W, H, (o[0]+L-tl, o[1], o[2]), color=BODY_COLOR, opacity=BODY_OPACITY, showlegend=False))
            fig3d.add_trace(cuboid_mesh_for(L-2*tl, tb, H-2*tt, (o[0]+tl, o[1]+W-tb, o[2]+tt), color=BODY_COLOR, opacity=BODY_OPACITY, showlegend=False))
            
            # Porte
            if cab['door_props']['has_door']:
                dp = cab['door_props']; gap = dp['door_gap'] * unit_factor; thk = dp.get('door_thickness', 19.0) * unit_factor; dy = o[1] - thk
                dH = H + st.session_state.foot_height*unit_factor - gap if dp.get('door_model')=='floor_length' and (i==0) and st.session_state.has_feet else H - 2*gap
                dz = o[2] + (gap * (1.0 if dp.get('door_model')=='standard' else 0.0))
                
                rot_angle = -45 if dp.get('door_opening')=='right' else 45
                
                if dp.get('door_type') == 'single':
                    pivot_x = o[0] + L - gap if dp.get('door_opening')=='right' else o[0] + gap
                    fig3d.add_trace(cuboid_mesh_for(L-2*gap, thk, dH, (o[0]+gap, dy, dz), 
                                                    color=ACCESSORY_COLOR, opacity=ACCESSORY_OPACITY, name=f"Porte {i}",
                                                    rotation_angle=rot_angle, rotation_axis='z', rotation_pivot=(pivot_x, dy, dz)))
                else:
                    dl_half = (L-2*gap)/2; pivot_g = o[0] + gap; pivot_d = o[0] + L - gap
                    fig3d.add_trace(cuboid_mesh_for(dl_half, thk, dH, (o[0]+gap, dy, dz), 
                                                    color=ACCESSORY_COLOR, opacity=ACCESSORY_OPACITY, name=f"Porte G {i}",
                                                    rotation_angle=45, rotation_axis='z', rotation_pivot=(pivot_g, dy, dz)))
                    fig3d.add_trace(cuboid_mesh_for(dl_half, thk, dH, (o[0]+L-gap-dl_half, dy, dz), 
                                                    color=ACCESSORY_COLOR, opacity=ACCESSORY_OPACITY, name=f"Porte D {i}",
                                                    rotation_angle=-45, rotation_axis='z', rotation_pivot=(pivot_d, dy, dz)))

            # Tiroir
            if cab['drawer_props']['has_drawer']:
                drp = cab['drawer_props']; gap = drp['drawer_gap'] * unit_factor; thk = drp.get('drawer_face_thickness', 19.0) * unit_factor
                fig3d.add_trace(cuboid_mesh_for(L-2*gap, thk, drp['drawer_face_H_raw']*unit_factor, (o[0]+gap, o[1]-thk, o[2]+drp['drawer_bottom_offset']*unit_factor), color=ACCESSORY_COLOR, opacity=ACCESSORY_OPACITY, name=f"Tiroir {i}"))

            if 'shelves' in cab:
                for s in cab['shelves']:
                    sh_z = o[2] + tt + (s['height'] * unit_factor)
                    fig3d.add_trace(cuboid_mesh_for(L-2*tl, W-0.01, s['thickness']*unit_factor, (o[0]+tl, o[1], sh_z), color=BODY_COLOR, opacity=BODY_OPACITY, showlegend=False))

        if st.session_state.has_feet:
            l_coords = [abs_origins[i][0] for i in range(len(scene))]; min_L = min(l_coords); max_L = max([abs_origins[i][0] + scene[i]['dims']['L_raw']*unit_factor for i in range(len(scene))])
            min_W = min([abs_origins[i][1] for i in range(len(scene))]); max_W = max([abs_origins[i][1] + scene[i]['dims']['W_raw']*unit_factor for i in range(len(scene))])
            fh = st.session_state.foot_height * unit_factor
            for x in [min_L+0.05, max_L-0.05]:
                for y in [min_W+0.05, max_W-0.05]:
                    fig3d.add_trace(cylinder_mesh_for((x, y, -fh), fh, 0.02, color='#333', showlegend=False))

    fig3d.update_layout(
        scene=dict(
            aspectmode='data',
            xaxis=dict(visible=True, showgrid=True, title="X"), 
            yaxis=dict(visible=True, showgrid=True, title="Y"), 
            zaxis=dict(visible=True, showgrid=True, title="Z"),
            camera=dict(eye=dict(x=1.6, y=1.6, z=1.4))
        ),
        margin=dict(l=0,r=0,t=0,b=0), 
        uirevision='constant'
    ) 
    st.plotly_chart(fig3d, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📤 Exportation")
    if st.session_state['scene_cabinets']:
        html_data, html_ok = generate_stacked_html_plans(st.session_state['scene_cabinets'], list(range(len(st.session_state['scene_cabinets']))))
        
        dl_col1, dl_col2 = st.columns([1, 1])
        
        project_info_export = {"project_name": st.session_state.project_name, "client": st.session_state.client, "adresse_chantier": st.session_state.adresse_chantier, "ref_chantier": st.session_state.ref_chantier, "telephone": st.session_state.telephone, "date_souhaitee": st.session_state.date_souhaitee, "panneau_decor": st.session_state.panneau_decor, "chant_mm": st.session_state.chant_mm, "decor_chant": st.session_state.decor_chant, "corps_meuble": "Ensemble", "quantity": 1, "date": datetime.date.today().strftime("%Y-%m-%d")}
        save_data_export = {'project_name': st.session_state.project_name, 'scene_cabinets': st.session_state.scene_cabinets}
        xls_data = create_styled_excel(project_info_export, pd.DataFrame(all_calculated_parts), save_data_export)
        
        if html_ok: dl_col1.download_button("📄 Télécharger Dossier Plans (HTML)", html_data, f"Dossier_{st.session_state.project_name.replace(' ', '_')}.html", "text/html", use_container_width=True)
        dl_col2.download_button("📥 Télécharger Fiche de Débit (.xlsx)", xls_data, f"Projet_{st.session_state.project_name.replace(' ', '_')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    st.markdown("---")
    st.subheader("📋 Feuille de Débit")
    if all_calculated_parts: st.dataframe(pd.DataFrame(all_calculated_parts), hide_index=True, use_container_width=True)

    st.markdown("---")
    unit_str = st.session_state.unit_select
    
    sel_idx = st.session_state.get('selected_cabinet_index')
    if sel_idx is None and st.session_state['scene_cabinets']: sel_idx = 0
    st.subheader(f"📋 Feuilles d'usinage (Caisson {sel_idx})")
    
    if sel_idx is not None and 0 <= sel_idx < len(st.session_state['scene_cabinets']):
        cab = st.session_state['scene_cabinets'][sel_idx]
        dims = cab['dims']
        L_raw, W_raw, H_raw = dims['L_raw'], dims['W_raw'], dims['H_raw']
        t_lr, t_fb, t_tb = dims['t_lr_raw'], dims['t_fb_raw'], dims['t_tb_raw']
        W_back, H_back = L_raw - 2.0, H_raw - 2.0
        h_side, L_trav, W_mont = H_raw, L_raw-2*t_lr, W_raw
        
        ys_vis, ys_dowel = calculate_hole_positions(W_raw)
        holes_mg, holes_md = [], []
        
        # Trous structure
        for x in ys_vis:
            holes_mg.append({'type':'vis','x':x,'y':t_tb/2,'diam_str':"⌀3"}); holes_mg.append({'type':'vis','x':x,'y':h_side-t_tb/2,'diam_str':"⌀3"})
            holes_md.append({'type':'vis','x':x,'y':t_tb/2,'diam_str':"⌀3"}); holes_md.append({'type':'vis','x':x,'y':h_side-t_tb/2,'diam_str':"⌀3"})
        for x in ys_dowel:
            holes_mg.append({'type':'tourillon','x':x,'y':t_tb/2,'diam_str':"⌀8/20"}); holes_mg.append({'type':'tourillon','x':x,'y':h_side-t_tb/2,'diam_str':"⌀8/20"})
            holes_md.append({'type':'tourillon','x':x,'y':t_tb/2,'diam_str':"⌀8/20"}); holes_md.append({'type':'tourillon','x':x,'y':h_side-t_tb/2,'diam_str':"⌀8/20"})
            
        W_shelf_fixe = W_raw - 10.0
        ys_vis_sf, ys_dowel_sf = calculate_hole_positions(W_shelf_fixe)
        fixed_shelf_tr_draw = {}
        
        if 'shelves' in cab:
            for s_idx, s in enumerate(cab['shelves']):
                # SÉCURITÉ ICI : .get
                s_type = s.get('shelf_type', 'mobile')
                if s_type == 'fixe':
                    yc_val = t_tb + s['height'] + s['thickness']/2.0 
                    
                    for x in ys_vis_sf: holes_mg.append({'type':'vis','x':x+10.0,'y':yc_val,'diam_str':"⌀3"})
                    for x in ys_dowel_sf: holes_mg.append({'type':'tourillon','x':x+10.0,'y':yc_val,'diam_str':"⌀8/20"})
                    for x in ys_vis_sf: holes_md.append({'type':'vis','x':x,'y':yc_val,'diam_str':"⌀3"})
                    for x in ys_dowel_sf: holes_md.append({'type':'tourillon','x':x,'y':yc_val,'diam_str':"⌀8/20"})
                    
                    tr = []
                    for x in ys_vis_sf: tr.append({'type':'vis','x':s['thickness']/2,'y':x,'diam_str':"⌀3"})
                    for x in ys_dowel_sf: tr.append({'type':'tourillon','x':s['thickness']/2,'y':x,'diam_str':"⌀8/20"})
                    fixed_shelf_tr_draw[s_idx] = tr
                else:
                    holes_mg.extend(get_mobile_shelf_holes(h_side, t_tb, s, W_mont))
                    holes_md.extend(get_mobile_shelf_holes(h_side, t_tb, s, W_mont))
                    
        if cab['door_props']['has_door']:
             yh = get_hinge_y_positions(h_side)
             for y in yh: 
                 if cab['door_props']['door_opening']=='left': 
                     holes_mg.append({'type':'vis','x':20.0,'y':y,'diam_str':"⌀5/11.5"}); holes_mg.append({'type':'vis','x':52.0,'y':y,'diam_str':"⌀5/11.5"})
                 else: 
                     holes_md.append({'type':'vis','x':20.0,'y':y,'diam_str':"⌀5/11.5"}); holes_md.append({'type':'vis','x':52.0,'y':y,'diam_str':"⌀5/11.5"})

        # --- NOUVEAU : TROUS DE COULISSES SUR LES MONTANTS (Selon largeur et type) ---
        if cab['drawer_props']['has_drawer']:
            drp = cab['drawer_props']
            tech_type = drp.get('drawer_tech_type', 'K')
            
            # Formule Y = épaisseur montant (t_tb) + 33mm + Offset
            y_slide = t_tb + 33.0 + drp['drawer_bottom_offset']
            
            x_slide_holes = []
            wr = W_raw
            
            # Priorité : Si > 643mm (Overrides)
            if wr > 643:
                x_slide_holes = [19, 37, 133, 261, 293, 389, 421, 549]
            else:
                # Logique par ranges
                # TYPE N (Specifique)
                if tech_type == 'N':
                    if 403 < wr < 452: x_slide_holes = [19, 37, 133, 165, 229, 325]
                    elif 453 < wr < 502: x_slide_holes = [19, 37, 133, 165, 261, 357]
                    elif 503 < wr < 552: x_slide_holes = [19, 37, 133, 261, 293, 453]
                    elif 553 < wr < 602: x_slide_holes = [19, 37, 133, 261, 293, 453]
                    else:
                        pass 

                # TYPE D, K, M (et fallback N)
                if not x_slide_holes:
                    if 273 < wr < 302: x_slide_holes = [19, 37, 133, 261]
                    elif 303 < wr < 352: x_slide_holes = [19, 37, 133, 165, 261]
                    elif 353 < wr < 402: x_slide_holes = [19, 37, 133, 165, 325]
                    elif 403 < wr < 452: x_slide_holes = [19, 37, 133, 165, 229, 325]
                    elif 453 < wr < 502: x_slide_holes = [19, 37, 133, 165, 261, 357]
                    elif 503 < wr < 552: x_slide_holes = [19, 37, 133, 261, 293, 453]
                    elif 553 < wr < 602: x_slide_holes = [19, 37, 133, 261, 293, 453]
                    elif 603 < wr < 652: x_slide_holes = [19, 37, 133, 261, 293, 325, 357, 517]

            for x_s in x_slide_holes:
                # Montant Gauche (Reference Avant = 0)
                holes_mg.append({'type': 'vis', 'x': x_s, 'y': y_slide, 'diam_str': "⌀5/12"})
                # Montant Droit (Reference Avant = Opposé si miroir)
                # ICI CORRECTION : Inversion de l'axe X pour le montant droit
                holes_md.append({'type': 'vis', 'x': W_mont - x_s, 'y': y_slide, 'diam_str': "⌀5/12"})

        proj = {"project_name": st.session_state.project_name, "corps_meuble": f"Caisson {sel_idx}", "quantity": 1, "date": ""}
        tholes = [{'type':'tourillon','x':t_tb/2,'y':y,'diam_str':"⌀8/20"} for y in ys_dowel]
        
        c_trav = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":False, "Chant Droit":False}
        st.plotly_chart(draw_machining_view_pro_final("Traverse Bas (Tb)", L_trav, W_mont, t_tb, unit_str, proj, c_trav, [], [], tholes), use_container_width=True)
        st.plotly_chart(draw_machining_view_pro_final("Traverse Haut (Th)", L_trav, W_mont, t_tb, unit_str, proj, c_trav, [], [], tholes), use_container_width=True)
        
        c_mont = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":True, "Chant Droit":True}
        st.plotly_chart(draw_machining_view_pro_final("Montant Gauche (Mg)", W_mont, h_side, t_lr, unit_str, proj, c_mont, holes_mg), use_container_width=True)
        st.plotly_chart(draw_machining_view_pro_final("Montant Droit (Md)", W_mont, h_side, t_lr, unit_str, proj, c_mont, holes_md), use_container_width=True)
        
        c_fond = {"Chant Avant":False, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
        st.plotly_chart(draw_machining_view_pro_final("Panneau Arrière (F)", W_back, H_back, t_fb, unit_str, proj, c_fond, calculate_back_panel_holes(W_back, H_back)), use_container_width=True)
        
        if cab['door_props']['has_door']:
            dp = cab['door_props']
            dH = H_raw + st.session_state.foot_height - dp['door_gap'] - 10.0 if dp.get('door_model')=='floor_length' else H_raw - (2 * dp['door_gap'])
            dW = L_raw - (2 * dp['door_gap'])
            y_h = get_hinge_y_positions(dH)
            
            holes_p = []; xc = 23.5 if dp['door_opening']=='left' else dW-23.5; xv = 33.0 if dp['door_opening']=='left' else dW-33.0
            for y in y_h: 
                holes_p.append({'type':'tourillon','x':xc,'y':y,'diam_str':"⌀35"}); holes_p.append({'type':'vis','x':xv,'y':y+22.5,'diam_str':"⌀8"}); holes_p.append({'type':'vis','x':xv,'y':y-22.5,'diam_str':"⌀8"})

            c_p = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":True, "Chant Droit":True}
            st.plotly_chart(draw_machining_view_pro_final(f"Porte (C{sel_idx})", dW, dH, dp['door_thickness'], unit_str, proj, c_p, holes_p), use_container_width=True)
            
        if cab['drawer_props']['has_drawer']:
            drp = cab['drawer_props']
            f_holes = [] 
            dr_H = drp['drawer_face_H_raw']
            dr_L = L_raw - (2 * drp['drawer_gap'])
            
            tech_type = drp.get('drawer_tech_type', 'K')
            
            # --- LOGIQUE PERÇAGE FAÇADE (Selon type) ---
            # K: 3 trous (47.5, 79.5, 111.5)
            # M: 2 trous (47.5, 79.5)
            # N: 2 trous (32.5, 64.5)
            # D: 3 trous (47.5, 79.5, 207.5)
            
            face_coords_map = {
                'K': [47.5, 79.5, 111.5],
                'M': [47.5, 79.5],
                'N': [32.5, 64.5],
                'D': [47.5, 79.5, 207.5]
            }
            
            y_coords_face = face_coords_map.get(tech_type, [47.5, 79.5, 111.5])
            
            for y in y_coords_face:
                if y < dr_H:
                    f_holes.append({'type': 'tourillon', 'x': 32.5, 'y': y, 'diam_str': "⌀10/12"})
                    f_holes.append({'type': 'tourillon', 'x': dr_L - 32.5, 'y': y, 'diam_str': "⌀10/12"})

            c_tf = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":True, "Chant Droit":True}
            cutout = {'width': drp.get('drawer_handle_width', 150.0), 'height': drp.get('drawer_handle_height', 40.0), 'offset_top': drp.get('drawer_handle_offset_top', 10.0)} if drp.get('drawer_handle_type') == 'integrated_cutout' else None
            
            st.plotly_chart(draw_machining_view_pro_final(f"Tiroir-Face (C{sel_idx}) [Type {tech_type}]", dr_L, dr_H, drp.get('drawer_face_thickness', 19.0), unit_str, proj, c_tf, f_holes, [], [], cutout), use_container_width=True)
            
            # --- LOGIQUE PERÇAGE DOS (Selon type) ---
            # Hauteur forcée selon type
            back_height_map = {'N': 69.0, 'M': 84.0, 'K': 116.0, 'D': 199.0}
            fixed_back_h = back_height_map.get(tech_type, 116.0)
            
            c_td = {"Chant Avant":False, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
            d_L_t = (L_raw - (2 * t_lr)) - 49.0
            d_holes_t = []
            
            # Coordonnées Y pour le dos (X=9mm du bord)
            back_coords_map = {
                'K': [30.0, 62.0, 94.0],
                'M': [32.0, 64.0],
                'N': [31.0, 47.0],
                'D': [31.0, 63.0, 95.0, 159.0, 191.0]
            }
            y_coords_back = back_coords_map.get(tech_type, [30.0, 62.0, 94.0])
            
            for dy in y_coords_back:
                # Côté Gauche (9mm du bord)
                d_holes_t.append({'type': 'vis', 'x': 9.0, 'y': dy, 'diam_str': "⌀2.5/3"})
                # Côté Droit (9mm du bord)
                d_holes_t.append({'type': 'vis', 'x': d_L_t - 9.0, 'y': dy, 'diam_str': "⌀2.5/3"})

            # Le Dos
            st.plotly_chart(draw_machining_view_pro_final(f"Tiroir-Dos (C{sel_idx}) [Type {tech_type}]", d_L_t, fixed_back_h, 16.0, unit_str, proj, c_td, d_holes_t), use_container_width=True)
            # Le Fond (Horizontal) - Epaisseur forcée à 16mm
            st.plotly_chart(draw_machining_view_pro_final(f"Tiroir-Fond (C{sel_idx})", d_L_t, W_raw - (20.0 + t_fb), 16.0, unit_str, proj, c_td), use_container_width=True)

        if 'shelves' in cab:
            for s_idx, s in enumerate(cab['shelves']):
                c_eta = {"Chant Avant":True, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
                sl, sw = shelf_dims_cache.get(f"C{sel_idx}_S{s_idx}", (100,100))
                
                # SÉCURITÉ ICI : .get
                s_type = s.get('shelf_type', 'mobile')
                
                trh = fixed_shelf_tr_draw.get(s_idx, []) if s_type == 'fixe' else []
                
                st.plotly_chart(draw_machining_view_pro_final(f"Etagère {s_idx+1} ({s_type})", sl, sw, s['thickness'], unit_str, proj, c_eta, [], [], trh), use_container_width=True)

    else:
        st.info("Créez un caisson pour voir les plans.")
