"""Bounded isolated OCR execution, including termination of descendant Tesseract processes."""
import asyncio
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

class JobError(Exception):
    def __init__(self,reason,retry=False):super().__init__(reason);self.retry=retry

async def terminate_tree(process):
    if os.name=='posix':
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    else:
        killer=await asyncio.create_subprocess_exec('taskkill','/PID',str(process.pid),'/T','/F',
            stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
        try:await asyncio.wait_for(killer.wait(),10)
        except asyncio.TimeoutError:killer.kill()
        if process.returncode is None:process.kill()
    try:await asyncio.wait_for(process.wait(),10)
    except asyncio.TimeoutError:
        if process.returncode is None:process.kill()

async def run_ocr(paths,timeout,runner=None):
    runner=Path(runner or Path(__file__).with_name('ocr_runner.py')).resolve()
    options={'start_new_session':True} if os.name=='posix' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}
    env={**os.environ,'OMP_THREAD_LIMIT':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    process=await asyncio.create_subprocess_exec(sys.executable,str(runner),*map(str,paths),
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env=env,**options)
    try:
        output,_=await asyncio.wait_for(process.communicate(),timeout)
    except asyncio.TimeoutError:
        await terminate_tree(process)
        raise JobError('OCR job exceeded its time limit; it will be retried if attempts remain.',retry=True)
    except asyncio.CancelledError:
        await terminate_tree(process)
        raise
    if process.returncode!=0:raise JobError('OCR subprocess exited unexpectedly.',retry=True)
    if len(output)>100_000:raise JobError('OCR subprocess returned an invalid result.',retry=True)
    try:result=json.loads(output)
    except (ValueError,UnicodeError):raise JobError('OCR subprocess returned an invalid result.',retry=True)
    if not isinstance(result,dict):raise JobError('OCR subprocess returned an invalid result.',retry=True)
    if not result.get('ok'):raise JobError(str(result.get('reason','OCR failed.'))[:500],retry=bool(result.get('retry')))
    if not isinstance(result.get('values'),dict):raise JobError('OCR subprocess returned no scores.',retry=True)
    return result['values']
