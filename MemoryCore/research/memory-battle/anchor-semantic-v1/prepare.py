"""Select public STALE observation boundaries, emit raw runtime separately from labels."""
import argparse,hashlib,json,re,collections
from pathlib import Path

def norm(s):return re.sub(r'\W+','',s.casefold())
def sha(s):return hashlib.sha256(s.encode()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    rows=json.loads(a.input.read_text());eligible=[];excluded=[]
    for row in rows:
        matches=[]
        for field,si in zip(['M_old','M_new'],row['relevant_session_index']):
            found=[(si,mi) for mi,m in enumerate(row['haystack_session'][si]) if m['role']=='user' and norm(row[field]) in norm(m['content'])]
            matches.append(found)
        if any(len(v)!=1 for v in matches):excluded.append(row['uid']);continue
        eligible.append((row,matches[0][0],matches[1][0]))
    selected=[];used=set()
    for kind in ['T1','T2']:
        count=0
        for row,old,new in sorted(eligible,key=lambda v:sha(norm(v[0]['M_old']))):
            group=sha(norm(row['M_old']))
            if row['type']!=kind or group in used:continue
            used.add(group);selected.append((row,old,new,['development','calibration','heldout'][count%3],group));count+=1
            if count==24:break
    runtime=[];gold={}
    for row,old,new,split,group in selected:
        sources=[];targets=[]
        for si,session in enumerate(row['haystack_session']):
            for mi,m in enumerate(session):
                if (si,mi)>=new:break
                if m['role']!='user':continue
                for part,start in enumerate(range(0,len(m['content']),1600)):
                    rid=f's{si}m{mi}p{part}';sources.append(dict(id=rid,order=[si,mi,part],observedAt=row['timestamps'][si],content=m['content'][start:start+1600]))
                    if (si,mi)==old:targets.append(rid)
            if si>=new[0]:break
        observation=row['haystack_session'][new[0]][new[1]]['content']
        runtime.append(dict(id=row['uid'],split=split,group=group,sources=sources,
                            observation=dict(id=f's{new[0]}m{new[1]}',order=list(new),observedAt=row['timestamps'][new[0]],content=observation),
                            query=row['probing_queries']['dim1_query']))
        gold[row['uid']]=dict(type=row['type'],target_record_ids=targets,old=row['M_old'],new=row['M_new'],explanation=row['explanation'])
    a.output.mkdir(parents=True,exist_ok=True)
    for name,data in [('runtime.json',runtime),('gold.json',gold),('manifest.json',dict(selected=len(runtime),split_counts=dict(collections.Counter(x['split'] for x in runtime)),excluded_alignment=excluded,source_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest()))]:
        (a.output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'selected':len(runtime),'split_counts':dict(collections.Counter(x['split'] for x in runtime)),'excluded_alignment':len(excluded)}))

if __name__=='__main__':main()
