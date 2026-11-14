"""One isolated OCR job; parent enforces a wall-clock timeout and kills the process tree."""
import json
import os
import sys
# Set these before importing libraries in this fresh subprocess.
os.environ['OMP_THREAD_LIMIT']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
import cv2
cv2.setNumThreads(1)
from ocr import extract,merge_screenshots,OCRFailure
from submission_replay import failure_reason

def main(paths):
    try:
        if not 1<=len(paths)<=2:raise OCRFailure('Attach one or two screenshots per message')
        results=[];warnings=[]
        for path in paths:
            try:
                with open(path,'rb') as source:results.append(extract(source.read()))
            except OCRFailure as error:warnings.append(f'Image {len(results)+len(warnings)+1}: {error}')
        if not results:raise OCRFailure('; '.join(warnings))
        values=merge_screenshots(results)
        if warnings:values.setdefault('_warnings',[]).extend(warnings)
        output={'ok':True,'values':values}
    except Exception as error:
        output={'ok':False,'reason':failure_reason(error),'retry':not isinstance(error,OCRFailure)}
    print(json.dumps(output,ensure_ascii=True))

if __name__=='__main__':main(sys.argv[1:])
