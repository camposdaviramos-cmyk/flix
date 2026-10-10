"""Versioned schema changes for streaming profiles, MFA and device grants."""
import account_profiles,auth_security,device_login

def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS account_access_version(version INTEGER PRIMARY KEY)');db.commit()
    if db.execute('SELECT 1 FROM account_access_version WHERE version=1').fetchone():return
    account_profiles.migrate(db);auth_security.migrate(db);device_login.migrate(db)
    db.execute('INSERT INTO account_access_version VALUES(1)');db.commit()
