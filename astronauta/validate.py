"""Structural checks for the generated asset; not a Khronos certification."""
import json, math, struct, io, sys
from pathlib import Path
p=Path(__file__).with_name('astronauta.glb').read_bytes()
magic,version,size=struct.unpack_from('<III',p)
assert magic==0x46546c67 and version==2 and size==len(p)
n,t=struct.unpack_from('<II',p,12); assert t==0x4e4f534a
d=json.loads(p[20:20+n]); length,kind=struct.unpack_from('<II',p,20+n)
assert kind==0x004e4942
b=p[28+n:]; assert len(b)==length
def read(i):
    a=d['accessors'][i]; v=d['bufferViews'][a['bufferView']]
    width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
    fmt={5126:'f',5123:'H',5125:'I'}[a['componentType']]
    count=a['count']*width; offset=v.get('byteOffset',0)+a.get('byteOffset',0)
    assert offset+count*struct.calcsize(fmt)<=v.get('byteOffset',0)+v['byteLength']<=len(b)
    values=struct.unpack_from('<'+fmt*count,b,offset)
    assert all(math.isfinite(x) for x in values)
    return values
for i in range(len(d['accessors'])): read(i)
skin=d['skins'][0]; count=len(skin['joints'])
for prim in d['meshes'][0]['primitives']:
    attrs=prim['attributes']; nv=d['accessors'][attrs['POSITION']]['count']
    assert all(d['accessors'][i]['count']==nv for i in attrs.values())
    assert max(read(prim['indices']))<nv
    assert max(read(attrs['JOINTS_0']))<count
    w=read(attrs['WEIGHTS_0'])
    assert all(abs(sum(w[i:i+4])-1)<1e-5 for i in range(0,len(w),4))
    normals=read(attrs['NORMAL'])
    assert all(abs(sum(x*x for x in normals[i:i+3])-1)<1e-3 for i in range(0,len(normals),3))
    assert 'TEXCOORD_0' in attrs
world=[]
parents={c:i for i,node in enumerate(d['nodes']) for c in node.get('children',[])}
for i in skin['joints']:
    t=d['nodes'][i]['translation']; parent=parents.get(i)
    world.append([t[k]+(world[parent][k] if parent is not None else 0) for k in range(3)])
mat=read(skin['inverseBindMatrices'])
for i,t in enumerate(world):
    assert all(abs(t[k]+mat[i*16+12+k])<1e-6 for k in range(3))
for anim in d['animations']:
    for s in anim['samplers']:
        times=read(s['input']); assert all(a<b for a,b in zip(times,times[1:]))
        assert d['accessors'][s['input']]['count']==d['accessors'][s['output']]['count']
sys.path.insert(0,'/tmp/astronauta-tools')
from PIL import Image
assert len(d['images'])==4
for image in d['images']:
    v=d['bufferViews'][image['bufferView']];offset=v['byteOffset']
    im=Image.open(io.BytesIO(b[offset:offset+v['byteLength']]));im.verify()
for material in d['materials']:
    for key in ['baseColorTexture','metallicRoughnessTexture']:
        tex=material['pbrMetallicRoughness'].get(key)
        if tex:assert 0<=tex['index']<len(d['textures'])
cloth=next(p for p in d['meshes'][0]['primitives'] if p['material']==0)
xyz=read(cloth['attributes']['POSITION'])
vertices=list(zip(xyz[::3],xyz[1::3],xyz[2::3]))
def front_depth(ymin,ymax):
    return max(z for x,y,z in vertices if abs(x)<.03 and ymin<=y<=ymax)
belly=front_depth(1.00,1.10);upper_chest=front_depth(1.33,1.38);lower_abdomen=front_depth(.73,.78)
assert belly-upper_chest>.09, 'Belly profile must protrude beyond upper chest.'
assert belly-lower_abdomen>.10, 'Lower abdomen must curve back into the hips.'
visor=next(p for p in d['meshes'][0]['primitives'] if p['material']==1)
xyz=read(visor['attributes']['POSITION']);rim_gaps=[]
for x,y,z in zip(xyz[::3],xyz[1::3],xyz[2::3]):
    boundary=(abs(x)/.379)**(2/.90)+(abs(y-1.797)/.313)**(2/.90)
    if boundary>.999:
        shell_z=-.028+.372*math.sqrt(max(.001,1-(x/.424)**2-((y-1.80)/.386)**2))
        rim_gaps.append(z-shell_z)
assert rim_gaps and -.003<min(rim_gaps) and max(rim_gaps)<.035, 'Visor perimeter must follow the helmet shell.'
print(f'Volume regression: belly={belly:.3f}, upper chest={upper_chest:.3f}, lower abdomen={lower_abdomen:.3f}; visor-shell gap <= {max(rim_gaps):.3f}.')
print('PASS: GLB chunks, buffer bounds, finite values, mesh indices, normalized normals, UVs, embedded PNG textures, skin weights, inverse bind matrices and animation tracks.')
