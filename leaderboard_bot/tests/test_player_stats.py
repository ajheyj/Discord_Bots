import os
import json
import sqlite3
import tempfile
import unittest
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from ocr import extract,OCRFailure,merge_screenshots,playtime_seconds,number
from player_panel import agree,category,username
from store import Store
from admin_commands import parse_score

STAMP=datetime(2026,11,10,tzinfo=timezone.utc)
class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=str(Path(self.temp.name)/'db');self.store=Store(self.path)
    def tearDown(self):self.store.db.close();self.temp.cleanup()
    def record(self,mid,user,values,time=STAMP):self.store.record(mid,user,'Discord Name','url',values,submitted_at=time)
    def test_epic_rename_updates_one_discord_record_and_preserves_scores(self):
        self.record(1,20,dict(username='OLD_NAME',packs=9000,money=100,coins=500,shiny=6,playtime=294090))
        self.record(2,20,dict(username='NEW_NAME',packs=10,money=90,coins=400,shiny=2),STAMP+timedelta(hours=1))
        self.assertEqual(self.store.ranked('packs'),[('20','NEW_NAME',9000)])
        self.assertEqual(self.store.ranked('playtime')[0][2],294090)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM scores').fetchone()[0],1)
        names=self.store.db.execute('SELECT name FROM player_names WHERE user="20" ORDER BY name').fetchall()
        self.assertEqual(names,[('NEW_NAME',),('OLD_NAME',)])
    def test_old_history_replay_does_not_restore_old_epic_name(self):
        self.record(2,20,dict(username='NEW_NAME',money=100,coins=9,shiny=3),STAMP)
        self.record(1,20,dict(username='OLD_NAME',packs=9000,money=90,coins=8,shiny=2),STAMP-timedelta(days=1))
        self.assertEqual(self.store.identity(20),'NEW_NAME')
        self.assertEqual(self.store.ranked('packs')[0][2],9000)
    def test_matching_epic_names_from_different_discord_users_are_not_merged(self):
        for uid in [20,21]:self.record(uid,uid,dict(username='SAME_NAME',packs=10,money=2,coins=3))
        self.assertEqual(len(self.store.ranked('packs')),2)
    def test_scrolled_first_submission_does_not_invent_packs_or_time(self):
        self.record(1,20,dict(username='PLAYER',money=10,coins=3,shiny=0))
        self.assertEqual(self.store.ranked('packs'),[]);self.assertEqual(self.store.ranked('playtime'),[])
        self.assertEqual(self.store.ranked('shiny'),[('20','PLAYER',0)])
        self.record(2,20,dict(username='PLAYER',packs=99,money=11,coins=5,shiny=6,playtime=42))
        self.record(3,20,dict(username='PLAYER',money=9,coins=2,shiny=4))
        self.assertEqual(self.store.ranked('packs')[0][2],99);self.assertEqual(self.store.ranked('playtime')[0][2],42)
        self.assertEqual(self.store.ranked('shiny')[0][2],6)
    def test_legacy_submission_preserves_known_epic_name(self):
        self.record(1,20,dict(username='EPIC',packs=10,money=2,coins=3))
        self.record(2,20,dict(packs=20,money=4,coins=5),STAMP+timedelta(days=1))
        self.assertEqual(self.store.identity(20),'EPIC')
    def test_additive_migration_retains_original_three_scores(self):
        self.store.db.close()
        con=sqlite3.connect(self.path)
        con.executescript('DROP TABLE scores; CREATE TABLE scores(user TEXT PRIMARY KEY,name TEXT,packs TEXT,money TEXT,coins TEXT); INSERT INTO scores VALUES("20","Original", "100","100000000000000000001","5");')
        con.close();self.store=Store(self.path)
        self.assertEqual(self.store.ranked('money'),[('20','Original',100000000000000000001)])
        self.assertEqual(self.store.ranked('shiny'),[])
        self.record(1,20,dict(username='EPIC',money=100,coins=3,shiny=6,playtime=10))
        self.assertEqual(self.store.ranked('packs')[0][2],100)
        self.store.db.close();self.store=Store(self.path)
        self.assertEqual(self.store.identity(20),'EPIC');self.assertEqual(self.store.ranked('playtime')[0][2],10)
    def test_profile_failure_rolls_back_score_and_name_changes(self):
        self.record(1,20,dict(username='ORIGINAL',packs=10,money=2,coins=3))
        self.store.db.execute("CREATE TRIGGER fail_profile BEFORE UPDATE ON player_profiles BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.record(2,20,dict(username='NEW',packs=100,money=20,coins=30),STAMP+timedelta(hours=1))
        self.assertEqual(self.store.ranked('packs'),[('20','ORIGINAL',10)])
        self.assertFalse(self.store.seen(2))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM player_names').fetchone()[0],1)
    def test_admin_can_initialize_new_metric_and_removal_preserves_alias_history(self):
        self.record(1,20,dict(username='EPIC',packs=10,money=2,coins=3))
        before,after=self.store.admin_change(99,20,'verified','playtime',294090)
        self.assertNotIn('playtime',before);self.assertEqual(after['playtime'],294090)
        self.store.admin_change(99,20,'verified','shiny',0)
        self.assertEqual(self.store.ranked('shiny')[0][2],0)
        self.store.admin_change(99,20,'remove')
        for key in ['packs','money','coins','shiny','playtime']:self.assertEqual(self.store.ranked(key),[])
        self.assertEqual(self.store.identity(20),'EPIC')
    def test_invalid_stat_value_has_no_partial_write(self):
        for vals in [dict(username='NAME'),dict(packs=-1),dict(shiny=True),dict(playtime=1.5)]:
            with self.assertRaises(ValueError):self.record(1,20,vals)
        self.assertEqual(self.store.ranked('packs'),[])

class PlayerParsingTests(unittest.TestCase):
    def test_time_format_and_zero_ocr_normalization(self):
        self.assertEqual(playtime_seconds('03d 09h 41m 30s'),294090)
        self.assertEqual(playtime_seconds('O3dO9h41m30s'),294090)
        self.assertEqual(playtime_seconds('00d 00h 00m 00s'),0)
        for text in ['03d 25h 00m 00s','03d 09h 61m 00s','03d 09h 00m 60s','-1d00h00m00s','3:09:41:30']:
            with self.assertRaises(OCRFailure):playtime_seconds(text)
    def test_combined_views_keep_maxima_not_sums(self):
        one=dict(username='CROSSBAR_CHRIS',packs=9057,money=347*10**17,coins=986,shiny=6)
        two=dict(username='CROSSBAR_CHRIS',money=347*10**17,coins=986,shiny=6,playtime=294090)
        expected={**one,'playtime':294090}
        self.assertEqual(merge_screenshots([one,two]),expected)
        self.assertEqual(merge_screenshots([two,one]),expected)
    def test_mismatched_or_legacy_two_views_are_rejected(self):
        for results in [[],[{}, {}, {}],[dict(username='A',money=1),dict(username='B',money=2)],
                        [dict(money=1),dict(money=2)]]:
            with self.assertRaises(OCRFailure):merge_screenshots(results)
    def test_ambiguous_or_single_numeric_reading_is_not_accepted(self):
        im=Image.new('RGB',(50,50))
        for readings in [['5'],['5','6'],['unknown','unknown']]:
            with patch('player_panel.readings',return_value=iter(readings)):
                with self.assertRaises(OCRFailure):agree(im,lambda t:number(t),'score')
    def test_label_matching_and_username_preservation(self):
        self.assertEqual(category('Nioney Earned'),'money')
        self.assertEqual(category('Grade Coins Collected'),'coins')
        self.assertEqual(category('Shiny Cards Collected'),'shiny')
        self.assertEqual(username('CROSSBAR_CHRIS'),'CROSSBAR_CHRIS')
        with self.assertRaises(ValueError):category('Random Cards Data')
        with self.assertRaises(ValueError):username('<@everyone>')
    def test_new_admin_categories(self):
        self.assertEqual(parse_score('shiny','6'),6)
        self.assertEqual(parse_score('playtime','03d09h41m30s'),294090)
        self.assertEqual(parse_score('playtime','294090'),294090)
        with self.assertRaises(ValueError):parse_score('shiny','1.5')

@unittest.skipUnless(os.getenv('PLAYER_STATS_SAMPLE_DIR'),'Set PLAYER_STATS_SAMPLE_DIR to run private new-UI image tests')
class NewImageTests(unittest.TestCase):
    def test_top_view(self):
        p=Path(os.environ['PLAYER_STATS_SAMPLE_DIR'])/'Fortnite Screenshot 2026.11.09 - 22.53.34.80.png'
        self.assertEqual(extract(p.read_bytes()),dict(username='CROSSBAR_CHRIS',packs=9057,money=34700000000000000000,coins=986,shiny=6))
    def test_scrolled_view(self):
        p=Path(os.environ['PLAYER_STATS_SAMPLE_DIR'])/'Fortnite Screenshot 2026.11.09 - 22.54.38.73.png'
        self.assertEqual(extract(p.read_bytes()),dict(username='CROSSBAR_CHRIS',money=34700000000000000000,coins=986,shiny=6,playtime=294090))

if __name__=='__main__':unittest.main()
