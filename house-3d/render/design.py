"""Luxury interior pieces modelled directly in Blender. Coordinates are three.js plan metres (x, y-up, z)."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler

def T(x, y, z): return Vector((x, -z, y))
_col = None
def coll():
    global _col
    if _col is None:
        _col = bpy.data.collections.new('luxury'); bpy.context.scene.collection.children.link(_col)
    return _col

# ---------- materials ----------
def mat(name, color, rough=0.5, metal=0.0, sheen=0.0, coat=0.0, bump=0.0, bscale=300.0, emit=None, estr=0.0, sss=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*color, 1); p.inputs['Roughness'].default_value = rough; p.inputs['Metallic'].default_value = metal
    if sheen: p.inputs['Sheen Weight'].default_value = sheen; p.inputs['Sheen Roughness'].default_value = 0.4
    if coat: p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = 0.04
    if sss: p.inputs['Subsurface Weight'].default_value = sss
    if bump:
        tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = bscale; nz.inputs['Detail'].default_value = 8
        b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = bump
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(nz.outputs['Fac'], b.inputs['Height']); nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    if emit: p.inputs['Emission Color'].default_value = (*emit, 1); p.inputs['Emission Strength'].default_value = estr
    return m

def banded(name, c1, c2, rough, scale=6.0, dist=4.0):
    """Travertine-like horizontal banding."""
    m = mat(name, c1, rough); nt = m.node_tree; p = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = scale
    wv.inputs['Distortion'].default_value = dist; wv.inputs['Detail'].default_value = 6
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (*c1, 1); ramp.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(tc.outputs['Object'], wv.inputs['Vector']); nt.links.new(wv.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], p.inputs['Base Color'])
    return m

def emission(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], o.inputs['Surface']); return m

def find(base):
    return next(m for m in bpy.data.materials if m.name.split('.')[0] == base)

# ---------- mesh building ----------
class MB:
    def __init__(s): s.bm = bmesh.new()
    def box(s, x0, x1, y0, y1, z0, z1):
        c = T((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        M = Matrix.Translation(c) @ Matrix.Diagonal((abs(x1 - x0), abs(z1 - z0), abs(y1 - y0), 1))
        bmesh.ops.create_cube(s.bm, size=1.0, matrix=M); return s
    def cyl(s, x, z, r, y0, y1, seg=48, r2=None):
        M = Matrix.Translation(T(x, (y0 + y1) / 2, z))
        bmesh.ops.create_cone(s.bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=y1 - y0, matrix=M); return s
    def obj(s, name, m, bevel=0.0, seg=2, sub=0, smooth=None):
        me = bpy.data.meshes.new(name); s.bm.to_mesh(me); s.bm.free()
        ob = bpy.data.objects.new(name, me); coll().objects.link(ob); me.materials.append(m)
        smooth = (bevel > 0 or sub > 0) if smooth is None else smooth
        for p in me.polygons: p.use_smooth = smooth
        if bevel:
            md = ob.modifiers.new('bv', 'BEVEL'); md.width = bevel; md.segments = seg; md.limit_method = 'ANGLE'; md.use_clamp_overlap = True
            md.harden_normals = not sub
        if sub:
            md = ob.modifiers.new('ss', 'SUBSURF'); md.levels = sub; md.render_levels = sub
        return ob

def frame(x0, x1, z0, z1, back):
    if back in ('-x', '+x'):
        L, D = z1 - z0, x1 - x0
        def R(u0, u1, d0, d1):
            xs = (x0 + d0, x0 + d1) if back == '-x' else (x1 - d1, x1 - d0)
            return xs[0], xs[1], z0 + u0, z0 + u1
        f = (1, 0) if back == '-x' else (-1, 0)
    else:
        L, D = x1 - x0, z1 - z0
        def R(u0, u1, d0, d1):
            zs = (z0 + d0, z0 + d1) if back == '-z' else (z1 - d1, z1 - d0)
            return x0 + u0, x0 + u1, zs[0], zs[1]
        f = (0, 1) if back == '-z' else (0, -1)
    return L, D, R, f

def pillow(x, y, z, f, m, size=0.46, tilt=0.3, jit=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((size, 0.16, size, 1)))
    me = bpy.data.meshes.new('pillow'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('pillow', me); coll().objects.link(ob); me.materials.append(m)
    for p in me.polygons: p.use_smooth = True
    md = ob.modifiers.new('bv', 'BEVEL'); md.width = 0.07; md.segments = 3; md.use_clamp_overlap = True
    md = ob.modifiers.new('ss', 'SUBSURF'); md.levels = 2; md.render_levels = 2
    fb = Vector((f[0], -f[1])); th = math.atan2(-fb.x, fb.y)
    ob.rotation_euler = Euler((tilt, 0, th + jit), 'XYZ'); ob.location = T(x, y, z)

def sofa(x0, x1, z0, z1, back, fab, leg, pmats, arm=0.13, seat_n=None, armh=0.58):
    L, D, R, f = frame(x0, x1, z0, z1, back)
    a = R(0, L, 0, D); MB().box(a[0], a[1], 0.14, 0.37, a[2], a[3]).obj('sofa_base', fab, bevel=0.035, seg=4)
    arms = MB()
    for (u0, u1) in ((0, arm), (L - arm, L)):
        a = R(u0, u1, 0, D); arms.box(a[0], a[1], 0.14, armh, a[2], a[3])
    arms.obj('sofa_arms', fab, bevel=0.06, seg=5)
    a = R(arm - 0.001, L - arm + 0.001, 0, 0.2); MB().box(a[0], a[1], 0.37, 0.7, a[2], a[3]).obj('sofa_back', fab, bevel=0.05, seg=4)
    n = seat_n or max(1, round((L - 2 * arm) / 0.82)); w = (L - 2 * arm) / n
    seat, bk = MB(), MB()
    for i in range(n):
        u0, u1 = arm + i * w + 0.008, arm + (i + 1) * w - 0.008
        a = R(u0, u1, 0.2, D - 0.005); seat.box(a[0], a[1], 0.37, 0.53, a[2], a[3])
        a = R(u0, u1, 0.19, 0.4); bk.box(a[0], a[1], 0.53, 0.88, a[2], a[3])
    seat.obj('seat', fab, bevel=0.06, seg=3, sub=2); bk.obj('back_cush', fab, bevel=0.08, seg=3, sub=2)
    lg = MB()
    for (u, d) in ((0.1, 0.1), (L - 0.1, 0.1), (0.1, D - 0.1), (L - 0.1, D - 0.1)):
        a = R(u, u, d, d); lg.cyl(a[0], a[2], 0.016, 0.0, 0.14, seg=16)
    lg.obj('legs', leg, bevel=0.002)
    spots = [arm + 0.3, L - arm - 0.3] if L > 1.2 else [L / 2]
    for k, u in enumerate(spots):
        a = R(u, u, 0.5, 0.5); pillow(a[0], 0.75, a[2], f, pmats[k % len(pmats)], jit=(0.18 if k else -0.15))
    if L > 2.0:
        a = R(arm + 0.62, arm + 0.62, 0.5, 0.5); pillow(a[0], 0.72, a[2], f, pmats[-1], size=0.4, jit=0.1)

def leaves(cx, cy, cz, rx, ry, rz, n, m, seed=3, size=0.07):
    rnd = random.Random(seed); bm = bmesh.new()
    for _ in range(n):
        while True:
            p = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
            if p.length <= 1: break
        pos = T(cx + p.x * rx, cy + p.y * ry, cz + p.z * rz)
        R = Euler((rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))).to_matrix().to_4x4()
        s = size * rnd.uniform(0.7, 1.2)
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0, matrix=Matrix.Translation(pos) @ R @ Matrix.Diagonal((s, s * 0.28, s * 0.05, 1)))
    me = bpy.data.meshes.new('leaves'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('leaves', me); coll().objects.link(ob); me.materials.append(m)
    for p in me.polygons: p.use_smooth = True

def twig(x0, y0, z0, x1, y1, z1, r, m):
    a, b = T(x0, y0, z0), T(x1, y1, z1); d = b - a
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r, radius2=r * 0.6, depth=d.length)
    me = bpy.data.meshes.new('twig'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('twig', me); coll().objects.link(ob); me.materials.append(m)
    ob.location = (a + b) / 2; ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    for p in me.polygons: p.use_smooth = True

def olive(x, z, M):
    MB().cyl(x, z, 0.27, 0.0, 0.52, r2=0.3, seg=48).obj('pot', M['potm'], bevel=0.01, seg=2)
    MB().cyl(x, z, 0.27, 0.5, 0.505).obj('soil', M['soil'])
    twig(x, 0.5, z, x + 0.05, 1.3, z + 0.03, 0.035, M['bark']); twig(x + 0.04, 1.1, z, x - 0.18, 1.7, z + 0.1, 0.02, M['bark'])
    twig(x + 0.05, 1.2, z + 0.02, x + 0.22, 1.85, z - 0.08, 0.02, M['bark'])
    leaves(x - 0.12, 1.75, z + 0.06, 0.3, 0.25, 0.28, 650, M['leaf'], seed=5)
    leaves(x + 0.18, 1.9, z - 0.06, 0.28, 0.22, 0.26, 600, M['leaf'], seed=6)
    leaves(x + 0.02, 1.45, z, 0.25, 0.2, 0.25, 350, M['leaf'], seed=7)

def books(x, z, y, n, mats, rot=0.0, seed=1):
    rnd = random.Random(seed); yy = y
    for i in range(n):
        w, d, h = rnd.uniform(0.2, 0.26), rnd.uniform(0.27, 0.32), rnd.uniform(0.025, 0.04)
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((w, d, h, 1)))
        me = bpy.data.meshes.new('book'); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new('book', me); coll().objects.link(ob); me.materials.append(mats[i % len(mats)])
        md = ob.modifiers.new('bv', 'BEVEL'); md.width = 0.003; md.segments = 2
        ob.location = T(x, yy + h / 2, z); ob.rotation_euler = (0, 0, rot + rnd.uniform(-0.15, 0.15)); yy += h
    return yy

def vase(x, z, y, r, h, m, neck=0.5):
    MB().cyl(x, z, r, y, y + h * 0.65, r2=r * 0.95, seg=48).obj('vase', m, bevel=0.02, seg=4)
    MB().cyl(x, z, r * 0.95, y + h * 0.65, y + h, r2=r * neck, seg=48).obj('vase_top', m, bevel=0.01, seg=3)

# ---------- scene clean-up ----------
KEEP = {'floor', 'paint', 'cap', 'stone', 'ceiling', 'alu', 'GLASS_R', 'glass', 'bathWall', 'bathFloor', 'door', 'doorWhite', 'doorWood', 'entry', 'gap', 'bedFloor', 'outdoor', 'ground'}
def clear_box(x0, x1, z0, z1, ymax=2.9, keep=KEEP):
    for ob in list(bpy.context.scene.objects):
        if ob.type != 'MESH' or not ob.material_slots or not ob.material_slots[0].material: continue
        if ob.material_slots[0].material.name.split('.')[0] in keep: continue
        c = sum((ob.matrix_world @ Vector(v) for v in ob.bound_box), Vector()) / 8
        if x0 < c.x < x1 and z0 < -c.y < z1 and c.z < ymax: bpy.data.objects.remove(ob, do_unlink=True)

# ---------- lighting fixtures ----------
def track_spot(x, z, y_track, LED, BLK, power=28, angle=38):
    MB().cyl(x, z, 0.03, y_track - 0.11, y_track, seg=24).obj('trk_spot', BLK, bevel=0.004)
    MB().cyl(x, z, 0.022, y_track - 0.112, y_track - 0.109, seg=24).obj('trk_lens', LED)
    ld = bpy.data.lights.new('trk', 'SPOT'); ld.energy = power; ld.spot_size = math.radians(angle); ld.spot_blend = 0.5
    ld.color = (1.0, 0.88, 0.74); ld.shadow_soft_size = 0.02
    lo = bpy.data.objects.new('trk', ld); lo.location = T(x, y_track - 0.115, z); coll().objects.link(lo)

def track_line(axis, c, a0, a1, y, LED, BLK, spots_at=(), bars=()):
    """Recessed black magnetic track with linear bars and spot heads."""
    if axis == 'x': MB().box(a0, a1, y - 0.012, y + 0.002, c - 0.022, c + 0.022).obj('track', BLK, bevel=0.002)
    else: MB().box(c - 0.022, c + 0.022, y - 0.012, y + 0.002, a0, a1).obj('track', BLK, bevel=0.002)
    for (b0, b1) in bars:
        if axis == 'x': MB().box(b0, b1, y - 0.016, y - 0.012, c - 0.014, c + 0.014).obj('bar', LED)
        else: MB().box(c - 0.014, c + 0.014, y - 0.016, y - 0.012, b0, b1).obj('bar', LED)
    for u in spots_at:
        track_spot(u if axis == 'x' else c, c if axis == 'x' else u, y - 0.012, LED, BLK)

def drape(axis, c, a0, a1, m, top=2.7, amp=0.06, period=0.22):
    n = max(8, int((a1 - a0) / 0.03)); verts, faces = [], []
    for y in (0.01, top):
        for i in range(n + 1):
            u = a0 + (a1 - a0) * i / n; off = amp * math.sin((u - a0) / period * 2 * math.pi)
            verts.append(T(u, y, c + off) if axis == 'x' else T(c + off, y, u))
    for i in range(n): faces.append((i, i + 1, n + 2 + i, n + 1 + i))
    me = bpy.data.meshes.new('drape'); me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new('drape', me); coll().objects.link(ob); me.materials.append(m)
    for p in me.polygons: p.use_smooth = True
    md = ob.modifiers.new('sol', 'SOLIDIFY'); md.thickness = 0.006

def gyps(x0, x1, z0, z1, PAINT, LED, w=0.42, drop=2.72):
    """Second gypsum step inside the raised field and an LED reveal washing the walls."""
    ix0, ix1, iz0, iz1 = x0 + w + 0.5, x1 - w - 0.5, z0 + w + 0.5, z1 - w - 0.5
    g = MB()
    for (a0, a1, b0, b1) in [(x0 + w, x1 - w, z0 + w, iz0), (x0 + w, x1 - w, iz1, z1 - w), (x0 + w, ix0, iz0, iz1), (ix1, x1 - w, iz0, iz1)]:
        g.box(a0, a1, 2.86, 3.0, b0, b1)
    g.obj('gyps_step', PAINT, bevel=0.003)
    led = MB()
    for (a0, a1, b0, b1) in [(ix0, ix1, iz0, iz0 + 0.012), (ix0, ix1, iz1 - 0.012, iz1), (ix0, ix0 + 0.012, iz0, iz1), (ix1 - 0.012, ix1, iz0, iz1)]:
        led.box(a0, a1, 2.862, 2.872, b0, b1)
    led.obj('step_led', LED, smooth=False)
    wash = MB(); o = 0.035
    for (a0, a1, b0, b1) in [(x0 + o, x1 - o, z0 + o, z0 + o + 0.015), (x0 + o, x1 - o, z1 - o - 0.015, z1 - o), (x1 - o - 0.015, x1 - o, z0 + o, z1 - o)]:
        wash.box(a0, a1, drop - 0.006, drop - 0.002, b0, b1)
    wash.obj('wall_wash', LED, smooth=False)

# ---------- the living room ----------
def build_living(LED):
    M = {}
    M['linen'] = mat('linen', (0.70, 0.64, 0.56), 0.92, sheen=0.4, bump=0.25, bscale=900)
    M['boucle'] = mat('boucle', (0.86, 0.82, 0.75), 0.95, sheen=0.6, bump=0.6, bscale=420)
    M['pil1'] = mat('pil_caramel', (0.66, 0.53, 0.40), 0.85, sheen=0.6, bump=0.2, bscale=900)
    M['pil2'] = mat('pil_ivory', (0.88, 0.84, 0.77), 0.95, sheen=0.5, bump=0.5, bscale=420)
    M['pil3'] = mat('pil_taupe', (0.55, 0.50, 0.44), 0.85, sheen=0.6, bump=0.2, bscale=900)
    M['brass'] = mat('brass_b', (0.80, 0.62, 0.36), 0.28, metal=1.0)
    M['blk'] = mat('black_matte', (0.02, 0.02, 0.022), 0.45)
    M['trav'] = banded('travertine', (0.80, 0.72, 0.60), (0.90, 0.84, 0.74), 0.4, scale=3, dist=8)
    M['tv'] = mat('tv_glass', (0.004, 0.004, 0.005), 0.04, coat=1.0)
    M['rug'] = mat('rug_wool', (0.76, 0.70, 0.61), 1.0, sheen=0.5, bump=1.0, bscale=700)
    M['drape'] = mat('drape_velvet', (0.48, 0.42, 0.35), 0.8, sheen=0.8, bump=0.1, bscale=500)
    M['potm'] = mat('pot_stone', (0.28, 0.25, 0.22), 0.8, bump=0.4, bscale=60)
    M['soil'] = mat('soil', (0.08, 0.06, 0.04), 1.0, bump=0.8, bscale=200)
    M['bark'] = mat('bark', (0.22, 0.17, 0.12), 0.9, bump=0.6, bscale=80)
    M['leaf'] = mat('leaf', (0.17, 0.22, 0.12), 0.55, sss=0.1)
    M['cer1'] = mat('ceramic_sand', (0.82, 0.76, 0.66), 0.7, bump=0.15, bscale=120)
    M['cer2'] = mat('ceramic_dark', (0.10, 0.09, 0.085), 0.35, coat=0.5)
    bk = [mat('book1', (0.80, 0.76, 0.68), 0.7), mat('book2', (0.35, 0.28, 0.22), 0.6), mat('book3', (0.62, 0.55, 0.44), 0.7), mat('book4', (0.16, 0.17, 0.16), 0.6)]
    WAL = find('wood'); MAR = find('counter'); PAINT = find('paint')

    clear_box(4.75, 8.58, -0.62, 4.01)

    # TV wall: book-matched slab between fluted walnut columns, floating console
    slab = MB()
    for (a, b) in ((6.1, 6.88), (6.886, 7.664), (7.67, 8.45)):
        slab.box(a, b, 0.0, 2.72, 3.95, 4.0)
    slab.obj('tv_travertine', M['trav'], bevel=0.003, seg=2)
    MB().box(6.1, 8.45, 2.1, 2.4, 3.8, 3.95).obj('niche_top', M['trav'], bevel=0.004)
    MB().box(6.15, 8.4, 2.096, 2.1, 3.84, 3.94).obj('niche_led', LED, smooth=False)
    MB().box(6.43, 8.12, 1.02, 1.99, 3.93, 3.955).obj('tv', M['tv'], bevel=0.004)
    MB().box(6.45, 8.1, 0.3, 0.6, 3.52, 3.955).obj('console', WAL, bevel=0.008, seg=3)
    MB().box(6.5, 8.05, 0.296, 0.3, 3.56, 3.92).obj('console_led', LED, smooth=False)
    vase(6.75, 3.74, 0.6, 0.075, 0.34, M['cer2']); vase(6.95, 3.78, 0.6, 0.06, 0.22, M['cer1'], neck=0.7)
    books(7.75, 3.74, 0.6, 3, bk, rot=0.2, seed=4)

    # ceiling: walnut slats in the raised field, magnetic track loop in the gypsum band
    gyps(5.0, 8.6, -0.64, 4.0, PAINT, LED)
    yb = 2.72
    track_line('x', -0.43, 5.21, 8.39, yb, LED, M['blk'], spots_at=(5.9, 7.7), bars=((6.45, 7.15),))
    track_line('x', 3.79, 5.21, 8.39, yb, LED, M['blk'], spots_at=(6.2, 7.3, 8.15), bars=())
    track_line('z', 8.39, -0.43, 3.79, yb, LED, M['blk'], spots_at=(0.4, 2.2), bars=((1.0, 1.6), (2.7, 3.3)))

    # seating
    sofa(7.55, 8.5, 0.35, 3.15, '+x', M['linen'], M['brass'], [M['pil1'], M['pil2'], M['pil3']])
    sofa(5.75, 7.4, -0.55, 0.38, '-z', M['linen'], M['brass'], [M['pil2'], M['pil1']])
    sofa(4.85, 5.75, 0.6, 1.45, '-x', M['boucle'], M['brass'], [M['pil1']], arm=0.2, seat_n=1, armh=0.55)
    sofa(4.85, 5.75, 1.75, 2.6, '-x', M['boucle'], M['brass'], [M['pil3']], arm=0.2, seat_n=1, armh=0.55)

    # rug and nested travertine / marble tables
    MB().box(5.3, 7.9, 0.0, 0.016, 0.15, 3.25).obj('rug', M['rug'], bevel=0.008, seg=2)
    MB().cyl(6.4, 1.45, 0.56, 0.31, 0.36, seg=96).obj('ct_top', M['trav'], bevel=0.012, seg=3)
    MB().cyl(6.4, 1.45, 0.36, 0.016, 0.31, seg=96).obj('ct_base', M['trav'], bevel=0.01, seg=2)
    MB().cyl(7.08, 2.2, 0.33, 0.42, 0.445, seg=96).obj('ct2_top', MAR, bevel=0.008, seg=3)
    MB().cyl(7.08, 2.2, 0.04, 0.03, 0.42, seg=24).obj('ct2_leg', M['brass'], bevel=0.003)
    MB().cyl(7.08, 2.2, 0.2, 0.016, 0.03, seg=64).obj('ct2_foot', M['brass'], bevel=0.004)
    top = books(6.25, 1.3, 0.36, 2, bk, rot=0.5, seed=2)
    MB().cyl(6.25, 1.3, 0.05, top, top + 0.1, seg=48).obj('orb', M['brass'], bevel=0.02, seg=4)
    MB().cyl(6.6, 1.65, 0.16, 0.36, 0.42, r2=0.2, seg=64).obj('bowl', M['cer2'], bevel=0.02, seg=4)
    vase(7.05, 2.15, 0.445, 0.07, 0.3, M['cer1'], neck=0.4)
    twig(7.05, 0.7, 2.15, 6.95, 1.15, 2.05, 0.004, M['bark']); twig(7.05, 0.7, 2.15, 7.2, 1.1, 2.3, 0.004, M['bark'])
    leaves(6.97, 1.1, 2.08, 0.1, 0.12, 0.1, 60, M['leaf'], seed=11, size=0.035)
    leaves(7.18, 1.06, 2.28, 0.1, 0.1, 0.1, 50, M['leaf'], seed=12, size=0.035)

    # floor lamp in the sofa corner
    MB().cyl(8.3, 3.55, 0.16, 0.0, 0.03, seg=64).obj('lamp_base', MAR, bevel=0.006)
    MB().cyl(8.3, 3.55, 0.012, 0.03, 1.55, seg=16).obj('lamp_pole', M['brass'])
    MB().cyl(8.3, 3.55, 0.2, 1.3, 1.62, r2=0.17, seg=64).obj('lamp_shade', emission('shade_glow', (1.0, 0.8, 0.55), 3.0))
    ld = bpy.data.lights.new('lamp', 'POINT'); ld.energy = 45; ld.color = (1.0, 0.78, 0.5); ld.shadow_soft_size = 0.1
    lo = bpy.data.objects.new('lamp', ld); lo.location = T(8.3, 1.45, 3.55); coll().objects.link(lo)

    olive(8.18, -0.3, M)
    # velvet side drapes framing the sheers
    drape('x', -0.5, 5.02, 5.42, M['drape']); drape('x', -0.5, 8.05, 8.42, M['drape'])
    drape('z', 8.48, -0.6, -0.2, M['drape']); drape('z', 8.48, 3.25, 3.62, M['drape'])
    return M

def kitchen_extras(LED):
    blk = mat('black_k', (0.02, 0.02, 0.022), 0.45)
    for c in (1.0, 2.15):
        track_line('x', c, 0.45, 3.55, 3.0, LED, blk, spots_at=(0.9, 2.0, 3.1), bars=((1.25, 1.75), (2.35, 2.85)))
    cer = mat('ceramic_k', (0.85, 0.80, 0.72), 0.6); cer2 = mat('ceramic_k2', (0.12, 0.1, 0.09), 0.35, coat=0.5)
    board = mat('oak_board', (0.55, 0.38, 0.22), 0.5)
    leaf = mat('leaf_k', (0.17, 0.22, 0.12), 0.55)
    vase(1.0, 0.3, 0.9, 0.08, 0.28, cer2, neck=0.55); vase(1.2, 0.32, 0.9, 0.06, 0.18, cer, neck=0.7)
    MB().box(2.95, 3.35, 0.9, 0.92, 0.08, 0.36).obj('board', board, bevel=0.006)
    MB().cyl(4.08, 1.35, 0.17, 0.9, 0.97, r2=0.21, seg=64).obj('fruit_bowl', cer, bevel=0.015, seg=3)
    leaves(4.08, 1.0, 1.35, 0.13, 0.04, 0.13, 25, mat('lemon', (0.85, 0.65, 0.12), 0.4), seed=9, size=0.06)

# ---------- the master bedroom ----------
def build_master(LED, SHEER):
    M = {}
    M['head'] = mat('headboard_velvet', (0.62, 0.55, 0.47), 0.75, sheen=0.9, bump=0.15, bscale=600)
    M['boucle'] = mat('boucle_m', (0.86, 0.82, 0.75), 0.95, sheen=0.6, bump=0.6, bscale=420)
    M['sheet'] = mat('sheet', (0.92, 0.90, 0.86), 0.85, sheen=0.4, bump=0.1, bscale=900)
    M['duvet'] = mat('duvet', (0.85, 0.81, 0.74), 0.9, sheen=0.5, bump=0.2, bscale=700)
    M['throw'] = mat('throw', (0.50, 0.36, 0.24), 0.9, sheen=0.6, bump=0.4, bscale=500)
    M['pil'] = mat('pil_m', (0.72, 0.66, 0.57), 0.9, sheen=0.5, bump=0.2, bscale=800)
    M['brass'] = mat('brass_m', (0.80, 0.62, 0.36), 0.28, metal=1.0)
    M['blk'] = mat('black_m', (0.02, 0.02, 0.022), 0.45)
    M['rug'] = mat('rug_m', (0.66, 0.60, 0.52), 1.0, sheen=0.5, bump=1.0, bscale=700)
    M['drape'] = mat('drape_m', (0.48, 0.42, 0.35), 0.8, sheen=0.8, bump=0.1, bscale=500)
    M['cer'] = mat('ceramic_m', (0.82, 0.76, 0.66), 0.7, bump=0.15, bscale=120)
    M['leaf'] = mat('leaf_m', (0.17, 0.22, 0.12), 0.55, sss=0.1); M['bark'] = mat('bark_m', (0.22, 0.17, 0.12), 0.9)
    M['potm'] = mat('pot_m', (0.28, 0.25, 0.22), 0.8, bump=0.4, bscale=60); M['soil'] = mat('soil_m', (0.08, 0.06, 0.04), 1.0)
    glow = emission('globe_glow', (1.0, 0.8, 0.55), 6.0)
    WAL = find('wood'); MAR = find('counter')
    keep = KEEP | {'LED_R'}
    clear_box(2.78, 7.04, 8.05, 11.385, keep=keep)

    # curtain wall behind the bed
    for a0, a1 in ((2.85, 7.0),):
        n = 1
    import math as _m
    def sheer_wall(z, a0, a1):
        drape('x', z, a0, a1, SHEER, top=2.7, amp=0.045, period=0.2)
    sheer_wall(11.33, 2.85, 7.0)
    drape('x', 11.25, 2.85, 3.3, M['drape']); drape('x', 11.25, 6.55, 7.0, M['drape'])
    MB().box(2.8, 7.03, 2.68, 2.72, 11.2, 11.385).obj('curtain_pelmet', find('paint'), bevel=0.004)

    # bed: tall channel-tufted headboard, platform, mattress, softly rounded duvet
    bx0, bx1, bz0, bz1 = 3.85, 5.77, 9.15, 11.15
    hb = MB(); x = bx0 - 0.25
    while x < bx1 + 0.25 - 0.01:
        hb.box(x + 0.004, x + 0.196, 0.25, 1.35, 11.08, 11.2); x += 0.2
    hb.obj('headboard', M['head'], bevel=0.05, seg=3, sub=1)
    MB().box(bx0 - 0.25, bx1 + 0.25, 0.0, 0.25, 11.08, 11.2).obj('head_base', M['head'], bevel=0.02, seg=2)
    MB().box(bx0, bx1, 0.08, 0.34, bz0, bz1 - 0.08).obj('bed_base', M['head'], bevel=0.04, seg=3)
    MB().box(bx0 + 0.06, bx1 - 0.06, 0.0, 0.08, bz0 + 0.06, bz1 - 0.14).obj('bed_plinth', M['blk'])
    MB().box(bx0 + 0.03, bx1 - 0.03, 0.34, 0.58, bz0 + 0.03, bz1 - 0.12).obj('mattress', M['sheet'], bevel=0.05, seg=3, sub=1)
    MB().box(bx0 - 0.02, bx1 + 0.02, 0.5, 0.64, bz0 - 0.02, bz1 - 0.75).obj('duvet', M['duvet'], bevel=0.06, seg=3, sub=2)
    MB().box(bx0 - 0.03, bx1 + 0.03, 0.62, 0.665, bz0 + 0.15, bz0 + 0.65).obj('throw', M['throw'], bevel=0.02, seg=2, sub=1)
    for i, x in enumerate((bx0 + 0.45, bx1 - 0.45)):
        pillow(x, 0.78, bz1 - 0.42, (0, -1), M['sheet'], size=0.6, tilt=0.45, jit=0.05 * (1 if i else -1))
        pillow(x + (0.05 if i else -0.05), 0.75, bz1 - 0.6, (0, -1), M['pil'], size=0.48, tilt=0.35, jit=0.12 * (1 if i else -1))
    pillow((bx0 + bx1) / 2, 0.72, bz1 - 0.72, (0, -1), M['throw'], size=0.36, tilt=0.3)

    # floating nightstands with brass globe pendants
    for (x0, x1) in ((3.2, 3.75), (5.87, 6.42)):
        MB().box(x0, x1, 0.32, 0.55, 10.7, 11.2).obj('ns', WAL, bevel=0.006, seg=2)
        MB().box(x0, x1, 0.55, 0.57, 10.7, 11.2).obj('ns_top', MAR, bevel=0.004)
        cx = (x0 + x1) / 2
        MB().cyl(cx, 10.95, 0.003, 1.45, 3.0, seg=8).obj('wire', M['brass'])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=T(cx, 1.33, 10.95), segments=48, ring_count=24)
        g = bpy.context.object; g.data.materials.append(glow)
        for c in g.users_collection: c.objects.unlink(g)
        coll().objects.link(g); g.data.polygons.foreach_set('use_smooth', [True] * len(g.data.polygons))
        MB().cyl(cx, 10.95, 0.035, 1.43, 1.47, seg=32).obj('cap', M['brass'], bevel=0.005)
        ld = bpy.data.lights.new('pend', 'POINT'); ld.energy = 25; ld.color = (1.0, 0.78, 0.5); ld.shadow_soft_size = 0.11
        lo = bpy.data.objects.new('pend', ld); lo.location = T(cx, 1.33, 10.95); coll().objects.link(lo)
    books(3.45, 10.9, 0.57, 2, [M['cer'], M['throw']], seed=8)
    vase(6.2, 10.95, 0.57, 0.06, 0.22, M['cer'], neck=0.6)

    # ceiling: walnut slats over the bed, magnetic tracks in the band
    sl = MB(); x = bx0 - 0.4
    while x < bx1 + 0.4:
        sl.box(x, x + 0.035, 2.955, 3.0, 9.0, 10.96); x += 0.06
    sl.obj('bed_slats', WAL, bevel=0.003)
    MB().box(bx0 - 0.42, bx1 + 0.44, 2.996, 3.0, 8.98, 10.97).obj('slat_back_m', M['blk'])
    track_line('z', 3.0, 8.25, 11.15, 2.72, LED, M['blk'], spots_at=(8.7, 9.9), bars=((10.3, 10.9),))
    track_line('z', 6.82, 8.25, 11.15, 2.72, LED, M['blk'], spots_at=(8.7, 9.9), bars=((10.3, 10.9),))

    # wall facing the bed: fluted walnut with a floating dresser and mirror
    fl = MB(); x = 4.05
    while x < 5.9:
        fl.box(x + 0.003, x + 0.033, 0.0, 2.72, 8.04, 8.08); x += 0.036
    fl.obj('flutes_m', WAL, bevel=0.006, seg=3)
    MB().box(4.25, 5.75, 0.35, 0.8, 8.08, 8.55).obj('dresser', WAL, bevel=0.008, seg=3)
    MB().box(4.25, 5.75, 0.8, 0.82, 8.08, 8.56).obj('dresser_top', MAR, bevel=0.004)
    MB().box(4.3, 5.7, 0.346, 0.35, 8.12, 8.5).obj('dresser_led', LED, smooth=False)
    MB().cyl(5.0, 8.1, 0.5, 1.1, 1.13, seg=96).obj('mirror_frame', M['brass'])
    mir = mat('mirror_m', (0.9, 0.9, 0.9), 0.02, metal=1.0)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.48, depth=0.02, location=T(5.0, 1.6, 8.1), rotation=(math.pi / 2, 0, 0), vertices=96)
    mo = bpy.context.object; mo.data.materials.append(mir)
    for c in mo.users_collection: c.objects.unlink(mo)
    coll().objects.link(mo)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.49, minor_radius=0.012, location=T(5.0, 1.6, 8.11), rotation=(math.pi / 2, 0, 0), major_segments=96)
    to = bpy.context.object; to.data.materials.append(M['brass'])
    for c in to.users_collection: c.objects.unlink(to)
    coll().objects.link(to)
    vase(4.55, 8.32, 0.82, 0.07, 0.3, M['cer'], neck=0.4)
    books(5.4, 8.32, 0.82, 3, [M['throw'], M['cer'], M['pil']], seed=5)

    # rug, bench, reading chair and plant
    MB().box(3.25, 6.4, 0.0, 0.016, 8.75, 10.95).obj('rug_m', M['rug'], bevel=0.008)
    MB().box(4.1, 5.5, 0.12, 0.45, 8.62, 9.02).obj('bench', M['boucle'], bevel=0.05, seg=4, sub=1)
    MB().box(4.15, 5.45, 0.0, 0.12, 8.67, 8.97).obj('bench_base', M['brass'], bevel=0.004)
    sofa(6.2, 6.95, 9.85, 10.65, '+x', M['boucle'], M['brass'], [M['throw']], arm=0.18, seat_n=1, armh=0.55)
    olive(6.7, 8.45, {'potm': M['potm'], 'soil': M['soil'], 'bark': M['bark'], 'leaf': M['leaf']})
    drape('z', 6.98, 8.12, 8.5, M['drape']); drape('z', 6.98, 9.3, 9.7, M['drape'])

# ======== v2: warm-modern living room following the client's references ========
def ramp_mat(name, cols, rough, scale=3.0, dist=4.0, bump=0.0, bscale=600, sheen=0.0):
    """Abstract multi-tone pattern (rug)."""
    m = mat(name, cols[0], rough, sheen=sheen, bump=bump, bscale=bscale); nt = m.node_tree; p = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = scale; nz.inputs['Distortion'].default_value = dist; nz.inputs['Detail'].default_value = 10
    r = nt.nodes.new('ShaderNodeValToRGB'); els = r.color_ramp.elements
    els[0].position = 0.0; els[0].color = (*cols[0], 1); els[1].position = 1.0; els[1].color = (*cols[-1], 1)
    for i, c in enumerate(cols[1:-1]):
        e = els.new((i + 1) / (len(cols) - 1)); e.color = (*c, 1)
    r.color_ramp.interpolation = 'CONSTANT'
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(nz.outputs['Fac'], r.inputs['Fac']); nt.links.new(r.outputs['Color'], p.inputs['Base Color'])
    return m

def channel_sofa(x0, x1, z0, z1, back, fab, arms=(True, True), ch=0.2, seat_h=0.44, back_h=0.74):
    """Soft channel-tufted modular sofa (reference image 1)."""
    L, D, R, f = frame(x0, x1, z0, z1, back)
    a0 = 0.16 if arms[0] else 0.0; a1 = L - (0.16 if arms[1] else 0.0)
    n = max(1, round((a1 - a0) / ch)); w = (a1 - a0) / n
    seat, bk = MB(), MB()
    for i in range(n):
        u0, u1 = a0 + i * w + 0.004, a0 + (i + 1) * w - 0.004
        a = R(u0, u1, 0.24, D); seat.box(a[0], a[1], 0.02, seat_h, a[2], a[3])
        a = R(u0, u1, 0.0, 0.26); bk.box(a[0], a[1], 0.02, back_h, a[2], a[3])
    seat.obj('channel_seat', fab, bevel=0.07, seg=3, sub=2); bk.obj('channel_back', fab, bevel=0.08, seg=3, sub=2)
    ar = MB()
    for flag, (u0, u1) in zip(arms, ((0, 0.16), (L - 0.16, L))):
        if flag:
            a = R(u0, u1, 0.0, D); ar.box(a[0], a[1], 0.02, 0.6, a[2], a[3])
    if any(arms): ar.obj('channel_arms', fab, bevel=0.07, seg=3, sub=2)
    return L, D, R, f

def wave_pendant(x, y, z, r, m, glow):
    n, rings = 72, 10; verts, faces = [], []
    for j in range(rings + 1):
        rr = r * j / rings
        for i in range(n):
            t = 2 * math.pi * i / n
            h = 0.07 * (j / rings) ** 2 * math.sin(3 * t + 0.6) + 0.03 * (j / rings) ** 2 * math.sin(5 * t)
            verts.append(T(x + rr * math.cos(t), y + h - 0.05 * (j / rings), z + rr * math.sin(t)))
    for j in range(rings):
        for i in range(n):
            a = j * n + i; b = j * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
    me = bpy.data.meshes.new('wave'); me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new('wave_pendant', me); coll().objects.link(ob); me.materials.append(m)
    for p in me.polygons: p.use_smooth = True
    md = ob.modifiers.new('sol', 'SOLIDIFY'); md.thickness = 0.008
    md = ob.modifiers.new('ss', 'SUBSURF'); md.levels = 1; md.render_levels = 2
    MB().cyl(x, z, 0.09, y - 0.06, y - 0.04, seg=48).obj('wave_glow', glow)
    MB().cyl(x, z, 0.002, y, 3.0, seg=8).obj('wave_wire', mat('wire_b', (0.05, 0.05, 0.05), 0.4))
    ld = bpy.data.lights.new('wave', 'POINT'); ld.energy = 60; ld.color = (1.0, 0.86, 0.68); ld.shadow_soft_size = 0.15
    lo = bpy.data.objects.new('wave', ld); lo.location = T(x, y - 0.1, z); coll().objects.link(lo)

def fig_tree(x, z, M, h=2.1, seed=21):
    MB().cyl(x, z, 0.24, 0.0, 0.5, r2=0.2, seg=48).obj('pot2', M['potm'], bevel=0.01, seg=2)
    MB().cyl(x, z, 0.2, 0.47, 0.48).obj('soil2', M['soil'])
    twig(x, 0.48, z, x + 0.02, h * 0.95, z, 0.022, M['bark'])
    rnd = random.Random(seed); bm = bmesh.new()
    for _ in range(110):
        yy = rnd.uniform(h * 0.45, h); spread = 0.42 * (1 - (yy - h * 0.45) / (h * 0.7)) + 0.12
        ang = rnd.uniform(0, 6.283); rad = rnd.uniform(0.05, spread)
        pos = T(x + math.cos(ang) * rad, yy, z + math.sin(ang) * rad)
        Rm = Euler((rnd.uniform(-0.9, 0.3), rnd.uniform(-0.5, 0.5), ang + rnd.uniform(-0.6, 0.6))).to_matrix().to_4x4()
        s = rnd.uniform(0.11, 0.16)
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0, matrix=Matrix.Translation(pos) @ Rm @ Matrix.Diagonal((s * 0.62, s, s * 0.06, 1)))
    me = bpy.data.meshes.new('fig'); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new('fig_leaves', me); coll().objects.link(ob); me.materials.append(M['fig'])
    for p in me.polygons: p.use_smooth = True

def build_living_v2(LED):
    M = {}
    M['boucle'] = mat('boucle2', (0.86, 0.82, 0.75), 0.95, sheen=0.7, bump=0.5, bscale=450)
    M['ivory'] = mat('pil_iv', (0.90, 0.87, 0.81), 0.9, sheen=0.5, bump=0.3, bscale=600)
    M['rust'] = mat('pil_rust', (0.36, 0.17, 0.09), 0.85, sheen=0.7, bump=0.2, bscale=800)
    M['blk'] = mat('black_v2', (0.02, 0.02, 0.022), 0.45)
    M['dwood'] = mat('dark_wood', (0.11, 0.075, 0.05), 0.4, coat=0.3)
    M['trav'] = banded('trav_v2', (0.83, 0.77, 0.68), (0.91, 0.87, 0.80), 0.45, scale=2.5, dist=10)
    M['joint'] = mat('joint', (0.25, 0.22, 0.19), 0.8)
    M['oak'] = mat('oak_flute', (0.62, 0.50, 0.38), 0.5, bump=0.1, bscale=40)
    M['tv'] = mat('tv_glass2', (0.004, 0.004, 0.005), 0.04, coat=1.0)
    M['rug'] = ramp_mat('rug_abstract', [(0.86, 0.83, 0.77), (0.80, 0.76, 0.69), (0.66, 0.62, 0.57), (0.88, 0.85, 0.79), (0.62, 0.36, 0.22), (0.86, 0.83, 0.77)], 1.0, scale=2.2, dist=6, bump=0.9, bscale=700, sheen=0.5)
    M['drape'] = mat('drape_v2', (0.56, 0.50, 0.43), 0.8, sheen=0.8, bump=0.1, bscale=500)
    M['potm'] = mat('pot_v2', (0.80, 0.76, 0.69), 0.85, bump=0.4, bscale=60)
    M['soil'] = mat('soil_v2', (0.08, 0.06, 0.04), 1.0); M['bark'] = mat('bark_v2', (0.25, 0.19, 0.13), 0.9, bump=0.5, bscale=80)
    M['fig'] = mat('fig_leaf', (0.07, 0.17, 0.05), 0.35, sss=0.15)
    M['fabric_shade'] = mat('pendant_fabric', (0.92, 0.89, 0.83), 0.9, sheen=0.4, sss=0.5)
    M['cer'] = mat('cer_v2', (0.84, 0.80, 0.73), 0.7, bump=0.2, bscale=120); M['cer2'] = mat('cer2_v2', (0.12, 0.10, 0.09), 0.35, coat=0.5)
    bk = [mat('bk_a', (0.86, 0.83, 0.76), 0.7), mat('bk_b', (0.30, 0.25, 0.20), 0.6), mat('bk_c', (0.62, 0.55, 0.45), 0.7)]
    MAR = find('counter'); PAINT = find('paint')
    clear_box(4.75, 8.58, -0.62, 4.01, keep=KEEP | {'LED_R'})
    clear_box(4.75, 8.58, -0.62, 4.01, ymax=2.6)

    # TV wall: travertine panels with thin joints, light fluted oak behind the TV, floating console
    pan, jn = MB(), MB(); xs = [5.95, 6.6, 8.0, 8.6]; ys = [0.0, 1.36, 2.72]
    for (a, b) in ((5.95, 6.55), (8.05, 8.6)):
        for j in range(2):
            pan.box(a + 0.002, b - 0.002, ys[j] + 0.002, ys[j + 1] - 0.002, 3.955, 4.0)
    pan.obj('trav_panels', M['trav'], bevel=0.002)
    for (a, b) in ((5.95, 6.55), (8.05, 8.6)):
        jn.box(a, b, 1.355, 1.365, 3.995, 4.0)
    jn.obj('joints', M['joint'])
    fl = MB(); x = 6.55
    while x < 8.05 - 0.005:
        fl.box(x + 0.003, min(x + 0.04, 8.05) - 0.003, 0.0, 2.72, 3.96, 4.0); x += 0.042
    fl.obj('oak_flutes', M['oak'], bevel=0.008, seg=3)
    MB().box(6.55, 6.56, 0.0, 2.72, 3.955, 4.0).obj('reveal_l', M['joint']); MB().box(8.04, 8.05, 0.0, 2.72, 3.955, 4.0).obj('reveal_r', M['joint'])
    MB().box(6.5, 8.1, 1.05, 1.98, 3.925, 3.958).obj('tv', M['tv'], bevel=0.004)
    MB().box(6.0, 8.55, 0.28, 0.55, 3.55, 3.955).obj('console', M['dwood'], bevel=0.006, seg=2)
    MB().box(6.05, 8.5, 0.276, 0.28, 3.6, 3.92).obj('console_led', LED, smooth=False)
    MB().box(5.97, 8.58, 2.715, 2.72, 3.97, 3.985).obj('wall_wash', LED, smooth=False)
    vase(6.25, 3.74, 0.55, 0.08, 0.36, M['cer']); vase(6.45, 3.76, 0.55, 0.055, 0.2, M['cer2'], neck=0.6)
    books(8.25, 3.74, 0.55, 3, bk, rot=0.3, seed=7)

    # ceiling: clean gypsum, black magnetic track lines in the raised field
    for xc in (5.9, 7.7):
        track_line('z', xc, -0.15, 3.5, 3.0, LED, M['blk'], spots_at=(0.3, 2.9), bars=((0.9, 1.6), (1.9, 2.5)))

    # L-shaped channel sofa (long side under the front windows, return along the side windows)
    channel_sofa(5.55, 8.5, -0.58, 0.45, '-z', M['boucle'], arms=(True, False))
    channel_sofa(7.45, 8.5, 0.45, 2.6, '+x', M['boucle'], arms=(False, True))
    for (x, z, f, m, j) in ((5.95, -0.12, (0, 1), M['rust'], -0.1), (6.55, -0.1, (0, 1), M['ivory'], 0.05), (7.2, -0.08, (0, 1), M['ivory'], -0.05),
                            (7.9, -0.1, (0, 1), M['ivory'], 0.1), (8.1, 0.9, (-1, 0), M['ivory'], 0.0), (8.1, 2.15, (-1, 0), M['rust'], 0.1)):
        pillow(x, 0.7, z, f, m, size=0.48, tilt=0.25, jit=j)

    # sculptural boucle armchair
    sofa(4.9, 5.75, 1.9, 2.75, '-x', M['boucle'], M['blk'], [M['rust']], arm=0.22, seat_n=1, armh=0.55)

    # rug, nested marble tables on dark wood, fabric wave pendant
    MB().box(5.25, 8.0, 0.0, 0.016, 0.5, 3.4).obj('rug2', M['rug'], bevel=0.008)
    MB().cyl(6.55, 1.65, 0.46, 0.34, 0.375, seg=96).obj('ct_top', MAR, bevel=0.01, seg=3)
    MB().cyl(6.55, 1.65, 0.3, 0.016, 0.34, r2=0.24, seg=96).obj('ct_base', M['dwood'], bevel=0.01, seg=2)
    MB().cyl(7.12, 2.3, 0.3, 0.27, 0.3, seg=96).obj('ct2_top', M['dwood'], bevel=0.008, seg=3)
    MB().cyl(7.12, 2.3, 0.2, 0.016, 0.27, seg=96).obj('ct2_base', M['dwood'], bevel=0.008)
    top = books(6.4, 1.55, 0.375, 3, bk, rot=0.4, seed=3)
    MB().cyl(6.75, 1.8, 0.14, 0.375, 0.43, r2=0.18, seg=64).obj('bowl', M['cer'], bevel=0.02, seg=4)
    vase(7.12, 2.3, 0.3, 0.06, 0.24, M['cer2'], neck=0.5)
    wave_pendant(6.6, 2.15, 1.7, 0.55, M['fabric_shade'], emission('wave_glow', (1.0, 0.85, 0.65), 10))

    # plants and black floor lamp
    fig_tree(5.35, -0.3, M); fig_tree(8.3, 3.45, M, h=1.6, seed=22)
    MB().cyl(5.2, 0.75, 0.13, 0.0, 0.02, seg=48).obj('fl_base', M['blk'], bevel=0.004)
    MB().cyl(5.2, 0.75, 0.01, 0.02, 1.55, seg=12).obj('fl_pole', M['blk'])
    MB().cyl(5.2, 0.75, 0.16, 1.45, 1.6, r2=0.04, seg=48).obj('fl_shade', mat('fl_shade', (0.92, 0.89, 0.83), 0.8, sss=0.5))
    ld = bpy.data.lights.new('fl', 'POINT'); ld.energy = 30; ld.color = (1.0, 0.85, 0.66); ld.shadow_soft_size = 0.08
    lo = bpy.data.objects.new('fl', ld); lo.location = T(5.2, 1.47, 0.75); coll().objects.link(lo)

    drape('x', -0.5, 5.02, 5.4, M['drape']); drape('x', -0.5, 8.1, 8.45, M['drape'])
    drape('z', 8.49, 3.2, 3.62, M['drape'])

# ======== v3 seating: clean tailored L-sofa, two lounge chairs, pouf ========
def cush(x0, x1, y0, y1, z0, z1, m, name='cush', r=0.035):
    return MB().box(x0, x1, y0, y1, z0, z1).obj(name, m, bevel=r, seg=4, sub=1)

def clean_seating(M):
    F, P1, P2, P3 = M['smooth'], M['pil_a'], M['pil_b'], M['pil_c']
    BL = M['blk']
    MB().box(5.45, 8.5, 0.07, 0.36, -0.58, 0.42).box(7.5, 8.5, 0.07, 0.36, 0.42, 3.0).obj('sofa_base', F, bevel=0.02, seg=3)
    MB().box(5.53, 8.42, 0.0, 0.07, -0.5, 0.34).box(7.58, 8.42, 0.0, 0.07, 0.34, 2.92).obj('plinth', BL)
    MB().box(5.444, 5.61, 0.07, 0.6, -0.586, 0.426).box(7.494, 8.506, 0.07, 0.6, 2.84, 3.006).obj('arms', F, bevel=0.03, seg=4)
    MB().box(5.61, 8.506, 0.36, 0.66, -0.586, -0.4).box(8.32, 8.506, 0.36, 0.66, -0.4, 2.84).obj('back_frame', F, bevel=0.02, seg=3)
    for (a, b) in ((5.62, 6.24), (6.25, 6.87), (6.88, 7.49)):
        cush(a, b, 0.36, 0.53, -0.4, 0.42, F)
    cush(7.5, 8.31, 0.36, 0.53, -0.4, 0.42, F)
    for (a, b) in ((0.43, 1.23), (1.24, 2.03), (2.04, 2.83)):
        cush(7.5, 8.31, 0.36, 0.53, a, b, F)
    for (a, b) in ((5.62, 6.24), (6.25, 6.87), (6.88, 7.49), (7.5, 8.12)):
        cush(a, b, 0.53, 0.88, -0.4, -0.2, F, 'back')
    for (a, b) in ((-0.2, 0.42), (0.43, 1.23), (1.24, 2.03), (2.04, 2.83)):
        cush(8.11, 8.31, 0.53, 0.88, a, b, F, 'back')
    for (x, m, s) in ((5.93, P2, 0.46), (6.56, P1, 0.5), (7.19, P3, 0.42), (7.8, P1, 0.5)):
        pillow(x, 0.76, -0.06, (0, 1), m, size=s, tilt=0.22)
    pillow(7.95, 0.76, 0.02, (-1, 0), P2, size=0.46, tilt=0.22, jit=0.35)
    for (z, m, s) in ((0.83, P1, 0.5), (1.63, P3, 0.42), (2.43, P2, 0.46)):
        pillow(7.98, 0.76, z, (-1, 0), m, size=s, tilt=0.22)
    MB().box(7.6, 8.4, 0.6, 0.63, 2.84, 3.02).obj('throw', M['throw'], bevel=0.012, seg=2, sub=1)
    for (z0, z1) in ((0.95, 1.8), (2.05, 2.9)):
        MB().box(4.9, 5.75, 0.08, 0.38, z0, z1).obj('ch_base', F, bevel=0.04, seg=4, sub=1)
        MB().box(4.894, 5.12, 0.38, 0.8, z0 + 0.13, z1 - 0.13).obj('ch_back', F, bevel=0.06, seg=4, sub=1)
        MB().box(4.894, 5.756, 0.3, 0.6, z0 - 0.006, z0 + 0.13).box(4.894, 5.756, 0.3, 0.6, z1 - 0.13, z1 + 0.006).obj('ch_arms', F, bevel=0.05, seg=4, sub=1)
        cush(5.12, 5.73, 0.38, 0.5, z0 + 0.13, z1 - 0.13, F, 'ch_seat')
        lg = MB()
        for (x, z) in ((4.97, z0 + 0.07), (5.68, z0 + 0.07), (4.97, z1 - 0.07), (5.68, z1 - 0.07)):
            lg.cyl(x, z, 0.014, 0.0, 0.08, seg=16)
        lg.obj('ch_legs', M['brass'], bevel=0.002)
        pillow(5.25, 0.68, (z0 + z1) / 2, (1, 0), P1 if z0 < 1 else P3, size=0.4, tilt=0.25)
    MB().cyl(6.05, 3.15, 0.3, 0.0, 0.42, seg=96).obj('pouf', M['pil_b'], bevel=0.05, seg=4)

def build_living_v3(LED):
    build_living_v2(LED)
    for ob in list(bpy.data.objects):
        if ob.name.split('.')[0] in ('channel_seat', 'channel_back', 'channel_arms', 'pillow', 'sofa_base', 'sofa_arms', 'sofa_back', 'seat', 'back_cush', 'legs'):
            bpy.data.objects.remove(ob, do_unlink=True)
    M = {
        'smooth': mat('smooth_fabric', (0.80, 0.76, 0.69), 0.78, sheen=0.35),
        'pil_a': mat('pil_sand', (0.88, 0.85, 0.79), 0.8, sheen=0.4),
        'pil_b': mat('pil_mocha', (0.47, 0.38, 0.30), 0.75, sheen=0.6),
        'pil_c': mat('pil_caramel2', (0.60, 0.43, 0.28), 0.75, sheen=0.6),
        'throw': mat('throw2', (0.47, 0.38, 0.30), 0.85, sheen=0.5, bump=0.3, bscale=300),
        'blk': mat('black_v3', (0.02, 0.02, 0.022), 0.45),
        'brass': mat('brass_v3', (0.80, 0.62, 0.36), 0.28, metal=1.0),
    }
    clean_seating(M)

# ======== v4: 3 + 3 + 1 + 1, woven fabric ========
def weave_mat(name, color, rough=0.85, sheen=0.4, scale=260.0, strength=0.35):
    m = mat(name, color, rough, sheen=sheen); nt = m.node_tree; p = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    w1 = nt.nodes.new('ShaderNodeTexWave'); w1.wave_type = 'BANDS'; w1.bands_direction = 'X'
    w2 = nt.nodes.new('ShaderNodeTexWave'); w2.wave_type = 'BANDS'; w2.bands_direction = 'Z'
    for w in (w1, w2): w.inputs['Scale'].default_value = scale; w.inputs['Distortion'].default_value = 0.6
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; nz.inputs['Detail'].default_value = 4
    mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'MULTIPLY'
    ad = nt.nodes.new('ShaderNodeMath'); ad.operation = 'ADD'
    b = nt.nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value = strength
    for w in (w1, w2): nt.links.new(tc.outputs['Object'], w.inputs['Vector'])
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    nt.links.new(w1.outputs['Fac'], mx.inputs[0]); nt.links.new(w2.outputs['Fac'], mx.inputs[1])
    nt.links.new(mx.outputs[0], ad.inputs[0]); nt.links.new(nz.outputs['Fac'], ad.inputs[1])
    nt.links.new(ad.outputs[0], b.inputs['Height']); nt.links.new(b.outputs['Normal'], p.inputs['Normal'])
    return m

def tidy_sofa(x0, x1, z0, z1, back, F, BL, pmats, seats=3):
    """Tailored sofa: recessed plinth, slim square arms, firm seat and back cushions."""
    L, D, R, f = frame(x0, x1, z0, z1, back)
    arm = 0.16
    a = R(0.006, L - 0.006, 0.006, D - 0.006); MB().box(a[0], a[1], 0.07, 0.36, a[2], a[3]).obj('t_base', F, bevel=0.02, seg=3)
    a = R(0.08, L - 0.08, 0.08, D - 0.08); MB().box(a[0], a[1], 0.0, 0.07, a[2], a[3]).obj('t_plinth', BL)
    ar = MB()
    for (u0, u1) in ((0, arm), (L - arm, L)):
        a = R(u0, u1, 0, D); ar.box(a[0], a[1], 0.07, 0.6, a[2], a[3])
    ar.obj('t_arms', F, bevel=0.03, seg=4)
    a = R(arm, L - arm, 0, 0.18); MB().box(a[0], a[1], 0.36, 0.64, a[2], a[3]).obj('t_back', F, bevel=0.02, seg=3)
    w = (L - 2 * arm) / seats
    for i in range(seats):
        u0, u1 = arm + i * w + 0.006, arm + (i + 1) * w - 0.006
        a = R(u0, u1, 0.18, D - 0.004); cush(a[0], a[1], 0.36, 0.53, a[2], a[3], F, 't_seat')
        a = R(u0, u1, 0.17, 0.37); cush(a[0], a[1], 0.53, 0.88, a[2], a[3], F, 't_backc')
    order = [(arm + 0.3, pmats[0], 0.5, -0.12), (arm + 0.62, pmats[1], 0.42, 0.06), (L - arm - 0.62, pmats[1], 0.42, -0.06), (L - arm - 0.3, pmats[0], 0.5, 0.12)]
    for (u, m, s, j) in order:
        a = R(u, u, 0.45, 0.45); pillow(a[0], 0.77, a[2], f, m, size=s, tilt=0.2, jit=j)

def build_living_v4(LED):
    build_living_v2(LED)
    for ob in list(bpy.data.objects):
        if ob.name.split('.')[0] in ('channel_seat', 'channel_back', 'channel_arms', 'pillow', 'sofa_base', 'sofa_arms', 'sofa_back', 'seat', 'back_cush', 'legs'):
            bpy.data.objects.remove(ob, do_unlink=True)
    F = weave_mat('weave_ivory', (0.80, 0.76, 0.69))
    P1 = weave_mat('weave_mocha', (0.42, 0.34, 0.27), sheen=0.6, scale=320)
    P2 = weave_mat('weave_sand', (0.88, 0.84, 0.77), scale=320)
    P3 = weave_mat('weave_caramel', (0.58, 0.42, 0.28), sheen=0.6, scale=320)
    BL = mat('black_v4', (0.02, 0.02, 0.022), 0.45); BR = mat('brass_v4', (0.80, 0.62, 0.36), 0.28, metal=1.0)
    tidy_sofa(5.62, 7.92, -0.58, 0.38, '-z', F, BL, [P1, P2])          # 3-seater facing the TV
    tidy_sofa(7.54, 8.5, 0.62, 2.92, '+x', F, BL, [P1, P2])            # 3-seater along the side windows
    for (z0, z1, pm) in ((0.95, 1.8, P3), (2.07, 2.92, P3)):              # two armchairs
        MB().box(4.906, 5.744, 0.08, 0.38, z0 + 0.006, z1 - 0.006).obj('ch_base', F, bevel=0.03, seg=4)
        MB().box(4.9, 5.12, 0.38, 0.8, z0 + 0.13, z1 - 0.13).obj('ch_back', F, bevel=0.04, seg=4, sub=1)
        MB().box(4.9, 5.75, 0.3, 0.6, z0, z0 + 0.13).box(4.9, 5.75, 0.3, 0.6, z1 - 0.13, z1).obj('ch_arms', F, bevel=0.035, seg=4)
        cush(5.12, 5.74, 0.38, 0.5, z0 + 0.13, z1 - 0.13, F, 'ch_seat')
        lg = MB()
        for (x, z) in ((4.97, z0 + 0.07), (5.68, z0 + 0.07), (4.97, z1 - 0.07), (5.68, z1 - 0.07)):
            lg.cyl(x, z, 0.014, 0.0, 0.08, seg=16)
        lg.obj('ch_legs', BR, bevel=0.002)
        pillow(5.26, 0.69, (z0 + z1) / 2, (1, 0), pm, size=0.4, tilt=0.22)
