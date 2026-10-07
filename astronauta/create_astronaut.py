"""Generate a self-contained, skinned glTF 2.0 astronaut. Pillow is used for embedded PBR textures."""
import json, math, struct
from pathlib import Path

OUT = Path(__file__).parent
nodes=[]; joints=[]; rest=[]; names={}; groups={}; blob=bytearray(); views=[]; accessors=[]
def bone(name, pos, parent=None):
    i=len(nodes); names[name]=i; joints.append(i); rest.append(pos)
    p=rest[parent] if parent is not None else (0,0,0)
    nodes.append(dict(name=name,translation=[pos[k]-p[k] for k in range(3)]))
    if parent is not None: nodes[parent].setdefault('children',[]).append(i)
    return i
root=bone('Root',(0,0,0)); hips=bone('Hips',(0,.91,0),root)
spine=bone('Spine',(0,1.10,0),hips); chest=bone('Chest',(0,1.34,0),spine)
neck=bone('Neck',(0,1.43,0),chest); head=bone('Head',(0,1.73,0),neck)
for side,s in [('L',1),('R',-1)]:
    clav=bone('Clavicle.'+side,(s*.21,1.29,0),chest)
    upper=bone('UpperArm.'+side,(s*.32,1.29,0),clav)
    lower=bone('Forearm.'+side,(s*.58,1.29,0),upper)
    hand=bone('Hand.'+side,(s*.82,1.29,0),lower)
    for f,z in [('Thumb',.095),('Index',.062),('Middle',.02),('Ring',-.025),('Little',-.068)]:
        p=hand
        for n in range(3): p=bone(f+str(n+1)+'.'+side,(s*(.88+n*.044),1.28-(.055 if f=='Thumb' else 0),z),p)
    thigh=bone('Thigh.'+side,(s*.17,.91,0),hips)
    shin=bone('Shin.'+side,(s*.19,.55,0),thigh)
    foot=bone('Foot.'+side,(s*.20,.20,0),shin)
    bone('Toes.'+side,(s*.20,.10,.14),foot)

from geometry_v2 import build
materials, texture_pngs = build(globals())

def acc(data,kind,component=5126):
    while len(blob)%4: blob.append(0)
    fmt={5126:'f',5123:'H',5125:'I'}[component]; width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[kind]
    packed=struct.pack('<'+fmt*len(data),*data); vi=len(views)
    views.append(dict(buffer=0,byteOffset=len(blob),byteLength=len(packed))); blob.extend(packed)
    a=dict(bufferView=vi,componentType=component,count=len(data)//width,type=kind)
    if kind in ['SCALAR','VEC3']:
        a['min']=[min(data[k::width]) for k in range(width)]; a['max']=[max(data[k::width]) for k in range(width)]
    accessors.append(a); return len(accessors)-1
primitives=[]
for mat,g in groups.items():
    primitives.append(dict(attributes=dict(POSITION=acc(g['p'],'VEC3'),NORMAL=acc(g['n'],'VEC3'),TEXCOORD_0=acc(g['uv'],'VEC2'),JOINTS_0=acc(g['j'],'VEC4',5123),WEIGHTS_0=acc(g['w'],'VEC4')),indices=acc(g['idx'],'SCALAR',5125),material=mat))
ibm=[]
for x,y,z in rest: ibm.extend([1,0,0,0,0,1,0,0,0,0,1,0,-x,-y,-z,1])
skin=dict(name='Astronaut humanoid',joints=joints,skeleton=root,inverseBindMatrices=acc(ibm,'MAT4'))
meshnode=len(nodes); nodes.append(dict(name='Astronaut suit',mesh=0,skin=0))
animations=[]
def animation(name,tracks):
    samplers=[]; channels=[]
    for node,path,times,values in tracks:
        samplers.append(dict(input=acc(times,'SCALAR'),output=acc(values,'VEC4' if path=='rotation' else 'VEC3'),interpolation='LINEAR'))
        channels.append(dict(sampler=len(samplers)-1,target=dict(node=node,path=path)))
    animations.append(dict(name=name,samplers=samplers,channels=channels))
def rot(axis,angles):
    result=[]
    for a in angles:
        q=[0,0,0,math.cos(a/2)]; q[axis]=math.sin(a/2); result.extend(q)
    return result
animation('Float',[(root,'translation',[0,1,2,3,4],[0,0,0,0,.035,0,0,.06,0,0,.035,0,0,0,0]),(head,'rotation',[0,1,2,3,4],rot(1,[0,.10,0,-.10,0]))])
animation('Wave',[(names['Forearm.L'],'rotation',[0,.5,1,1.5,2,2.5,3],rot(2,[0,.8,1.2,.8,1.2,.8,0]))])
tracks=[]
for side,s in [('L',1),('R',-1)]:
    tracks.append((names['UpperArm.'+side],'rotation',[0,.5,1,1.5,2],rot(2,[-s*1.25]*5)))
    tracks.append((names['Thigh.'+side],'rotation',[0,.5,1,1.5,2],rot(0,[s*.4,0,-s*.4,0,s*.4])))
    tracks.append((names['Shin.'+side],'rotation',[0,.5,1,1.5,2],rot(0,[0,.5 if s==1 else 0,0,.5 if s==-1 else 0,0])))
animation('WalkInPlace',tracks)
images=[]
for i,png_data in enumerate(texture_pngs):
    while len(blob)%4:blob.append(0)
    view=len(views);views.append(dict(buffer=0,byteOffset=len(blob),byteLength=len(png_data)));blob.extend(png_data)
    images.append(dict(name=['Textile color','Textile weave normal','Textile roughness','WORK print'][i],bufferView=view,mimeType='image/png'))
doc=dict(asset=dict(version='2.0',generator='Reference-inspired astronaut v3'),scene=0,scenes=[dict(nodes=[root,meshnode])],nodes=nodes,meshes=[dict(name='Astronaut',primitives=primitives)],skins=[skin],materials=materials,animations=animations,bufferViews=views,accessors=accessors,buffers=[dict(byteLength=len(blob))],images=images,textures=[dict(source=i,sampler=0 if i<3 else 1) for i in range(4)],samplers=[dict(magFilter=9729,minFilter=9987,wrapS=10497,wrapT=10497),dict(magFilter=9729,minFilter=9987,wrapS=33071,wrapT=33071)],extensionsUsed=['KHR_materials_clearcoat','KHR_materials_unlit'])
js=json.dumps(doc,separators=(',',':')).encode(); js+=b' '*((-len(js))%4); blob.extend(b'\0'*((-len(blob))%4))
payload=struct.pack('<III',0x46546c67,2,12+8+len(js)+8+len(blob))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(blob),0x004e4942)+blob
path=OUT/'astronauta.glb'; path.write_bytes(payload)
assert all(abs(sum(g['w'][i:i+4])-1)<1e-6 for g in groups.values() for i in range(0,len(g['w']),4))
assert all(max(g['idx'])<len(g['p'])//3 for g in groups.values())
print(json.dumps(dict(file=str(path),bytes=len(payload),bones=len(joints),triangles=sum(len(g['idx'])//3 for g in groups.values()),animations=[a['name'] for a in animations]),indent=2))
