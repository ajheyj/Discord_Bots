"""Local OCR. Unknown suffixes and conflicting readings fail closed."""
import io, os, re
from decimal import Decimal
from difflib import SequenceMatcher
from collections import defaultdict
from PIL import Image, ImageOps, ImageEnhance
import pytesseract

SUFFIXES = {'':0, 'K':3, 'M':6, 'B':9, 'T':12, 'Qa':15, 'Qi':18}
LABELS = {'packs':'Packs Opened','money':'Total Money Earned','coins':'Total Grade Coins Earned'}
class OCRFailure(ValueError): pass

def number(text, money=False):
    text=text.strip().replace('$','').replace(',','').replace(' ','')
    match=re.fullmatch(r'(\d+(?:\.\d+)?)([A-Za-z]*)',text)
    if not match: raise OCRFailure('Invalid number')
    value,suffix=match.groups()
    if suffix not in SUFFIXES or (not money and (suffix or '.' in value)):
        raise OCRFailure('Unknown suffix or invalid count')
    return int(Decimal(value) * (10 ** SUFFIXES[suffix]))

def panel_regions(original):
    """Locate wide green header candidates; derive bounded crops from their geometry."""
    import cv2
    import numpy as np
    rgb=np.asarray(original)
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    mask=cv2.inRange(hsv,(30,100,100),(90,255,255))
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    regions=[]
    for x,y,w,h,area in stats[1:]:
        if w < max(120,original.width*.12) or h < 15 or not 2 < w/h < 12:
            continue
        if area/(w*h) < .30:
            continue
        regions.append((int(area),int(x),int(y),int(w),int(h)))
    for _,x,y,w,h in sorted(regions,reverse=True)[:2]:
        # Relative to a detected banner, never fixed screenshot coordinates.
        box=(max(0,x-int(w*.05)),y+h,min(original.width,x+int(w*1.25)),
             min(original.height,y+h+int(w*.9)))
        if box[2]>box[0] and box[3]>box[1]:
            yield original.crop(box)


def panel_variants(region):
    """Isolate bright neutral text from colorful characters/backgrounds."""
    import cv2
    import numpy as np
    rgb=np.asarray(region)
    for threshold in (140,190,210):
        text=255-cv2.inRange(rgb,(threshold,threshold,threshold),(255,255,255))
        yield Image.fromarray(cv2.resize(text,None,fx=2,fy=2,interpolation=cv2.INTER_LINEAR))


def read_variant(variant,found,psm=11):
    d=pytesseract.image_to_data(variant,config=f'--psm {psm}',output_type=pytesseract.Output.DICT,timeout=20)
    lines=defaultdict(list)
    for i,word in enumerate(d['text']):
        if word.strip(): lines[(d['block_num'][i],d['par_num'][i],d['line_num'][i])].append(i)
    for indices in lines.values():
        line=' '.join(d['text'][i] for i in indices)
        if ':' not in line: continue
        label,tail=line.split(':',1)
        for key,target in LABELS.items():
            clean=lambda s: re.sub('[^a-z]','',s.lower())
            if SequenceMatcher(None,clean(label),clean(target)).ratio()<0.88: continue
            match=re.match(r'\s*(\$?\d[\d,]*(?:\.\d+)?[A-Za-z]*)\b',tail)
            if not match: continue
            token=match.group(1)
            value_indices=[i for i in indices if d['text'][i].strip().startswith(('$',*'0123456789'))]
            if not value_indices or min(float(d['conf'][i]) for i in value_indices)<65: continue
            try: found[key].append(number(token,key=='money'))
            except OCRFailure: continue


def resolve(found):
    result={}
    for key in LABELS:
        values=found[key]
        if len(values)<2 or len(set(values))!=1:
            raise OCRFailure('Could not confidently read '+LABELS[key])
        result[key]=values[0]
    return result


def extract(data):
    if os.getenv('TESSERACT_CMD'): pytesseract.pytesseract.tesseract_cmd=os.environ['TESSERACT_CMD']
    Image.MAX_IMAGE_PIXELS=20_000_000
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.width*source.height > 20_000_000:
                raise OCRFailure('Image too large')
            source.load(); original=ImageOps.exif_transpose(source).convert('RGB')
    except OCRFailure:
        raise
    except Exception as e:
        raise OCRFailure('Unreadable image') from e
    original.thumbnail((2600,2600))
    gray=ImageOps.grayscale(original)
    variants=[original, original.resize((original.width*2,original.height*2)), ImageEnhance.Contrast(gray).enhance(2), gray.resize((gray.width*2,gray.height*2))]
    found=defaultdict(list)
    for variant in variants:
        read_variant(variant,found)
    try:
        return resolve(found)
    except OCRFailure:
        pass
    # Only try panel processing if the existing full-image path fails.
    for region in panel_regions(original):
        for variant in panel_variants(region):
            read_variant(variant,found,psm=6)
    return resolve(found)

if __name__=='__main__':
    import sys,json
    print(json.dumps(extract(open(sys.argv[1],'rb').read()),indent=2))
