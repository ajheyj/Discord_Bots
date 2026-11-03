import sqlite3,json
from datetime import datetime,timezone
from pathlib import Path

class Store:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS scores(user TEXT PRIMARY KEY,name TEXT,packs TEXT,money TEXT,coins TEXT);
        CREATE TABLE IF NOT EXISTS audit(message TEXT PRIMARY KEY,user TEXT,url TEXT,time TEXT,status TEXT,details TEXT);
        CREATE TABLE IF NOT EXISTS boards(category TEXT PRIMARY KEY,message TEXT);
        CREATE TABLE IF NOT EXISTS admin_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,user TEXT NOT NULL,time TEXT NOT NULL,action TEXT NOT NULL,
        category TEXT,before_values TEXT NOT NULL,after_values TEXT NOT NULL,reason TEXT NOT NULL);''')
    def seen(self,message):
        return self.db.execute('SELECT 1 FROM audit WHERE message=? AND status="ok"',(str(message),)).fetchone() is not None
    def record(self,message,user,name,url,values=None,error=None):
        with self.db:
            if values:
                old=self.db.execute('SELECT packs,money,coins FROM scores WHERE user=?',(str(user),)).fetchone()
                vals=[max(values[k],int(old[i]) if old else 0) for i,k in enumerate(('packs','money','coins'))]
                self.db.execute('INSERT OR REPLACE INTO scores VALUES(?,?,?,?,?)',(str(user),name,*map(str,vals)))
            self.db.execute('INSERT OR REPLACE INTO audit VALUES(?,?,?,?,?,?)',(str(message),str(user),url,datetime.now(timezone.utc).isoformat(),'ok' if values else 'failed',json.dumps(values) if values else error))
    def ranked(self,key):
        if key not in ('packs','money','coins'): raise ValueError(key)
        rows=self.db.execute('SELECT user,name,'+key+' FROM scores').fetchall()
        return sorted([(u,n,int(v)) for u,n,v in rows],key=lambda row:(-row[2],int(row[0])))
    def board(self,key):
        row=self.db.execute('SELECT message FROM boards WHERE category=?',(key,)).fetchone()
        return int(row[0]) if row else None
    def save_board(self,key,message):
        with self.db: self.db.execute('INSERT OR REPLACE INTO boards VALUES(?,?)',(key,str(message)))

    def admin_change(self,actor,user,reason,category=None,value=None):
        """Override an existing entry and append its audit row atomically."""
        if not isinstance(reason,str) or not 1 <= len(reason.strip()) <= 300:
            raise ValueError('Provide a reason between 1 and 300 characters.')
        if category is not None:
            if category not in ('packs','money','coins'):
                raise ValueError('Unknown category.')
            if type(value) is not int or not 0 <= value < 10**60:
                raise ValueError('Score must be a nonnegative integer below 10^60.')
        with self.db:
            row=self.db.execute('SELECT packs,money,coins FROM scores WHERE user=?',(str(user),)).fetchone()
            if row is None:
                raise ValueError('That player has no recorded scores.')
            before=dict(zip(('packs','money','coins'),map(int,row)))
            after=None if category is None else {**before,category:value}
            if category is None:
                self.db.execute('DELETE FROM scores WHERE user=?',(str(user),))
            else:
                self.db.execute('UPDATE scores SET '+category+'=? WHERE user=?',(str(value),str(user)))
            self.db.execute('''INSERT INTO admin_audit(actor,user,time,action,category,before_values,after_values,reason)
                VALUES(?,?,?,?,?,?,?,?)''',(str(actor),str(user),datetime.now(timezone.utc).isoformat(),
                'remove' if category is None else 'set',category,json.dumps(before),json.dumps(after),reason.strip()))
        return before,after
