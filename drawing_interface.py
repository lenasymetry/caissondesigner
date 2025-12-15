# Contenu de drawing_interface.py
import plotly.graph_objects as go
import numpy as np
import re
import base64
import os
import io

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

def create_hatch_lines(x0, y0, x1, y1, density=20):
    """Génère des lignes diagonales épaisses sans dépasser du cadre."""
    lines_x, lines_y = [], []
    xmin, xmax = min(x0, x1), max(x0, x1)
    ymin, ymax = min(y0, y1), max(y0, y1)
    
    # Equation y = x + c
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

def draw_machining_view_pro_final(panel_name, L, W, T, unit_str, project_info, 
                                 chants, face_holes_list=[], tranche_longue_holes_list=[], 
                                 tranche_cote_holes_list=[], center_cutout_props=None):
    fig = go.Figure()
    
    # --- CONFIGURATION VISUELLE ---
    line_color, dim_line_color = "black", "#4a4a4a"
    line_width, dim_line_width = 1, 0.5
    
    # Hachures : Gris foncé, Epaisseur 2px
    HATCH_COLOR = "rgba(80, 80, 80, 0.8)" 
    HATCH_WIDTH_PX = 2 
    
    # ESPACEMENT DYNAMIQUE (CALIBRÉ POUR VISUEL A4)
    # On prend la plus grande dimension et on divise pour avoir environ 40-50 lignes max
    # Minimum 20mm pour éviter la densité excessive sur les petites pièces
    HATCH_SPACING = max(max(L, W) / 40, 20.0)

    margin = max(L, W) * 0.25 
    if margin < 100: margin = 100
    text_offset = margin * 0.05
    dim_level_offsets = [margin * 0.2, margin * 0.3]
    dim_offset_global = margin * 0.5 
    ext_line_overshoot = margin * 0.1 
    tranche_visual_thickness = T * 2
    if tranche_visual_thickness < 15: tranche_visual_thickness = 15
    
    # 1. Panneau Central
    fig.add_shape(type="rect", x0=0, y0=0, x1=L, y1=W, line=dict(color=line_color, width=line_width), fillcolor="white", layer="below")
    
    # 2. Tranches (Cadres + Hachures conditionnelles)
    
    # --- Tranche Bas (Avant) ---
    tb_y0 = -dim_offset_global
    tb_y1 = tb_y0 - tranche_visual_thickness
    fig.add_trace(go.Scatter(x=[0, L, L, 0, 0], y=[tb_y0, tb_y0, tb_y1, tb_y1, tb_y0], fill="toself", fillcolor="#f0f0f0", line=dict(color=line_color, width=line_width), hoverinfo="none", showlegend=False, mode='lines'))
    
    if chants.get("Chant Avant"):
        hx, hy = create_hatch_lines(0, tb_y0, L, tb_y1, density=HATCH_SPACING)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=HATCH_WIDTH_PX), hoverinfo='skip', showlegend=False))

    # --- Tranche Haut (Arrière) ---
    y_cote_L = W + dim_offset_global
    th_y0 = y_cote_L + text_offset + margin*0.1
    th_y1 = th_y0 + tranche_visual_thickness
    fig.add_trace(go.Scatter(x=[0, L, L, 0, 0], y=[th_y0, th_y0, th_y1, th_y1, th_y0], fill="toself", fillcolor="#f0f0f0", line=dict(color=line_color, width=line_width), hoverinfo="none", showlegend=False, mode='lines'))
    
    if chants.get("Chant Arrière"):
        hx, hy = create_hatch_lines(0, th_y0, L, th_y1, density=HATCH_SPACING)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=HATCH_WIDTH_PX), hoverinfo='skip', showlegend=False))

    # --- Tranche Gauche ---
    x_cote_W = -dim_offset_global
    tg_x0 = x_cote_W
    tg_x1 = tg_x0 - tranche_visual_thickness
    fig.add_trace(go.Scatter(x=[tg_x0, tg_x1, tg_x1, tg_x0, tg_x0], y=[0, 0, W, W, 0], fill="toself", fillcolor="#f0f0f0", line=dict(color=line_color, width=line_width), hoverinfo="none", showlegend=False, mode='lines'))
    
    if chants.get("Chant Gauche"):
        hx, hy = create_hatch_lines(tg_x0, 0, tg_x1, W, density=HATCH_SPACING)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=HATCH_WIDTH_PX), hoverinfo='skip', showlegend=False))

    # --- Tranche Droite ---
    td_x0 = L + margin*0.5
    td_x1 = td_x0 + tranche_visual_thickness
    fig.add_trace(go.Scatter(x=[td_x0, td_x1, td_x1, td_x0, td_x0], y=[0, 0, W, W, 0], fill="toself", fillcolor="#f0f0f0", line=dict(color=line_color, width=line_width), hoverinfo="none", showlegend=False, mode='lines'))
    
    if chants.get("Chant Droit"):
        hx, hy = create_hatch_lines(td_x0, 0, td_x1, W, density=HATCH_SPACING)
        fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=HATCH_WIDTH_PX), hoverinfo='skip', showlegend=False))

    # 3. Cotes (Identique)
    cx = L + margin*0.1
    fig.add_annotation(x=cx+text_offset, y=(tb_y0+tb_y1)/2, text=f"{T:.0f}", textangle=-90, showarrow=False, font=dict(color=line_color, size=12))
    fig.add_annotation(x=cx+text_offset, y=(th_y0+th_y1)/2, text=f"{T:.0f}", textangle=-90, showarrow=False, font=dict(color=line_color, size=12))
    fig.add_shape(type="line", x0=0, y0=W, x1=0, y1=y_cote_L + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=L, y0=W, x1=L, y1=y_cote_L + ext_line_overshoot, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=0, y0=y_cote_L, x1=L, y1=y_cote_L, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=L/2, y=y_cote_L + text_offset, text=f"{L:.0f}", showarrow=False, font=dict(color=line_color, size=12))
    
    fig.add_shape(type="line", x0=0, y0=0, x1=x_cote_W - ext_line_overshoot, y1=0, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=0, y0=W, x1=x_cote_W - ext_line_overshoot, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_shape(type="line", x0=x_cote_W, y0=0, x1=x_cote_W, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
    fig.add_annotation(x=x_cote_W - text_offset, y=W/2, text=f"{W:.0f}", textangle=-90, showarrow=False, font=dict(color=line_color, size=12))

    # 4. Trous et Découpes
    if center_cutout_props:
        cut_W, cut_H = center_cutout_props['width'], center_cutout_props['height']
        cut_off = center_cutout_props['offset_top']
        x0, x1 = (L-cut_W)/2, (L-cut_W)/2 + cut_W
        y1, y0 = W-cut_off, W-cut_off-cut_H
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=dim_line_color, width=1, dash="dash"), layer="above")
        y_dim_cut = y_cote_L + ext_line_overshoot
        fig.add_shape(type="line", x0=x0, y0=y1, x1=x0, y1=y_dim_cut, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x1, y0=y1, x1=x1, y1=y_dim_cut, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x0, y0=y_dim_cut-text_offset, x1=x1, y1=y_dim_cut-text_offset, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=L/2, y=y_dim_cut, text=f"{cut_W:.0f}", showarrow=False, font=dict(color=dim_line_color, size=10))
        x_dim_cut = x_cote_W - ext_line_overshoot
        fig.add_shape(type="line", x0=x0, y0=y1, x1=x_dim_cut, y1=y1, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x_dim_cut, y1=y0, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x_dim_cut+text_offset, y0=y0, x1=x_dim_cut+text_offset, y1=y1, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=x_dim_cut, y=(y0+y1)/2, text=f"{cut_H:.0f}", textangle=-90, showarrow=False, font=dict(color=dim_line_color, size=10))
        fig.add_shape(type="line", x0=x0, y0=W, x1=x_dim_cut, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_shape(type="line", x0=x_dim_cut-text_offset, y0=y1, x1=x_dim_cut-text_offset, y1=W, line=dict(color=dim_line_color, width=dim_line_width))
        fig.add_annotation(x=x_dim_cut-(2*text_offset), y=(y1+W)/2, text=f"{cut_offset:.0f}", textangle=-90, showarrow=False, font=dict(color=dim_line_color, size=10))

    # Trous Face
    if face_holes_list:
        y_coords = sorted(list(set(h['y'] for h in face_holes_list)))
        for i, y_pos in enumerate(y_coords):
            x_d = -dim_level_offsets[i%2]
            fig.add_shape(type="line", x0=x_d, y0=0, x1=x_d, y1=W, line=dict(color=dim_line_color, width=0.5, dash="dot"))
            fig.add_shape(type="line", x0=0, y0=y_pos, x1=x_d, y1=y_pos, line=dict(color=dim_line_color, width=0.5))
            fig.add_annotation(x=x_d-text_offset, y=y_pos, text=f"{y_pos:.0f}", showarrow=False, font=dict(size=10))
        
        x_coords = sorted(list(set(h['x'] for h in face_holes_list)))
        for i, x_pos in enumerate(x_coords):
            y_d = -dim_level_offsets[i%2]
            fig.add_shape(type="line", x0=0, y0=y_d, x1=L, y1=y_d, line=dict(color=dim_line_color, width=0.5, dash="dot"))
            fig.add_shape(type="line", x0=x_pos, y0=0, x1=x_pos, y1=y_d, line=dict(color=dim_line_color, width=0.5))
            fig.add_annotation(x=x_pos, y=y_d-text_offset, text=f"{x_pos:.0f}", showarrow=False, font=dict(size=10))

    seen_t = set()
    for h in face_holes_list:
        x, y = h['x'], h['y']
        diam_str = h.get('diam_str', '⌀8')
        is_through = "/" not in diam_str
        try: r = float(re.findall(r"[\d\.]+", diam_str)[0])/2
        except: r = 4.0
        fig.add_shape(type="circle", x0=x-r, y0=y-r, x1=x+r, y1=y+r, line_color="black", fillcolor="white", layer="above")
        if is_through:
            fig.add_shape(type="line", x0=x-r, y0=y-r, x1=x+r, y1=y+r, line_color="black", line_width=0.5, layer="above")
            fig.add_shape(type="line", x0=x-r, y0=y+r, x1=x+r, y1=y-r, line_color="black", line_width=0.5, layer="above")
        
        k = f"{h['type']}_{diam_str}"
        if k not in seen_t:
            fig.add_annotation(x=x+r, y=y+r, text=diam_str, showarrow=False, font=dict(size=8, color="gray"))
            seen_t.add(k)

    # Trous Tranches
    seen_tr_t = set()
    tx_tour, ty_tour = [], []
    tx_vis, ty_vis = [], []
    
    if tranche_cote_holes_list:
        off = tranche_visual_thickness/2
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
                fig.add_annotation(x=gx, y=h['y'], text=diam, xshift=-10, showarrow=False, font=dict(size=9))
                seen_tr_t.add(k)
    
    if tx_tour:
        fig.add_trace(go.Scatter(x=tx_tour, y=ty_tour, mode='markers', marker=dict(color='white', size=8, line=dict(width=1, color='black')), showlegend=False, hoverinfo='none'))
    if tx_vis:
        fig.add_trace(go.Scatter(x=tx_vis, y=ty_vis, mode='markers', marker=dict(color='black', size=4), showlegend=False, hoverinfo='none'))

    # 7. Cartouche
    c_h = margin * 0.8
    c_y = tb_y1 - (margin * 0.2)
    c_w = 700
    cx0 = (L - c_w)/2
    cx1 = cx0 + c_w
    
    fig.add_shape(type="rect", x0=cx0, y0=c_y-c_h, x1=cx1, y1=c_y, line=dict(color=line_color, width=1), fillcolor="#f9f9f0", layer="below")
    
    col_w = (c_w * 0.85) / 4.0
    logo_w = c_w * 0.15
    x_logo = cx0 + col_w * 4
    
    if 'load_image_base64' in globals():
        logo = load_image_base64("logo.png")
        if logo:
            fig.add_layout_image(dict(source=logo, xref="x", yref="y", x=x_logo + logo_w/2, y=c_y - c_h/2, sizex=logo_w*0.8, sizey=c_h*0.8, xanchor="center", yanchor="middle", layer="above"))
            
    for i in range(1, 5):
        lx = cx0 + i*col_w
        fig.add_shape(type="line", x0=lx, y0=c_y-c_h, x1=lx, y1=c_y, line=dict(color=line_color, width=dim_line_width))
        
    yt = c_y - (c_h * 0.25)
    yv = c_y - (c_h * 0.65)
    
    texts = [("Projet", project_info['project_name']), ("Désignation", panel_name.replace(" (", "<br>(")), ("Quantité", str(project_info['quantity'])), ("Date", project_info['date'])]
    for i, (lbl, val) in enumerate(texts):
        px = cx0 + (col_w * (i + 0.5))
        fig.add_annotation(x=px, y=yt, text=f"<b>{lbl}</b>", showarrow=False, font=dict(size=10))
        fig.add_annotation(x=px, y=yv, text=val, showarrow=False, font=dict(size=11))

    ymx = max(y_cote_L + text_offset + margin*0.1 + tranche_visual_thickness, y_dim_cut + text_offset if center_cutout_props else 0)
    ymi = min(tb_y1 - margin*0.2, c_y - c_h - margin*0.1, -dim_offset_global - (text_offset * 4))
    xmi = min(-dim_offset_global - (text_offset * 4), cx0, x_dim_cut - margin*0.1 if center_cutout_props else 0)
    xmx = max(td_x1 + (margin*0.2), cx1) + margin*0.1

    fig.update_layout(title=f"<b>Feuille d'usinage: {panel_name}</b>", height=750, xaxis=dict(visible=False, range=[xmi, xmx]), yaxis=dict(visible=False, range=[ymi, ymx], scaleanchor="x", scaleratio=1), margin=dict(l=10, r=10, t=50, b=10), showlegend=False, plot_bgcolor="white")
    return fig
