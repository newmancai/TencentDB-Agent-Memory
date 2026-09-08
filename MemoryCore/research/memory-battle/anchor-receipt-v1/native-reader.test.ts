import {it,expect} from 'vitest';
import {mkdtemp} from 'node:fs/promises';
import {join} from 'node:path';
import {VectorStore} from '../../../src/core/store/sqlite.js';
import {writeMemory} from '../../../src/core/record/l1-writer.js';
import {executeMemorySearch} from '../../../src/core/tools/memory-search.js';
import {readControlled} from './native-reader.js';
it('uses exact native base path on off, error, timeout, corrupt scope and stale version',async()=>{
  const root=await mkdtemp('/tmp/receipt-fallback-test-'),base=new VectorStore(join(root,'base.sqlite'),0),evolved=new VectorStore(join(root,'e.sqlite'),0);base.init();evolved.init();
  try{
    for(const [store,id,value] of [[base,'old',10],[evolved,'old',10],[evolved,'new',20]] as const){
      await writeMemory({baseDir:join(root,id),sessionKey:'scope',sessionId:'task',userId:'scope',agentId:'test',vectorStore:store,
        memory:{content:`cart subtotal ${value}`,type:'episodic',priority:60,scene_name:'test',source_message_ids:['receipt'],metadata:{}},decision:{record_id:id,action:'store',target_ids:[]}});
    }
    const common={query:'cart subtotal',scope:'scope',base,evolved,timeoutMs:5};
    const baseline=await executeMemorySearch({query:common.query,limit:8,vectorStore:base});
    expect((await readControlled({...common,enabled:false,load:async()=>{throw Error('must bypass');}})).result).toEqual(baseline);
    for(const load of [async()=>{throw Error('read failure');},async()=>({schema:99}),async()=>({schema:1,scope:'other',active:[]}),async()=>({schema:1,scope:'scope',active:[{id:'new',version:2}]}),()=>new Promise(()=>{})]){
      const r=await readControlled({...common,enabled:true,load});expect(r.fallback).toBe(true);expect(r.result).toEqual(baseline);
    }
    const r=await readControlled({...common,timeoutMs:1000,enabled:true,load:async()=>({schema:1,scope:'scope',active:[{id:'new',version:1}]})});
    expect(r.fallback).toBe(false);expect(r.result.results.map(x=>x.id)).toEqual(['new']);
    const broken=new VectorStore(join(root,'corrupt.sqlite'),0);
    broken.getRawDb().exec('CREATE VIEW l1_records AS SELECT 1 AS corrupt');broken.init();
    try{
      expect(broken.isDegraded()).toBe(true);
      const fallback=await readControlled({...common,evolved:broken,enabled:true,load:async()=>({schema:1,scope:'scope',active:[]})});
      expect(fallback.fallback).toBe(true);expect(fallback.result).toEqual(baseline);
    }finally{broken.close();}
  }finally{base.close();evolved.close();}
});
