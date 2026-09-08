import {readFile,writeFile,mkdtemp} from 'node:fs/promises';
import {join} from 'node:path';
import {VectorStore} from '../../../src/core/store/sqlite.js';
import {writeMemory} from '../../../src/core/record/l1-writer.js';
import {executeMemorySearch} from '../../../src/core/tools/memory-search.js';
const [input,output]=process.argv.slice(2);if(!input||!output)throw Error('retrieve.ts runtime.json output.json');
const tasks=JSON.parse(await readFile(input,'utf8')),result=[];
for(const task of tasks){
  const root=await mkdtemp('/tmp/anchor-semantic-native-'),store=new VectorStore(join(root,'memory.sqlite'),0);store.init();
  if(store.isDegraded())throw Error('native SQLite unavailable');
  try{
    for(const s of task.sources)await writeMemory({baseDir:root,sessionKey:task.id,sessionId:task.id,userId:task.id,agentId:'semantic-research',vectorStore:store,
      memory:{content:s.content,type:'episodic',priority:60,scene_name:'raw-history',source_message_ids:[s.id],metadata:{}},decision:{record_id:s.id,action:'store',target_ids:[]}});
    const search=await executeMemorySearch({query:task.observation.content,limit:8,vectorStore:store});
    result.push({id:task.id,split:task.split,root,observation:task.observation,
      candidates:search.results.map(r=>({id:r.id,version:r.version,content:r.content,order:task.sources.find((s:any)=>s.id===r.id).order})),
      readerQuery:task.query,strategy:search.strategy,sourceCount:task.sources.length});
  }finally{store.close();}
}
await writeFile(output,JSON.stringify(result,null,2));console.log(JSON.stringify({tasks:result.length,output}));
