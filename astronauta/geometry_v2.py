"""Refined reference-inspired suit surfaces, seams, PBR textures and rounded hardware."""
import io, math, random, sys
from pathlib import Path
sys.path.insert(0,'/tmp/astronauta-tools')
from PIL import Image, ImageDraw, ImageFont, ImageFilter

pi=math.pi
def add(a,b): return [x+y for x,y in zip(a,b)]
def sub(a,b): return [x-y for x,y in zip(a,b)]
def mul(a,k): return [x*k for x in a]
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def unit(a):
    length=math.sqrt(dot(a,a))
    return mul(a,1/length) if length>1e-30 else [0,1,0]
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a))); return t*t*(3-2*t)
def signedpower(x,p): return math.copysign(abs(x)**p,x)
def png(im):
    output=io.BytesIO(); im.save(output,format='PNG',optimize=True); return output.getvalue()

def textures():
    rng=random.Random(21); n=256
    color=Image.new('RGB',(n,n)); normal=Image.new('RGB',(n,n)); rough=Image.new('RGB',(n,n))
    for y in range(n):
        for x in range(n):
            weave=math.sin(x*pi/2)*math.cos(y*pi/2)
            shade=244+round(1.2*weave+rng.uniform(-.65,.65))
            color.putpixel((x,y),(shade,shade,max(0,shade-1)))
            dx=math.cos(x*pi/2)*math.cos(y*pi/2)*.07
            dy=-math.sin(x*pi/2)*math.sin(y*pi/2)*.07
            normal.putpixel((x,y),(round(128+dx*127),round(128+dy*127),254))
            r=round(152+weave*4);rough.putpixel((x,y),(255,r,0))
    logo=Image.new('RGBA',(1024,384),(0,0,0,0))
    draw=ImageDraw.Draw(logo);font=ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',290)
    bounds=draw.textbbox((0,0),'WORK',font=font); w=bounds[2]-bounds[0];h=bounds[3]-bounds[1]
    draw.text(((1024-w)/2-bounds[0],(384-h)/2-bounds[1]),'WORK',font=font,fill=(0,143,248,255))
    return [png(color),png(normal),png(rough),png(logo)]

def build(ctx):
    groups=ctx['groups']; names=ctx['names']; head=ctx['head'];neck=ctx['neck'];hips=ctx['hips'];spine=ctx['spine'];chest=ctx['chest']
    groups.clear()
    def material(name,color,metal,rough,**more):
        return dict(name=name,pbrMetallicRoughness=dict(baseColorFactor=[*color,1],metallicFactor=metal,roughnessFactor=rough),**more)
    mats=[
        material('Pearl textile — micro weave',[.88,.885,.895],0,1,normalTexture=dict(index=1,scale=.12)),
        material('Obsidian visor',[.001,.0015,.002],.03,.035,extensions={'KHR_materials_clearcoat':dict(clearcoatFactor=1,clearcoatRoughnessFactor=.025)}),
        material('Anodized electric blue',[.002,.27,.78],.42,.17,emissiveFactor=[0,.025,.07]),
        material('Visor gasket',[.006,.007,.009],.25,.26),
        material('Soft white sole',[.69,.71,.74],0,.53),
        material('Pearl helmet lacquer',[.91,.93,.96],.12,.23,extensions={'KHR_materials_clearcoat':dict(clearcoatFactor=.65,clearcoatRoughnessFactor=.18)}),
        material('Suit stitched piping',[.74,.76,.79],0,.68),
        material('Kneepad fabric',[.84,.85,.86],0,1,normalTexture=dict(index=1,scale=.15)),
        material('White hardware',[.88,.9,.93],.10,.32),
        material('WORK print',[1,1,1],0,.62,alphaMode='BLEND',doubleSided=False,extensions={'KHR_materials_unlit':{}}),
    ]
    for m in [mats[0],mats[7]]:
        m['pbrMetallicRoughness']['baseColorTexture']=dict(index=0)
        m['pbrMetallicRoughness']['metallicRoughnessTexture']=dict(index=2)
    mats[9]['pbrMetallicRoughness']['baseColorTexture']=dict(index=3)

    def surface(fn,nu,nv,j,mat=0,weights=None,orientation=1,uvscale=(1,1)):
        nu=min(nu,64);nv=min(nv,64)
        g=groups.setdefault(mat,dict(p=[],n=[],j=[],w=[],uv=[],idx=[]));start=len(g['p'])//3
        eps=.00005
        for v in range(nv+1):
            t=v/nv
            for u in range(nu+1):
                s=u/nu;p=fn(s,t)
                du=sub(fn(s+eps,t),fn(s-eps,t));dv=sub(fn(s,t+eps),fn(s,t-eps))
                raw=cross(du,dv)
                if dot(raw,raw)<1e-20:
                    tt=max(.0001,min(.9999,t))
                    du=sub(fn(s+eps,tt),fn(s-eps,tt));dv=sub(fn(s,tt+eps),fn(s,tt-eps));raw=cross(du,dv)
                normal=mul(unit(raw),orientation)
                influences=weights(p) if weights else [(j,1)]
                influences=[(a,w) for a,w in influences if w>1e-8][:4]
                total=sum(w for a,w in influences)
                js=[a for a,w in influences];ws=[w/total for a,w in influences]
                js.extend([0]*(4-len(js)));ws.extend([0]*(4-len(ws)))
                g['p'].extend(p);g['n'].extend(normal);g['j'].extend(js);g['w'].extend(ws);g['uv'].extend([s*uvscale[0],t*uvscale[1]])
        for v in range(nv):
            for u in range(nu):
                a=start+v*(nu+1)+u;b=a+nu+1
                faces=[a,a+1,b,b,a+1,b+1] if orientation==1 else [a,b,a+1,b,b+1,a+1]
                g['idx'].extend(faces)

    def ellipsoid(c,r,j,mat=0,nu=40,nv=24,power=1,bottom=None):
        max_angle=pi if bottom is None else math.acos(max(-1,min(1,(bottom-c[1])/r[1])))
        def fn(u,v):
            a=u*2*pi;t=max_angle*v
            q=[signedpower(math.sin(t)*math.cos(a),power),signedpower(math.cos(t),power),signedpower(math.sin(t)*math.sin(a),power)]
            return [c[k]+r[k]*q[k] for k in range(3)]
        surface(fn,nu,nv,j,mat,uvscale=(5,5) if mat in [0,7] else (1,1))

    def tube(points,r,j,mat=6,segments=8,weights=None):
        pts=points
        def fn(u,v):
            f=max(0,min(len(pts)-1.000001,v*(len(pts)-1)));i=int(f);t=f-i
            p=add(mul(pts[i],1-t),mul(pts[i+1],t));tangent=unit(sub(pts[i+1],pts[i]))
            axis=[0,0,1] if abs(tangent[2])<.8 else [0,1,0]
            normal=unit(cross(tangent,axis));second=cross(tangent,normal)
            return add(p,add(mul(normal,r*math.cos(2*pi*u)),mul(second,r*math.sin(2*pi*u))))
        surface(fn,segments,len(pts)-1,j,mat,weights)

    def ring(c,rx,rz,thick,j,mat=2,axis='y'):
        def fn(u,v):
            a=2*pi*u;b=2*pi*v
            p=[(rx+thick*math.cos(b))*math.cos(a),thick*math.sin(b),(rz+thick*math.cos(b))*math.sin(a)]
            if axis=='x':p=[p[1],p[0],p[2]]
            if axis=='z':p=[p[0],p[2],p[1]]
            return add(c,p)
        surface(fn,48,10,j,mat,orientation=-1 if axis=='y' else 1)

    def profile(points,t):
        t=max(0,min(1,t));x=t*(len(points)-1);i=min(len(points)-2,int(x));f=x-i
        # Catmull-Rom profile keeps inflated limbs continuous between controls.
        out=[]
        for k in range(len(points[0])):
            a=points[max(0,i-1)][k];b=points[i][k];c=points[i+1][k];d=points[min(len(points)-1,i+2)][k]
            out.append(.5*((2*b)+(-a+c)*f+(2*a-5*b+4*c-d)*f*f+(-a+3*b-3*c+d)*f*f*f))
        return out

    def profile_at(points,y):
        lo=0;hi=1
        for _ in range(24):
            mid=(lo+hi)/2
            if profile(points,mid)[0]>y:lo=mid
            else:hi=mid
        return profile(points,(lo+hi)/2)

    def bodyweights(p):
        y=p[1]
        if y<1.05:
            w=smooth(.92,1.05,y);return [(hips,1-w),(spine,w)]
        w=smooth(1.20,1.39,y);return [(spine,1-w),(chest,w)]

    # Separate front/back depths produce a convex belly in profile. The old
    # almost constant .20 depth made the chest-to-hip silhouette cylindrical.
    torso=[
        (1.43,.218,.143,.145), (1.36,.275,.205,.180),
        (1.27,.292,.266,.195), (1.16,.306,.318,.204),
        (1.045,.318,.343,.214), (.95,.312,.325,.215),
        (.85,.298,.282,.204), (.765,.247,.211,.166),
        (.705,.132,.109,.088), (.675,.0,.0,.0),
    ]
    def cloth_fold(y,a):
        return .0015*math.sin(y*54+2*math.sin(a*3))*(1-smooth(.96,1.09,y))+.0003*math.cos(a*11+y*13)
    def torso_section(u,parameters):
        y,rx,front,back=parameters;a=2*pi*u
        fold=cloth_fold(y,a)*smooth(.675,.74,y)
        return [(rx+fold)*math.cos(a),y,(front-back)/2+((front+back)/2+fold)*math.sin(a)]
    def torso_fn(u,v):
        return torso_section(u,profile(torso,v))
    def body_front(x,y):
        by,rx,front,back=profile_at(torso,y)
        a=math.acos(max(-1,min(1,x/max(rx,.0001))))
        for _ in range(3):
            fold=cloth_fold(y,a)*smooth(.675,.74,y)
            a=math.acos(max(-1,min(1,x/max(rx+fold,.0001))))
        return (front-back)/2+((front+back)/2+fold)*math.sin(a)
    surface(torso_fn,96,88,spine,0,bodyweights,uvscale=(10,12))

    # Large spherical shell, broad curved visor and separate polished blue trim.
    ellipsoid((0,1.80,-.028),(.424,.386,.372),head,5,72,48)
    shell_edge=[]
    for i in range(97):
        a=2*pi*i/96;shell_edge.append([.425*math.cos(a),1.80+.387*math.sin(a),-.028])
    tube(shell_edge,.0014,head,6,6)
    def visor(u,v):
        a=2*pi*u;rho=v
        x=.379*rho*signedpower(math.cos(a),.90)
        y=1.797+.313*rho*signedpower(math.sin(a),.90)
        # Follow the helmet ellipsoid all the way to its perimeter, avoiding
        # the former detached plate with a large empty gap behind the rim.
        z=-.022+.380*math.sqrt(max(.001,1-(x/.431)**2-((y-1.80)/.394)**2))
        return [x,y,z]
    surface(visor,96,40,head,1,orientation=-1)
    def bezel(u,v):
        p=visor(u,1.002+.057*v)
        shell_z=-.028+.372*math.sqrt(max(.001,1-(p[0]/.424)**2-((p[1]-1.80)/.386)**2))
        p[2]=p[2]*(1-v)+(shell_z+.002)*v
        return p
    surface(bezel,64,8,head,8,orientation=-1)
    for scale,radius,mat in [(1.009,.005,3),(1.030,.003,2)]:
        points=[]
        for i in range(129):
            p=bezel(i/128,(scale-1.002)/.057);p[2]+=.001;points.append(p)
        tube(points,radius,head,mat,10)
    # Fine helmet shell seam, along the back and crown.
    points=[]
    for i in range(70):
        t=-pi/2+i/69*pi;p=[0,1.80+.387*math.sin(t),-.028-.373*math.cos(t)];points.append(p)
    tube(points,.0013,head,6,6)

    # Collar uses real hollow rings instead of flattened spheres.
    for y in [1.397,1.421,1.445]:ring((0,y,0),.266,.218,.010,neck,8)
    # Fit the belt to the same belly surface; a fixed-radius band would clip
    # through the new volume or float away from it at the sides.
    def belt_fn(u,v):
        v=max(0,min(1,v));y=.983-.071*v;a=2*pi*u
        p=torso_section(u,profile_at(torso,y));padding=.005+.012*math.sin(pi*v)**.5
        return add(p,[padding*math.cos(a),0,padding*math.sin(a)])
    surface(belt_fn,80,18,hips,8,bodyweights)
    for v in [.12,.88]:
        points=[belt_fn(i/80,v) for i in range(81)]
        tube(points,.0017,hips,6,8,bodyweights)
    buckle_z=body_front(0,.949)+.022
    ellipsoid((0,.949,buckle_z),(.076,.076,.018),hips,8,40,24)
    ring((0,.949,buckle_z+.021),.039,.039,.0038,hips,3,'z')

    # Rounded rectangular backpack with raised rear panel and blue status strip.
    ellipsoid((0,1.17,-.258),(.318,.335,.115),chest,8,48,32,power=.43)
    ellipsoid((0,1.18,-.376),(.23,.252,.018),chest,5,40,28,power=.45)
    ellipsoid((0,1.18,-.401),(.012,.17,.008),chest,2,24,16,power=.45)
    for side,s in [('L',1),('R',-1)]:
        arm=names['UpperArm.'+side];fore=names['Forearm.'+side];hand=names['Hand.'+side]
        thigh=names['Thigh.'+side];shin=names['Shin.'+side];foot=names['Foot.'+side]
        def armweights(p):
            x=abs(p[0]);w=smooth(.51,.66,x);return [(arm,1-w),(fore,w)]
        sleeve=[(.278,.119),(.33,.126),(.40,.112),(.47,.110),(.55,.103),(.61,.107),(.68,.104),(.74,.096),(.81,.084)]
        def sleeve_fn(u,v):
            x,r=profile(sleeve,v);a=2*pi*u
            folds=.0018*math.sin(x*65+math.sin(a*3)*1.5)+.0007*math.sin(x*115+a*2)
            folds*=smooth(.30,.40,x)*(1-smooth(.76,.82,x))
            return [s*x,1.39+(r+folds)*math.cos(a),(r+folds)*math.sin(a)]
        surface(sleeve_fn,64,80,arm,0,armweights,orientation=s,uvscale=(6,12))
        for x,r,j in [(.338,.125,arm),(.589,.11,fore),(.797,.091,fore)]:
            for offset in [-.005,.005]:ring((s*(x+offset),1.39,0),r,r,.006,j,2,'x')
            ring((s*x,1.39,0),r-.001,r-.001,.003,j,3,'x')
        # Sleeve stitched underside follows inflated cloth, not an exposed joint.
        points=[]
        for i in range(55):
            x,r=profile(sleeve,i/54);points.append([s*x,1.39-r-.002,.016])
        tube(points,.0014,arm,6,6,armweights)
        ellipsoid((s*.854,1.39,.003),(.077,.071,.080),hand,0,32,20,power=.78)
        for f,z,width in [('Index',.061,.024),('Middle',.020,.026),('Ring',-.023,.024),('Little',-.061,.021)]:
            for n in range(3):
                x=.886+n*.044
                ellipsoid((s*(x+.012),1.388,z),(.034,.025 if f!='Little' else .022,width),names[f+str(n+1)+'.'+side],0,16,12,power=.90)
            # Subtle glove seam around the fingertips.
        ellipsoid((s*.868,1.329,.074),(.048,.033,.03),names['Thumb1.'+side],0,24,16)
        ellipsoid((s*.900,1.316,.081),(.035,.029,.027),names['Thumb2.'+side],0,24,16)
        ellipsoid((s*.923,1.311,.084),(.024,.025,.024),names['Thumb3.'+side],0,20,12)
        # One continuous leg envelope, weighted across the knee.
        leg=[(.90,.146,.164),(.83,.153,.174),(.75,.143,.163),(.66,.138,.153),(.585,.13,.15),(.52,.137,.156),(.435,.139,.157),(.35,.142,.153),(.278,.139,.148),(.22,.130,.140)]
        def legweights(p):
            w=1-smooth(.48,.64,p[1]);return [(thigh,1-w),(shin,w)]
        def leg_fn(u,v):
            y,rx,rz=profile(leg,v);a=2*pi*u
            wrinkle=.0022*math.sin(y*52+2.5*math.sin(a*2))+.0010*math.sin(y*87+a*3)
            wrinkle*=smooth(.23,.32,y)*(1-smooth(.79,.90,y))
            cx=s*(.175+.015*smooth(.85,.3,y))
            return [cx+(rx+wrinkle)*math.cos(a),y,(rz+wrinkle)*math.sin(a)]
        surface(leg_fn,64,88,thigh,0,legweights,uvscale=(6,12))
        for y,r in [(.567,.144),(.286,.15)]:
            for offset in [-.005,.005]:ring((s*.19,y+offset,0),r,r+.01,.0055,shin,2)
        # Rectangular fabric kneepads and raised stitching/channel lines.
        ellipsoid((s*.19,.537,.157),(.090,.115,.033),shin,7,40,32,power=.52)
        outline=[]
        for i in range(97):
            a=2*pi*i/96;outline.append([s*.19+.089*signedpower(math.cos(a),.54),.537+.114*signedpower(math.sin(a),.54),.165])
        tube(outline,.0022,shin,8,8)
        for y in [.497,.535,.573]:
            pts=[]
            for i in range(25):
                x=-.076+i/24*.152;dy=y-.537
                z=.157+.033*max(.001,1-(abs(x)/.090)**(2/.52)-(abs(dy)/.115)**(2/.52))**(.52/2)
                pts.append([s*.19+x,y,z+.001])
            tube(pts,.0014,shin,6,8)
        # Structured boots with a broad toe and cylindrical ankle.
        boot=[(.275,.130,.135,.0),(.24,.134,.15,.018),(.19,.145,.188,.047),(.14,.158,.219,.065),(.09,.162,.23,.075),(.06,.163,.23,.076)]
        def boot_fn(u,v):
            y,rx,rz,cz=profile(boot,v);a=2*pi*u
            return [s*.20+rx*signedpower(math.cos(a),.88),y,cz+rz*signedpower(math.sin(a),.88)]
        surface(boot_fn,64,40,foot,8)
        ellipsoid((s*.20,.105,.142),(.145,.112,.17),foot,8,40,24,bottom=.063)
        # Soft sole has real height and a gently rounded perimeter.
        sole=[(.073,.161,.23),(.068,.17,.24),(.038,.17,.24),(.025,.159,.23)]
        def sole_fn(u,v):
            y,rx,rz=profile(sole,v);a=u*2*pi
            return [s*.20+rx*signedpower(math.cos(a),.85),y,.077+rz*signedpower(math.sin(a),.85)]
        surface(sole_fn,64,16,foot,4)
        for y in [.034,.066]:ring((s*.20,y,.077),.168,.237,.0015,foot,6)
        ellipsoid((s*.20,.035,.076),(.163,.01,.233),foot,4,48,12,power=.80)
        # Toe ridges on the front upper surface, five stitched channels.
        for dx in [-.112,-.057,0,.057,.112]:
            pts=[]
            for i in range(22):
                cap_height=.105+.112*math.sqrt(1-(abs(dx)/.145)**2)
                y=.074+i/21*(cap_height-.078)
                by,rx,rz,cz=profile_at(boot,y)
                factor=max(.05,1-(abs(dx)/rx)**(2/.88))**(.88/2)
                cap_z=.142+.17*math.sqrt(max(.001,1-(dx/.145)**2-((y-.105)/.112)**2))
                pts.append([s*.20+dx,y,max(cz+rz*factor,cap_z)+.002])
            tube(pts,.0018,foot,6,8)
        # Small sole tread cuts around the front and sides.
        for i in range(16):
            a=pi*.03+i/15*pi*.94;x=s*.20+.172*math.cos(a);z=.077+.241*math.sin(a)
            tube([[x,.029,z],[x,.043,z]],.0017,foot,6,6)
        # Ear cups: lacquer housing, dark thin gasket, saturated blue central disk.
        ellipsoid((s*.423,1.79,-.015),(.028,.132,.132),head,3,40,24)
        ellipsoid((s*.447,1.79,-.015),(.035,.126,.126),head,8,40,24,power=.70)
        ellipsoid((s*.477,1.79,-.015),(.013,.093,.093),head,2,40,24)
        ring((s*.491,1.79,-.015),.083,.083,.0025,head,8,'x')

    # Front suit piping outlines shoulder seams, chest panel and crotch folds.
    for s in [-1,1]:
        points=[]
        for i in range(48):
            y=1.38-i/47*.415;x=s*(.235-.065*(1.38-y)/.415)
            z=body_front(x,y)+.0025
            points.append([x,y,z])
        tube(points,.0020,spine,6,8,bodyweights)
        points=[]
        for i in range(34):
            t=i/33;x=s*(.17*(1-t)+.025*t);y=.914-.192*t
            z=body_front(x,y)
            points.append([x,y,z+.003])
        tube(points,.0017,hips,6,8,bodyweights)
        pts=[]
        for i in range(28):
            y=1.36-i/27*.23;by,rx,front,back=profile_at(torso,y);x=s*rx*.95
            pts.append([x,y,body_front(x,y)+.003])
        tube(pts,.003,spine,8,8,bodyweights)

    # Crisp transparent decal hugs the curved chest instead of bead lettering.
    def decal(u,v):
        x=(u-.5)*.326;y=1.337-v*.113
        z=body_front(x,y)+.0025
        return [x,y,z]
    surface(decal,36,16,spine,9,weights=bodyweights,orientation=-1)
    # Lower shoulder line to match the reference proportions; finger joints move with it.
    arm_bones={i for name,i in names.items() if any(name.startswith(prefix) for prefix in ['UpperArm.','Forearm.','Hand.','Thumb','Index','Middle','Ring','Little'])}
    for g in groups.values():
        for i in range(len(g['p'])//3):
            if g['j'][i*4] in arm_bones:g['p'][i*3+1]-=.10
    return mats,textures()
