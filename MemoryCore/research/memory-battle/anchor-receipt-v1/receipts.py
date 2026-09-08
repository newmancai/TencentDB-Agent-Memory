"""Observable receipt adapter. No imports from the offline oracle or environment."""
from dataclasses import dataclass
import hashlib,json

@dataclass(frozen=True)
class Fact:
    scope:str
    entity:str
    identity:str
    field:str
    value:object
    source:str
    @property
    def key(self):return (self.scope,self.entity,self.identity,self.field)

class ReceiptAdapter:
    def __init__(self):self.cart_ids={}
    def observe(self,e):
        r=e['result'];a=e['arguments'];tool=e['tool'];scope=e['scope'];out=[]
        if not isinstance(r,dict) or 'error' in r:return out,'error_or_unstructured'
        def emit(entity,identity,values,allowed=None):
            if not isinstance(identity,str) or not identity:return
            for field,value in values.items():
                if (allowed is None or field in allowed) and (value is None or isinstance(value,(str,int,float,bool))):
                    out.append(Fact(scope,entity,identity,field,value,e['id']))
        read={'get_booking':('bookings','booking_id'),'get_hotel_reservation':('hotels','reservation_id'),
              'get_car_rental':('car_rentals','rental_id'),'get_customer':('customers','customer_id'),
              'get_customer_account':('customers','customer_id'),'get_user_details':('users','user_id')}
        if tool in read:
            entity,key=read[tool];emit(entity,r.get(key),r);return out,'read'
        if tool=='get_order':
            emit('orders',r.get('order_id'),r)
            for item in r.get('items',[]):emit('order_items',item.get('item_id'),item)
            return out,'read'
        if tool=='get_cart':
            cid=r.get('cart_id');customer=r.get('customer_id')
            if cid and customer:self.cart_ids[(scope,customer)]=cid
            emit('carts',cid,r)
            for item in r.get('items',[]):emit('cart_items',item.get('cart_item_id'),item,{'cart_item_id','product_id','variant_id','quantity','gift_wrap'})
            return out,'read'
        if r.get('status') in ['preview','rejected']:return out,'noncommit'
        if tool=='process_return' and r.get('status')=='returned':
            emit('order_items',r.get('item_id'),{**{k:r[k] for k in ['refund_amount','refund_method','restocking_fee','return_label_issued'] if k in r},'item_status':'returned'})
        elif tool=='process_refund' and r.get('status')=='refunded':
            values={}
            if r.get('mode') in ['refund','refund_method_update']:
                if 'refund_amount' in r:values['refund_amount']=r['refund_amount']
                # 'split' describes payout routing, not the persisted refund_method.
                if r.get('refund_method')!='split' and 'refund_method' in r:values['refund_method']=r['refund_method']
            if r.get('mode') in ['supplemental_refund','goodwill_credit'] and 'total_goodwill_credit' in r:
                values['goodwill_credit']=r['total_goodwill_credit']
            emit('order_items',r.get('item_id'),values)
        elif tool in ['cancel_booking','cancel_hotel_reservation','cancel_car_rental'] and r.get('status')=='cancelled':
            entity,key={'cancel_booking':('bookings','booking_id'),'cancel_hotel_reservation':('hotels','reservation_id'),'cancel_car_rental':('car_rentals','rental_id')}[tool]
            emit(entity,r.get(key),r,{'status','refund_amount','cancellation_fee'})
        elif tool=='update_booking' and r.get('status')=='updated':
            emit('bookings',r.get('booking_id'),{**{k:r[k] for k in ['price_paid','change_fee','fare_difference'] if k in r},'status':'confirmed'})
            # Other changes_applied values need additional schema interpretation;
            # absent returned values are not fabricated from requested arguments.
        elif tool in ['add_to_cart','update_cart_item','remove_from_cart','apply_promo','remove_promo','set_shipping_option','redeem_loyalty_points','cancel_loyalty_redemption']:
            expected={'add_to_cart':{'added','updated'},'update_cart_item':{'updated'},'remove_from_cart':{'removed'},'apply_promo':{'applied'},'remove_promo':{'removed'},'set_shipping_option':{'set'},'redeem_loyalty_points':{'redeemed'},'cancel_loyalty_redemption':{'cancelled'}}[tool]
            if r.get('status') not in expected:return out,'unknown_outcome'
            cid=r.get('cart_id') or self.cart_ids.get((scope,a.get('customer_id')))
            values={dst:r[src] for src,dst in [('cart_total','total'),('cart_subtotal','subtotal'),('discount_amount','discount_amount'),('shipping_cost','shipping_cost'),('shipping_option','shipping_option')] if src in r}
            emit('carts',cid,values)
            if tool in ['add_to_cart','update_cart_item']:emit('cart_items',r.get('cart_item_id'),r,{'cart_item_id','product_id','variant_id','quantity','gift_wrap'})
        else:return out,'unsupported'
        return out,'completed_receipt'

class FeedbackLedger:
    """Bounded record/version state; unknown evidence never invalidates records."""
    def __init__(self,capacity=2048):self.capacity=capacity;self.active={};self.history=[];self.seen=set()
    def consume(self,facts,event_id,enabled=True):
        if event_id in self.seen:return [],'duplicate'
        if len(self.seen)>=4096:return [],'event_capacity'
        pending={};records=[];signals=[]
        for fact in facts:
            previous=pending.get(fact.key,self.active.get(fact.key))
            if previous and previous['fact'].value==fact.value:continue
            if previous and not enabled:continue
            if len(self.history)+len(records)>=self.capacity:return [],'record_capacity'
            generation=previous['generation']+1 if previous else 1
            rid='receipt_'+hashlib.sha256(json.dumps([fact.key,generation]).encode()).hexdigest()[:24]
            record={'id':rid,'version':1,'generation':generation,'fact':fact}
            if previous:signals.append({'target':previous,'replacement':record,'evidence':event_id,'kind':'value_changed'})
            records.append(record);pending[fact.key]=record
        self.history.extend(records);self.active.update(pending);self.seen.add(event_id)
        return signals,'ok'

class PreviewAsCompletion(ReceiptAdapter):
    """Ablation: treat preview/rejected payloads as completed writes; same field mapping."""
    def observe(self,e):
        r=e['result']
        completed={'process_return':'returned','process_refund':'refunded','update_booking':'updated',
                   'cancel_booking':'cancelled','cancel_hotel_reservation':'cancelled','cancel_car_rental':'cancelled'}
        if isinstance(r,dict) and r.get('status') in ['preview','rejected'] and e['tool'] in completed:
            e={**e,'result':{**r,'status':completed[e['tool']]}}
        return super().observe(e)
