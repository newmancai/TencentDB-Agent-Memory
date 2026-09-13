import { it,expect } from 'vitest';
import { mkdtemp,rm } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from './sqlite.js';
it('honors exact record IDs together with ownership filters',async()=>{
 const root=await mkdtemp('/tmp/anchor-record-id-test-');const store=new VectorStore(join(root,'db.sqlite'),0);store.init();
 try{
  const base={type:'episodic',priority:50,scene_name:'test',source_message_ids:['s'],metadata:{},timestamps:[],createdAt:'2026-09-08T00:00:00Z',updatedAt:'2026-09-08T00:00:00Z',version:1,sessionKey:'test',sessionId:'test',agentId:'a'};
  await store.upsertL1({...base,id:'one',content:'first',userId:'u1'},undefined);
  await store.upsertL1({...base,id:'two',content:'second',userId:'u2'},undefined);
  expect(store.queryL1Records({recordIds:['one']}).map(r=>r.record_id)).toEqual(['one']);
  expect(store.queryL1Records({recordIds:[]})).toEqual([]);
  expect(store.queryL1Records({recordIds:['one'],userId:'u2'})).toEqual([]);
  expect(store.queryL1Records({recordIds:['two','absent'],userId:'u2'}).map(r=>r.record_id)).toEqual(['two']);
 }finally{store.close();await rm(root,{recursive:true,force:true});}
});
