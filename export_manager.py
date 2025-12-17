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
            box-shadow: 0 0 10px rgba(0,0,0,0.2);
            page-break-after: always;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }
        @media print {
            body { background: white; }
            .page-container {
                margin: 0;
                box-shadow: none;
                width: 100%;
                height: 100vh;
            }
            .no-print { display: none; }
        }
    </style>
</head>
<body>
<div class="no-print" style="text-align:center; padding:20px;">
    <h1>Dossier Technique</h1>
    <p>Pour imprimer : CTRL+P > Destination "Enregistrer au format PDF" > Mise en page "Paysage" > Marges "Aucune"</p>
</div>
"""
    
    try:
        for i, cab in enumerate(cabinets_to_process):
            cab_idx = indices_to_process[i]
            dims = cab['dims']
            
            # Dimensions brutes (FLOAT EXPLICITE pour éviter le bug 100x100)
            L_raw = float(dims['L_raw'])
            W_raw = float(dims['W_raw'])
            H_raw = float(dims['H_raw'])
            t_lr = float(dims['t_lr_raw'])
            t_fb = float(dims['t_fb_raw'])
            t_tb = float(dims['t_tb_raw'])
            
            h_side = H_raw
            L_trav = L_raw - 2 * t_lr
            W_mont = W_raw
            W_back = L_raw - 2.0
            H_back = H_raw - 2.0
            
            ys_vis, ys_dowel = calculate_hole_positions(W_raw)
            holes_mg, holes_md = [], []
            
            # --- 1. STRUCTURE (Type: structure_*) ---
            for x in ys_vis:
                holes_mg.extend([{'type': 'structure_vis', 'x': x, 'y': t_tb/2, 'diam_str': "⌀3"}, {'type': 'structure_vis', 'x': x, 'y': h_side - t_tb/2, 'diam_str': "⌀3"}])
                holes_md.extend([{'type': 'structure_vis', 'x': x, 'y': t_tb/2, 'diam_str': "⌀3"}, {'type': 'structure_vis', 'x': x, 'y': h_side - t_tb/2, 'diam_str': "⌀3"}])
            for x in ys_dowel:
                holes_mg.extend([{'type': 'structure_tourillon', 'x': x, 'y': t_tb/2, 'diam_str': "⌀8/20"}, {'type': 'structure_tourillon', 'x': x, 'y': h_side - t_tb/2, 'diam_str': "⌀8/20"}])
                holes_md.extend([{'type': 'structure_tourillon', 'x': x, 'y': t_tb/2, 'diam_str': "⌀8/20"}, {'type': 'structure_tourillon', 'x': x, 'y': h_side - t_tb/2, 'diam_str': "⌀8/20"}])
            
            plans = []
            
            # --- 2. ÉTAGÈRES (Type: etagere_*) ---
            fixed_shelf_tr_draw = {} # Dictionnaire pour stocker les trous sur l'étagère elle-même
            
            if 'shelves' in cab:
                for s_idx, s in enumerate(cab['shelves']):
                    s_type = s.get('shelf_type', 'mobile')
                    s_th = float(s.get('thickness', 19.0))
                    
                    if s_type == 'fixe':
                        # Pour une étagère fixe, c'est la largeur INTERNE exacte
                        L_shelf = float(L_raw - (2 * t_lr))
                        y_c = t_tb + s['height'] + s_th/2.0
                        
                        # Trous sur les montants
                        W_shelf_fixe = W_raw - 10.0 # Standard retrait
                        ys_vis_sf, ys_dowel_sf = calculate_hole_positions(W_shelf_fixe)
                        
                        for x in ys_vis_sf: 
                            holes_mg.append({'type': 'etagere_fixe_vis', 'x': x+10.0, 'y': y_c, 'diam_str': "⌀3"})
                            holes_md.append({'type': 'etagere_fixe_vis', 'x': x, 'y': y_c, 'diam_str': "⌀3"})
                        for x in ys_dowel_sf:
                            holes_mg.append({'type': 'etagere_fixe_tourillon', 'x': x+10.0, 'y': y_c, 'diam_str': "⌀8/20"})
                            holes_md.append({'type': 'etagere_fixe_tourillon', 'x': x, 'y': y_c, 'diam_str': "⌀8/20"})
                            
                        # Trous sur la tranche de l'étagère (Stockage pour dessin plus bas)
                        tr = []
                        for x in ys_vis_sf: tr.append({'type':'vis','x':s_th/2,'y':x,'diam_str':"⌀3"})
                        for x in ys_dowel_sf: tr.append({'type':'tourillon','x':s_th/2,'y':x,'diam_str':"⌀8/20"})
                        
                        # Note: pour l'export HTML, on les passe directement au plan, pas via un dict global complexe
                        # On stocke temporairement
                        fixed_shelf_tr_draw[s_idx] = tr

                    else:
                        # Mobile : Jeu de 2mm total
                        L_shelf = float(L_raw - (2 * t_lr) - 2.0)
                        
                        # Trous taquets
                        h_mob = get_mobile_shelf_holes(h_side, t_tb, s, W_mont)
                        for h in h_mob: h['type'] = 'etagere_taquet' 
                        holes_mg.extend(h_mob)
                        
                        h_mob_d = get_mobile_shelf_holes(h_side, t_tb, s, W_mont)
                        for h in h_mob_d: h['type'] = 'etagere_taquet'
                        holes_md.extend(h_mob_d)
                    
                    # PLAN ÉTAGÈRE
                    W_shelf = float(W_raw - 10.0)
                    c_shelf = {"Chant Avant":True, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
                    
                    # Récupération des trous de tranche si fixe
                    th_shelf = fixed_shelf_tr_draw.get(s_idx, [])
                    
                    plans.append((f"Etagère {s_type.capitalize()} {s_idx+1} (C{cab_idx})", L_shelf, W_shelf, s_th, c_shelf, [], [], th_shelf, None))

            # --- 3. COULISSES (Type: coulisse_*) - MISE A JOUR LOGIQUE 2.PY ---
            if cab['drawer_props']['has_drawer']:
                drp = cab['drawer_props']
                tech_type = drp.get('drawer_tech_type', 'K')
                
                # Formule Y exacte du 2.py
                y_slide = t_tb + 33.0 + drp['drawer_bottom_offset']
                
                x_slide_holes = []
                wr = W_raw
                
                # Logique exacte copiée de 2.py
                if wr > 643:
                    x_slide_holes = [19, 37, 133, 261, 293, 389, 421, 549]
                else:
                    if tech_type == 'N':
                        if 403 < wr < 452: x_slide_holes = [19, 37, 133, 165, 229, 325]
                        elif 453 < wr < 502: x_slide_holes = [19, 37, 133, 165, 261, 357]
                        elif 503 < wr < 552: x_slide_holes = [19, 37, 133, 261, 293, 453]
                        elif 553 < wr < 602: x_slide_holes = [19, 37, 133, 261, 293, 453]
                    
                    if not x_slide_holes: # Default K, M, D or fallback N
                        if 273 < wr < 302: x_slide_holes = [19, 37, 133, 261]
                        elif 303 < wr < 352: x_slide_holes = [19, 37, 133, 165, 261]
                        elif 353 < wr < 402: x_slide_holes = [19, 37, 133, 165, 325]
                        elif 403 < wr < 452: x_slide_holes = [19, 37, 133, 165, 229, 325]
                        elif 453 < wr < 502: x_slide_holes = [19, 37, 133, 165, 261, 357]
                        elif 503 < wr < 552: x_slide_holes = [19, 37, 133, 261, 293, 453]
                        elif 553 < wr < 602: x_slide_holes = [19, 37, 133, 261, 293, 453]
                        elif 603 < wr < 652: x_slide_holes = [19, 37, 133, 261, 293, 325, 357, 517]

                for x_s in x_slide_holes:
                    # Montant Gauche
                    holes_mg.append({'type': 'coulisse_vis', 'x': x_s, 'y': y_slide, 'diam_str': "⌀5/12"})
                    # Montant Droit (Inversion X comme dans 2.py)
                    holes_md.append({'type': 'coulisse_vis', 'x': W_mont - x_s, 'y': y_slide, 'diam_str': "⌀5/12"})

            # --- 4. CHARNIÈRES (Type: charniere_*) ---
            if cab['door_props']['has_door']:
                dp = cab['door_props']
                # Calcul hauteur porte exact comme 2.py
                dH_door = H_raw + st.session_state.foot_height - dp['door_gap'] - 10.0 if dp.get('door_model')=='floor_length' else H_raw - (2 * dp['door_gap'])
                
                yh = get_hinge_y_positions(dH_door) # Utiliser la hauteur porte, pas caisson !
                
                if cab['door_props']['door_opening'] == 'left':
                    for y in yh: holes_mg.extend([{'type':'charniere_vis','x':37,'y':y+16,'diam_str':"⌀5"}, {'type':'charniere_vis','x':37,'y':y-16,'diam_str':"⌀5"}])
                else:
                    for y in yh: holes_md.extend([{'type':'charniere_vis','x':37,'y':y+16,'diam_str':"⌀5"}, {'type':'charniere_vis','x':37,'y':y-16,'diam_str':"⌀5"}])

            holes_fond = calculate_back_panel_holes(W_back, H_back)
            tholes = [{'type': 'structure_tourillon', 'x': t_tb/2, 'y': y, 'diam_str': "⌀8/20"} for y in ys_dowel]
            proj = {"project_name": st.session_state.project_name, "quantity": 1, "date": datetime.date.today().strftime("%d/%m/%Y")}
            
            cav_t, car_t, cg_t, cd_t = get_automatic_edge_banding_export("Traverse")
            c_trav = {"Chant Avant":cav_t, "Chant Arrière":car_t, "Chant Gauche":cg_t, "Chant Droit":cd_t}
            cav_m, car_m, cg_m, cd_m = get_automatic_edge_banding_export("Montant")
            c_mont = {"Chant Avant":cav_m, "Chant Arrière":car_m, "Chant Gauche":cg_m, "Chant Droit":cd_m}
            c_fond = {"Chant Avant":False, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
            
            plans.append(("Traverse Bas (Tb)", L_trav, W_mont, t_tb, c_trav, [], [], tholes, None))
            plans.append(("Traverse Haut (Th)", L_trav, W_mont, t_tb, c_trav, [], [], tholes, None))
            plans.append(("Montant Gauche (Mg)", W_mont, h_side, t_lr, c_mont, holes_mg, [], [], None))
            plans.append(("Montant Droit (Md)", W_mont, h_side, t_lr, c_mont, holes_md, [], [], None))
            plans.append(("Panneau Arrière (F)", W_back, H_back, t_fb, c_fond, holes_fond, [], [], None))

            # --- 5. TIROIR - MISE A JOUR LOGIQUE 2.PY ---
            if cab['drawer_props']['has_drawer']:
                drp = cab['drawer_props']
                tech_type = drp.get('drawer_tech_type', 'K')
                
                dr_L = L_raw - (2 * drp['drawer_gap'])
                dr_H = drp['drawer_face_H_raw']
                f_holes = []
                
                # Logique coordonnées Façade (copiée de 2.py)
                face_coords_map = {
                    'K': [47.5, 79.5, 111.5],
                    'M': [47.5, 79.5],
                    'N': [32.5, 64.5],
                    'D': [47.5, 79.5, 207.5]
                }
                y_coords_face = face_coords_map.get(tech_type, [47.5, 79.5, 111.5])

                for y in y_coords_face:
                    if y < dr_H:
                        f_holes.append({'type': 'tourillon_facade', 'x': 32.5, 'y': y, 'diam_str': "⌀10"})
                        f_holes.append({'type': 'tourillon_facade', 'x': dr_L - 32.5, 'y': y, 'diam_str': "⌀10"})
                
                cutout = None
                if drp.get('drawer_handle_type') == 'integrated_cutout':
                    cutout = {'width': drp.get('drawer_handle_width', 150.0), 'height': drp.get('drawer_handle_height', 40.0), 'offset_top': drp.get('drawer_handle_offset_top', 10.0)}
                
                c_fa = {"Chant Avant":True, "Chant Arrière":True, "Chant Gauche":True, "Chant Droit":True}
                plans.append((f"Façade Tiroir (C{cab_idx}) [Type {tech_type}]", dr_L, dr_H, drp.get('drawer_face_thickness', 19.0), c_fa, f_holes, [], [], cutout))
                
                # Logique Dos (copiée de 2.py)
                back_height_map = {'N': 69.0, 'M': 84.0, 'K': 116.0, 'D': 199.0}
                fixed_back_h = back_height_map.get(tech_type, 116.0)
                
                d_L_t = (L_raw - 2*t_lr) - 49.0
                d_holes_t = []
                
                back_coords_map = {
                    'K': [30.0, 62.0, 94.0],
                    'M': [32.0, 64.0],
                    'N': [31.0, 47.0],
                    'D': [31.0, 63.0, 95.0, 159.0, 191.0]
                }
                y_coords_back = back_coords_map.get(tech_type, [30.0, 62.0, 94.0])
                
                for dy in y_coords_back:
                    d_holes_t.append({'type': 'vis_dos', 'x': 9.0, 'y': dy, 'diam_str': "⌀2.5/3"}) 
                    d_holes_t.append({'type': 'vis_dos', 'x': d_L_t - 9.0, 'y': dy, 'diam_str': "⌀2.5/3"}) 
                
                c_td = {"Chant Avant":False, "Chant Arrière":False, "Chant Gauche":False, "Chant Droit":False}
                plans.append((f"Tiroir-Dos (C{cab_idx}) [Type {tech_type}]", d_L_t, fixed_back_h, 16.0, c_td, d_holes_t, [], [], None))
                plans.append((f"Tiroir-Fond (C{cab_idx})", d_L_t, W_raw - (20.0+t_fb), 16.0, c_td, [], [], [], None))

            for item in plans:
                # Déballage sécurisé (9 éléments attendus par draw_machining_view_pro_final, mais ici on gère les listes variables)
                if len(item) == 9:
                    title, Lp, Wp, Tp, ch, fh, t_long_h, t_cote_h, cut = item
                else:
                    # Fallback au cas où (ancien format à 8 éléments)
                    title, Lp, Wp, Tp, ch, fh, t_long_h, cut = item
                    t_cote_h = []

                # Appel avec les types enrichis
                fig = draw_machining_view_pro_final(title, Lp, Wp, Tp, st.session_state.unit_select, proj, ch, fh, t_long_h, t_cote_h, cut)
                html_fig = fig.to_html(include_plotlyjs=False, full_html=False, config={'staticPlot': True})
                full_html += f'<div class="page-container">{html_fig}</div>'
        
        full_html += '</body></html>'
        return full_html.encode('utf-8'), True
        
    except Exception as e:
        import traceback
        return f"Erreur : {e} <br> {traceback.format_exc()}".encode('utf-8'), False
