import {executeMemorySearch} from '../../../src/core/tools/memory-search.js';
import type {IMemoryStore} from '../../../src/core/store/types.js';
export interface Head {schema:1;scope:string;active:{id:string;version:number}[]}
/** Separate base store remains readable even when every auxiliary artifact fails. */
export async function readControlled(p:{query:string;scope:string;enabled:boolean;base:IMemoryStore;evolved:IMemoryStore;load:()=>Promise<unknown>;timeoutMs?:number}){
  const baseline=()=>executeMemorySearch({query:p.query,limit:8,vectorStore:p.base});
  if(!p.enabled)return {result:await baseline(),fallback:false,reason:'off'};
  let timer:ReturnType<typeof setTimeout>|undefined;
  try{
    const result=await Promise.race([(async()=>{
      if(p.evolved.isDegraded())throw Error('evolved store degraded');
      const h:any=await p.load();
      if(h?.schema!==1||h.scope!==p.scope||!Array.isArray(h.active)||h.active.length>2048)throw Error('invalid head');
      const rows=await p.evolved.queryL1Records();
      if(rows.length>2048||rows.some(r=>r.user_id!==p.scope))throw Error('invalid store scope/capacity');
      const seen=new Set<string>();
      for(const entry of h.active){
        if(typeof entry?.id!=='string'||!Number.isInteger(entry.version)||entry.version<1||seen.has(entry.id))throw Error('invalid identity');
        if(!rows.some(r=>r.record_id===entry.id&&r.version===entry.version))throw Error('missing record/version');
        seen.add(entry.id);
      }
      return executeMemorySearch({query:p.query,limit:8,vectorStore:p.evolved,excludedRecordIds:rows.filter(r=>!seen.has(r.record_id)).map(r=>r.record_id)});
    })(),new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(Error('timeout')),p.timeoutMs??1000);})]);
    return {result,fallback:false,reason:'evolved'};
  }catch(e){return {result:await baseline(),fallback:true,reason:String(e)};}
  finally{if(timer)clearTimeout(timer);}
}
