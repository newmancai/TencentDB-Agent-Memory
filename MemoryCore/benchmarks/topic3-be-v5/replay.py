"""Post-output host-contract diagnosis; no model calls or gold in feedback parser."""
import json
import sys
from pathlib import Path
from detect import v4
from partial import partial_feedback

root=Path(sys.argv[1]);pairs={r['id']:r['pair'] for r in json.loads((root/'adapted/pairs.json').read_text())}
results=[]
for line in (root/'model/results.jsonl').read_text().splitlines():
    row=json.loads(line);out=dict(id=row['id'],arms={})
    for arm,data in row['arms'].items():
        if arm=='direct' or len(data['calls'])<2:
            out['arms'][arm]=dict(relation=data['relation'],replayed=False,issues=[data['contract_error']] if data['contract_error'] else [])
            continue
        evidence={'later':{'spans':v4.segments(pairs[row['id']]['later']['content'],'n')}}
        out['arms'][arm]=dict(partial_feedback(data['calls'][1],data['targets'],evidence),replayed=True)
    results.append(out)
(root/'partial-replay.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
labels={r['id']:r['relation'] for r in json.loads((root/'source-review.json').read_text())['rows']}
summary={arm:dict(n=sum(bool(r['arms']) for r in results),agreement=sum(r['arms'][arm]['relation']==labels[r['id']] for r in results if r['arms']),
                 changed=sum(r['arms'][arm]['relation']=='changed' for r in results if r['arms'])) for arm in ['direct','joint','old_only']}
(root/'partial-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
