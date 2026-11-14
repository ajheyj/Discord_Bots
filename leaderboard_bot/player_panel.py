"""Read the blue Player Stats layout by detecting its banner and row/value boxes."""
import re
import unicodedata
from difflib import SequenceMatcher
import cv2
import numpy as np
import pytesseract
from ocr import OCRFailure, number, playtime_seconds

ALIASES = {'packs': ('Packs Opened',), 'money': ('Money Earned',),
           'coins': ('Grade Coins Collected',), 'shiny': ('Shiny Cards Collected',),
           'playtime': ('Total Playtime',)}

def clean(text):
    return re.sub('[^a-z]', '', text.lower())

def readings(image,min_conf=65):
    rgb = np.asarray(image)
    for threshold, scale in ((100, 2), (140, 2), (140, 4)):
        mask = 255-cv2.inRange(rgb,(threshold,threshold,threshold),(255,255,255))
        mask = cv2.copyMakeBorder(mask,8,8,8,8,cv2.BORDER_CONSTANT,value=255)
        mask = cv2.resize(mask,None,fx=scale,fy=scale,interpolation=cv2.INTER_LINEAR)
        data = pytesseract.image_to_data(mask,config='--psm 7',
                    output_type=pytesseract.Output.DICT,timeout=20)
        indices = [i for i,text in enumerate(data['text']) if text.strip()]
        if indices and min(float(data['conf'][i]) for i in indices) >= min_conf:
            yield ' '.join(data['text'][i].strip() for i in indices)

def agree(image, parser, label, min_conf=65):
    accepted=[]
    for text in readings(image,min_conf):
        try: accepted.append(parser(text))
        except (ValueError, OCRFailure): pass
    if len(accepted)<2 or len(set(accepted)) != 1:
        raise OCRFailure('Could not confidently read '+label)
    return accepted[0]

def username(text):
    text=unicodedata.normalize('NFC',' '.join(text.split()))
    if not 1 <= len(text) <= 64 or any(c in text for c in '<>@') or not any(c.isalnum() for c in text):
        raise ValueError('Invalid username')
    return text

def category(text):
    candidates=[(SequenceMatcher(None,clean(text),clean(alias)).ratio(),key)
                for key,aliases in ALIASES.items() for alias in aliases]
    ranked=sorted(candidates,reverse=True)
    confidence,key=ranked[0]
    if confidence < .84 or confidence-ranked[1][0]<.08: raise ValueError('Unrecognized row')
    return key

def extract_player_panel(image):
    hsv=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2HSV)
    _,_,stats,_=cv2.connectedComponentsWithStats(cv2.inRange(hsv,(90,90,90),(130,255,255)))
    components=[tuple(map(int,row)) for row in stats[1:]]
    headers=[r for r in components if r[2]>=max(180,image.width*.12) and r[3]>=25
             and 3<r[2]/r[3]<14 and r[4]/(r[2]*r[3])>.40]
    results=[]
    for x,y,w,h,_ in sorted(headers,key=lambda r:r[4],reverse=True)[:4]:
        title=image.crop((x+int(w*.18),y+int(h*.04),x+int(w*.86),y+int(h*.65)))
        if not any(SequenceMatcher(None,clean(t),'playerstats').ratio()>=.9 for t in readings(title)):
            continue
        name_image=image.crop((x+int(w*.18),y+int(h*.66),x+int(w*.86),y+h-2))
        try:name=agree(name_image,username,'Player Stats username')
        except OCRFailure:name=None
        rows=[r for r in components if .75*w<=r[2]<=1.05*w and .45*h<=r[3]<=1.4*h
              and x-w*.05<=r[0] and r[0]+r[2]<=x+w*1.05
              and y+h<r[1]<y+h*7 and .015<r[4]/(r[2]*r[3])<.35]
        result={'_warnings':[]}
        if name:result['username']=name
        else:result['_warnings'].append('Could not confidently read Player Stats username; Discord identity retained.')
        conflicts=set()
        for rx,ry,rw,rh,_ in sorted(rows,key=lambda r:r[1]):
            boxes=[r for r in components if .12*rw<=r[2]<=.42*rw and .3*rh<=r[3]<rh
                   and rx+rw*.55<r[0] and r[0]+r[2]<rx+rw
                   and ry<r[1] and r[1]+r[3]<ry+rh]
            try:
                if not boxes:continue # Tabs and clipped row borders are not complete value rows.
                vx,vy,vw,vh,_=max(boxes,key=lambda r:r[4])
                label_image=image.crop((rx+int(rw*.18),ry+int(rh*.1),vx-4,ry+rh-int(rh*.1)))
                key=agree(label_image,category,'visible Player Stats label',min_conf=0)
                value_image=image.crop((vx+int(vw*.06),vy+int(vh*.1),vx+vw-int(vw*.06),vy+vh-int(vh*.1)))
                parser=playtime_seconds if key=='playtime' else lambda text,k=key:number(text,k=='money')
                value=agree(value_image,parser,ALIASES[key][0])
                if key in result and result[key]!=value:
                    result.pop(key,None);conflicts.add(key)
                    raise OCRFailure('Conflicting visible '+key+' rows')
                if key not in conflicts:result[key]=value
            except OCRFailure as error:
                result['_warnings'].append(str(error))
        if not any(key in result for key in ALIASES):
            raise OCRFailure('Could not confidently read any Player Stats values')
        if not result['_warnings']:result.pop('_warnings')
        results.append(result)
    if len(results)>1:raise OCRFailure('More than one Player Stats panel found; crop to one player')
    return results[0] if results else None
