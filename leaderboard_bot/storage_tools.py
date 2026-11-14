"""Private spool writes, single-instance lock and consistent SQLite backups."""
import json
import os
import shutil
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

class InstanceLock:
    def __init__(self,path):self.path=Path(path);self.handle=None
    def acquire(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.handle=open(self.path,'a+b')
        try:
            os.chmod(self.path,0o600)
            if os.name=='posix':
                import fcntl
                fcntl.flock(self.handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            else:
                import msvcrt
                if self.path.stat().st_size==0:self.handle.write(b'0');self.handle.flush()
                self.handle.seek(0);msvcrt.locking(self.handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError as error:
            self.handle.close();self.handle=None
            raise RuntimeError('Another bot instance is using this database queue.') from error
    def close(self):
        if self.handle:self.handle.close();self.handle=None

class Spool:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        os.chmod(self.root,0o700)
    def directory(self,message):
        if not str(message).isdigit():raise ValueError('Invalid message ID for spool path')
        return self.root/str(message)
    def paths(self,row):
        return [self.directory(row['message'])/(str(i)+'.img') for i in range(len(json.loads(row['attachments'])))]
    def complete(self,row):
        return all(p.is_file() and p.stat().st_size==a['size']
                   for p,a in zip(self.paths(row),json.loads(row['attachments'])))
    def write(self,message,index,data):
        directory=self.directory(message);created=not directory.exists()
        directory.mkdir(mode=0o700,exist_ok=True)
        if created and os.name=='posix':
            root_fd=os.open(self.root,os.O_RDONLY)
            try:os.fsync(root_fd)
            finally:os.close(root_fd)
        target=directory/(str(index)+'.img');temp=target.with_suffix('.part')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'wb') as file:
            file.write(data);file.flush();os.fsync(file.fileno())
        os.replace(temp,target)
        if os.name=='posix':
            fd=os.open(directory,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
    def delete(self,message):
        directory=self.directory(message)
        if directory.exists():shutil.rmtree(directory)


def backup_database(database,directory,keep=7):
    database=Path(database).resolve();directory=Path(directory).resolve()
    if directory==database.parent or directory in database.parents:
        raise ValueError('Backup destination must be a dedicated directory separate from the database file.')
    if not database.is_file():raise FileNotFoundError('Database does not exist: '+str(database))
    directory.mkdir(parents=True,exist_ok=True);os.chmod(directory,0o700)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target=directory/('leaderboard-'+stamp+'.sqlite3');temp=target.with_suffix('.part')
    # SQLite backup API includes committed WAL contents; never copy only the live .db file.
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    source=destination=None
    try:
        source=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=10)
        destination=sqlite3.connect(temp)
        source.backup(destination,pages=128,sleep=.01)
        if destination.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity check failed')
        destination.close();destination=None;source.close();source=None
        with open(temp,'rb') as file:os.fsync(file.fileno())
        os.replace(temp,target)
        if os.name=='posix':
            directory_fd=os.open(directory,os.O_RDONLY)
            try:os.fsync(directory_fd)
            finally:os.close(directory_fd)
        for old in sorted(directory.glob('leaderboard-*.sqlite3'),reverse=True)[keep:]:old.unlink()
        return target
    finally:
        if destination:destination.close()
        if source:source.close()
        if temp.exists():temp.unlink()

if __name__=='__main__':
    import argparse
    from dotenv import load_dotenv
    load_dotenv()
    parser=argparse.ArgumentParser(description='Create a consistent SQLite backup, including WAL data')
    parser.add_argument('--database',default=os.getenv('DATABASE_PATH','data/leaderboard.sqlite3'))
    parser.add_argument('--destination',required=True)
    parser.add_argument('--keep',type=int,default=7)
    args=parser.parse_args()
    if args.keep<1:parser.error('--keep must be positive')
    print(backup_database(args.database,args.destination,args.keep))
