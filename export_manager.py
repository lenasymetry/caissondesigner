import streamlit as st
import datetime
from io import BytesIO
from utils import calculate_hole_positions
from machining_logic import calculate_back_panel_holes, get_hinge_y_positions, get_mobile_shelf_holes
from drawing_interface import draw_machining_view_pro_final

def get_automatic_edge_banding_export(part_name):
    name = part_name.lower()
    if "etagère" in name or "etagere" in name: return True, False, False, False
    elif "fond" in name or "dos" in name:
        if "façade" in name or "face" in name: return True, True, True, True
        return False, False, False, False
    elif "traverse" in name: return True, True, False, False
    else: return True, True, True, True

def generate_stacked_html_plans(cabinets_to_process, indices_to_process):
    # CSS STRICT POUR A4 PAYSAGE
    full_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'>
    <title>Dossier Technique</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        @page { size: A4 landscape; margin: 0mm; }
        body { margin: 0; padding: 0; background-color: #eee; font-family: Arial, sans-serif; }
        .page-container {
            width: 297mm;
            height: 209mm; 
            background: white; 
            margin: 10mm auto; 
            position: relative; 
            overflow: hidden; 
            page-break-after: always;
            box-shadow: 0 0 10px rgba(0,0,0,0.2);
        }
        .graph-container { width: 100%; height: 100%; }
        @media print {
            body { background: white; }
            .page-container { box-shadow: none; margin: 0; width: 100%; height: 100%; page-break-after: always; }
        }
    </style>
</head>
<body>
"""
    
    project_name = st.session_state.project_name
    date_str = st.session_state.date_souhaitee.strftime("%d/%m/%Y")
    unit_str = st.session_state.unit_select
    
    plans_generated = 0
    
    for i, cabinet in enumerate(cabinets_to_process):
        if i not in indices_to_process: continue
        
        cab_idx = i
        dims = cabinet['dims']
        L_raw, W_raw, H_raw = dims['L_raw'], dims['W_raw'], dims['H_raw']
        t_lr, t_fb, t_tb = dims['t_lr_raw'], dims['t_fb_raw'], dims['t_tb_raw']
        
        W_mont = W_raw
        h_side = H_raw
        L_trav = L_raw - 2 * t_lr
        W_back = L_raw - 2.0
        H_back = H_raw - 2.0
        
        ys_vis, ys_dowel = calculate_hole_positions(W_raw)
        
        holes_mg = []
        holes_md = []
        
        # Trous structure
        for x in ys_vis:
            holes_mg.append({'type':'vis','x':x,'y':t_tb/2,'diam_str':"⌀3",'tag':'structure'})
            holes_mg.append({'type':'vis','x':x,'y':h_side-t_tb/2,'diam_str':"⌀3",'tag':'structure'})
            holes_md.append({'type':'vis','x':x,'y':t_tb/2,'diam_str':"⌀3",'tag':'structure'})
            holes_md.append({'type':'vis','x':x,'y':h_side-t_tb/2,'diam_str':"⌀3",'tag':'structure'})
        for x in ys_dowel:
            holes_mg.append({'type':'tourillon','x':x,'y':t_tb/2,'diam_str':"⌀8/20",'tag':'structure'})
            holes_mg.append({'type':'tourillon','x':x,'y':h_side-t_tb/2,'diam_str':"⌀8/20",'tag':'structure'})
            holes_md.append({'type':'tourillon','x':x,'y':t_tb/2,'diam_str':"⌀8/20",'tag':'structure'})
            holes_md.append({'type':'tourillon','x':x,'y':h_side-t_tb/2,'diam_str':"⌀8/20",'tag':'structure'})
            
        W_shelf_fixe = W_raw - 10.0
        ys_vis_sf, ys_dowel_sf = calculate_hole_positions(W_shelf_fixe)
        fixed_shelf_tr_draw = {}
        
        if 'shelves' in cabinet:
            for s_idx, s in enumerate(cabinet['shelves']):
                s_type = s.get('shelf_type', 'mobile')
                if s_type == 'fixe':
                    yc_val = t_tb + s['height'] + s['thickness']/2.0 
                    for x in ys_vis_sf: holes_mg.append({'type':'vis','x':x+10.0,'y':yc_val,'diam_str':"⌀3", 'tag':'structure'})
                    for x in ys_dowel_sf: holes_mg.append({'type':'tourillon','x':x+10.0,'y':yc_val,'diam_str':"⌀8/20", 'tag':'structure'})
                    for x in ys_vis_sf: holes_md.append({'type':'vis','x':x,'y':yc_val,'diam_str':"⌀3", 'tag':'structure'})
                    for x in ys_dowel_sf: holes_md.append({'type':'tourillon','x':x,'y':yc_val,'diam_str':"⌀8/20", 'tag':'structure'})
                    
                    tr = []
                    for x in ys_vis_sf: tr.append({'type':'vis','x':s['thickness']/2,'y':x,'diam_str':"⌀3"})
                    for x in ys_dowel_sf: tr.append({'type':'tourillon','x':s['thickness']/2,'y':x,'diam_str':"⌀8/20"})
                    fixed_shelf_tr_draw[s_idx] = tr
                else:
                    holes_mg.extend(get_mobile_shelf_holes(h_side, t_tb, s, W_mont))
                    holes_md.extend(get_mobile_shelf_holes(h_side, t_tb, s, W_mont))
                    
        if cabinet['door_props']['has_door']:
             yh = get_hinge_y_positions(h_side)
             for y in yh: 
                 if cabinet['door_props']['door_opening']=='left': 
                     holes_mg.append({'type':'vis','x':20.0,'y':y,'diam_str':"⌀5/11.5", 'tag':'slide'})
                     holes_mg.append({'type':'vis','x':52.0,'y':y,'diam_str':"⌀5/11.5", 'tag':'slide'})
                 else: 
                     holes_md.append({'type':'vis','x':20.0,'y':y,'diam_str':"⌀5/11.5", 'tag':'slide'})
                     holes_md.append({'type':'vis','x':52.0,'y':y,'diam_str':"⌀5/11.5", 'tag':'slide'})

        # --- NOUVEAU : TROUS DE COULISSES EXPORT ---
        if cabinet['drawer_props']['has_drawer']:
            drp = cabinet['drawer_props']
            tech_type = drp.get('drawer_tech_type', 'K')
            
            y_slide = t_tb + 33.0 + drp['drawer_bottom_offset']
            x_slide_holes = []
            wr = W_raw
            
            if wr > 643:
                x_slide_holes = [19, 37, 133, 261, 293, 389, 421, 549]
            else:
                if tech_type == 'N':
                    if 403 < wr < 452: x_slide_holes = [19, 37, 133, 165, 229, 325]
                    elif 453 < wr < 502: x_slide_holes = [19, 37, 133, 165, 261, 357]
                    elif 503 < wr < 552: x_slide_holes = [19, 37, 133, 261, 293, 453]
                    elif 553 < wr < 602: x_slide_holes = [19, 37, 133, 261, 293, 453]
                
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
                holes_mg.append({'type': 'vis', 'x': x_s, 'y': y_slide, 'diam_str': "⌀5/12", 'tag':'slide'})
                holes_md.append({'type': 'vis', 'x': W_mont - x_s, 'y': y_slide, 'diam_str': "⌀5/12", 'tag':'slide'})

        plans = []
        
        # Structure Tuples: (Title, L, W, T, Chants, FaceHoles, TrancheCoteHoles, Cutout)
        tholes = [{'type':'tourillon','x':t_tb/2,'y':y,'diam_str':"⌀8/20"} for y in ys_dowel]
        c_trav = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":False, "Chant Droit":False}
        plans.append(("Traverse Bas (Tb)", L_trav, W_mont, t_tb, c_trav, [], tholes, None))
        plans.append(("Traverse Haut (Th)", L_trav, W_mont, t_tb, c_trav, [], tholes, None))
        
        c_mont = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":True, "Chant Droit":True}
        plans.append(("Montant Gauche (Mg)", W_mont, h_side, t_lr, c_mont, holes_mg, [], None))
        plans.append(("Montant Droit (Md)", W_mont, h_side, t_lr, c_mont, holes_md, [], None))
        
        c_fond = {"Chant Avant":False, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
        plans.append(("Panneau Arrière (F)", W_back, H_back, t_fb, c_fond, calculate_back_panel_holes(W_back, H_back), [], None))
        
        if cabinet['door_props']['has_door']:
            dp = cabinet['door_props']
            dH = H_raw + st.session_state.foot_height - dp['door_gap'] - 10.0 if dp.get('door_model')=='floor_length' else H_raw - (2 * dp['door_gap'])
            dW = L_raw - (2 * dp['door_gap'])
            y_h = get_hinge_y_positions(dH)
            holes_p = []
            xc = 23.5 if dp['door_opening']=='left' else dW-23.5
            xv = 33.0 if dp['door_opening']=='left' else dW-33.0
            for y in y_h: 
                holes_p.append({'type':'tourillon','x':xc,'y':y,'diam_str':"⌀35"})
                holes_p.append({'type':'vis','x':xv,'y':y+22.5,'diam_str':"⌀8"})
                holes_p.append({'type':'vis','x':xv,'y':y-22.5,'diam_str':"⌀8"})
            
            c_p = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":True, "Chant Droit":True}
            plans.append((f"Porte (C{cab_idx})", dW, dH, dp['door_thickness'], c_p, holes_p, [], None))

        if cabinet['drawer_props']['has_drawer']:
            drp = cabinet['drawer_props']
            tech_type = drp.get('drawer_tech_type', 'K')
            
            dr_H = drp['drawer_face_H_raw']
            dr_L = L_raw - (2 * drp['drawer_gap'])
            f_holes = []
            
            face_coords_map = {'K': [47.5, 79.5, 111.5], 'M': [47.5, 79.5], 'N': [32.5, 64.5], 'D': [47.5, 79.5, 207.5]}
            y_coords_face = face_coords_map.get(tech_type, [47.5, 79.5, 111.5])
            
            for y in y_coords_face:
                if y < dr_H:
                    f_holes.append({'type': 'tourillon', 'x': 32.5, 'y': y, 'diam_str': "⌀10/12"})
                    f_holes.append({'type': 'tourillon', 'x': dr_L - 32.5, 'y': y, 'diam_str': "⌀10/12"})
            
            c_tf = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":True, "Chant Droit":True}
            cutout = {'width': drp.get('drawer_handle_width', 150.0), 'height': drp.get('drawer_handle_height', 40.0), 'offset_top': drp.get('drawer_handle_offset_top', 10.0)} if drp.get('drawer_handle_type') == 'integrated_cutout' else None
            plans.append((f"Tiroir-Face (C{cab_idx}) [Type {tech_type}]", dr_L, dr_H, drp.get('drawer_face_thickness', 19.0), c_tf, f_holes, [], cutout))
            
            back_height_map = {'N': 69.0, 'M': 84.0, 'K': 116.0, 'D': 199.0}
            fixed_back_h = back_height_map.get(tech_type, 116.0)
            d_L_t = (L_raw - 2*t_lr) - 49.0
            
            d_holes_t = []
            back_coords_map = {'K': [30.0, 62.0, 94.0], 'M': [32.0, 64.0], 'N': [31.0, 47.0], 'D': [31.0, 63.0, 95.0, 159.0, 191.0]}
            y_coords_back = back_coords_map.get(tech_type, [30.0, 62.0, 94.0])
            
            for dy in y_coords_back:
                d_holes_t.append({'type': 'vis', 'x': 9.0, 'y': dy, 'diam_str': "⌀2.5/3"})
                d_holes_t.append({'type': 'vis', 'x': d_L_t - 9.0, 'y': dy, 'diam_str': "⌀2.5/3"})
            
            c_td = {"Chant Avant":False, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
            plans.append((f"Tiroir-Dos (C{cab_idx}) [Type {tech_type}]", d_L_t, fixed_back_h, 16.0, c_td, d_holes_t, [], None))
            plans.append((f"Tiroir-Fond (C{cab_idx})", d_L_t, W_raw - (20.0 + t_fb), 16.0, c_td, [], [], None))

        if 'shelves' in cabinet:
            for s_idx, s in enumerate(cabinet['shelves']):
                sl, sw = (L_raw - 2*t_lr, W_raw - 10.0)
                trh = fixed_shelf_tr_draw.get(s_idx, []) if s.get('shelf_type') == 'fixe' else []
                c_eta = {"Chant Avant":True, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
                plans.append((f"Etagère {s_idx+1} ({s.get('shelf_type','mobile')})", sl, sw, s['thickness'], c_eta, [], trh, None))

        for title, Lp, Wp, Tp, ch, fh, tch, cut in plans:
            proj = {"project_name": project_name, "quantity": 1, "date": date_str}
            fig = draw_machining_view_pro_final(title, Lp, Wp, Tp, unit_str, proj, ch, fh, [], tch, cut)
            plot_html = fig.to_html(full_html=False, include_plotlyjs=False, config={'displayModeBar': False})
            full_html += f"""
            <div class="page-container">
                <div class="graph-container">
                    {plot_html}
                </div>
            </div>
            """
            plans_generated += 1

    full_html += "</body></html>"
    return full_html.encode('utf-8'), True
