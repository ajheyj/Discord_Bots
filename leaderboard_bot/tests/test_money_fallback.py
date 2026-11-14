import unittest
from unittest.mock import patch
from PIL import Image
import player_panel as panel
from ocr import OCRFailure

class MoneyFallbackTests(unittest.TestCase):
    def setUp(self):self.image=Image.new('RGB',(150,45),'black')
    def test_normal_success_does_not_do_extra_ocr(self):
        with patch.object(panel,'readings',return_value=iter(['$82.2Qi','$82.2Qi'])),patch.object(panel,'money_readings',side_effect=AssertionError('unneeded')):
            self.assertEqual(panel.agree_money(self.image),82200000000000000000)
    def test_zero_normal_readings_can_use_two_agreeing_fallbacks(self):
        with patch.object(panel,'readings',return_value=iter([])),patch.object(panel,'money_readings',return_value=iter(['$82.2Qi','$82.2Qi'])):
            self.assertEqual(panel.agree_money(self.image),82200000000000000000)
    def test_one_normal_read_and_matching_fallback_can_agree(self):
        with patch.object(panel,'readings',return_value=iter(['$82.2Qi'])),patch.object(panel,'money_readings',return_value=iter(['$82.2Qi'])):
            self.assertEqual(panel.agree_money(self.image),82200000000000000000)
    def test_normal_conflict_cannot_be_outvoted(self):
        with patch.object(panel,'readings',return_value=iter(['$82.2Qi','$82.2Qa'])),patch.object(panel,'money_readings',side_effect=AssertionError('conflict must fail')):
            with self.assertRaisesRegex(OCRFailure,'conflicting'):panel.agree_money(self.image)
    def test_fallback_conflict_cannot_be_outvoted(self):
        with patch.object(panel,'readings',return_value=iter(['$82.2Qi'])),patch.object(panel,'money_readings',return_value=iter(['$82.2Qi','$82.2Qa','$82.2Qi'])):
            with self.assertRaisesRegex(OCRFailure,'conflicting'):panel.agree_money(self.image)
    def test_unknown_suffix_is_not_rewritten(self):
        with patch.object(panel,'readings',return_value=iter(['$82.2Q1'])),patch.object(panel,'money_readings',return_value=iter(['$82.2Q1','$82.2Q1'])):
            with self.assertRaisesRegex(OCRFailure,'only 0 valid'):panel.agree_money(self.image)
    def test_one_read_is_still_rejected(self):
        with patch.object(panel,'readings',return_value=iter([])),patch.object(panel,'money_readings',return_value=iter(['$82.2Qi'])):
            with self.assertRaisesRegex(OCRFailure,'only 1 valid'):panel.agree_money(self.image)
    def test_fallback_filters_low_confidence_tokens_and_uses_no_whitelist(self):
        def response(conf):return {'text':['$82.2Qi'],'conf':[conf]}
        with patch.object(panel.pytesseract,'image_to_data',side_effect=[response(64),response(65),response(90),response(20),response(0),response(99)]) as read:
            self.assertEqual(list(panel.money_readings(self.image)),['$82.2Qi']*3)
            self.assertEqual(read.call_count,6)
            for call in read.call_args_list:self.assertNotIn('whitelist',call.kwargs['config'])
