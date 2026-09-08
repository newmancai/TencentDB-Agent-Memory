/** Native field-addressed retrieval BEFORE the next public result is written.
 * Probe values are evaluator-only; only identity/field enter search. This is not
 * an autonomous agent or an end-to-end natural-language query benchmark.
 */
import {readFile,writeFile,mkdtemp} from 'node:fs/promises';
import {join} from 'node:path';
import {VectorStore} from '../../../src/core/store/sqlite.js';
import {writeMemory} from '../../../src/core/record/l1-writer.js';
import {readControlled,type Head} from './native-reader.js';
const [input,output]=process.argv.slice(2);
if(!input||!output)throw Error('native-temporal.ts temporal-native-input.jsonl output.json');
const arms=['base','naive','E'] as const;
const key=(f:any)=>JSON.stringify([f.scope,f.entity,f.identity,f.field]);
const summaries:Record<string,any>={},details:any[]=[];
for(const task of (await readFile(input,'utf8')).trim().split('\n').map(x=>JSON.parse(x))){
  const root=await mkdtemp('/tmp/anchor-receipt-temporal-');
  const stores=Object.fromEntries(arms.map(a=>[a,new VectorStore(join(root,`${a}.sqlite`),0)])) as Record<typeof arms[number],VectorStore>;
  const heads:Record<string,Head>={},records:Record<string,Map<string,any>>={};
  const c=summaries[task.split]??={tasks:0,reads:0,fields:0,base:0,naive:0,E:0,regressions:0,improvements:0,fallbacks:0,historicalLeaks:0,searchMs:[]};
  try{
    for(const arm of arms){stores[arm].init();if(stores[arm].isDegraded())throw Error('SQLite unavailable');heads[arm]={schema:1,scope:task.id,active:[]};records[arm]=new Map();}
    for(const step of task.timeline){
      if(step.probes.length){
        const correct:Record<string,boolean>={};const fieldResults:any[]=[];
        for(const arm of arms){
          const active=new Set(heads[arm].active.map(r=>r.id));let all=true;
          for(const probe of step.probes){
            const started=performance.now();
            const r=await readControlled({query:`${probe.identity} ${probe.field}`,scope:task.id,enabled:arm!=='base',base:stores.base,evolved:stores[arm],load:async()=>heads[arm]});
            c.searchMs.push(performance.now()-started);c.fallbacks+=Number(r.fallback);
            const leak=arm!=='base'&&r.result.results.some(x=>!active.has(x.id));c.historicalLeaks+=Number(leak);
            // First retrieved record for the requested field, with its persisted
            // content checked, rather than using the ledger's active answer.
            const hit=r.result.results.find(x=>records[arm].has(x.id)&&key(records[arm].get(x.id).fact)===key(probe));
            const expected=`${probe.entity} ${probe.identity} ${probe.field} = ${JSON.stringify(probe.value)}`;
            const match=!!hit&&hit.content===expected;all&&=match;
            fieldResults.push({arm,key:key(probe),found:!!hit,correct:match,recordId:hit?.id});
          }
          correct[arm]=all;c[arm]+=Number(all);
        }
        c.reads++;c.fields+=step.probes.length;c.regressions+=Number(correct.base&&!correct.E);c.improvements+=Number(!correct.base&&correct.E);
        details.push({task:task.id,event:step.event,correct,fieldResults});
      }
      // Future records and head updates become accessible only after scoring.
      for(const arm of arms){
        for(const r of step.after[arm].records){
          const f=r.fact;
          const saved=await writeMemory({baseDir:join(root,arm),sessionKey:task.id,sessionId:task.id,userId:task.id,agentId:'receipt-temporal',vectorStore:stores[arm],memory:{content:`${f.entity} ${f.identity} ${f.field} = ${JSON.stringify(f.value)}`,type:'episodic',priority:60,scene_name:'receipt-state',source_message_ids:[f.source],metadata:{}},decision:{record_id:r.id,action:'store',target_ids:[]}});
          if(!saved||saved.id!==r.id||saved.version!==r.version)throw Error('native write identity mismatch');
          records[arm].set(r.id,r);
        }
        heads[arm]={schema:1,scope:task.id,active:step.after[arm].active};
      }
    }
    c.tasks++;
  }finally{for(const store of Object.values(stores))store.close();}
}
for(const c of Object.values(summaries)){const times=c.searchMs.sort((a:number,b:number)=>a-b);c.searchCalls=times.length;c.searchP50Ms=times[Math.floor(times.length*.5)];c.searchP95Ms=times[Math.floor(times.length*.95)];delete c.searchMs;}
await writeFile(output,JSON.stringify({summaries,limit:'Field-addressed native replay; known fields selected offline, values hidden from retrieval. Not new autonomous Agent E2E. All 300 original tasks, unchanged splits and policy.',details},null,2)+'\n');
console.log(JSON.stringify(summaries,null,2));
