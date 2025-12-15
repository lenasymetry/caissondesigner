# Contenu de machining_logic.py
import math

def calculate_origins_recursively(scene_cabinets, unit_factor):
    calculated_origins = {}
    def get_absolute_origin(caisson_index):
        if caisson_index in calculated_origins: return calculated_origins[caisson_index]
        caisson = scene_cabinets[caisson_index]
        parent_idx = caisson['parent_index']
        if parent_idx is None or parent_idx >= len(scene_cabinets):
            calculated_origins[caisson_index] = (0.0, 0.0, 0.0)
            return (0.0, 0.0, 0.0)
        
        parent_xyz = get_absolute_origin(parent_idx)
        px, py, pz = parent_xyz
        
        parent_L = scene_cabinets[parent_idx]['dims']['L_raw'] * unit_factor
        parent_H = scene_cabinets[parent_idx]['dims']['H_raw'] * unit_factor
        my_L = caisson['dims']['L_raw'] * unit_factor
        
        if caisson['attachment_dir'] == 'right': px += parent_L
        elif caisson['attachment_dir'] == 'left': px -= my_L
        elif caisson['attachment_dir'] == 'up': pz += parent_H
        
        calculated_origins[caisson_index] = (px, py, pz)
        return (px, py, pz)
    
    for i in range(len(scene_cabinets)): get_absolute_origin(i)
    return calculated_origins

def get_hinge_y_positions(door_height_raw):
    if door_height_raw <= 1000: num = 2
    elif door_height_raw <= 1500: num = 3
    elif door_height_raw <= 2000: num = 4
    elif door_height_raw <= 2400: num = 5
    else: num = 6
    if num == 2: return [80.0, door_height_raw - 80.0]
    res = [80.0]
    spacing = (door_height_raw - 160.0) / (num - 1)
    for i in range(1, num - 1): res.append(80.0 + (i * spacing))
    res.append(door_height_raw - 80.0)
    return sorted(list(set(res)))

def round_to_closest_32(y_pos):
    if y_pos < 50.0: return 50.0
    return 50.0 + round((y_pos - 50.0) / 32.0) * 32.0

def get_mobile_shelf_holes(H_side_raw, t_tb_raw, shelf_props, W_raw_val):
    holes = []
    machining_type = shelf_props.get('mobile_machining_type', 'full_height')
    x_front, x_back = 37.0, W_raw_val - 37.0
    start_y, end_y = 50.0, H_side_raw - 50.0
    
    keep = []
    if machining_type == 'full_height': 
        curr = start_y
        while curr <= end_y:
            keep.append(curr)
            curr += 32.0
    else:
        center = shelf_props['height'] + (shelf_props['thickness'] / 2.0)
        y_closest = round_to_closest_32(center)
        keep.append(y_closest)
        if machining_type == '5_holes_centered':
            keep.extend([round_to_closest_32(y_closest + d) for d in [32, 64, -32, -64]])
        elif machining_type == 'custom_n_m':
            n, m = shelf_props.get('custom_holes_above', 0), shelf_props.get('custom_holes_below', 0)
            for i in range(1, n + 1): keep.append(round_to_closest_32(y_closest + i*32))
            for i in range(1, m + 1): keep.append(round_to_closest_32(y_closest - i*32))
    
    keep = sorted(list(set([y for y in keep if start_y <= y <= end_y])))
    
    shelf_id = id(shelf_props) 
    
    for y in keep:
        holes.extend([
            {'type': 'tourillon', 'x': x_front, 'y': y, 'diam_str': "⌀5/12", 'source': 'shelf_mobile', 'group_id': shelf_id}, 
            {'type': 'tourillon', 'x': x_back, 'y': y, 'diam_str': "⌀5/12", 'source': 'shelf_mobile', 'group_id': shelf_id}
        ])
    return holes

def calculate_back_panel_holes(L_back, H_back):
    holes = []
    margin = 8.0
    diam = "⌀3"
    x_min, x_max = margin, L_back - margin
    y_min, y_max = margin, H_back - margin
    
    holes.append({'x': x_min, 'y': y_min, 'type': 'vis', 'diam_str': diam}) 
    holes.append({'x': x_max, 'y': y_min, 'type': 'vis', 'diam_str': diam}) 
    holes.append({'x': x_max, 'y': y_max, 'type': 'vis', 'diam_str': diam}) 
    holes.append({'x': x_min, 'y': y_max, 'type': 'vis', 'diam_str': diam}) 
    
    dist_x = x_max - x_min
    if dist_x > 200:
        nb_inter = int(dist_x / 200)
        step_x = dist_x / (nb_inter + 1)
        for i in range(1, nb_inter + 1):
            cx = x_min + (i * step_x)
            holes.append({'x': cx, 'y': y_min, 'type': 'vis', 'diam_str': diam})
            holes.append({'x': cx, 'y': y_max, 'type': 'vis', 'diam_str': diam})

    dist_y = y_max - y_min
    if dist_y > 200:
        nb_inter = int(dist_y / 200)
        step_y = dist_y / (nb_inter + 1)
        for i in range(1, nb_inter + 1):
            cy = y_min + (i * step_y)
            holes.append({'x': x_min, 'y': cy, 'type': 'vis', 'diam_str': diam})
            holes.append({'x': x_max, 'y': cy, 'type': 'vis', 'diam_str': diam})
            
    return holes

# --- CORRECTION DE LA SIGNATURE ICI ---
def detect_collisions(holes_list, shelves_list=[], panel_name=""):
    """
    Détecte les superpositions d'usinages.
    Retourne une liste de dictionnaires pour l'affichage.
    """
    conflicts = []
    processed_pairs = set()
    
    # 1. Identifier les zones d'étagères mobiles
    mobile_zones = {} 
    
    for h in holes_list:
        src_name = h.get('source_name', 'Inconnu')
        src_id = h.get('group_id', 'unk')
        
        if src_id not in mobile_zones and h.get('source') == 'shelf_mobile':
            mobile_zones[src_id] = {'min': h['y'], 'max': h['y'], 'name': src_name, 'type': 'shelf_mobile'}
        elif src_id in mobile_zones:
            mobile_zones[src_id]['min'] = min(mobile_zones[src_id]['min'], h['y'])
            mobile_zones[src_id]['max'] = max(mobile_zones[src_id]['max'], h['y'])

    # 2. Vérifier Règle 2 : Intrusion dans la zone mobile
    for h in holes_list:
        h_gid = h.get('group_id')
        
        for gid, zone in mobile_zones.items():
            if h_gid != gid: # Ce trou ne fait pas partie de CETTE étagère mobile
                # Zone de sécurité de 5mm
                if zone['min'] - 5 <= h['y'] <= zone['max'] + 5:
                    
                    # On crée un ID unique pour ce conflit pour éviter les doublons
                    conflict_id = f"zone_{gid}_hole_{h['y']}"
                    if conflict_id not in processed_pairs:
                        src_trou = h.get('source_name', 'Autre usinage')
                        conflicts.append({
                            'msg': f"Conflit de Zone : {src_trou} (Y={h['y']:.1f}) tombe dans la crémaillère de {zone['name']}",
                            'overlap_dist': 32.0, # Valeur par défaut pour sortir de la zone
                            'y': h['y']
                        })
                        processed_pairs.add(conflict_id)
    
    # 3. Vérifier Règle 1 : Proximité directe (Distance < 10mm)
    n = len(holes_list)
    for i in range(n):
        h1 = holes_list[i]
        for j in range(i + 1, n):
            h2 = holes_list[j]
            
            # On ignore si même source de type mobile (déjà géré par zone ou normal)
            src1, src2 = h1.get('source'), h2.get('source')
            if src1 == src2 and src1 == 'shelf_mobile': continue 
            
            dist = math.sqrt((h1['x'] - h2['x'])**2 + (h1['y'] - h2['y'])**2)
            
            if dist < 10.0:
                # Clé unique pour éviter les doublons (A vs B et B vs A)
                pair_key = tuple(sorted((str(h1), str(h2))))
                if pair_key not in processed_pairs:
                    name1 = h1.get('source_name', 'Usinage 1')
                    name2 = h2.get('source_name', 'Usinage 2')
                    
                    overlap = 10.0 - dist
                    conflicts.append({
                        'msg': f"Chevauchement entre {name1} et {name2} à Y={h1['y']:.1f} (Dist: {dist:.1f}mm)",
                        'overlap_dist': overlap,
                        'y': h1['y']
                    })
                    processed_pairs.add(pair_key)

    return conflicts
