import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from feature_flow import brainstorm_page


class PortablePage(unittest.TestCase):
    def test_plan_without_brainstorm_can_launch_and_answer(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            draft = root / '.feature-flow/state/draft/demo'
            (draft / 'tasks').mkdir(parents=True)
            (draft / 'commands.md').write_text('Profile: standard\n')
            (draft / 'tasks/01-test.md').write_text('# Test\n\nStatus: open\nBlocked by: none\n')
            folder = root / 'live'
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=str(root)):
                result = brainstorm_page.main(['demo', '--live', str(folder), '--provider', 'local'], out, err)
            self.assertEqual(result, 0, err.getvalue())
            self.assertTrue((folder / 'state.json').exists())
            self.assertIn('not used', (folder / 'index.html').read_text().lower())
            self.assertFalse((root / 'plans/demo/brainstorm.md').exists())
