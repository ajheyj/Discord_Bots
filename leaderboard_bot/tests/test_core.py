import unittest,tempfile
from pathlib import Path
from ocr import number,OCRFailure,extract
from store import Store
from PIL import Image
import io
class CoreTests(unittest.TestCase):
 def test_suffixes(self):
  self.assertEqual(number('$26.7Qa',True),26700000000000000)
  self.assertEqual(number('$1.93Qi',True),1930000000000000000)
  for text in ['$1.930i','$2ZZ','-1','nan']:
   with self.assertRaises(OCRFailure):number(text,True)
 def test_highest_and_exact_sort(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(str(Path(d)/'db'))
   s.record(1,1,'A','url',dict(packs=100,money=10**18+1,coins=4))
   s.record(2,1,'A','url',dict(packs=20,money=10,coins=8))
   s.record(3,2,'B','url',dict(packs=100,money=10**18,coins=1))
   self.assertEqual(s.ranked('money')[0][2],10**18+1)
   self.assertEqual(s.ranked('coins')[0][2],8)
   self.assertTrue(s.seen(1)); self.assertFalse(s.seen(4))
   s.record(4,1,'A','url',error='unreadable')
   self.assertFalse(s.seen(4));self.assertEqual(s.ranked('packs')[0][2],100)
   s.db.close();s=Store(str(Path(d)/'db'));self.assertEqual(len(s.ranked('packs')),2)
 def test_blank_rejected(self):
  b=io.BytesIO();Image.new('RGB',(500,300),'white').save(b,format='PNG')
  with self.assertRaises(OCRFailure):extract(b.getvalue())
if __name__=='__main__':unittest.main()
