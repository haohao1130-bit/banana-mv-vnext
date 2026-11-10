import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from banana_mv.local_guide import ensure_local_guide,guide_record
from banana_mv import services

class LocalGuideTests(unittest.TestCase):
    def test_download_once_and_preserve_existing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'guides/ref.md';cfg={'guides':{'ref':str(path)}}
            with patch('banana_mv.local_guide.urlopen',return_value=io.BytesIO(b'# Full-Reference Mode Rewrite Output Format Guide\nOfficial content.')) as request:
                first=ensure_local_guide(cfg);second=ensure_local_guide(cfg)
            self.assertEqual(request.call_count,1)
            self.assertEqual(first['status'],'downloaded');self.assertEqual(second['status'],'existing')
            self.assertEqual(first['sha256'],second['sha256'])

    def test_unavailable_or_invalid_download_never_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ref.md';cfg={'guides':{'ref':str(path)}}
            for response in (OSError('offline'),io.BytesIO(b'<html>error</html>')):
                with patch('banana_mv.local_guide.urlopen',side_effect=response if isinstance(response,Exception) else None,return_value=response):
                    result=ensure_local_guide(cfg)
                self.assertFalse(result['available']);self.assertEqual(result['status'],'warning')
                self.assertFalse(path.exists())

    def test_existing_explicit_path_wins_and_stale_path_falls_back_to_cache(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(services,'DATA',Path(tmp)):
            guide=Path(tmp)/'custom.md';guide.write_text('Local guide')
            config=Path(tmp)/'config.json';config.write_text(json.dumps({'guides':{'ref':str(guide)}}))
            with patch.dict('os.environ',{'BANANA_REF_GUIDE':''}):
                self.assertEqual(services.load_config()['guides']['ref'],str(guide.resolve()))
                guide.unlink()
                self.assertEqual(services.load_config()['guides']['ref'],str(Path(tmp)/'guides/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md'))
            self.assertFalse(guide_record(guide)['available'])
