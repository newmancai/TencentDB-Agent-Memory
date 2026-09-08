import unittest
from receipts import ReceiptAdapter,FeedbackLedger,Fact

class ReceiptTests(unittest.TestCase):
    def test_capacity_rejects_whole_event_and_allows_retry(self):
        ledger=FeedbackLedger(capacity=2)
        old=Fact('u','items','i','value',1,'a');ledger.consume([old],'a')
        changed=Fact('u','items','i','value',2,'b')
        extra=Fact('u','items','i','other',3,'b')
        self.assertEqual(ledger.consume([changed,extra],'b'),([],'record_capacity'))
        self.assertEqual(ledger.history[0]['fact'],old)
        self.assertEqual(len(ledger.history),1)
        self.assertNotIn('b',ledger.seen)
        signals,status=ledger.consume([changed],'b')
        self.assertEqual(status,'ok');self.assertEqual(len(signals),1)
    def event(self,result):return dict(id='e',scope='task',tool='process_refund',arguments={'confirm':True},result=result)
    def test_supplement_does_not_overwrite_refund(self):
        facts,_=ReceiptAdapter().observe(self.event({'status':'refunded','mode':'supplemental_refund','item_id':'i','refund_amount':10,'total_goodwill_credit':20}))
        self.assertEqual([(f.field,f.value) for f in facts],[('goodwill_credit',20)])
    def test_preview_and_rejection_do_not_assert_state(self):
        for status in ['preview','rejected']:
            self.assertEqual(ReceiptAdapter().observe(self.event({'status':status,'item_id':'i','refund_amount':10}))[0],[])
    def test_split_is_not_persisted_method(self):
        facts,_=ReceiptAdapter().observe(self.event({'status':'refunded','mode':'refund','item_id':'i','refund_amount':10,'refund_method':'split'}))
        self.assertEqual([f.field for f in facts],['refund_amount'])
    def test_scope_version_history_and_repeat(self):
        ledger=FeedbackLedger();f=Fact('u1','items','i','value',1,'a');ledger.consume([f],'a')
        ledger.consume([Fact('u2','items','i','value',2,'b')],'b')
        signals,_=ledger.consume([Fact('u1','items','i','value',3,'c')],'c')
        self.assertEqual(len(signals),1);self.assertEqual(signals[0]['target']['fact'],f)
        self.assertEqual(signals[0]['target']['version'],1);self.assertEqual(len(ledger.history),3)
        self.assertEqual(ledger.consume([f],'c')[1],'duplicate')

if __name__=='__main__':unittest.main()
