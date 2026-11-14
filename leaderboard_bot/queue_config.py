"""Validated resource limits; all sizes are MiB and times are seconds unless noted."""
import os
from dataclasses import dataclass
from pathlib import Path

def integer(name, default, minimum, maximum):
    try:value=int(os.getenv(name,str(default)))
    except ValueError as error:raise ValueError(name+' must be an integer') from error
    if not minimum<=value<=maximum:raise ValueError(f'{name} must be between {minimum} and {maximum}')
    return value

@dataclass
class QueueConfig:
    spool: Path
    backup_dir: Path
    max_jobs: int=2000
    per_user: int=5
    spool_bytes: int=2048*1024*1024
    min_free_bytes: int=512*1024*1024
    download_workers: int=2
    download_timeout: int=90
    ocr_timeout: int=180
    attempts: int=3
    retry_delay: int=60
    failed_retention_hours: int=72
    backup_hours: int=24
    backup_keep: int=7
    board_interval: int=30

    @classmethod
    def from_env(cls, database_path):
        parent=Path(database_path).resolve().parent
        spool=Path(os.getenv('SPOOL_PATH') or str(parent/'spool')).resolve()
        backup=Path(os.getenv('BACKUP_PATH') or str(parent/'backups')).resolve()
        for directory in (spool,backup):
            if directory==parent or directory in parent.parents:
                raise ValueError('SPOOL_PATH and BACKUP_PATH must be dedicated directories, not ancestors of DATABASE_PATH.')
        if spool==backup or spool in backup.parents or backup in spool.parents:
            raise ValueError('Spool and backup directories must be separate and not nested.')
        return cls(spool,backup,
            integer('QUEUE_MAX_PENDING',2000,1,100000),integer('QUEUE_MAX_PER_USER',5,1,10000),
            integer('SPOOL_MAX_MB',2048,1,1048576)*1024*1024,
            integer('SPOOL_MIN_FREE_MB',512,0,1048576)*1024*1024,
            integer('DOWNLOAD_WORKERS',2,1,4),integer('DOWNLOAD_TIMEOUT_SECONDS',90,5,600),
            integer('OCR_JOB_TIMEOUT_SECONDS',180,5,1800),integer('JOB_MAX_ATTEMPTS',3,1,10),
            integer('JOB_RETRY_SECONDS',60,1,3600),integer('FAILED_IMAGE_RETENTION_HOURS',72,0,720),
            integer('BACKUP_INTERVAL_HOURS',24,0,720),integer('BACKUP_KEEP',7,1,100),integer('LEADERBOARD_REFRESH_SECONDS',30,10,3600))
