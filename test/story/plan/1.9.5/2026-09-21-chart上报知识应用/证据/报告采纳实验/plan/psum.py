import json,sys
ph=sys.argv[1]
j=json.load(open(f'doc/features/ISSUE-206/{ph}/reports/summary.json',encoding='utf-8-sig'))
print(ph, {'closure_status':j.get('closure_status'),'verdict':j.get('verdict'),'subject':(j.get('verifier_subject_id') or '')[:16],
 'mode':(j.get('verifier_closure') or {}).get('mode'),
 'signals':[s.get('id') if isinstance(s,dict) else s for s in j.get('readiness_signals') or []]})
