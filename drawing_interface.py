import plotly.graph_objects as go
import numpy as np
import re
import base64
import os
import io

# --- GESTION DES IMPORTS IMAGE ---
try:
    from PIL import Image
except ImportError:
    def load_image_base64(filepath): return None

if 'Image' in locals():
    def load_image_base64(filepath):
        if not os.path.exists(filepath): return None
        try:
            img = Image.open(filepath)
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="PNG")
            encoded = base64.b64encode(output_buffer.getvalue()).decode()
            return f"data:image/png;base64,{encoded}"
        except: return None

# --- FONCTIONS UTILITAIRES ---
def create_hatch_lines(x0, y0, x1, y1, density=20):
    lines_x, lines_y = [], []
    xmin, xmax = min(x0, x1), max(x0, x1)
    ymin, ymax = min(y0, y1), max(y0, y1)
    start_c = ymin - xmax
    end_c = ymax - xmin
    c = start_c
    while c <= end_c:
        pts = []
        if ymin <= xmin + c <= ymax: pts.append((xmin, xmin + c))
        if ymin <= xmax + c <= ymax: pts.append((xmax, xmax + c))
        if xmin <= ymin - c <= xmax: pts.append((ymin - c, ymin))
        if xmin <= ymax - c <= xmax: pts.append((ymax - c, ymax))
        pts = sorted(list(set(pts)))
        if len(pts) >= 2:
            lines_x.extend([pts[0][0], pts[-1][0], None])
            lines_y.extend([pts[0][1], pts[-1][1], None])
        c += density
    return lines_x, lines_y

def add_pro_dimension(fig, x0, y0, x1, y1, text_val, offset_dist, axis='x', color="#4a4a4a", text_scale=1.0):
    """Ajoute une ligne de cote (avec scale optionnel pour le texte)"""
    tick_len = 5 * text_scale
    line_width = 1
    ext_overshoot = 5 * text_scale
    
    # Taille de police adaptée
    font_sz = max(11, 11 * text_scale)
    text_font = dict(color=color, size=font_sz)
    text_bg = "white"

    if axis == 'x':
        y_dim = y0 + offset_dist if offset_dist != 0 else y0
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x0, y1=y_dim + (np.sign(offset_dist)*ext_overshoot), line=dict(color=color, width=0.5))
        fig.add_shape(type="line", x0=x1, y0=y1, x1=x1, y1=y_dim + (np.sign(offset_dist)*ext_overshoot), line=dict(color=color, width=0.5))
        fig.add_shape(type="line", x0=x0, y0=y_dim, x1=x1, y1=y_dim, line=dict(color=color, width=line_width))
        fig.add_shape(type="line", x0=x0, y0=y_dim-tick_len, x1=x0, y1=y_dim+tick_len, line=dict(color=color, width=1.5))
        fig.add_shape(type="line", x0=x1, y0=y_dim-tick_len, x1=x1, y1=y_dim+tick_len, line=dict(color=color, width=1.5))
        text_y_pos = y_dim + (np.sign(offset_dist) * (15 * text_scale))
        fig.add_annotation(x=(x0+x1)/2, y=text_y_pos, text=str(text_val), showarrow=False, font=text_font, bgcolor=text_bg)
        
    elif axis == 'y':
        x_dim = x0 + offset_dist
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x_dim + (np.sign(offset_dist)*ext_overshoot), y1=y0, line=dict(color=color, width=0.5))
        fig.add_shape(type="line", x0=x1, y0=y1, x1=x_dim + (np.sign(offset_dist)*ext_overshoot), y1=y1, line=dict(color=color, width=0.5))
        fig.add_shape(type="line", x0=x_dim, y0=y0, x1=x_dim, y1=y1, line=dict(color=color, width=line_width))
        fig.add_shape(type="line", x0=x_dim-tick_len, y0=y0, x1=x_dim+tick_len, y1=y0, line=dict(color=color, width=1.5))
        fig.add_shape(type="line", x0=x_dim-tick_len, y0=y1, x1=x_dim+tick_len, y1=y1, line=dict(color=color, width=1.5))
        
        text_x_pos = x_dim + (np.sign(offset_dist) * (15 * text_scale))
        fig.add_annotation(x=text_x_pos, y=(y0+y1)/2, text=str(text_val), showarrow=False, textangle=-90, font=text_font, bgcolor=text_bg)

def draw_machining_view_pro_final(panel_name, L, W, T, unit_str, project_info, 
                                 chants, face_holes_list=[], tranche_longue_holes_list=[], 
                                 tranche_cote_holes_list=[], center_cutout_props=None):
    fig = go.Figure()
    
    # --- CALCUL DE L'ECHELLE GLOBALE POUR LE RENDU ---
    # Si la pièce est très grande (ex: 2000mm), le cartouche de 80mm parait minuscule.
    # On définit un facteur d'échelle visuel.
    max_dimension = max(L, W)
    # 800mm est la "taille standard" pour laquelle l'échelle est 1.0
    legend_scale = max_dimension / 800.0
    if legend_scale < 1.0: legend_scale = 1.0 # On ne réduit pas pour les petites pièces
    
    # --- CONFIGURATION STYLE ---
    line_color, dim_line_color = "black", "#4a4a4a"
    line_width, dim_line_width = 1, 0.5
    HATCH_COLOR = "rgba(80, 80, 80, 0.8)" 
    HATCH_WIDTH_PX = 1
    HATCH_SPACING = max(max_dimension / 40, 20.0)

    GAP_FOR_DIMS = 250.0 * legend_scale # On adapte aussi l'espacement
    if GAP_FOR_DIMS < 250: GAP_FOR_DIMS = 250.0

    dist_panel_to_tranche = GAP_FOR_DIMS + 10 
    
    margin = max_dimension * 0.45
    if margin < 200: margin = 200
    
    text_offset = 20 * legend_scale
    tranche_visual_thickness = T * 2
    if tranche_visual_thickness < 15: tranche_visual_thickness = 15
    
    # Offsets des cotes
    hole_dim_offset_1 = 50 
    hole_dim_offset_2 = 100 
    dim_level_offsets = [hole_dim_offset_1, hole_dim_offset_2]

    global_dim_offset = dist_panel_to_tranche + tranche_visual_thickness + (40 * legend_scale)
    y_cote_L_line = W + global_dim_offset
    x_cote_W_line = -global_dim_offset
    ext_line_overshoot = margin * 0.1 

    # --- 1. Panneau Central ---
    fig.add_shape(type="rect", x0=0, y0=0, x1=L, y1=W, line=dict(color=line_color, width=line_width), fillcolor="white", layer="below")
    
    # --- 2. Tranches ---
    # Bas
    tb_y0 = -dist_panel_to_tranche
    tb_y1 = tb_y0 - tranche_visual_thickness
    fig.add_trace(go.Scatter(x=[0, L, L, 0, 0], y=[tb_y0, tb_y0, tb_y1, tb_y1, tb_y0], fill="toself", fillcolor="#f0f0f0", line=dict(color=line_color, width=line_width), hoverinfo="none", showlegend=False, mode='lines'))
    if chants.get("Chant Avant"):
        hx, hy = create_hatch_lines(0, tb_y0, L, tb_y1, density=HATCH_SPACING)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=HATCH_WIDTH_PX), hoverinfo='skip', showlegend=False))

    # Haut
    th_y0 = W + dist_panel_to_tranche
    th_y1 = th_y0 + tranche_visual_thickness
    fig.add_trace(go.Scatter(x=[0, L, L, 0, 0], y=[th_y0, th_y0, th_y1, th_y1, th_y0], fill="toself", fillcolor="#f0f0f0", line=dict(color=line_color, width=line_width), hoverinfo="none", showlegend=False, mode='lines'))
    if chants.get("Chant Arrière"):
        hx, hy = create_hatch_lines(0, th_y0, L, th_y1, density=HATCH_SPACING)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=HATCH_WIDTH_PX), hoverinfo='skip', showlegend=False))

    # Gauche
    tg_x0 = -dist_panel_to_tranche
    tg_x1 = tg_x0 - tranche_visual_thickness
    fig.add_trace(go.Scatter(x=[tg_x0, tg_x1, tg_x1, tg_x0, tg_x0], y=[0, 0, W, W, 0], fill="toself", fillcolor="#f0f0f0", line=dict(color=line_color, width=line_width), hoverinfo="none", showlegend=False, mode='lines'))
    if chants.get("Chant Gauche"):
        hx, hy = create_hatch_lines(tg_x0, 0, tg_x1, W, density=HATCH_SPACING)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=HATCH_WIDTH_PX), hoverinfo='skip', showlegend=False))

    # Droite
    td_x0 = L + dist_panel_to_tranche
    td_x1 = td_x0 + tranche_visual_thickness
    fig.add_trace(go.Scatter(x=[td_x0, td_x1, td_x1, td_x0, td_x0], y=[0, 0, W, W, 0], fill="toself", fillcolor="#f0f0f0", line=dict(color=line_color, width=line_width), hoverinfo="none", showlegend=False, mode='lines'))
    if chants.get("Chant Droit"):
        hx, hy = create_hatch_lines(td_x0, 0, td_x1, W, density=HATCH_SPACING)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=HATCH_WIDTH_PX), hoverinfo='skip', showlegend=False))

    # --- 3. COTES GLOBALES & EPAISSEURS ---
    dim_font = dict(color=line_color, size=max(12, 12 * legend_scale))
    dim_bg = "white"

    # Epaisseurs
    cote_T_bas_x = L + margin*0.1
    fig.add_shape(type="line", x0=L, y0=tb_y0, x1=cote_T_bas_x + ext_line_overshoot, y1=tb_y0, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=L, y0=tb_y1, x1=cote_T_bas_x + ext_line_overshoot, y1=tb_y1, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=cote_T_bas_x, y0=tb_y0, x1=cote_T_bas_x, y1=tb_y1, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=cote_T_bas_x + text_offset, y=(tb_y0+tb_y1)/2, text=f"{T:.0f}", textangle=-90, showarrow=False, font=dim_font, bgcolor=dim_bg)

    cote_T_haut_x = L + margin*0.1
    fig.add_shape(type="line", x0=L, y0=th_y0, x1=cote_T_haut_x + ext_line_overshoot, y1=th_y0, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=L, y0=th_y1, x1=cote_T_haut_x + ext_line_overshoot, y1=th_y1, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=cote_T_haut_x, y0=th_y0, x1=cote_T_haut_x, y1=th_y1, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=cote_T_haut_x + text_offset, y=(th_y0+th_y1)/2, text=f"{T:.0f}", textangle=-90, showarrow=False, font=dim_font, bgcolor=dim_bg)

    cote_T_g_y = W + margin*0.1
    fig.add_shape(type="line", x0=tg_x0, y0=W, x1=tg_x0, y1=cote_T_g_y + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=tg_x1, y0=W, x1=tg_x1, y1=cote_T_g_y + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=tg_x0, y0=cote_T_g_y, x1=tg_x1, y1=cote_T_g_y, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=(tg_x0+tg_x1)/2, y=cote_T_g_y + text_offset, text=f"{T:.0f}", showarrow=False, font=dim_font, bgcolor=dim_bg)

    cote_T_d_y = W + margin*0.1
    fig.add_shape(type="line", x0=td_x0, y0=W, x1=td_x0, y1=cote_T_d_y + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=td_x1, y0=W, x1=td_x1, y1=cote_T_d_y + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=td_x0, y0=cote_T_d_y, x1=td_x1, y1=cote_T_d_y, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=(td_x0+td_x1)/2, y=cote_T_d_y + text_offset, text=f"{T:.0f}", showarrow=False, font=dim_font, bgcolor=dim_bg)

    # Globales
    fig.add_shape(type="line", x0=0, y0=W, x1=0, y1=y_cote_L_line + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=L, y0=W, x1=L, y1=y_cote_L_line + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=0, y0=y_cote_L_line, x1=L, y1=y_cote_L_line, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=L/2, y=y_cote_L_line + text_offset, text=f"{L:.0f}", showarrow=False, font=dim_font, bgcolor=dim_bg)
    
    fig.add_shape(type="line", x0=0, y0=0, x1=x_cote_W_line - ext_line_overshoot, y1=0, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=0, y0=W, x1=x_cote_W_line - ext_line_overshoot, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=x_cote_W_line, y0=0, x1=x_cote_W_line, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=x_cote_W_line - text_offset, y=W/2, text=f"{W:.0f}", textangle=-90, showarrow=False, font=dim_font, bgcolor=dim_bg)

    # --- 4. Trous et Découpes ---
    if center_cutout_props:
        cut_W, cut_H = center_cutout_props['width'], center_cutout_props['height']
        cut_off = center_cutout_props['offset_top']
        
        x0, x1 = (L-cut_W)/2, (L-cut_W)/2 + cut_W
        y1, y0 = W-cut_off, W-cut_off-cut_H
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=dim_line_color, width=1, dash="dash"), layer="above")
        
        y_dim_cut = y_cote_L_line + ext_line_overshoot 
        fig.add_shape(type="line", x0=x0, y0=y1, x1=x0, y1=y_dim_cut, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x1, y0=y1, x1=x1, y1=y_dim_cut, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x0, y0=y_dim_cut-text_offset, x1=x1, y1=y_dim_cut-text_offset, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=L/2, y=y_dim_cut, text=f"{cut_W:.0f}", showarrow=False, font=dict(color=dim_line_color, size=10*legend_scale), bgcolor="white")
        
        x_dim_cut = x_cote_W_line - ext_line_overshoot 
        fig.add_shape(type="line", x0=x0, y0=y1, x1=x_dim_cut, y1=y1, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x_dim_cut, y1=y0, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x_dim_cut+text_offset, y0=y0, x1=x_dim_cut+text_offset, y1=y1, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=x_dim_cut, y=(y0+y1)/2, text=f"{cut_H:.0f}", textangle=-90, showarrow=False, font=dict(color=dim_line_color, size=10*legend_scale), bgcolor="white")
        
        fig.add_shape(type="line", x0=x0, y0=W, x1=x_dim_cut, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x_dim_cut-text_offset, y0=y1, x1=x_dim_cut-text_offset, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=x_dim_cut-(2*text_offset), y=(y1+W)/2, text=f"{cut_off:.0f}", textangle=-90, showarrow=False, font=dict(color=dim_line_color, size=10*legend_scale), bgcolor="white")

    # --- 5. COTATION INTELLIGENTE DES TROUS ---
    if face_holes_list:
        holes_by_x = {}
        for h in face_holes_list:
            rx = round(h['x'], 1)
            if rx not in holes_by_x: holes_by_x[rx] = []
            holes_by_x[rx].append(h['y'])
        
        x_coords_sorted = sorted(holes_by_x.keys())
        
        for i, x_val in enumerate(x_coords_sorted):
            y_vals = sorted(holes_by_x[x_val])
            if len(y_vals) > 6:
                ys_to_dim = [y_vals[0], y_vals[-1]]
                is_simplified = True
            else:
                ys_to_dim = y_vals
                is_simplified = False
            
            x_d = -dim_level_offsets[i % 2] 
            fig.add_shape(type="line", x0=x_d, y0=min(ys_to_dim), x1=x_d, y1=max(ys_to_dim), line=dict(color=dim_line_color, width=0.5, dash="dot"))
            for y_pos in ys_to_dim:
                fig.add_shape(type="line", x0=0, y0=y_pos, x1=x_d, y1=y_pos, line=dict(color=dim_line_color, width=0.5))
                fig.add_annotation(
                    x=x_d, y=y_pos, xshift=-8, yshift=0,
                    text=f"{y_pos:.0f}", showarrow=False, textangle=-90,
                    xanchor="center", yanchor="middle", 
                    font=dict(size=10*legend_scale, color=dim_line_color), bgcolor="white" 
                )
            if is_simplified:
                fig.add_annotation(x=x_d, y=(y_vals[0]+y_vals[-1])/2, xshift=-8, text="Pas 32mm", textangle=-90, showarrow=False, font=dict(size=9*legend_scale, color="#666"), bgcolor="white")

        all_x_unique = sorted(list(set(h['x'] for h in face_holes_list)))
        for i, x_pos in enumerate(all_x_unique):
            y_d = -dim_level_offsets[i % 2]
            fig.add_shape(type="line", x0=x_pos, y0=0, x1=x_pos, y1=y_d, line=dict(color=dim_line_color, width=0.5))
            fig.add_shape(type="line", x0=0, y0=y_d, x1=L, y1=y_d, line=dict(color=dim_line_color, width=0.5, dash="dot"))
            fig.add_annotation(
                x=x_pos, y=y_d, yshift=-5,
                text=f"{x_pos:.0f}", showarrow=False, xanchor="center", yanchor="top", 
                font=dict(size=10*legend_scale, color=dim_line_color), bgcolor="white"
            )

    # Dessin des trous
    seen_t = set()
    for h in face_holes_list:
        x, y = h['x'], h['y']
        diam_str = h.get('diam_str', '⌀8')
        try: r = float(re.findall(r"[\d\.]+", diam_str)[0])/2
        except: r = 4.0
        
        is_vis = (h['type'] == 'vis')
        fill = "black" if is_vis else "white"
        fig.add_shape(type="circle", x0=x-r, y0=y-r, x1=x+r, y1=y+r, line_color="black", fillcolor=fill, layer="above")
        if "/" not in diam_str:
            fig.add_shape(type="line", x0=x-r, y0=y-r, x1=x+r, y1=y+r, line_color="black", line_width=0.5, layer="above")
            fig.add_shape(type="line", x0=x-r, y0=y+r, x1=x+r, y1=y-r, line_color="black", line_width=0.5, layer="above")
        
        k = f"{h['type']}_{diam_str}"
        if k not in seen_t:
            fig.add_annotation(
                x=x, y=y, text=diam_str, showarrow=False, xanchor="left", yanchor="bottom", 
                xshift=r+2, yshift=r+2, font=dict(size=9*legend_scale, color="black")
            )
            seen_t.add(k)

    # --- 6. COTATION DES TROUS SUR TRANCHES ---
    seen_tr_t = set()
    tx_tour, ty_tour = [], []
    tx_vis, ty_vis = [], []
    
    # On passe legend_scale aux fonctions de cote
    dim_edge_offset = 60 * legend_scale

    if tranche_cote_holes_list:
        off = tranche_visual_thickness/2
        unique_y_edge = sorted(list(set(h['y'] for h in tranche_cote_holes_list)))
        for y_pos in unique_y_edge:
            add_pro_dimension(fig, tg_x1, 0, tg_x1, y_pos, f"{y_pos:.0f}", -dim_edge_offset, axis='y', text_scale=legend_scale)
            add_pro_dimension(fig, td_x1, 0, td_x1, y_pos, f"{y_pos:.0f}", dim_edge_offset, axis='y', text_scale=legend_scale)

        for h in tranche_cote_holes_list:
            gx, gy = tg_x0 - off, h['y']
            dx, dy = td_x0 + off, h['y']
            if h['type'] == 'vis':
                tx_vis.extend([gx, dx])
                ty_vis.extend([gy, dy])
            else:
                tx_tour.extend([gx, dx])
                ty_tour.extend([gy, dy])
            
            diam = h.get('diam_str', '⌀8')
            k = f"T_{diam}"
            if k not in seen_tr_t:
                fig.add_annotation(x=gx-10, y=h['y'], text=diam, showarrow=False, font=dict(size=9*legend_scale))
                seen_tr_t.add(k)
    
    # Gestion des trous sur chants longs (manquant dans le code envoyé mais ajouté par sécurité si besoin)
    if tranche_longue_holes_list:
        off = tranche_visual_thickness/2
        unique_x_edge = sorted(list(set(h['x'] for h in tranche_longue_holes_list)))
        for x_pos in unique_x_edge:
            add_pro_dimension(fig, 0, tb_y1, x_pos, tb_y1, f"{x_pos:.0f}", -dim_edge_offset, axis='x', text_scale=legend_scale)
            add_pro_dimension(fig, 0, th_y1, x_pos, th_y1, f"{x_pos:.0f}", dim_edge_offset, axis='x', text_scale=legend_scale)

        for h in tranche_longue_holes_list:
            bx, by = h['x'], tb_y0 - off
            hx_pos, hy_pos = h['x'], th_y0 + off
            if h['type'] == 'vis':
                tx_vis.extend([bx, hx_pos])
                ty_vis.extend([by, hy_pos])
            else:
                tx_tour.extend([bx, hx_pos])
                ty_tour.extend([by, hy_pos])
            
            diam = h.get('diam_str', '⌀8')
            k = f"TL_{diam}"
            if k not in seen_tr_t:
                fig.add_annotation(x=h['x'], y=by-10, text=diam, showarrow=False, font=dict(size=9*legend_scale))
                seen_tr_t.add(k)

    if tx_tour:
        fig.add_trace(go.Scatter(x=tx_tour, y=ty_tour, mode='markers', marker=dict(color='white', size=8*legend_scale, line=dict(width=1, color='black')), showlegend=False, hoverinfo='none'))
    if tx_vis:
        fig.add_trace(go.Scatter(x=tx_vis, y=ty_vis, mode='markers', marker=dict(color='black', size=4*legend_scale), showlegend=False, hoverinfo='none'))

    # --- 7. CARTOUCHE DYNAMIQUE ---
    view_x_min = x_cote_W_line - (text_offset * 4)
    # On recalcule les bornes avec l'échelle
    view_x_max = max(L + dist_panel_to_tranche + tranche_visual_thickness + (50*legend_scale), L + margin)
    
    actual_width = view_x_max - view_x_min
    virtual_page_width = max(actual_width * 1.5, 1600 * legend_scale) # La largeur du cartouche suit aussi l'échelle
    c_w = virtual_page_width * 0.5 
    
    # HAUTEUR DU CARTOUCHE ADAPTÉE A LA GRANDEUR DE LA PIÈCE
    c_h = 80 * legend_scale
    
    lowest_y = min(tb_y1, -hole_dim_offset_2)
    c_y_top = lowest_y - (60 * legend_scale)
    
    c_x_left = (L / 2) - (c_w / 2)
    
    fig.add_shape(type="rect", x0=c_x_left, y0=c_y_top-c_h, x1=c_x_left+c_w, y1=c_y_top, line=dict(color=line_color, width=1), fillcolor="#f9f9f0", layer="below")
    
    if 'load_image_base64' in globals():
        logo = load_image_base64("logo.png")
        if logo:
            fig.add_layout_image(dict(source=logo, xref="x", yref="y", x=c_x_left + c_w - (50*legend_scale), y=c_y_top - c_h/2, sizex=80*legend_scale, sizey=60*legend_scale, xanchor="center", yanchor="middle", layer="above"))
    
    col_w = (c_w * 0.85) / 4.0
    for i in range(1, 5):
        lx = c_x_left + i*col_w
        fig.add_shape(type="line", x0=lx, y0=c_y_top-c_h, x1=lx, y1=c_y_top, line=dict(color=line_color, width=dim_line_width))

    yt = c_y_top - (c_h * 0.25)
    yv = c_y_top - (c_h * 0.65)
    
    # Textes avec tailles de police dynamiques
    font_title_sz = 11 * legend_scale
    font_val_sz = 12 * legend_scale
    
    texts = [("Projet", project_info['project_name']), ("Désignation", panel_name.replace(" (", "<br>(")), ("Quantité", str(project_info['quantity'])), ("Date", project_info['date'])]
    for i, (lbl, val) in enumerate(texts):
        px = c_x_left + (col_w * (i + 0.5))
        fig.add_annotation(x=px, y=yt, text=f"<b>{lbl}</b>", showarrow=False, font=dict(size=font_title_sz))
        fig.add_annotation(x=px, y=yv, text=val, showarrow=False, font=dict(size=font_val_sz))

    # Mise en page finale
    ymx = max(y_cote_L_line + text_offset + margin*0.1, y_dim_cut + text_offset if center_cutout_props else 0)
    ymi = c_y_top - c_h - (20 * legend_scale)
    xmi = min(x_cote_W_line - (text_offset * 4), c_x_left)
    xmx = max(td_x1 + (margin*0.2), c_x_left + c_w)

    fig.update_layout(title=f"<b>Feuille d'usinage: {panel_name}</b>", height=750, xaxis=dict(visible=False, range=[xmi, xmx]), yaxis=dict(visible=False, range=[ymi, ymx], scaleanchor="x", scaleratio=1), margin=dict(l=10, r=10, t=50, b=10), showlegend=False, plot_bgcolor="white")
    return fig
