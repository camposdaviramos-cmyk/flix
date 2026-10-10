#!/usr/bin/env python3
"""Local PostgreSQL + encryption-key backup. Run by the root systemd timer.
Backups contain sensitive data. Directory 0700 and files 0600; retain 14 days.
Configure encrypted off-host replication separately for host-loss resilience.
"""
import datetime,hashlib,json,os,subprocess,tarfile,time
from pathlib import Path
os.umask(0o077)
root=Path('/opt/flix/Streaming/data');backups=root/'backups/postgresql';backups.mkdir(parents=True,exist_ok=True,mode=0o700)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');target=backups/(stamp+'.dump');partial=target.with_suffix('.partial')
try:
 with partial.open('xb') as output:
  subprocess.run(['runuser','-u','postgres','--','pg_dump','--format=custom','--no-owner','--no-acl','worktv'],stdout=output,check=True)
 partial.replace(target)
 with tarfile.open(backups/(stamp+'-keys.tar.gz'),'w:gz') as archive:
  for name in ['secret.key','push-private.pem']:
   path=root/name
   if path.exists():archive.add(path,arcname=name)
 report={'created_at':stamp,'database':'worktv','bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 (backups/(stamp+'.json')).write_text(json.dumps(report,indent=2)+'\n')
 for path in backups.iterdir():
  if path.is_file() and path.suffix in ('.dump','.gz','.json') and path.stat().st_mtime<time.time()-14*86400:path.unlink()
 print(json.dumps({'backup':'complete','bytes':report['bytes']}))
finally:
 partial.unlink(missing_ok=True)
