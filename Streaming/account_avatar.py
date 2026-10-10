"""Account avatars remain available independently of the social module."""
import base64,struct,time,zlib
from flask import g,jsonify,Response

def png(value,error):
    try:
        if not isinstance(value,str) or not value.startswith('data:image/png;base64,') or len(value)>400022:raise ValueError()
        blob=base64.b64decode(value.split(',',1)[1],validate=True)
        if len(blob)>300000 or blob[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError()
        pos=8;chunks=[];pixels=[];header=None
        while pos<len(blob):
            size=struct.unpack('>I',blob[pos:pos+4])[0];kind=blob[pos+4:pos+8];body=blob[pos+8:pos+8+size];end=pos+12+size
            if end>len(blob) or zlib.crc32(kind+body)!=struct.unpack('>I',blob[end-4:end])[0]:raise ValueError()
            if header is None:
                if kind!=b'IHDR' or size!=13:raise ValueError()
                header=body
            elif kind==b'IHDR':raise ValueError()
            if kind==b'IDAT':pixels.append(body)
            if kind in (b'IHDR',b'IDAT',b'IEND'):chunks.append(blob[pos:end])
            elif kind[:1].isupper():raise ValueError()
            pos=end
            if kind==b'IEND':
                if size or pos!=len(blob):raise ValueError()
                break
        w,h,bits,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',header)
        if not 1<=w<=512 or not 1<=h<=512 or bits!=8 or color not in (2,6) or compression or filtering or interlace or kind!=b'IEND':raise ValueError()
        stride=1+w*(4 if color==6 else 3);limit=stride*h;decoder=zlib.decompressobj();raw=decoder.decompress(b''.join(pixels),limit+1)
        if len(raw)!=limit or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or any(raw[i]>4 for i in range(0,limit,stride)):raise ValueError()
        return blob[:8]+b''.join(chunks)
    except (ValueError,TypeError,struct.error,zlib.error):
        raise error('Envie uma imagem PNG válida de até 512 px e 300 KB.',400)

def register(app,db,auth,data,error):
    @app.get('/api/account/avatar')
    @auth()
    def account_avatar_image():
        row=db().execute('SELECT avatar_png,avatar FROM community_profiles WHERE user_id=?',(g.user['id'],)).fetchone()
        if not row or not row['avatar_png'] or not row['avatar']:raise error('Avatar não encontrado.',404)
        return Response(bytes(row['avatar_png']),mimetype='image/png')

    @app.route('/api/account/avatar',methods=['PUT','DELETE'])
    @auth()
    def account_avatar_update():
        from flask import request
        blob=None if request.method=='DELETE' else png(data().get('avatar'),error)
        now=time.time();url='/api/community/avatars/'+g.user['id']+'?v='+str(int(now*1000)) if blob else ''
        db().execute('INSERT INTO community_profiles(user_id,avatar,avatar_png,updated_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET avatar=excluded.avatar,avatar_png=excluded.avatar_png,updated_at=excluded.updated_at',(g.user['id'],url,blob,now))
        db().commit()
        return jsonify(ok=True,avatar='/api/account/avatar?v='+str(int(now*1000)) if blob else '')
