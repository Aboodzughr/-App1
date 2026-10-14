"""GLB -> SketchUp-friendly Collada (.dae, Z-up, metres, baked texture tiling) + OBJ."""
import bpy, bmesh, os, sys, re
import numpy as np
import collada
from collada import material, geometry, scene, source, asset
SP = sys.argv[sys.argv.index('--') + 1]
OUT = SP + '/sketchup/house_sketchup/'
os.makedirs(OUT + 'textures', exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SP + '/render/house.glb')
for ob in list(bpy.context.scene.objects):   # drop the outdoor ground plane
    if ob.type == 'MESH' and ob.data.materials and ob.data.materials[0] and ob.data.materials[0].name.split('.')[0] == 'ground':
        bpy.data.objects.remove(ob, do_unlink=True)

# --- bake texture-transform (tiling) into UVs, and find each material's image / colour ---
matinfo = {}
for m in bpy.data.materials:
    if not m.node_tree: continue
    nt = m.node_tree
    p = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    img = next((n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image), None)
    mp = next((n for n in nt.nodes if n.type == 'MAPPING'), None)
    col = tuple(p.inputs['Base Color'].default_value) if p else (0.8, 0.8, 0.8, 1)
    alpha = p.inputs['Alpha'].default_value if p else 1.0
    xf = None
    if mp:
        L = mp.inputs['Location'].default_value; S = mp.inputs['Scale'].default_value
        xf = (S[0], S[1], L[0], L[1])
    matinfo[m.name] = dict(img=img.image if img else None, col=col, alpha=alpha, xf=xf)

for ob in bpy.context.scene.objects:
    if ob.type != 'MESH' or not ob.data.uv_layers: continue
    me = ob.data
    if not me.materials or not me.materials[0]: continue
    info = matinfo.get(me.materials[0].name)
    if not info or not info['xf']: continue
    sx, sy, lx, ly = info['xf']
    uv = me.uv_layers.active.data
    arr = np.empty(len(uv) * 2); uv.foreach_get('uv', arr); arr = arr.reshape(-1, 2)
    arr[:, 0] = arr[:, 0] * sx + lx; arr[:, 1] = arr[:, 1] * sy + ly
    uv.foreach_set('uv', arr.ravel())
    info['xf_done'] = True
# tiling is now in the UVs: neutralise the mapping nodes so OBJ does not scale twice
for m in bpy.data.materials:
    for n in (m.node_tree.nodes if m.node_tree else []):
        if n.type == 'MAPPING':
            n.inputs['Location'].default_value = (0, 0, 0); n.inputs['Scale'].default_value = (1, 1, 1); n.inputs['Rotation'].default_value = (0, 0, 0)

# --- save textures as PNG ---
texfile = {}
for name, info in matinfo.items():
    im = info['img']
    if im is None: continue
    if im.name not in texfile:
        fn = re.sub(r'[^A-Za-z0-9_]+', '_', im.name) + '.png'
        im.filepath_raw = OUT + 'textures/' + fn; im.file_format = 'PNG'; im.save()
        texfile[im.name] = 'textures/' + fn

for im in bpy.data.images:   # every image, so the OBJ/MTL can reference them too
    if im.name not in texfile and im.size[0] > 0:
        fn = re.sub(r'[^A-Za-z0-9_]+', '_', im.name) + '.png'
        im.filepath_raw = OUT + 'textures/' + fn; im.file_format = 'PNG'; im.save(); texfile[im.name] = 'textures/' + fn
# --- build collada ---
mesh = collada.Collada()
mesh.assetInfo.upaxis = asset.UP_AXIS.Z_UP
mesh.assetInfo.unitmeter = 1.0; mesh.assetInfo.unitname = 'meter'
cmats = {}
def cmat(name):
    if name in cmats: return cmats[name]
    info = matinfo.get(name, dict(img=None, col=(0.8, 0.8, 0.8, 1), alpha=1))
    sid = 'm%d' % len(cmats)
    if info['img'] is not None:
        im = collada.material.CImage(sid + '_img', texfile[info['img'].name]); mesh.images.append(im)
        surf = material.Surface(sid + '_surf', im); samp = material.Sampler2D(sid + '_samp', surf)
        mapp = material.Map(samp, 'UVSET0')
        eff = material.Effect(sid + '_fx', [surf, samp], 'lambert', diffuse=mapp, transparency=info['alpha'])
    else:
        c = info['col']; eff = material.Effect(sid + '_fx', [], 'lambert', diffuse=(c[0], c[1], c[2], 1.0), transparency=info['alpha'])
    safe = re.sub(r'[^A-Za-z0-9_]+', '_', name)
    mat = material.Material(sid, safe, eff)
    mesh.effects.append(eff); mesh.materials.append(mat); cmats[name] = mat
    return mat

groups = {'House': [], 'Ceilings': []}; dg = bpy.context.evaluated_depsgraph_get(); count = 0
def top(o):
    while o.parent: o = o.parent
    return 'Ceilings' if o.name.startswith('Ceilings') else 'House'
for ob in bpy.context.scene.objects:
    if ob.type != 'MESH': continue
    me = ob.evaluated_get(dg).to_mesh()
    me.transform(ob.matrix_world); me.calc_loop_triangles()
    if not me.loop_triangles: continue
    co = np.array([v.co[:] for v in me.vertices], dtype=np.float32)
    tris = me.loop_triangles
    vi = np.array([t.vertices[:] for t in tris], dtype=np.int32)
    li = np.array([t.loops[:] for t in tris], dtype=np.int32)
    nrm = np.array([t.normal[:] for t in tris], dtype=np.float32)
    has_uv = bool(me.uv_layers)
    if has_uv:
        uvd = np.empty(len(me.loops) * 2, dtype=np.float32); me.uv_layers.active.data.foreach_get('uv', uvd); uvd = uvd.reshape(-1, 2)
    gid = 'g%d' % count; count += 1
    srcs = [source.FloatSource(gid + '_v', co.ravel(), ('X', 'Y', 'Z')), source.FloatSource(gid + '_n', nrm.ravel(), ('X', 'Y', 'Z'))]
    if has_uv: srcs.append(source.FloatSource(gid + '_t', uvd.ravel(), ('S', 'T')))
    g = geometry.Geometry(mesh, gid, re.sub(r'[^A-Za-z0-9_]+', '_', ob.name), srcs)
    il = source.InputList(); il.addInput(0, 'VERTEX', '#' + gid + '_v'); il.addInput(1, 'NORMAL', '#' + gid + '_n')
    if has_uv: il.addInput(2, 'TEXCOORD', '#' + gid + '_t', set='0')
    mname = me.materials[0].name if me.materials and me.materials[0] else 'default'
    mat = cmat(mname)
    nidx = np.repeat(np.arange(len(tris), dtype=np.int32), 3).reshape(-1, 3)
    cols = [vi, nidx] + ([li] if has_uv else [])
    idx = np.stack(cols, axis=2).ravel()
    tset = g.createTriangleSet(idx, il, mat.id + '_sym'); g.primitives.append(tset); mesh.geometries.append(g)
    mn = scene.MaterialNode(mat.id + '_sym', mat, inputs=[('UVSET0', 'TEXCOORD', '0')])
    groups[top(ob)].append(scene.Node(gid + '_node', children=[scene.GeometryNode(g, [mn])]))
    ob.evaluated_get(dg).to_mesh_clear()
sc = scene.Scene('house', [scene.Node(k, children=v) for k, v in groups.items() if v])
print('groups', {k: len(v) for k, v in groups.items()})
mesh.scenes.append(sc); mesh.scene = sc
mesh.write(OUT + 'house.dae')
print('DAE objects', count, 'materials', len(cmats), 'textures', len(texfile))
# OBJ (with the same baked UVs) for SketchUp 2021+ / other apps
bpy.ops.wm.obj_export(filepath=OUT + 'house.obj', path_mode='RELATIVE', export_materials=True, forward_axis='Y', up_axis='Z')
mtl = open(OUT + 'house.mtl').read()
mtl = re.sub(r'(map_\w+(?: -\S+(?: [-0-9.]+)*)*) \S*?([A-Za-z0-9_]+\.png)', lambda m: m.group(1) + ' textures/' + m.group(2), mtl)
open(OUT + 'house.mtl', 'w').write(mtl)
print('OBJ done')
