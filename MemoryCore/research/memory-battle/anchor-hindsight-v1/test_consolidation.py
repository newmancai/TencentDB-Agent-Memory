import unittest
from run import drain_consolidation


class RoundEngine:
    def __init__(self, pending=207, failed=0, stuck=False):
        self.pending, self.failed, self.stuck = pending, failed, stuck
        self.calls = 0

    async def get_bank_stats(self, *args, **kwargs):
        return dict(pending_consolidation=self.pending, failed_consolidation=self.failed)

    async def run_consolidation(self, *args, **kwargs):
        self.calls += 1
        if not self.stuck:
            self.pending = max(0, self.pending - 100)
        # Installed API's legacy result keys can all be zero despite progress.
        return dict(processed=0, created=0, updated=0)


class ConsolidationTest(unittest.IsolatedAsyncioTestCase):
    async def test_drains_native_round_limit_using_fresh_stats(self):
        engine = RoundEngine()
        rounds, stats = await drain_consolidation(engine, 'bank', None)
        self.assertEqual(len(rounds), 3)
        self.assertEqual(stats['pending_consolidation'], 0)

    async def test_no_progress_stops_instead_of_looping(self):
        engine = RoundEngine(stuck=True)
        with self.assertRaisesRegex(RuntimeError, 'no progress'):
            await drain_consolidation(engine, 'bank', None)
        self.assertEqual(engine.calls, 1)

    async def test_failed_facts_are_not_completion_even_without_pending(self):
        with self.assertRaisesRegex(RuntimeError, 'failed facts'):
            await drain_consolidation(RoundEngine(pending=0, failed=1), 'bank', None)


if __name__ == '__main__':
    unittest.main()
