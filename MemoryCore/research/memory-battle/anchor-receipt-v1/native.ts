/** Persist public replay records through MemoryCore; verify native retrieval and reopening. */
import {readFile,appendFile,mkdtemp,writeFile} from 'node:fs/promises';
import {join} from 'node:path';
import {VectorStore} from '../../../src/core/store/sqlite.js';
import {writeMemory} from '../../../src/core/record/l1-writer.js';
import {executeMemorySearch} from '../../../src/core/tools/memory-search.js';
import {readControlled} from './native-reader.js';
const [input,output]=process.argv.slice(2);if(!input||!output)throw Error('native.ts feedback.jsonl output.jsonl');
const tasks=(await readFile(input,'utf8')).trim().split('\n').map(x=>JSON.parse(x));
for(const task of tasks){
  const root=await mkdtemp('/tmp/anchor-receipt-native-'),path=join(root,'memory.sqlite');
  let store=new VectorStore(path,0);store.init();if(store.isDegraded())throw Error('SQLite unavailable');
  const baseStore=new VectorStore(join(root,'base.sqlite'),0);baseStore.init();
  const started=performance.now();
  try{
    for(const r of task.history){
      const f=r.fact,content=`${f.entity} ${f.identity} ${f.field} = ${JSON.stringify(f.value)}`;
      const save=(vectorStore:VectorStore,directory:string)=>writeMemory({baseDir:join(root,directory),sessionKey:task.id,sessionId:task.id,userId:task.id,agentId:'receipt-replay',vectorStore,
        memory:{content,type:'episodic',priority:60,scene_name:'receipt-state',source_message_ids:[f.source],metadata:{}},decision:{record_id:r.id,action:'store',target_ids:[]}});
      const saved=await save(store,'evolved');
      if(r.generation===1)await save(baseStore,'base');
      if(!saved||saved.id!==r.id||saved.version!==r.version)throw Error('native identity/version mismatch');
    }
    const active=new Set<string>(task.active_ids),base=new Set<string>(task.history.filter((r:any)=>r.generation===1).map((r:any)=>r.id));
    const head={schema:1,scope:task.id,active:task.history.filter((r:any)=>active.has(r.id)).map((r:any)=>({id:r.id,version:r.version}))};
    await writeFile(join(root,'view.json'),JSON.stringify(head));
    store.close();store=new VectorStore(path,0);store.init();
    const rows=await store.queryL1Records(),persisted=new Set(rows.map(r=>r.record_id));
    if(task.history.some((r:any)=>!persisted.has(r.id)))throw Error('history lost on reopen');
    const changed=task.history.filter((r:any)=>active.has(r.id)&&r.generation>1);
    const checks=[];
    for(const r of changed){
      const query=`${r.fact.identity} ${r.fact.field}`;
      const controlled=await readControlled({query,scope:task.id,enabled:true,base:baseStore,evolved:store,load:async()=>JSON.parse(await readFile(join(root,'view.json'),'utf8'))});
      if(controlled.fallback)throw Error(`unexpected fallback ${controlled.reason}`);
      const result=controlled.result;
      const historicalLeak=result.results.some(x=>!active.has(x.id));
      checks.push({recordId:r.id,found:result.results.some(x=>x.id===r.id),historicalLeak});
    }
    const query=task.history.length?`${task.history[0].fact.identity} ${task.history[0].fact.field}`:'status';
    const baseline=await executeMemorySearch({query,limit:8,vectorStore:baseStore});
    const fallbackChecks=[];
    for(const [name,enabled,load] of [
      ['off',false,async()=>{throw Error('off must not load');}],
      ['read_failure',true,async()=>{throw Error('read failure');}],
      ['corrupt',true,async()=>({schema:99})],
      ['scope',true,async()=>({...head,scope:'wrong'})],
      ['version',true,async()=>({...head,active:[{id:'absent',version:2}]})],
      ['timeout',true,()=>new Promise(()=>{})],
    ] as const){
      const r=await readControlled({query,scope:task.id,enabled,base:baseStore,evolved:store,load,timeoutMs:5});
      fallbackChecks.push({name,exactBase:JSON.stringify(r.result)===JSON.stringify(baseline),fallback:r.fallback});
    }
    await appendFile(output,JSON.stringify({task:task.id,root,records:rows.length,historyPreserved:true,changedFields:changed.length,fallbackChecks,
      retrieved:checks.filter(x=>x.found).length,historicalLeaks:checks.filter(x=>x.historicalLeak).length,checks,ms:performance.now()-started})+'\n');
  }finally{store.close();baseStore.close();}
}
console.log(JSON.stringify({tasks:tasks.length,output}));
