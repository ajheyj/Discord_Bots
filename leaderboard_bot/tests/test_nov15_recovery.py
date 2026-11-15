import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch
import discord
from PIL import Image
from store import Store
from leaderboard_guide import ensure_guide,guide_embed
from image_scan import labels_in,read_value,extract_image_stats
from ocr import OCRFailure
from durable_service import DurablePipeline
from ocr_process import JobError
from test_durable_queue import config,message,bot_and_channel

class GuideTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db')
        self.bot=SimpleNamespace(user=SimpleNamespace(id=7));self.messages={};self.counter=100
        def make(mid,embed=None):
            msg=SimpleNamespace(id=mid,author=self.bot.user,embeds=[embed] if embed else [],pinned=False,edit=AsyncMock(),pin=AsyncMock())
            async def edit(**kwargs):msg.embeds=[kwargs['embed']]
            async def pin(**kwargs):msg.pinned=True
            msg.edit.side_effect=edit;msg.pin.side_effect=pin;return msg
        self.make=make
        async def fetch(mid):
            if mid not in self.messages:raise discord.NotFound(SimpleNamespace(status=404,reason='missing'),'missing')
            return self.messages[mid]
        async def send(**kwargs):
            self.counter+=1;msg=make(self.counter,kwargs['embed']);self.messages[msg.id]=msg;return msg
        self.channel=SimpleNamespace(fetch_message=AsyncMock(side_effect=fetch),send=AsyncMock(side_effect=send))
    async def asyncTearDown(self):self.store.db.close();self.tmp.cleanup()
    async def test_new_setup_posts_one_guide_and_reuses_it(self):
        a=await ensure_guide(self.bot,self.store,self.channel,['packs','money'])
        b=await ensure_guide(self.bot,self.store,self.channel,['packs','money'])
        self.assertEqual(a.id,b.id);self.channel.send.assert_awaited_once();a.pin.assert_awaited_once();a.edit.assert_not_awaited()
    async def test_existing_scoreboard_slots_become_guide_then_scores_without_deletion(self):
        for key,mid in [('packs',10),('money',20),('coins',30)]:
            self.store.save_board(key,mid);self.messages[mid]=self.make(mid)
        guide=await ensure_guide(self.bot,self.store,self.channel,['packs','money','coins'])
        self.assertEqual(guide.id,10);self.assertEqual(self.store.board('packs'),20)
        self.assertEqual(self.store.board('money'),30);self.assertIsNone(self.store.board('coins'))
        self.assertEqual(self.store.board('instructions'),10);self.channel.send.assert_not_awaited()
        await ensure_guide(self.bot,self.store,self.channel,['packs','money','coins'])
        self.assertEqual(self.store.board('packs'),20)
    async def test_does_not_repurpose_another_authors_message(self):
        self.store.save_board('packs',10);msg=self.make(10);msg.author=SimpleNamespace(id=88);self.messages[10]=msg
        await ensure_guide(self.bot,self.store,self.channel,['packs']);msg.edit.assert_not_awaited()
        self.channel.send.assert_awaited_once()
    async def test_pin_permission_failure_keeps_guide(self):
        msg=self.make(10,guide_embed());msg.pin.side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='denied'),'denied')
        self.messages[10]=msg;self.store.save_board('instructions',10)
        with self.assertLogs(level='WARNING'):await ensure_guide(self.bot,self.store,self.channel,['packs'])
        self.assertEqual(self.store.board('instructions'),10)

class DownloadMismatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=Store(self.root/'db')
        self.msg=message(count=1);self.bot,self.channel=bot_and_channel({1:self.msg})
        self.pipeline=DurablePipeline(self.bot,self.store,99,123,config(self.root))
        buf=io.BytesIO();Image.new('RGB',(30,30),'red').save(buf,format='PNG');self.png=buf.getvalue()
    async def asyncTearDown(self):await self.pipeline.close();self.store.db.close();self.tmp.cleanup()
    async def test_valid_mismatch_updates_disk_budget_and_cached_size_not_original_metadata(self):
        original=self.msg.attachments[0].size;self.msg.attachments[0].read.return_value=self.png
        self.pipeline.admit(self.msg);row=self.pipeline.jobs.claim('download');await self.pipeline.download(row)
        saved=self.pipeline.jobs.get(1);attachment=json.loads(saved['attachments'])[0]
        self.assertEqual(attachment['size'],original);self.assertEqual(attachment['cached_size'],len(self.png))
        self.assertTrue(self.pipeline.spool.complete(saved));self.assertEqual(saved['reserved'],len(self.png))
        await self.pipeline.download(saved);self.assertEqual(self.msg.attachments[0].read.await_count,1)
    async def test_invalid_mismatch_is_not_accepted(self):
        self.msg.attachments[0].read.return_value=b'truncated image bytes'
        self.pipeline.admit(self.msg);row=self.pipeline.jobs.claim('download')
        with self.assertRaisesRegex(JobError,'incomplete or invalid'):await self.pipeline.download(row)
        self.assertFalse(self.pipeline.spool.complete(self.pipeline.jobs.get(1)))
    async def test_growth_cannot_exceed_reserved_spool_capacity(self):
        self.msg.attachments[0].read.return_value=self.png
        self.pipeline.config.spool_bytes=self.msg.attachments[0].size
        self.pipeline.admit(self.msg);row=self.pipeline.jobs.claim('download')
        with self.assertRaisesRegex(JobError,'Insufficient image storage'):await self.pipeline.download(row)
        self.assertFalse(self.pipeline.spool.complete(self.pipeline.jobs.get(1)))
    async def test_zero_length_payload_is_rejected(self):
        self.msg.attachments[0].read.return_value=b'';self.pipeline.admit(self.msg)
        with self.assertRaisesRegex(JobError,'empty'):await self.pipeline.download(self.pipeline.jobs.claim('download'))

class WholeImageTests(unittest.TestCase):
    def data(self,words,lefts=None):
        n=len(words);return dict(text=words,conf=[95]*n,left=lefts or [100+i*100 for i in range(n)],top=[200]*n,width=[80]*n,height=[30]*n,block_num=[1]*n,par_num=[1]*n,line_num=[1]*n)
    def test_labels_are_found_at_arbitrary_positions(self):
        for origin in (30,800):
            got=labels_in(self.data(['Money','Earned'],[origin,origin+100]))
            self.assertEqual(got,[('money',origin,200,origin+180,230)])
    def test_icon_is_not_included_as_part_of_stat_label(self):
        got=labels_in(self.data(['$','Money','Earned']))
        self.assertEqual(got[0][1],200)
    def test_unsupported_hud_text_does_not_match(self):
        self.assertEqual(labels_in(self.data(['Cash','Multiplier'])),[])
    def test_whole_image_values_keep_confidence_and_conflict_rules(self):
        image=Image.new('RGB',(100,40))
        with patch('image_scan.readings',return_value=iter(['7,803'])),patch('image_scan.neutral_readings',return_value=iter(['7,803'])):
            self.assertEqual(read_value(image,'packs'),7803)
        with patch('image_scan.readings',return_value=iter(['7,803','7,804'])),patch('image_scan.neutral_readings',return_value=iter(['7,803'])):
            with self.assertRaises(OCRFailure):read_value(image,'packs')
    def test_single_label_cannot_establish_a_stats_panel(self):
        with patch('image_scan.pytesseract.image_to_data',return_value=self.data(['Money','Earned'])):
            self.assertIsNone(extract_image_stats(Image.new('RGB',(500,500))))

    def test_panel_conflict_cannot_be_rescued_by_whole_image_consensus(self):
        import ocr
        buffer=io.BytesIO();Image.new('RGB',(500,500)).save(buffer,format='PNG')
        partial={'coins':5,'_warnings':['Conflicting accepted readings for Packs Opened']}
        with patch('player_panel.extract_player_panel',return_value=partial),patch('image_scan.extract_image_stats',return_value={'packs':10,'coins':5}):
            result=ocr.extract(buffer.getvalue())
        self.assertNotIn('packs',result);self.assertEqual(result['coins'],5)

    def test_multiple_template_panels_are_not_overridden_by_fallback(self):
        import ocr
        buffer=io.BytesIO();Image.new('RGB',(500,500)).save(buffer,format='PNG')
        with patch('player_panel.extract_player_panel',side_effect=ocr.AmbiguousPanel('Multiple panels')),patch('image_scan.extract_image_stats',side_effect=AssertionError('must not bypass ambiguity')):
            with self.assertRaises(ocr.AmbiguousPanel):ocr.extract(buffer.getvalue())
