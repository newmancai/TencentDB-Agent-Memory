import {readFile,writeFile,mkdtemp} from 'node:fs/promises';
import {join} from 'node:path';
import {VectorStore} from '../../../src/core/store/sqlite.js';
import {writeMemory} from '../../../src/core/record/l1-writer.js';
import {executeMemorySearch} from '../../../src/core/tools/memory-search.js';
import type {EmbeddingService} from '../../../src/core/store/embedding.js';

const [input,embeddings,outputPrefix]=process.argv.slice(2);
if(!input||!embeddings||!outputPrefix)throw Error('retrieve-hybrid.ts runtime.json embeddings.json output-prefix');
const vectors=JSON.parse(await readFile(embeddings,'utf8'));
const tasks=JSON.parse(await readFile(input,'utf8')).filter((t:any)=>t.split===vectors.split);
function service(kind:'documents'|'queries'):EmbeddingService{
  const embed=async(text:string)=>{
    const value=vectors[kind][text];
    if(!Array.isArray(value)||value.length!==vectors.dimensions||!value.every(Number.isFinite))throw Error('missing or invalid actual embedding');
    return new Float32Array(value);
  };
  return {embed,embedBatch:texts=>Promise.all(texts.map(embed)),getDimensions:()=>vectors.dimensions,
    getProviderInfo:()=>({provider:'offline-real-embedding',model:'Qwen3-Embedding-0.6B'}),isReady:()=>true,startWarmup:()=>{}};
}
const documentService=service('documents'),queryService=service('queries');
const output:{fts:any[];hybrid:any[]}={fts:[],hybrid:[]};
for(const task of tasks){
  const root=await mkdtemp('/tmp/anchor-semantic-hybrid-'),store=new VectorStore(join(root,'memory.sqlite'),vectors.dimensions);store.init();
  if(store.isDegraded())throw Error('native vector/SQLite unavailable');
  try{
    for(const s of task.sources)await writeMemory({baseDir:root,sessionKey:task.id,sessionId:task.id,userId:task.id,agentId:'semantic-research',vectorStore:store,embeddingService:documentService,
      memory:{content:s.content,type:'episodic',priority:60,scene_name:'raw-history',source_message_ids:[s.id],metadata:s.observedAt?{observedAt:s.observedAt}:{}},decision:{record_id:s.id,action:'store',target_ids:[]}});
    for(const mode of ['fts','hybrid'] as const){
      const search=await executeMemorySearch({query:task.observation.content,limit:8,vectorStore:store,embeddingService:mode==='hybrid'?queryService:undefined});
      if(search.strategy!==mode)throw Error(`unexpected retrieval fallback: ${search.strategy}`);
      output[mode].push({id:task.id,split:task.split,root,observation:task.observation,
        candidates:search.results.map(r=>({id:r.id,version:r.version,content:r.content,order:task.sources.find((s:any)=>s.id===r.id).order,observedAt:task.sources.find((s:any)=>s.id===r.id).observedAt})),
        readerQuery:task.query,strategy:search.strategy,sourceCount:task.sources.length});
    }
  }finally{store.close();}
}
for(const mode of ['fts','hybrid'] as const)await writeFile(`${outputPrefix}.${mode}.json`,JSON.stringify(output[mode],null,2));
console.log(JSON.stringify({tasks:tasks.length,outputPrefix}));
