import os
import unittest
from pathlib import Path
from PIL import Image,ImageDraw
from image_scan import foreground_crop,labels_in
from ocr_process import run_ocr

class PhotoCropTests(unittest.TestCase):
    def test_crop_removes_colored_border_and_retains_white_characters(self):
        image=Image.new('RGB',(300,100),(0,70,150));draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,299,99),outline=(0,220,255),width=4)
        draw.rectangle((100,30,125,65),fill='white');draw.rectangle((145,30,170,65),fill='white')
        crop=foreground_crop(image)
        self.assertLess(crop.width,100);self.assertEqual(crop.height,48)
    def test_specific_short_labels_handle_unreadable_last_word(self):
        def data(words):
            n=len(words)
            return dict(text=words,conf=[95]*n,left=[100+i*100 for i in range(n)],top=[200]*n,
                width=[80]*n,height=[30]*n,block_num=[1]*n,par_num=[1]*n,line_num=[1]*n)
        self.assertEqual(labels_in(data(['Grade','Coins']))[0][0],'coins')
        self.assertEqual(labels_in(data(['Shiny','Cards']))[0][0],'shiny')
        self.assertEqual(labels_in(data(['Gold','Coins'])),[])

class RealPhotoTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.getenv('MONITOR_PHOTO_FIXTURE'),'Set MONITOR_PHOTO_FIXTURE to the original photo')
    async def test_original_photo_through_worker(self):
        values=await run_ocr([Path(os.environ['MONITOR_PHOTO_FIXTURE'])],120)
        self.assertEqual({k:values[k] for k in ('packs','money','coins','shiny')},
            dict(packs=4035,money=34200000000000000000,coins=2219,shiny=4))
        self.assertNotIn('playtime',values)
