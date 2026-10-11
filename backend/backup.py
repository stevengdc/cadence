"""Consistent local SQLite snapshot. This is not an off-host media backup."""
import datetime, pathlib, sqlite3,os
source=pathlib.Path(os.getenv('MC_STATE','/var/lib/media-center'))/'profile.sqlite'
folder=pathlib.Path(os.getenv('CADENCE_BACKUPS','/var/backups/media-center'));folder.mkdir(mode=0o700,parents=True,exist_ok=True)
target=folder/('profile-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.sqlite')
src=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True)
dst=sqlite3.connect(target)
try:
    src.backup(dst)
    if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Invalid backup')
finally:src.close();dst.close()
target.chmod(0o600)
for old in sorted(folder.glob('profile-*.sqlite'),reverse=True)[14:]:old.unlink()
print('Profile backup verified.')
