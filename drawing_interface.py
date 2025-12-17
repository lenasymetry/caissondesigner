import plotly.graph_objects as go
import numpy as np
import re
import base64
import os
import io

# --- GESTION ROBUSTE DES IMPORTS IMAGE ---
try:
    from PIL import Image
except ImportError:
    def load_image_base64(filename): return None

if 'Image' in locals():
    def load_image_base64(filename):
        candidates = [filename]
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(script_dir, filename))
        candidates.append(os.path.join(os.path.dirname(script_dir), filename))
        
        final_path = None
        for path in candidates:
            if os.path.exists(path):
                final_path = path
                break
        
        if not final_path:
            return None
            
        try:
            img = Image.open(final_path)
            output_buffer = io.BytesIO()
            img.save(output_buffer, format="PNG")
            encoded = base64.b64encode(output_buffer.getvalue()).decode()
            return f"data:image/png;base64,{encoded}"
        except Exception as e:
            print(f"Erreur chargement image: {e}")
            return None

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

def calculate_stagger_levels(coords, min_dist=45):
    if not coords: return []
    indices = np.argsort(coords)
    levels = [0] * len(coords)
    last_pos_at_level = {}
    for i in indices:
        val = coords[i]
        lvl = 0
        while True:
            last_val = last_pos_at_level.get(lvl, -99999)
            if (val - last_val) >= min_dist:
                levels[i] = lvl
                last_pos_at_level[lvl] = val
                break
            lvl += 1
    return levels

def add_pro_dimension(fig, x0, y0, x1, y1, text_val, offset_dist, axis='x', color="black", font_size=11, line_dash='solid', xanchor=None, yanchor=None):
    tick_len = 5
    line_width = 0.8
    ext_overshoot = 5
    text_font = dict(color="black", size=font_size, family="Arial") 
    text_bg = "white"

    if xanchor is None: xanchor = 'center'
    if yanchor is None: yanchor = 'middle'

    if axis == 'x':
        y_dim = y0 + offset_dist if offset_dist != 0 else y0
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x0, y1=y_dim + (np.sign(offset_dist)*ext_overshoot), line=dict(color=color, width=0.5, dash=line_dash))
        fig.add_shape(type="line", x0=x1, y0=y1, x1=x1, y1=y_dim + (np.sign(offset_dist)*ext_overshoot), line=dict(color=color, width=0.5, dash=line_dash))
        fig.add_shape(type="line", x0=x0, y0=y_dim, x1=x1, y1=y_dim, line=dict(color=color, width=line_width, dash=line_dash))
        fig.add_shape(type="line", x0=x0, y0=y_dim-tick_len, x1=x0, y1=y_dim+tick_len, line=dict(color=color, width=1.2, dash='solid'))
        fig.add_shape(type="line", x0=x1, y0=y_dim-tick_len, x1=x1, y1=y_dim+tick_len, line=dict(color=color, width=1.2, dash='solid'))
        text_y_pos = y_dim + (np.sign(offset_dist) * 15)
        fig.add_annotation(x=(x0+x1)/2, y=text_y_pos, text=str(text_val), showarrow=False, font=text_font, bgcolor=text_bg, yanchor=yanchor, xanchor=xanchor)
        
    elif axis == 'y':
        x_dim = x0 + offset_dist
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x_dim + (np.sign(offset_dist)*ext_overshoot), y1=y0, line=dict(color=color, width=0.5, dash=line_dash))
        fig.add_shape(type="line", x0=x1, y0=y1, x1=x_dim + (np.sign(offset_dist)*ext_overshoot), y1=y1, line=dict(color=color, width=0.5, dash=line_dash))
        fig.add_shape(type="line", x0=x_dim, y0=y0, x1=x_dim, y1=y1, line=dict(color=color, width=line_width, dash=line_dash))
        fig.add_shape(type="line", x0=x_dim-tick_len, y0=y0, x1=x_dim+tick_len, y1=y0, line=dict(color=color, width=1.2, dash='solid'))
        fig.add_shape(type="line", x0=x_dim-tick_len, y0=y1, x1=x_dim+tick_len, y1=y1, line=dict(color=color, width=1.2, dash='solid'))
        text_x_pos = x_dim + (np.sign(offset_dist) * 15)
        fig.add_annotation(x=text_x_pos, y=(y0+y1)/2, text=str(text_val), showarrow=False, textangle=-90, font=text_font, bgcolor=text_bg, xanchor=xanchor, yanchor=yanchor)

def check_label_overlap(new_pos, existing_positions, min_dist=35):
    nx, ny = new_pos
    for ex, ey in existing_positions:
        dist = ((nx - ex)**2 + (ny - ey)**2)**0.5
        if dist < min_dist: return True
    return False

def get_smart_label_pos(cx, cy, r, existing_labels):
    candidates = [(30, -30), (30, 30), (-30, 30), (-30, -30), (50, -50), (50, 50), (-50, 50)]
    for ax, ay in candidates:
        test_pos = (cx + ax, cy - ay)
        if not check_label_overlap(test_pos, existing_labels):
            return ax, ay, test_pos
    return 30, -30, (cx+30, cy+30)

def group_holes_for_dimensioning(y_vals):
    if not y_vals: return []
    y_vals = [round(y, 1) for y in y_vals]
    sorted_y = sorted(list(set(y_vals)))
    if not sorted_y: return []
    
    groups = []
    current_group = [sorted_y[0]]
    for i in range(1, len(sorted_y)):
        y = sorted_y[i]
        prev = current_group[-1]
        diff = y - prev
        if 31.0 < diff < 33.0:
            current_group.append(y)
        else:
            groups.append(current_group)
            current_group = [y]
    groups.append(current_group)
    
    result = []
    for grp in groups:
        if len(grp) >= 2: result.append({'start': grp[0], 'end': grp[-1], 'count': len(grp), 'type': 'rack'})
        else: result.append({'start': grp[0], 'end': grp[0], 'count': 1, 'type': 'single'})
    return result

def draw_machining_view_pro_final(panel_name, L, W, T, unit_str, project_info, 
                                 chants, face_holes_list=[], tranche_longue_holes_list=[], 
                                 tranche_cote_holes_list=[], center_cutout_props=None):
    fig = go.Figure()
    
    line_color = "black"
    dim_line_color = "black"
    HATCH_COLOR = "rgba(100, 100, 100, 0.5)"
    HATCH_SPACING = 20.0
    MARGIN_DIMS = 120.0 
    TRANCHE_THICK = max(T * 1.5, 30.0)
    
    bounds_x = [0, L]
    bounds_y = [0, W]
    
    # --- DESSIN PANNEAU ---
    fig.add_shape(type="rect", x0=0, y0=0, x1=L, y1=W, line=dict(color=line_color, width=1.5), fillcolor="white", layer="below")
    
    # --- TRANCHES ---
    def draw_tranche(tx, ty, hatch_key):
        fig.add_trace(go.Scatter(x=tx, y=ty, fill="toself", fillcolor="#f9f9f9", line=dict(color=line_color, width=1), hoverinfo="none", showlegend=False, mode='lines'))
        if chants.get(hatch_key):
            hx, hy = create_hatch_lines(min(tx), min(ty), max(tx), max(ty), density=HATCH_SPACING)
            fig.add_trace(go.Scatter(x=hx, y=hy, mode='lines', line=dict(color=HATCH_COLOR, width=1), hoverinfo='skip', showlegend=False))

    y_tb_0, y_tb_1 = -MARGIN_DIMS, -MARGIN_DIMS - TRANCHE_THICK
    y_th_0, y_th_1 = W + MARGIN_DIMS, W + MARGIN_DIMS + TRANCHE_THICK
    x_tg_0, x_tg_1 = -MARGIN_DIMS, -MARGIN_DIMS - TRANCHE_THICK
    x_td_0, x_td_1 = L + MARGIN_DIMS, L + MARGIN_DIMS + TRANCHE_THICK
    
    draw_tranche([0, L, L, 0, 0], [y_tb_0, y_tb_0, y_tb_1, y_tb_1, y_tb_0], "Chant Avant")
    draw_tranche([0, L, L, 0, 0], [y_th_0, y_th_0, y_th_1, y_th_1, y_th_0], "Chant Arrière")
    draw_tranche([x_tg_0, x_tg_1, x_tg_1, x_tg_0, x_tg_0], [0, 0, W, W, 0], "Chant Gauche")
    draw_tranche([x_td_0, x_td_1, x_td_1, x_td_0, x_td_0], [0, 0, W, W, 0], "Chant Droit")
    
    bounds_y.extend([y_tb_1, y_th_1])
    bounds_x.extend([x_tg_1, x_td_1])

    # --- COTES GLOBALES ---
    add_pro_dimension(fig, L+20, y_tb_0, L+20, y_tb_1, f"{T:.0f}", 20, axis='y', xanchor='center', yanchor='middle')
    add_pro_dimension(fig, L+20, y_th_0, L+20, y_th_1, f"{T:.0f}", 20, axis='y', xanchor='center', yanchor='middle')
    add_pro_dimension(fig, x_tg_0, W+20, x_tg_1, W+20, f"{T:.0f}", 20, axis='x', xanchor='center', yanchor='middle')
    add_pro_dimension(fig, x_td_0, W+20, x_td_1, W+20, f"{T:.0f}", 20, axis='x', xanchor='center', yanchor='middle')
    
    dist_global = MARGIN_DIMS + TRANCHE_THICK + 50
    add_pro_dimension(fig, 0, W, L, W, f"{L:.0f}", dist_global, axis='x', font_size=14, yanchor='bottom')
    add_pro_dimension(fig, 0, 0, 0, W, f"{W:.0f}", -dist_global, axis='y', font_size=14, xanchor='right')
    
    bounds_x.append(-dist_global - 50)
    bounds_y.append(W + dist_global + 50)

    # --- DÉCOUPES ---
    if center_cutout_props:
        cW, cH = center_cutout_props['width'], center_cutout_props['height']
        cOff = center_cutout_props['offset_top']
        x0, x1 = (L-cW)/2, (L-cW)/2 + cW
        y1, y0 = W-cOff, W-cOff-cH
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color="black", width=1, dash="dash"), layer="above")
        add_pro_dimension(fig, x0, y1, x1, y1, f"{cW:.0f}", -30, axis='x')
        add_pro_dimension(fig, x0, y0, x0, y1, f"{cH:.0f}", -30, axis='y')

    # --- COTATION INTELLIGENTE (Y: UNIQUE GAUCHE / X: STAGGERED BAS) ---
    if face_holes_list:
        # 1. COTES Y (Gauche) - Fusion Totale (Pas de doublon)
        # On regroupe TOUS les Y de la face en une seule liste unique
        all_y_raw = sorted(list(set([round(h['y'], 1) for h in face_holes_list])))
        groups = group_holes_for_dimensioning(all_y_raw)
        
        x_dim_base = -40 
        prev_end = 0
        
        for grp in groups:
            dist_gap = grp['start'] - prev_end
            # On trace l'écart depuis le dernier point
            if dist_gap > 1.0:
                add_pro_dimension(fig, x_dim_base, prev_end, x_dim_base, grp['start'], f"{dist_gap:.0f}", -10, axis='y', line_dash='dot')
            
            if grp['type'] == 'rack':
                span = grp['end'] - grp['start']
                nb_inter = grp['count'] - 1
                label = f"{nb_inter}x 32 = {span:.0f}"
                add_pro_dimension(fig, x_dim_base, grp['start'], x_dim_base, grp['end'], label, -10, axis='y', line_dash='dot')
                prev_end = grp['end']
            else:
                prev_end = grp['start']
        
        bounds_x.append(x_dim_base - 20)

        # 2. COTES X (Bas - Anti-Chevauchement)
        unique_x = sorted(list(set([round(h['x'], 1) for h in face_holes_list])))
        y_dim_base = -40
        x_levels = calculate_stagger_levels(unique_x, min_dist=45)
        
        fig.add_shape(type="line", x0=0, y0=y_dim_base, x1=L, y1=y_dim_base, line=dict(color="black", width=0.5))
        
        for i, x_pos in enumerate(unique_x):
            fig.add_shape(type="line", x0=x_pos, y0=0, x1=x_pos, y1=y_dim_base, line=dict(color="black", width=0.5, dash='dot'))
            fig.add_shape(type="line", x0=x_pos, y0=y_dim_base-3, x1=x_pos, y1=y_dim_base+3, line=dict(color="black", width=1.2))
            lvl = x_levels[i]
            text_y = y_dim_base - 15 - (lvl * 20)
            fig.add_annotation(x=x_pos, y=text_y, text=f"{x_pos:.0f}", showarrow=False, font=dict(size=10, color="black"), xanchor="center", yanchor="middle")
            bounds_y.append(text_y)

    # --- DESSIN DES TROUS ---
    annotated_types = set()
    existing_labels = [] 
    for h in face_holes_list:
        x, y = h['x'], h['y']
        diam_str = h.get('diam_str', '⌀8')
        r = 4.0
        try: r = float(re.findall(r"[\d\.]+", diam_str)[0])/2
        except: pass
        fill = "black" if h['type']=='vis' else "white"
        fig.add_shape(type="circle", x0=x-r, y0=y-r, x1=x+r, y1=y+r, line_color="black", fillcolor=fill, layer="above")
        
        type_key = f"{h['type']}_{diam_str}"
        if type_key not in annotated_types:
            ax, ay, final_pos = get_smart_label_pos(x, y, r, existing_labels)
            # FLÈCHE PLUS FINE (arrowwidth=1)
            fig.add_annotation(x=x, y=y, text=f"<b>{diam_str}</b>", showarrow=True, arrowwidth=1, arrowhead=2, ax=ax, ay=ay, font=dict(size=12, color="black"), bgcolor="white", bordercolor="black")
            annotated_types.add(type_key)
            existing_labels.append(final_pos)

    # --- COTES TRANCHES ---
    if tranche_cote_holes_list:
        y_locs = sorted(list(set([round(h['y'], 1) for h in tranche_cote_holes_list])))
        prev_y = 0
        for y_pos in y_locs:
            dist = y_pos - prev_y
            if dist > 0:
                add_pro_dimension(fig, x_td_1, prev_y, x_td_1, y_pos, f"{dist:.0f}", 40, axis='y', line_dash='dot')
            prev_y = y_pos
        for h in tranche_cote_holes_list:
            gx, dx = x_tg_0 - TRANCHE_THICK/2, x_td_0 + TRANCHE_THICK/2
            fig.add_trace(go.Scatter(x=[gx, dx], y=[h['y'], h['y']], mode='markers', marker=dict(color='black', size=4), showlegend=False))

    # --- CARTOUCHE PAPER SPACE ---
    CART_Y_MIN = 0.01
    CART_Y_MAX = 0.09 
    CART_BG_COLOR = "#f9f9f0"
    LINE_COLOR = "black"
    
    fig.add_shape(type="rect", xref="paper", yref="paper", x0=0.05, x1=0.95, y0=CART_Y_MIN, y1=CART_Y_MAX, line=dict(color=LINE_COLOR, width=1), fillcolor=CART_BG_COLOR, layer="below")
    
    col_pcts = [0.2, 0.5, 0.7, 0.85]
    for pct in col_pcts:
        x_pos = 0.05 + (0.90 * pct)
        fig.add_shape(type="line", xref="paper", yref="paper", x0=x_pos, x1=x_pos, y0=CART_Y_MIN, y1=CART_Y_MAX, line=dict(color=LINE_COLOR, width=0.5))
    
    def add_paper_txt(pct_center, title, val):
        x_c = 0.05 + (0.90 * pct_center)
        y_center = (CART_Y_MIN + CART_Y_MAX) / 2
        y_title = y_center + 0.015
        y_val = y_center - 0.015
        fig.add_annotation(xref="paper", yref="paper", x=x_c, y=y_title, text=f"<b>{title}</b>", showarrow=False, font=dict(size=11), xanchor="center", yanchor="middle")
        fig.add_annotation(xref="paper", yref="paper", x=x_c, y=y_val, text=str(val), showarrow=False, font=dict(size=13), xanchor="center", yanchor="middle")

    add_paper_txt(0.1, "Projet", project_info['project_name'])
    add_paper_txt(0.35, "Désignation", panel_name)
    add_paper_txt(0.6, "Quantité", project_info['quantity'])
    add_paper_txt(0.775, "Date", project_info['date'])
    
    logo_x_c = 0.05 + (0.90 * 0.925)
    logo_y_c = (CART_Y_MIN + CART_Y_MAX) / 2
    logo_file = "logo.png"
    logo_base64 = load_image_base64(logo_file)
    
    if logo_base64:
        fig.add_layout_image(dict(source=logo_base64, xref="paper", yref="paper", x=logo_x_c, y=logo_y_c, sizex=0.10, sizey=0.07, xanchor="center", yanchor="middle", layer="above"))
    else:
        fig.add_annotation(xref="paper", yref="paper", x=logo_x_c, y=logo_y_c, text="LOGO<br>MANQUANT", showarrow=False, font=dict(color="red", size=8), xanchor="center", yanchor="middle")

    margin_val = 50
    f_min_x, f_max_x = min(bounds_x) - 50, max(bounds_x) + 50
    f_min_y, f_max_y = min(bounds_y) - 50, max(bounds_y) + 50

    fig.update_layout(
        title=dict(text=f"FEUILLE D'USINAGE : {panel_name}", x=0.5, y=0.98),
        plot_bgcolor="white", paper_bgcolor="white",
        width=1123, height=794,
        margin=dict(l=margin_val, r=margin_val, t=50, b=30),
        xaxis=dict(visible=False, range=[f_min_x, f_max_x]),
        yaxis=dict(visible=False, range=[f_min_y, f_max_y], scaleanchor="x", scaleratio=1, domain=[0.10, 1.0]),
        showlegend=False
    )
    return fig
