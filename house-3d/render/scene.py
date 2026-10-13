import bpy, bmesh, math, sys, json
from mathutils import Vector
args = json.loads(sys.argv[sys.argv.index('--') + 1])
SP = args['sp']

def T(x, y, z):  # three.js (x, y-up, z) -> Blender (x, -z, y-up)
    return Vector((x, -z, y))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SP + '/render/house.glb')
sc = bpy.context.scene

# ---------- materials ----------
def base(name):
    return name.split('.')[0]
def principled(mat):
    return next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
def new_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; return m

glass = new_mat('GLASS_R'); nt = glass.node_tree; nt.nodes.clear()
o = nt.nodes.new('ShaderNodeOutputMaterial'); mx = nt.nodes.new('ShaderNodeMixShader'); tr = nt.nodes.new('ShaderNodeBsdfTransparent'); gl = nt.nodes.new('ShaderNodeBsdfGlossy')
gl.inputs['Roughness'].default_value = 0.0; mx.inputs[0].default_value = 0.12
nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(gl.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], o.inputs['Surface'])

sheer = new_mat('SHEER'); nt = sheer.node_tree; nt.nodes.clear()
o = nt.nodes.new('ShaderNodeOutputMaterial'); m1 = nt.nodes.new('ShaderNodeMixShader'); m2 = nt.nodes.new('ShaderNodeMixShader')
tp = nt.nodes.new('ShaderNodeBsdfTransparent'); df = nt.nodes.new('ShaderNodeBsdfDiffuse'); tl = nt.nodes.new('ShaderNodeBsdfTranslucent')
df.inputs['Color'].default_value = (0.93, 0.89, 0.82, 1); tl.inputs['Color'].default_value = (0.98, 0.94, 0.86, 1)
m2.inputs[0].default_value = 0.5; nt.links.new(df.outputs[0], m2.inputs[1]); nt.links.new(tl.outputs[0], m2.inputs[2])
m1.inputs[0].default_value = 0.74; nt.links.new(tp.outputs[0], m1.inputs[1]); nt.links.new(m2.outputs[0], m1.inputs[2])
nt.links.new(m1.outputs[0], o.inputs['Surface'])

def emis(name, color, strength):
    m = new_mat(name); nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = color; e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], o.inputs['Surface']); return m
LED = emis('LED_R', (1.0, 0.86, 0.70, 1), 14)
SHADE = emis('SHADE_R', (1.0, 0.82, 0.6, 1), 4)
SPOT = emis('SPOT_R', (1.0, 0.86, 0.7, 1), 30)

for m in list(bpy.data.materials):
    if not m.use_nodes: continue
    b = base(m.name); p = principled(m)
    if p is None: continue
    m.surface_render_method = 'DITHERED' if hasattr(m, 'surface_render_method') else None
    if b in ('paint', 'cap', 'ceiling'):
        p.inputs['Roughness'].default_value = 0.85
    if b in ('floor', 'counter', 'bathWall'):
        p.inputs['Coat Weight'].default_value = 0.35; p.inputs['Coat Roughness'].default_value = 0.05
    if b == 'mirror':
        p.inputs['Roughness'].default_value = 0.01
    if b == 'water':
        p.inputs['Transmission Weight'].default_value = 1.0; p.inputs['Roughness'].default_value = 0.0

for ob in list(sc.objects):
    if ob.type != 'MESH': continue
    for slot in ob.material_slots:
        if not slot.material: continue
        b = base(slot.material.name)
        if b == 'glass': slot.material = glass
        elif b == 'led': slot.material = LED
        elif b == 'shade': slot.material = SHADE

# ---------- soft edges ----------
for ob in list(sc.objects):
    if ob.type != 'MESH' or not ob.material_slots or not ob.material_slots[0].material: continue
    b = base(ob.material_slots[0].material.name)
    if b in ('GLASS_R', 'LED_R', 'outdoor', 'ground', 'floor', 'bedFloor', 'bathFloor', 'rug'): continue
    d = ob.dimensions
    if min(d) < 0.012: continue
    soft = b in ('fabric', 'fabric2', 'bedding', 'kids')
    md = ob.modifiers.new('bevel', 'BEVEL'); md.width = 0.035 if soft else 0.004; md.segments = 4 if soft else 2
    md.limit_method = 'ANGLE'; md.use_clamp_overlap = True

# ---------- helpers for added design elements ----------
col = bpy.data.collections.new('design'); sc.collection.children.link(col)
PAINT = next(m for m in bpy.data.materials if base(m.name) == 'paint')
METAL = next(m for m in bpy.data.materials if base(m.name) == 'metal')
BLACK = next(m for m in bpy.data.materials if base(m.name) == 'black')
def box(x0, x1, y0, y1, z0, z1, mat, name='b'):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); col.objects.link(ob)
    a, c = T(min(x0, x1), min(y0, y1), max(z0, z1)), T(max(x0, x1), max(y0, y1), min(z0, z1))
    ob.location = (a + c) / 2; ob.scale = (c - a)
    ob.data.materials.append(mat); return ob

def cove(x0, x1, z0, z1, w=0.42, drop=2.72):
    """Gypsum band around the room edge with a hidden LED slot facing the raised centre."""
    ix0, ix1, iz0, iz1 = x0 + w, x1 - w, z0 + w, z1 - w
    for (a0, a1, b0, b1) in [(x0, x1, z0, iz0), (x0, x1, iz1, z1), (x0, ix0, iz0, iz1), (ix1, x1, iz0, iz1)]:
        box(a0, a1, drop, 3.0, b0, b1, PAINT, 'cove')
    # lip below the slot, LED tucked behind it
    lip, t = 0.12, 0.012
    for (a0, a1, b0, b1, l0, l1, m0, m1) in [
        (ix0, ix1, drop, drop + 0.1, iz0, iz0 + lip, iz0 + 0.02, iz0 + 0.03),
        (ix0, ix1, drop, drop + 0.1, iz1 - lip, iz1, iz1 - 0.03, iz1 - 0.02)]:
        box(a0, a1, b0, b1, l0, l1, PAINT, 'lip'); box(a0 + 0.05, a1 - 0.05, drop + 0.1, drop + 0.115, m0, m1, LED, 'cove_led')
    for (a0, a1, l0, l1, m0, m1) in [(ix0, ix0 + lip, iz0, iz1, ix0 + 0.02, ix0 + 0.03), (ix1 - lip, ix1, iz0, iz1, ix1 - 0.03, ix1 - 0.02)]:
        box(a0, a1, drop, drop + 0.1, iz0, iz1, PAINT, 'lip'); box(m0, m1, drop + 0.1, drop + 0.115, iz0 + 0.05, iz1 - 0.05, LED, 'cove_led')

def spots(pts, y=2.715, power=22):
    for (x, z) in pts:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=0.01, location=T(x, y - 0.004, z))
        c = bpy.context.object; c.data.materials.append(SPOT)
        for o in c.users_collection: o.objects.unlink(c)
        col.objects.link(c)
        ld = bpy.data.lights.new('spot', 'SPOT'); ld.energy = power; ld.spot_size = math.radians(70); ld.spot_blend = 0.6
        ld.color = (1.0, 0.85, 0.68); ld.shadow_soft_size = 0.03
        lo = bpy.data.objects.new('spot', ld); lo.location = T(x, y - 0.02, z); col.objects.link(lo)  # points down (-Z) by default

def curtain(axis, c, a0, a1, top=2.7, waves=None, amp=0.05):
    n = max(8, int((a1 - a0) / 0.07)); rows = 2
    verts, faces = [], []
    for j, y in enumerate((0.02, top)):
        for i in range(n + 1):
            u = a0 + (a1 - a0) * i / n; off = amp * math.sin(i / n * (a1 - a0) / 0.2 * 2 * math.pi)
            verts.append(T(u, y, c + off) if axis == 'x' else T(c + off, y, u))
    for i in range(n): faces.append((i, i + 1, n + 1 + i + 1, n + 1 + i))
    me = bpy.data.meshes.new('curtain'); me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new('curtain', me); col.objects.link(ob); ob.data.materials.append(sheer)
    for p in me.polygons: p.use_smooth = True
    box(a0 - 0.05, a1 + 0.05, top, top + 0.04, c - 0.04, c + 0.04, BLACK, 'track')

# ---------- modern luxury upgrades ----------
LUX = args.get('lux', False)
if LUX:
    sys.path.insert(0, SP + '/render'); import design
cove(5.0, 8.6, -0.64, 4.0)                    # living room
cove(2.77, 7.05, 7.96, 11.39)                # master bedroom
cove(0.0, 3.85, 3.5, 7.0, w=0.38)            # hall
if LUX:
    if args.get('v4'): design.build_living_v4(LED); design.kitchen_extras(LED)
    elif args.get('v3'): design.build_living_v3(LED); design.kitchen_extras(LED)
    elif args.get('v2'): design.build_living_v2(LED); design.kitchen_extras(LED)
    else: design.build_living(LED); design.kitchen_extras(LED); design.build_master(LED, sheer)
else:
    spots([(6.0, 3.3), (7.6, 3.3), (5.7, -0.1), (8.0, -0.1)])
    spots([(1.2, 1.3), (2.4, 1.3), (3.4, 1.3), (1.2, 2.2), (2.4, 2.2)], y=2.985, power=18)   # kitchen (flat ceiling)
if not LUX: spots([(4.0, 8.5), (5.6, 8.5)])
spots([(1.0, 4.6), (2.6, 4.6), (1.0, 6.0), (2.6, 6.0)], y=2.985, power=26)   # hall
spots([(6.6, 6.3), (7.5, 6.3), (8.2, 6.7), (7.0, 4.9), (8.2, 4.9)], y=2.985, power=20)  # bathrooms
curtain('x', -0.585, 5.05, 8.45)                          # living, front windows
curtain('z', 8.545, -0.6, 1.5); curtain('z', 8.545, 2.4, 3.6)
curtain('x', 11.335, 2.85, 7.0, top=2.7)                 # full-width curtain wall behind the master bed
# linear pendant over the peninsula
box(4.05, 4.13, 1.62, 1.66, 0.35, 1.75, METAL, 'pendant'); box(4.065, 4.115, 1.6, 1.62, 0.38, 1.72, LED, 'pendant_led')
for zz in (0.45, 1.65): box(4.087, 4.093, 1.66, 3.0, zz - 0.003, zz + 0.003, METAL, 'wire')

# ---------- world, sun, window portals ----------
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
bg = world.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.62, 0.74, 0.92, 1); bg.inputs['Strength'].default_value = 1.6
if args.get('mood') == 'evening':
    bg.inputs['Color'].default_value = (0.05, 0.08, 0.16, 1); bg.inputs['Strength'].default_value = 0.5
if args.get('hdri'):
    wn = world.node_tree; env = wn.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(SP + '/render/' + args['hdri'] + '.exr')
    mp = wn.nodes.new('ShaderNodeMapping'); tc = wn.nodes.new('ShaderNodeTexCoord'); mp.inputs['Rotation'].default_value[2] = math.radians(args.get('hdri_rot', 0))
    wn.links.new(tc.outputs['Generated'], mp.inputs['Vector']); wn.links.new(mp.outputs['Vector'], env.inputs['Vector']); wn.links.new(env.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = args.get('hdri_str', 1.5)
sd = bpy.data.lights.new('sun', 'SUN'); sd.energy = 0.0 if args.get('mood') == 'evening' else 4.2; sd.angle = math.radians(1.2); sd.color = (1.0, 0.93, 0.84)
so = bpy.data.objects.new('sun', sd); sc.collection.objects.link(so)
direction = (T(3.3, 0, 5.4) - T(3.3 - 7, 15, 5.4 + 9)).normalized()
direction = (T(3.3, 0, 5.4) - T(3.3 + 9, 10, 5.4 - 7)).normalized() if args.get('sun') == 'ne' else direction
so.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
def portal(axis, c, a0, a1, s0, s1, inward):
    ld = bpy.data.lights.new('portal', 'AREA'); ld.shape = 'RECTANGLE'; ld.cycles.is_portal = True
    ld.size = a1 - a0; ld.size_y = s1 - s0
    lo = bpy.data.objects.new('portal', ld); sc.collection.objects.link(lo)
    lo.location = T((a0 + a1) / 2, (s0 + s1) / 2, c) if axis == 'x' else T(c, (s0 + s1) / 2, (a0 + a1) / 2)
    tgt = lo.location + (T(0, 0, inward) if axis == 'x' else T(inward, 0, 0))
    lo.rotation_euler = (tgt - lo.location).to_track_quat('-Z', 'Y').to_euler()
portal('x', -0.765, 5.05, 8.45, 0.45, 2.4, 1); portal('z', 8.725, -0.55, 1.45, 0.45, 2.4, -1); portal('z', 8.725, 2.45, 3.55, 0.45, 2.4, -1)
portal('x', -0.125, 1.81, 2.97, 1.1, 2.2, 1); portal('x', 11.515, 4.35, 5.55, 1.0, 2.3, -1); portal('x', 11.515, 0.25, 1.45, 1.0, 2.3, -1)
portal('z', 7.175, 8.16, 9.61, 0.0, 2.3, -1)

# ---------- camera & render ----------
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = args.get('lens', 20); cam_d.sensor_width = 36
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
eye, look = T(*args['eye']), T(*args['look'])
cam.location = eye; cam.rotation_euler = (look - eye).to_track_quat('-Z', 'Y').to_euler()
cam_d.shift_y = args.get('shift', 0)
if args.get('dof'):
    cam_d.dof.use_dof = True; cam_d.dof.focus_distance = (look - eye).length * args.get('focus', 0.55); cam_d.dof.aperture_fstop = args['dof']

sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = args.get('samples', 64)
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception as e: print('denoiser', e)
sc.cycles.sample_clamp_indirect = 8; sc.cycles.max_bounces = 8; sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
sc.render.threads_mode = 'FIXED'; sc.render.threads = 4
sc.render.resolution_x, sc.render.resolution_y = args.get('res', [1600, 900]); sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'AgX'
for look_name in ('AgX - Medium High Contrast', 'Medium High Contrast'):
    try: sc.view_settings.look = look_name; break
    except Exception: pass
sc.view_settings.exposure = args.get('exposure', 0.0)
sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
sc.render.filepath = args['out']
bpy.ops.render.render(write_still=True)
print('DONE', args['out'])
