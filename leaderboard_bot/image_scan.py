"""Whole-image stat-label search; no fixed screenshot/panel coordinates."""
from collections import defaultdict
from difflib import SequenceMatcher
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image,ImageOps
from ocr import OCRFailure,AmbiguousPanel,number,playtime_seconds
from player_panel import ALIASES,clean,readings,money_readings

SCAN_ALIASES={**ALIASES,'coins':ALIASES['coins']+('Grade Coins',),
              'shiny':ALIASES['shiny']+('Shiny Cards',)}


def labels_in(data):
    groups=defaultdict(list)
    for i,text in enumerate(data['text']):
        if text.strip():groups[data['block_num'][i],data['par_num'][i],data['line_num'][i]].append(i)
    found=[]
    for indices in groups.values():
        indices.sort(key=lambda i:data['left'][i])
        for start in range(len(indices)):
            for count in range(2,6):
                ids=indices[start:start+count]
                if len(ids)!=count:continue
                text=' '.join(data['text'][i] for i in ids)
                if any(float(data['conf'][i])<65 for i in ids):continue
                matches=sorted((SequenceMatcher(None,clean(text),clean(alias)).ratio(),key)
                               for key,aliases in SCAN_ALIASES.items() for alias in aliases)
                score,key=matches[-1]
                if score<.9:continue
                first=clean(data['text'][ids[0]])
                if not first or not any(SequenceMatcher(None,first,clean(alias.split()[0])).ratio()>=.8 for alias in SCAN_ALIASES[key]):continue
                x=min(data['left'][i] for i in ids);y=min(data['top'][i] for i in ids)
                right=max(data['left'][i]+data['width'][i] for i in ids)
                bottom=max(data['top'][i]+data['height'][i] for i in ids)
                if not any(key==k and abs(y-by)<10 for k,_,by,_,_ in found):found.append((key,x,y,right,bottom))
    return found


def value_boxes(image):
    hsv=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2HSV);boxes=[]
    for floor in (90,140,180,220):
        _,_,stats,_=cv2.connectedComponentsWithStats(cv2.inRange(hsv,(90,60,floor),(140,255,255)))
        for x,y,w,h,area in stats[1:]:
            if w<50 or h<20 or not 1.3<w/h<8 or area/(w*h)<.06:continue
            box=tuple(map(int,(x,y,w,h)))
            if not any(abs(x-a)<8 and abs(y-b)<8 and abs(w-c)<15 and abs(h-d)<15 for a,b,c,d in boxes):boxes.append(box)
    return boxes


def neutral_readings(image):
    gray=np.asarray(ImageOps.autocontrast(ImageOps.grayscale(image)))
    for threshold in (None,150):
        if threshold is None:_,mask=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
        else:mask=255-cv2.inRange(gray,threshold,255)
        mask=cv2.copyMakeBorder(mask,10,10,10,10,cv2.BORDER_CONSTANT,value=255)
        for scale in (2,3):
            scaled=cv2.resize(mask,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
            data=pytesseract.image_to_data(scaled,config='--psm 7',output_type=pytesseract.Output.DICT,timeout=20)
            ids=[i for i,text in enumerate(data['text']) if text.strip()]
            if ids and min(float(data['conf'][i]) for i in ids)>=65:
                yield ' '.join(data['text'][i].strip() for i in ids)


def foreground_crop(image):
    """Remove colored value-box borders without changing characters."""
    rgb=np.asarray(image.convert('RGB'))
    mask=cv2.inRange(rgb,(175,175,175),(255,255,255))
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    parts=[r for r in stats[1:] if r[4]>30 and r[2]>3 and r[3]>max(8,image.height*.12)
           and r[2]<image.width*.9]
    if not parts:return image
    x=min(r[0] for r in parts);y=min(r[1] for r in parts)
    right=max(r[0]+r[2] for r in parts);bottom=max(r[1]+r[3] for r in parts)
    return image.crop((max(0,x-6),max(0,y-6),min(image.width,right+6),min(image.height,bottom+6)))


def read_value(image,key):
    parse=playtime_seconds if key=='playtime' else lambda text:number(text,key=='money')
    image=foreground_crop(image)
    accepted=[]
    for texts in (readings(image),neutral_readings(image)):
        for text in texts:
            try:accepted.append(parse(text))
            except OCRFailure:pass
        if len(set(accepted))>1:raise OCRFailure('Conflicting whole-image '+key+' readings')
        if len(accepted)>=2:return accepted[0]
    if key=='money':
        for text in money_readings(image):
            try:accepted.append(parse(text))
            except OCRFailure:pass
    if len(accepted)<2 or len(set(accepted))!=1:raise OCRFailure('Could not confidently read '+ALIASES[key][0])
    return accepted[0]


def extract_image_stats(image):
    # Locate labels across the entire image. Two aligned, distinct labels establish a stats cluster.
    variants=[image,ImageOps.autocontrast(ImageOps.grayscale(image))]
    labels=[];text_boxes=[]
    for variant in variants:
        data=pytesseract.image_to_data(variant,config='--psm 11',output_type=pytesseract.Output.DICT,timeout=20)
        for i,text in enumerate(data['text']):
            if re.match(r'^\$?\d',text.strip()):
                x,y,w,h=(int(data[k][i]) for k in ('left','top','width','height'))
                text_boxes.append((max(0,x-6),max(0,y-6),w+12,h+12))
        for row in labels_in(data):
            if not any(row[0]==old[0] and abs(row[2]-old[2])<15 for old in labels):labels.append(row)
    clusters=[]
    for anchor in labels:
        cluster=[row for row in labels if abs(row[1]-anchor[1])<=max(40,(anchor[4]-anchor[2])*2)]
        if len({row[0] for row in cluster})>=2 and not any({r[:3] for r in cluster}=={r[:3] for r in c} for c in clusters):clusters.append(cluster)
    if not clusters:return None
    # Distinct simultaneous panels are unsafe to associate to a single account.
    if len(clusters)>1 and any(abs(c[0][1]-clusters[0][0][1])>100 for c in clusters[1:]):
        raise AmbiguousPanel('Multiple stat panels found; submit one player per image')
    labels=max(clusters,key=len);boxes=value_boxes(image)+text_boxes;result={};conflicts=set();notes=[]
    for key,x,y,right,bottom in labels:
        height=bottom-y;cy=(y+bottom)/2
        candidates=[box for box in boxes if box[0]>right and abs(box[1]+box[3]/2-cy)<=max(height*1.6,box[3]*.6)
                    and box[3]>=height*.7 and box[3]<=height*4]
        if not candidates:continue
        vx,vy,vw,vh=min(candidates,key=lambda b:b[0]-right)
        crop=image.crop((vx+int(vw*.08),vy+int(vh*.12),vx+vw-int(vw*.08),vy+vh-int(vh*.12)))
        try:value=read_value(crop,key)
        except OCRFailure as error:notes.append(str(error));continue
        if key in result and result[key]!=value:
            conflicts.add(key);result.pop(key,None);notes.append('Conflicting whole-image '+key+' rows')
        if key not in conflicts:result[key]=value
    if not result:return None
    if notes:result['_warnings']=list(dict.fromkeys(notes))
    return result
