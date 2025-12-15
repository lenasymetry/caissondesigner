# Contenu de geometry_helpers.py
import numpy as np
import plotly.graph_objects as go

# --- NOUVELLE FONCTION ---
def rotation_matrix(angle_deg, axis='z'):
    """
    Renvoie une matrice de rotation 3D pour un angle (degrés) et un axe.
    Conçue pour une multiplication (N, 3) @ R.
    """
    angle_rad = np.radians(angle_deg)
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    
    if axis == 'z':
        # Rotation autour de Z (axe vertical)
        return np.array([
            [c, -s, 0],
            [s,  c, 0],
            [0,  0, 1]
        ])
    elif axis == 'y':
        # Rotation autour de Y (profondeur)
        return np.array([
            [ c, 0, s],
            [ 0, 1, 0],
            [-s, 0, c]
        ])
    elif axis == 'x':
        # Rotation autour de X (largeur)
        return np.array([
            [1, 0,  0],
            [0, c, -s],
            [0, s,  c]
        ])
    return np.identity(3)
# --- FIN NOUVELLE FONCTION ---


def validate_dims(outer):
    return all(v > 0 for v in outer)

def inner_dims_from_thickness(outer, thickness):
    L, W, H = outer
    t_lr = thickness["left_right"]
    t_fb = thickness["front_back"]
    t_tb = thickness["top_bottom"]
    inner_L = L - 2 * t_lr 
    inner_W = W - 2 * t_fb
    inner_H = H - 2 * t_tb
    return (inner_L, inner_W, inner_H)

def can_make_inner(inner):
    return all(v > 0 for v in inner)

def make_cuboid_vertices(L, W, H, origin=(0,0,0)):
    x0,y0,z0 = origin
    verts = np.array([
        [x0,   y0,   z0],    #0
        [x0+L, y0,   z0],    #1
        [x0+L, y0+W, z0],    #2
        [x0,   y0+W, z0],    #3
        [x0,   y0,   z0+H],  #4
        [x0+L, y0,   z0+H],  #5
        [x0+L, y0+W, z0+H],  #6
        [x0,   y0+W, z0+H],  #7
    ])
    return verts

def cuboid_triangles():
    tris = np.array([
        [0,1,2],[0,2,3], [4,5,6],[4,6,7], [0,1,5],[0,5,4],
        [2,3,7],[2,7,6], [1,2,6],[1,6,5], [3,0,4],[3,4,7],
    ])
    return tris

def make_plotly_mesh(verts, tris, name="mesh", color='lightblue', opacity=0.5, showlegend=False):
    x, y, z = verts[:,0], verts[:,1], verts[:,2]
    i, j, k = tris[:,0], tris[:,1], tris[:,2]
    mesh = go.Mesh3d(
        x=x, y=y, z=z, i=i, j=j, k=k,
        opacity=opacity, color=color, name=name,
        flatshading=True, showscale=False, hoverinfo="skip",
        legendgroup=name, showlegend=showlegend
    )
    return mesh

# --- MODIFIÉ : Ajout des paramètres de rotation ---
def cuboid_mesh_for(L, W, H, origin=(0,0,0), name="outer", color='lightblue', opacity=0.5, showlegend=False,
                    rotation_angle=0, rotation_axis='z', rotation_pivot=None):
    """
    Crée un maillage Mesh3d pour un cuboïde, avec une rotation optionnelle.
    """
    
    # 1. Créer les sommets à leur position 'origin' (non pivotés)
    verts = make_cuboid_vertices(L, W, H, origin)
    tris = cuboid_triangles()
    
    # 2. Appliquer la rotation si nécessaire
    if rotation_angle != 0:
        
        # Définir le point de pivot
        if rotation_pivot is None:
            # Si aucun pivot n'est fourni, pivoter autour de l'origine du cube
            pivot = np.array(origin) 
        else:
            pivot = np.array(rotation_pivot)
            
        # Obtenir la matrice de rotation
        R = rotation_matrix(rotation_angle, rotation_axis)
        
        # Appliquer la rotation :
        # 1. Déplacer les sommets pour que le pivot soit à (0,0,0)
        verts_translated = verts - pivot
        
        # 2. Appliquer la rotation (multiplication matricielle)
        # (N, 3) @ (3, 3) -> (N, 3)
        verts_rotated = verts_translated @ R
        
        # 3. Redéplacer les sommets à leur position d'origine + rotation
        verts = verts_rotated + pivot
        
    # 3. Créer le maillage Plotly
    return make_plotly_mesh(verts, tris, name=name, color=color, opacity=opacity, showlegend=showlegend)
# --- FIN MODIFICATION ---


def center_origin_for_plot(outer):
    L,W,H = outer
    return (-L/2, -W/2, 0)

# --- NOUVELLE FONCTION (Inchangée) ---
def cylinder_mesh_for(origin, height, radius, n_points=20, color='grey', name="cyl", showlegend=False):
    """Crée un maillage Mesh3d pour un cylindre."""
    x0, y0, z0 = origin
    
    # Créer les points du cercle
    theta = np.linspace(0, 2*np.pi, n_points)
    a = radius * np.cos(theta)
    b = radius * np.sin(theta)
    
    # Points du bas (z=z0)
    points_bottom = np.array([a + x0, b + y0, np.full(n_points, z0)])
    # Points du haut (z=z0 + height)
    points_top = np.array([a + x0, b + y0, np.full(n_points, z0 + height)])
    
    # Points centraux
    center_bottom = np.array([[x0], [y0], [z0]])
    center_top = np.array([[x0], [y0], [z0 + height]])
    
    # Concaténer tous les points
    # Ordre: 0 à n_points-1 (cercle bas)
    #        n_points à 2*n_points-1 (cercle haut)
    #        2*n_points (centre bas)
    #        2*n_points+1 (centre haut)
    verts = np.concatenate([
        points_bottom.T, 
        points_top.T,
        center_bottom.T,
        center_top.T
    ], axis=0)
    
    x, y, z = verts[:,0], verts[:,1], verts[:,2]
    
    # Indices
    idx_bottom = np.arange(0, n_points)
    idx_top = np.arange(n_points, 2*n_points)
    idx_center_bottom = 2*n_points
    idx_center_top = 2*n_points + 1
    
    i_tris, j_tris, k_tris = [], [], []
    
    # Créer les triangles
    for i in range(n_points):
        idx_i = i
        idx_j = (i + 1) % n_points # Prochain point, boucle
        
        # 1. Capuchon du bas
        i_tris.append(idx_center_bottom)
        j_tris.append(idx_i)
        k_tris.append(idx_j)
        
        # 2. Capuchon du haut
        i_tris.append(idx_center_top)
        j_tris.append(idx_top[idx_i])
        k_tris.append(idx_top[idx_j])
        
        # 3. Côtés (deux triangles pour former un quad)
        i_tris.extend([idx_i, idx_top[idx_i]])
        j_tris.extend([idx_j, idx_top[idx_j]])
        k_tris.extend([idx_top[idx_i], idx_top[idx_j]])
        
        i_tris.extend([idx_i, idx_top[idx_j]])
        j_tris.extend([idx_j, idx_j])
        k_tris.extend([idx_top[idx_j], idx_i])

    return go.Mesh3d(
        x=x, y=y, z=z, 
        i=i_tris, j=j_tris, k=k_tris,
        opacity=1.0, color=color, name=name,
        flatshading=True, showscale=False, hoverinfo="skip",
        legendgroup=name, showlegend=showlegend
    )
# --- FIN NOUVELLE FONCTION ---
