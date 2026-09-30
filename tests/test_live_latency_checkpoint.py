"""Exercise actual rollback implementation only in a disposable sandbox."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools.diagnostics import checkpoint_live_latency as checkpoint


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backup = self.root / 'backups'
        self.old = self.root / 'old.py'
        self.new = self.root / 'new.py'
        self.old.write_bytes(b'previous user changes\r\n')

    def call(self, action):
        with patch.object(checkpoint, 'ROOT', self.root), \
             patch.object(checkpoint, 'CHECKPOINT', self.backup), \
             patch.object(checkpoint, 'FILES', ('old.py', 'new.py')), \
             patch.object(sys, 'argv', ['checkpoint', action]), redirect_stdout(io.StringIO()):
            checkpoint.main()

    def modified(self):
        self.call('snapshot')
        self.old.write_bytes(b'optimized version')
        self.new.write_bytes(b'new helper')
        self.call('seal')

    def test_restore_preserves_old_bytes_and_retains_replaced_files(self):
        self.modified()
        self.call('verify')
        self.call('restore')
        self.assertEqual(self.old.read_bytes(), b'previous user changes\r\n')
        self.assertFalse(self.new.exists())
        self.assertEqual((self.backup / 'replaced/new.py').read_bytes(), b'new helper')
        self.assertEqual((self.backup / 'replaced/old.py').read_bytes(), b'optimized version')

    def test_later_edit_refuses_entire_restore_before_mutations(self):
        self.modified()
        self.new.write_bytes(b'later user change')
        with self.assertRaises(RuntimeError):
            self.call('restore')
        self.assertEqual(self.old.read_bytes(), b'optimized version')
        self.assertEqual(self.new.read_bytes(), b'later user change')
        self.assertFalse((self.backup / 'replaced').exists())

    def test_corrupt_backup_refuses_restore(self):
        self.modified()
        (self.backup / 'before/old.py').write_bytes(b'corrupt')
        with self.assertRaises(RuntimeError):
            self.call('restore')
        self.assertEqual(self.old.read_bytes(), b'optimized version')

    def test_refuses_overwriting_checkpoint_or_resealing(self):
        self.modified()
        with self.assertRaises(FileExistsError):
            self.call('snapshot')
        with self.assertRaises(RuntimeError):
            self.call('seal')


if __name__ == '__main__':
    unittest.main()
