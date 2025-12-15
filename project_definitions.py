# Contenu de project_definitions.py
# Contient les constantes et configurations par défaut

def get_default_dims_19():
    return {
        'L_raw': 600.0, 'W_raw': 600.0, 'H_raw': 800.0,
        't_lr_raw': 19.0, 't_fb_raw': 19.0, 't_tb_raw': 19.0 
    }

def get_default_door_props_19():
    return {
        'has_door': False, 'door_type': 'single', 'door_opening': 'right',
        'door_thickness': 19.0, 'door_gap': 2.0, 'door_model': 'standard', 'material': 'Matière Porte'
    }

def get_default_drawer_props_19():
    return {
        'has_drawer': False, 'drawer_face_H_raw': 150.0, 'drawer_face_thickness': 19.0,
        'drawer_gap': 2.0, 'drawer_bottom_offset': 0.0, 'drawer_handle_type': 'none',
        'drawer_handle_width': 150.0, 'drawer_handle_height': 40.0, 'drawer_handle_offset_top': 10.0,
        'material': 'Matière Tiroir'
    }
