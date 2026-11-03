import io
import os
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
import ocr

class PanelTests(unittest.TestCase):
    def image_data(self):
        b=io.BytesIO();Image.new('RGB',(500,500),'black').save(b,format='PNG');return b.getvalue()
    def test_header_detection_follows_position_and_size(self):
        for box in [(100,50,500,130),(200,200,800,300)]:
            image=Image.new('RGB',(1100,1000),'black')
            ImageDraw.Draw(image).rectangle(box,fill=(30,220,10))
            regions=list(ocr.panel_regions(image))
            self.assertEqual(len(regions),1)
            self.assertGreater(regions[0].width,box[2]-box[0])
    def test_blank_image_has_no_panel(self):
        self.assertEqual(list(ocr.panel_regions(Image.new('RGB',(500,500),'black'))),[])
    def test_three_text_masks(self):
        masks=list(ocr.panel_variants(Image.new('RGB',(200,100),'white')))
        self.assertEqual(len(masks),3)
        for mask in masks:
            self.assertEqual(mask.size,(400,200));self.assertEqual(mask.mode,'L')
    def test_conflicting_or_missing_values_fail(self):
        for values in [[100],[],[100,100,101]]:
            found=defaultdict(list,packs=values,money=[10,10],coins=[5,5])
            with self.assertRaises(ocr.OCRFailure):ocr.resolve(found)
    def test_successful_full_image_does_not_trigger_fallback(self):
        def read(variant,found,psm=11):
            for key,value in [('packs',3),('money',4),('coins',5)]:found[key].append(value)
        with patch.object(ocr,'read_variant',side_effect=read),patch.object(ocr,'panel_regions',side_effect=AssertionError('unexpected fallback')):
            self.assertEqual(ocr.extract(self.image_data()),dict(packs=3,money=4,coins=5))
    def test_fallback_requires_two_agreeing_readings(self):
        def read(variant,found,psm=11):
            if psm==6:
                for key,value in [('packs',3),('money',4),('coins',5)]:found[key].append(value)
        image=Image.new('RGB',(200,100),'black')
        with patch.object(ocr,'read_variant',side_effect=read),patch.object(ocr,'panel_regions',return_value=[image]),patch.object(ocr,'panel_variants',return_value=[image,image]):
            self.assertEqual(ocr.extract(self.image_data()),dict(packs=3,money=4,coins=5))
        with patch.object(ocr,'read_variant',side_effect=read),patch.object(ocr,'panel_regions',return_value=[image]),patch.object(ocr,'panel_variants',return_value=[image]):
            with self.assertRaises(ocr.OCRFailure):ocr.extract(self.image_data())
    def test_fallback_does_not_override_conflicting_whole_image_value(self):
        def read(variant,found,psm=11):
            for key,value in [('packs',3 if psm==6 else 9),('money',4),('coins',5)]:found[key].append(value)
            if psm==11:found['coins'].clear() # force a missing stat to trigger fallback
        image=Image.new('RGB',(200,100),'black')
        with patch.object(ocr,'read_variant',side_effect=read),patch.object(ocr,'panel_regions',return_value=[image]),patch.object(ocr,'panel_variants',return_value=[image,image]):
            with self.assertRaises(ocr.OCRFailure):ocr.extract(self.image_data())
    def test_extra_new_ui_row_does_not_become_a_requested_stat(self):
        data={'text':['Total','Shiny','Cards','Collected:','6'],'conf':[99]*5,
              'block_num':[1]*5,'par_num':[1]*5,'line_num':[1]*5}
        found=defaultdict(list)
        with patch.object(ocr.pytesseract,'image_to_data',return_value=data):
            ocr.read_variant(Image.new('RGB',(50,50)),found,psm=6)
        self.assertEqual(dict(found),{})

@unittest.skipUnless(os.getenv('OCR_SAMPLE_DIR'),'Set OCR_SAMPLE_DIR to test private sample images locally')
class ImageRegressionTests(unittest.TestCase):
    def test_original_direct_screenshot(self):
        self.check('Fortnite Screenshot 2026.10.12 - 17.39.26.92.png',4619,26700000000000000,229)
    def test_original_monitor_photo(self):
        self.check('image(20261013-030813).png',2986,1930000000000000000,859)
    def test_reported_failure_photo(self):
        self.check('image(20261103-025938).png',5639,116000000000000000000,1478)
    def check(self,name,packs,money,coins):
        path=Path(os.environ['OCR_SAMPLE_DIR'])/name
        try:
            with Image.open(path) as source:source.load()
        except (OSError,FileNotFoundError) as error:
            self.skipTest('Private fixture unavailable or corrupt: '+str(error))
        result=ocr.extract(path.read_bytes())
        self.assertEqual(result,dict(packs=packs,money=money,coins=coins))

if __name__=='__main__':unittest.main()
