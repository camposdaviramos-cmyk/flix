"""Shared atomic authentication limits. Configured Redis failures fail closed."""
import hashlib
import redis

LIMIT_SCRIPT='''
for i,key in ipairs(KEYS) do
  if tonumber(redis.call('GET',key) or '0') >= tonumber(ARGV[i]) then return 0 end
end
for i,key in ipairs(KEYS) do
  local value=redis.call('INCR',key)
  if value==1 then redis.call('EXPIRE',key,tonumber(ARGV[#KEYS+1])) end
end
return 1
'''
class SecurityStore:
    def __init__(self,url,namespace='worktv:v1'):
        self.client=redis.Redis.from_url(url,max_connections=32,socket_connect_timeout=.5,socket_timeout=.5,health_check_interval=30)
        self.namespace=namespace
        self.limit_script=self.client.register_script(LIMIT_SCRIPT)
    def allow(self,category,limits,window):
        keys=[self.namespace+':limit:'+category+':'+hashlib.sha256(key.encode()).hexdigest() for key,limit in limits]
        return bool(self.limit_script(keys=keys,args=[limit for key,limit in limits]+[window]))
