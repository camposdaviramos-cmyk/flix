"""Canonical Unicode for user text; never decode HTML markup or credentials."""
import re
from flask.json.provider import DefaultJSONProvider
EMOJI = {"heart":"❤️","heart_eyes":"😍","laugh":"😂","joy":"😂","fire":"🔥","music":"🎵","musical_note":"🎵","smile":"😊","clap":"👏","thumbsup":"👍","popcorn":"🍿","rocket":"🚀","eyes":"👀","star":"⭐","sparkles":"✨","sob":"😭","cry":"😢","thinking":"🤔","sunglasses":"😎","tada":"🎉","+1":"👍","laughing":"😆","grin":"😁","purple_heart":"💜","blue_heart":"💙","100":"💯","wave":"👋"}
STICKERS={"popcorn":"🍿","hype":"🚀","love":"💜","gg":"🏆","hello":"👋","plot":"😱","dance":"🪩","sleep":"😴"}
FIELDS={"body","text","caption","bio","status_text","title","description","name","last_message","messagePreview","senderName","callerName"}
def emoji_char(n):
    return n in (0x200d,0xfe0f,0xfe0e) or 0x1f000<=n<=0x1faff or 0x2300<=n<=0x27ff

def normalize(value, stickers=False):
    if not isinstance(value,str):return value
    value=re.sub(r':([a-z_+0-9]+):',lambda m:EMOJI.get(m[1],m[0]),value)
    def entity(m):
        try:n=int(m[1][1:],16) if m[1].lower().startswith('x') else int(m[1]);return chr(n) if emoji_char(n) else m[0]
        except (ValueError,OverflowError):return m[0]
    value=re.sub(r'&(?:amp;)?#(x[0-9a-fA-F]+|[0-9]+);',entity,value)
    def code(m):
        n=int(m[1],16)
        return chr(n) if emoji_char(n) else m[0]
    value=re.sub(r'\\u\{([0-9a-fA-F]{4,6})\}',code,value)
    def surrogate(m):
        n=0x10000+(int(m[1],16)-0xd800)*1024+int(m[2],16)-0xdc00
        return chr(n) if emoji_char(n) else m[0]
    value=re.sub(r'\\u([dD][89abAB][0-9a-fA-F]{2})\\u([dD][c-fC-F][0-9a-fA-F]{2})',surrogate,value)
    value=re.sub(r'\\u([0-9a-fA-F]{4})',code,value)
    if stickers:value=re.sub(r'\[sticker:([a-z]+)\]',lambda m:STICKERS.get(m[1],m[0]),value)
    return value

def payload(value):
    if isinstance(value,dict):return {k:normalize(v) if k in FIELDS and isinstance(v,str) else payload(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [payload(v) for v in value]
    return value

class SocialJSONProvider(DefaultJSONProvider):
    ensure_ascii=False
    def dumps(self,obj,**kwargs):return super().dumps(payload(obj),**kwargs)
