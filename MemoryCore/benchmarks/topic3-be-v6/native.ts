/** Exact source persistence/readback; this diagnostic has no discovery credit. */
import { readFile,writeFile,mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { VectorStore } from '../../src/core/store/sqlite.js';
import { writeMemory } from '../../src/core/record/l1-writer.js';
const [input,out]=process.argv.slice(2);
if(!input||!out) throw Error('native.ts pairs.json fresh-output');
const tasks=JSON.parse(await readFile(input,'utf8'));await mkdir(out);const results=[];
for(const t of tasks){
 if(!t.pair){results.push({...t,record:null});continue;}
 const dir=join(out,t.id);await mkdir(dir);const db=new VectorStore(join(dir,'base.sqlite'),0);db.init();
 try{
  if(db.isDegraded())throw Error('native unavailable');
  const old=t.pair.old;
  const record=await writeMemory({baseDir:dir,sessionKey:t.id,sessionId:old.session,userId:t.id,agentId:'topic3-v6',vectorStore:db,
   memory:{content:old.content,type:'episodic',priority:60,scene_name:'original-source',source_message_ids:[old.id],metadata:{}},
   decision:{record_id:'raw_'+old.id,action:'store',target_ids:[]}});
  if(!record)throw Error('write failed');
  const stored=await db.queryL1Records({recordIds:[record.id],userId:t.id});
  if(stored.length!==1||stored[0].version!==record.version||stored[0].content!==old.content)throw Error('readback mismatch');
  for(const s of t.targets)if(stored[0].content.slice(s.start,s.end)!==s.text)throw Error('span mismatch');
  results.push({...t,pair:{...t.pair,old:{...old,content:stored[0].content}},record:{id:record.id,version:record.version,directory:dir}});
 }finally{db.close();}
}
await writeFile(join(out,'records.json'),JSON.stringify(results));console.log(JSON.stringify({tasks:results.length,records:results.filter(r=>r.record).length}));
