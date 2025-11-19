# Contenu de drawing.py
import streamlit as st 
import plotly.graph_objects as go
import numpy as np
import re
import base64 
import os      
import io      

try:
    from PIL import Image
except ImportError:
    st.error("BIBLIOTHÈQUE MANQUANTE ! Veuillez exécuter : pip install Pillow")
    def load_image_base64(filepath):
        return None

if 'Image' in locals():
    def load_image_base64(filepath):
        """Charge, valide, convertit en PNG, et encode en base64."""
        abs_path = os.path.abspath(filepath)
        
        if not os.path.exists(filepath):
            # N'affiche plus d'erreur, retourne juste None silencieusement
            # st.error(f"Logo introuvable ! L'application cherche ici : {abs_path}")
            return None
        try:
            img = Image.open(filepath)
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="PNG")
            img_bytes = output_buffer.getvalue()
            encoded = base64.b64encode(img_bytes).decode()
            return f"data:image/png;base64,{encoded}"
        except Exception as e:
            st.error(f"Erreur lors du chargement ou de la conversion du logo : {e}")
            return None

# --- MODIFIÉ : Ajout de 'center_cutout_props' ---
def draw_machining_view_professional(panel_name, L, W, T, unit_str, project_info, 
                                     chants,
                                     face_holes_list=[], 
                                     tranche_longue_holes_list=[],
                                     tranche_cote_holes_list=[],
                                     center_cutout_props=None # --- ARGUMENT MODIFIÉ ---
                                     ):
    """
    Dessine une feuille d'usinage 2D avec cotation complète
    pour les dimensions globales ET les perçages.
    """
    fig = go.Figure()
    
    # --- Constantes de Dessin ---
    line_color = "black"
    line_width = 1
    dim_line_color = "#4a4a4a"
    dim_line_width = 0.5
    hatch_pattern = "/" 

    margin = max(L, W) * 0.25 
    if margin < 100: margin = 100
    text_offset = margin * 0.05
    dim_level_offsets = [margin * 0.2, margin * 0.3, margin * 0.4] 
    dim_offset_global = margin * 0.5 
    ext_line_overshoot = margin * 0.1 
    
    tranche_visual_thickness = T * 2
    if tranche_visual_thickness < 15: tranche_visual_thickness = 15
    
    # --- 1. Dessin du Panneau (Vue de Face) ---
    fig.add_shape(type="rect",
                  x0=0, y0=0, x1=L, y1=W,
                  line=dict(color=line_color, width=line_width), fillcolor="white",
                  layer="below") 
    
    # --- NOUVEAU BLOC (CORRIGÉ) : Définition des positions des cotes globales ---
    # (Déplacé ici pour être accessible par la découpe)
    y_cote_L = W + dim_offset_global
    x_cote_W = -dim_offset_global
    # --- FIN DÉPLACEMENT ---

    # --- 1.B Dessin de Découpe Poignée (Rectangle) ---
    if center_cutout_props:
        cut_W = center_cutout_props['width']
        cut_H = center_cutout_props['height']
        cut_offset = center_cutout_props['offset_top']
        
        x0 = (L - cut_W) / 2
        x1 = x0 + cut_W
        y1 = W - cut_offset # Haut de la découpe
        y0 = y1 - cut_H     # Bas de la découpe
        
        # Dessine le rectangle en pointillé
        fig.add_shape(type="rect",
                      x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(color=dim_line_color, width=1, dash="dash"),
                      layer="above")
        
        # Ajoute les cotes pour la découpe
        # Cote X (largeur et position)
        y_dim_cutout = y_cote_L + ext_line_overshoot # Place au-dessus des cotes globales
        fig.add_shape(type="line", x0=x0, y0=y1, x1=x0, y1=y_dim_cutout, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x1, y0=y1, x1=x1, y1=y_dim_cutout, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x0, y0=y_dim_cutout - text_offset, x1=x1, y1=y_dim_cutout - text_offset, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=L/2, y=y_dim_cutout, text=f"{cut_W:.2f}", showarrow=False, font=dict(color=dim_line_color, size=10))

        # Cote Y (hauteur et position)
        x_dim_cutout = x_cote_W - ext_line_overshoot # Place à gauche
        fig.add_shape(type="line", x0=x0, y0=y1, x1=x_dim_cutout, y1=y1, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x_dim_cutout, y1=y0, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x_dim_cutout + text_offset, y0=y0, x1=x_dim_cutout + text_offset, y1=y1, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=x_dim_cutout, y=(y0+y1)/2, text=f"{cut_H:.2f}", textangle=-90, showarrow=False, font=dict(color=dim_line_color, size=10))
        
        # Cote Offset Y (depuis le haut)
        fig.add_shape(type="line", x0=x0, y0=W, x1=x_dim_cutout, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x_dim_cutout - text_offset, y0=y1, x1=x_dim_cutout - text_offset, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=x_dim_cutout - (2*text_offset), y=(y1+W)/2, text=f"{cut_offset:.2f}", textangle=-90, showarrow=False, font=dict(color=dim_line_color, size=10))

    # --- FIN NOUVEAU BLOC ---


    # --- 2. Lignes de Cote (Globales) ---
    # (La définition a été déplacée, on dessine juste)
    fig.add_shape(type="line", x0=0, y0=W, x1=0, y1=y_cote_L + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=L, y0=W, x1=L, y1=y_cote_L + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=0, y0=y_cote_L, x1=L, y1=y_cote_L, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=L/2, y=y_cote_L + text_offset, text=f"{L:.2f}", showarrow=False, font=dict(color=line_color, size=12))

    fig.add_shape(type="line", x0=0, y0=0, x1=x_cote_W - ext_line_overshoot, y1=0, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=0, y0=W, x1=x_cote_W - ext_line_overshoot, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=x_cote_W, y0=0, x1=x_cote_W, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=x_cote_W - text_offset, y=W/2, text=f"{W:.2f}", textangle=-90, showarrow=False, font=dict(color=line_color, size=12))

    # --- 3. Lignes de Cote (Perçages) ---
    if face_holes_list:
        y_coords = sorted(list(set(h['y'] for h in face_holes_list)))
        y_level = 0
        for y_pos in y_coords:
            x_dim_Y_holes = -dim_level_offsets[y_level % 2]
            fig.add_shape(type="line", x0=x_dim_Y_holes, y0=0, x1=x_dim_Y_holes, y1=W, line=dict(color=dim_line_color, width=dim_line_width, dash="dot"))
            fig.add_shape(type="line", x0=0, y0=y_pos, x1=x_dim_Y_holes - ext_line_overshoot, y1=y_pos, line=dict(color=dim_line_color, width=dim_line_width))
            fig.add_annotation(x=x_dim_Y_holes - text_offset, y=y_pos, text=f"{y_pos:.2f}", textangle=-90, showarrow=False, font=dict(color=dim_line_color, size=10))
            y_level += 1

        x_coords = sorted(list(set(h['x'] for h in face_holes_list)))
        x_level = 0
        for x_pos in x_coords:
            y_dim_X_holes = -dim_level_offsets[x_level % 2]
            fig.add_shape(type="line", x0=0, y0=y_dim_X_holes, x1=L, y1=y_dim_X_holes, line=dict(color=dim_line_color, width=dim_line_width, dash="dot"))
            fig.add_shape(type="line", x0=x_pos, y0=0, x1=x_pos, y1=y_dim_X_holes - ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
            fig.add_annotation(x=x_pos, y=y_dim_X_holes - text_offset, text=f"{x_pos:.2f}", showarrow=False, font=dict(color=dim_line_color, size=10))
            x_level += 1

    # --- 4. Dessin des Tranches ---
    tranche_longue_bas_y0 = -dim_offset_global
    tranche_longue_bas_y1 = tranche_longue_bas_y0 - tranche_visual_thickness
    fig.add_trace(go.Scatter(
        x=[0, L, L, 0, 0],
        y=[tranche_longue_bas_y0, tranche_longue_bas_y0, tranche_longue_bas_y1, tranche_longue_bas_y1, tranche_longue_bas_y0],
        fill="toself", fillcolor="#f0f0f0",
        line=dict(color=line_color, width=line_width),
        fillpattern=dict(shape=hatch_pattern if chants.get("Chant Avant") else "", fgcolor=dim_line_color, solidity=0.5),
        hoverinfo="none", showlegend=False, mode='lines'
    ))
    cote_T_bas_x = L + margin*0.1
    fig.add_shape(type="line", x0=L, y0=tranche_longue_bas_y0, x1=cote_T_bas_x + ext_line_overshoot, y1=tranche_longue_bas_y0, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=L, y0=tranche_longue_bas_y1, x1=cote_T_bas_x + ext_line_overshoot, y1=tranche_longue_bas_y1, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=cote_T_bas_x, y0=tranche_longue_bas_y0, x1=cote_T_bas_x, y1=tranche_longue_bas_y1, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=cote_T_bas_x + text_offset, y=(tranche_longue_bas_y0 + tranche_longue_bas_y1)/2, text=f"{T:.2f}", textangle=-90, showarrow=False, font=dict(color=line_color, size=12))
    
    tranche_longue_haut_y0 = y_cote_L + text_offset + margin*0.1
    tranche_longue_haut_y1 = tranche_longue_haut_y0 + tranche_visual_thickness
    fig.add_trace(go.Scatter(
        x=[0, L, L, 0, 0],
        y=[tranche_longue_haut_y0, tranche_longue_haut_y0, tranche_longue_haut_y1, tranche_longue_haut_y1, tranche_longue_haut_y0],
        fill="toself", fillcolor="#f0f0f0",
        line=dict(color=line_color, width=line_width),
        fillpattern=dict(shape=hatch_pattern if chants.get("Chant Arrière") else "", fgcolor=dim_line_color, solidity=0.5),
        hoverinfo="none", showlegend=False, mode='lines'
    ))
    cote_T_haut_x = L + margin*0.1
    fig.add_shape(type="line", x0=L, y0=tranche_longue_haut_y0, x1=cote_T_haut_x + ext_line_overshoot, y1=tranche_longue_haut_y0, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=L, y0=tranche_longue_haut_y1, x1=cote_T_haut_x + ext_line_overshoot, y1=tranche_longue_haut_y1, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=cote_T_haut_x, y0=tranche_longue_haut_y0, x1=cote_T_haut_x, y1=tranche_longue_haut_y1, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=cote_T_haut_x + text_offset, y=(tranche_longue_haut_y0 + tranche_longue_haut_y1)/2, text=f"{T:.2f}", textangle=-90, showarrow=False, font=dict(color=line_color, size=12))

    tranche_cote_g_x0 = -dim_offset_global
    tranche_cote_g_x1 = tranche_cote_g_x0 - tranche_visual_thickness
    fig.add_trace(go.Scatter(
        x=[tranche_cote_g_x0, tranche_cote_g_x1, tranche_cote_g_x1, tranche_cote_g_x0, tranche_cote_g_x0],
        y=[0, 0, W, W, 0],
        fill="toself", fillcolor="#f0f0f0",
        line=dict(color=line_color, width=line_width),
        fillpattern=dict(shape=hatch_pattern if chants.get("Chant Gauche") else "", fgcolor=dim_line_color, solidity=0.5),
        hoverinfo="none", showlegend=False, mode='lines'
    ))
    cote_T_gauche_y = W + margin*0.1
    fig.add_shape(type="line", x0=tranche_cote_g_x0, y0=W, x1=tranche_cote_g_x0, y1=cote_T_gauche_y + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=tranche_cote_g_x1, y0=W, x1=tranche_cote_g_x1, y1=cote_T_gauche_y + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=tranche_cote_g_x0, y0=cote_T_gauche_y, x1=tranche_cote_g_x1, y1=cote_T_gauche_y, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=(tranche_cote_g_x0 + tranche_cote_g_x1)/2, y=cote_T_gauche_y + text_offset, text=f"{T:.2f}", showarrow=False, font=dict(color=line_color, size=12))

    tranche_cote_d_x0 = L + margin*0.5
    tranche_cote_d_x1 = tranche_cote_d_x0 + tranche_visual_thickness
    fig.add_trace(go.Scatter(
        x=[tranche_cote_d_x0, tranche_cote_d_x1, tranche_cote_d_x1, tranche_cote_d_x0, tranche_cote_d_x0],
        y=[0, 0, W, W, 0],
        fill="toself", fillcolor="#f0f0f0",
        line=dict(color=line_color, width=line_width),
        fillpattern=dict(shape=hatch_pattern if chants.get("Chant Droit") else "", fgcolor=dim_line_color, solidity=0.5),
        hoverinfo="none", showlegend=False, mode='lines'
    ))
    cote_T_droite_y = W + margin*0.1
    fig.add_shape(type="line", x0=tranche_cote_d_x0, y0=W, x1=tranche_cote_d_x0, y1=cote_T_droite_y + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=tranche_cote_d_x1, y0=W, x1=tranche_cote_d_x1, y1=cote_T_droite_y + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=tranche_cote_d_x0, y0=cote_T_droite_y, x1=tranche_cote_d_x1, y1=cote_T_droite_y, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=(tranche_cote_d_x0 + tranche_cote_d_x1)/2, y=cote_T_droite_y + text_offset, text=f"{T:.2f}", showarrow=False, font=dict(color=line_color, size=12))


    # --- 5. Cartouche (Title Block) (CORRIGÉ) ---
    cartouche_height = margin * 0.8
    cartouche_y0 = tranche_longue_bas_y0 - tranche_visual_thickness - (margin*0.2)
    
    # --- NOUVELLE LOGIQUE DE LARGEUR FIXE ---
    fixed_cartouche_width = 700.0 # <-- CHANGÉ À 700
    panel_center_x = L / 2
    cartouche_x0 = panel_center_x - (fixed_cartouche_width / 2)
    cartouche_x1 = panel_center_x + (fixed_cartouche_width / 2)
    
    fig.add_shape(type="rect",
                  x0=cartouche_x0, y0=cartouche_y0 - cartouche_height, x1=cartouche_x1, y1=cartouche_y0,
                  line=dict(color=line_color, width=line_width), fillcolor="#f9f9f0",
                  layer="below")
    
    # Divise en 5 colonnes (4 texte, 1 logo)
    total_width = fixed_cartouche_width
    text_width_ratio = 0.85 # 85% pour le texte
    logo_width_ratio = 0.15 # 15% pour le logo
    
    text_col_width = (total_width * text_width_ratio) / 4.0
    logo_width = total_width * logo_width_ratio
    
    x1 = cartouche_x0 + text_col_width
    x2 = x1 + text_col_width
    x3 = x2 + text_col_width
    x_logo_start = x3 + text_col_width # Début de la 5ème colonne (logo)

    # Lignes de séparation
    fig.add_shape(type="line", x0=x1, y0=cartouche_y0 - cartouche_height, x1=x1, y1=cartouche_y0, line=dict(color=line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=x2, y0=cartouche_y0 - cartouche_height, x1=x2, y1=cartouche_y0, line=dict(color=line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=x3, y0=cartouche_y0 - cartouche_height, x1=x3, y1=cartouche_y0, line=dict(color=line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=x_logo_start, y0=cartouche_y0 - cartouche_height, x1=x_logo_start, y1=cartouche_y0, line=dict(color=line_color, width=dim_line_width))
    
    y_text_title = cartouche_y0 - (cartouche_height * 0.25)
    y_text_value = cartouche_y0 - (cartouche_height * 0.65)
    
    # --- AJOUT DU LOGO (DÉPLACÉ À DROITE ET CENTRÉ) ---
    if 'load_image_base64' in globals():
        logo_base64 = load_image_base64("logo.png") 
        if logo_base64:
            fig.add_layout_image(
                dict(
                    source=logo_base64,
                    xref="x", yref="y",
                    x=x_logo_start + logo_width / 2, # X centré
                    y=cartouche_y0 - cartouche_height / 2, # Y centré
                    sizex=logo_width * 0.8, # 80% de la petite colonne
                    sizey=cartouche_height * 0.8, # 80% de la hauteur
                    xanchor="center", yanchor="middle", # Ancrage au centre
                    layer="above"
                )
            )
    # --- FIN AJOUT LOGO ---

    # --- CORRECTION : Formatage Désignation ---
    # Remplace la première parenthèse ( s'il y en a une ) par <br>(
    formatted_panel_name = panel_name.replace(" (", "<br>(", 1)
    # --- FIN CORRECTION ---

    # Annotations (colonnes 1-4)
    fig.add_annotation(x=cartouche_x0 + text_col_width/2, y=y_text_title, text="<b>Projet</b>", showarrow=False)
    fig.add_annotation(x=cartouche_x0 + text_col_width/2, y=y_text_value, text=project_info['project_name'], showarrow=False)
    
    fig.add_annotation(x=x1 + text_col_width/2, y=y_text_title, text="<b>Désignation</b>", showarrow=False)
    fig.add_annotation(x=x1 + text_col_width/2, y=y_text_value, text=formatted_panel_name, showarrow=False) # <-- UTILISE LE TEXTE FORMATÉ
    
    fig.add_annotation(x=x2 + text_col_width/2, y=y_text_title, text="<b>Quantité</b>", showarrow=False)
    fig.add_annotation(x=x2 + text_col_width/2, y=y_text_value, text=str(project_info['quantity']), showarrow=False)
    
    fig.add_annotation(x=x3 + text_col_width/2, y=y_text_title, text="<b>Date</b>", showarrow=False)
    fig.add_annotation(x=x3 + text_col_width/2, y=y_text_value, text=project_info['date'], showarrow=False)
    # --- FIN MODIFICATION CARTPOUCHE ---


    # --- 6. Dessin des Trous (Visuels) ---
    annotated_hole_types = set()

    for hole in face_holes_list:
        x_pos, y_pos = hole['x'], hole['y']
        diam_text = hole.get('diam_str', '⌀8' if hole['type'] == 'tourillon' else '⌀3')
        hole_type_key = f"{hole['type']}_{diam_text}"

        try:
            diam = float(re.findall(r"[\d\.]+", diam_text.split('/')[0])[0])
            radius = diam / 2.0
        except (ValueError, IndexError):
            radius = 4.0 
            
        x0, x1 = x_pos - radius, x_pos + radius
        y0, y1 = y_pos - radius, y_pos + radius

        fillcolor = "white"
        line_color = "black"
        line_width = 1
        
        if hole['type'] == 'vis':
             fillcolor = "black" 
        
        fig.add_shape(
            type="circle",
            x0=x0, y0=y0, x1=x1, y1=y1,
            line_color=line_color,
            line_width=line_width,
            fillcolor=fillcolor,
            layer="above"
        )
        
        if hole_type_key not in annotated_hole_types:
            fig.add_annotation(
                x=x_pos, y=y_pos,
                text=diam_text,
                xshift=radius*1.5, yshift=radius*1.5, 
                showarrow=False,
                font=dict(size=9, color="#555")
            )
            annotated_hole_types.add(hole_type_key)

    # Trous sur les TRANCHES CÔTÉ (Gauche et Droite)
    dowel_tranche_c_g_x, dowel_tranche_c_g_y = [], [] 
    dowel_tranche_c_d_x, dowel_tranche_c_d_y = [], [] 
    visual_hole_center_offset = (tranche_visual_thickness / 2)
    
    if tranche_cote_holes_list:
        y_coords_tranche = sorted(list(set(h['y'] for h in tranche_cote_holes_list)))
        y_level = 0
        for y_pos in y_coords_tranche:
            x_dim_Y_tranche = -dim_level_offsets[y_level % 2] 
            fig.add_shape(type="line", x0=tranche_cote_g_x0, y0=y_pos, x1=x_dim_Y_tranche - ext_line_overshoot, y1=y_pos, line=dict(color=dim_line_color, width=dim_line_width))
            fig.add_annotation(x=x_dim_Y_tranche - text_offset, y=y_pos, text=f"{y_pos:.2f}", textangle=-90, showarrow=False, font=dict(color=dim_line_color, size=10))
            y_level += 1

    for hole in tranche_cote_holes_list:
        if hole['type'] == 'tourillon':
            y_pos = hole['y']
            x_pos_g = tranche_cote_g_x0 - visual_hole_center_offset
            dowel_tranche_c_g_x.append(x_pos_g)
            dowel_tranche_c_g_y.append(y_pos)
            x_pos_d = tranche_cote_d_x0 + visual_hole_center_offset
            dowel_tranche_c_d_x.append(x_pos_d)
            dowel_tranche_c_d_y.append(y_pos)
            diam_text = hole.get('diam_str', "⌀8")
            hole_type_key = f"tranche_{diam_text}"
            if hole_type_key not in annotated_hole_types:
                fig.add_annotation(x=x_pos_g, y=y_pos, text=diam_text, xshift=-10, yshift=10, showarrow=False, font=dict(size=9))
                annotated_hole_types.add(hole_type_key)

    if dowel_tranche_c_g_x:
        fig.add_trace(go.Scatter(x=dowel_tranche_c_g_x, y=dowel_tranche_c_g_y, mode='markers',
                                 marker=dict(color='rgba(0,0,0,0)', size=8, line=dict(width=1, color='black')),
                                 name="Tourillons (Tranche Côté G.)", showlegend=False, hoverinfo='none'))
    if dowel_tranche_c_d_x:
        fig.add_trace(go.Scatter(x=dowel_tranche_c_d_x, y=dowel_tranche_c_d_y, mode='markers',
                                 marker=dict(color='rgba(0,0,0,0)', size=8, line=dict(width=1, color='black')),
                                 name="Tourillons (Tranche Côté D.)", showlegend=False, hoverinfo='none'))

    # --- 7. Symboles d'Orientation (SUPPRIMÉ) ---

    # --- 8. Mise en page finale ---
    y_max_view = (y_cote_L + text_offset + margin*0.1 + tranche_visual_thickness)
    
    # MODIFIÉ : Assurer que les cotes de découpe sont incluses dans la vue
    y_max_view_cutout = y_cote_L + ext_line_overshoot + text_offset
    y_max_view = max(y_max_view, y_max_view_cutout)
    
    y_min_view_cotation = (tranche_longue_bas_y0 - tranche_visual_thickness - (margin*0.2))
    y_min_view_cartouche = (cartouche_y0 - cartouche_height - margin*0.1)
    y_min_view_sym = -dim_offset_global - (text_offset * 4) 
    y_min_view = min(y_min_view_cotation, y_min_view_cartouche, y_min_view_sym)
    
    # Recalculer l'étendue X en fonction de la largeur fixe du cartouche ET des cotes de découpe
    x_min_view_panel = -dim_offset_global - (text_offset * 4)
    x_min_view_cartouche = cartouche_x0
    x_min_view_cutout = -dim_offset_global - ext_line_overshoot - (3*text_offset)
    
    x_min_view = min(x_min_view_panel, x_min_view_cartouche, x_min_view_cutout) - margin*0.1 # Marge supplémentaire

    x_max_view_panel = (tranche_cote_d_x0 + tranche_visual_thickness + (margin*0.2))
    x_max_view_cartouche = cartouche_x1
    x_max_view = max(x_max_view_panel, x_max_view_cartouche) + margin*0.1 # Marge supplémentaire

    fig.update_layout(
        title=f"<b>Feuille d'usinage: {panel_name}</b>",
        height=700,
        xaxis=dict(visible=False, range=[x_min_view, x_max_view]),
        yaxis=dict(visible=False, range=[y_min_view, y_max_view], scaleanchor="x", scaleratio=1),
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False
    )
    return fig