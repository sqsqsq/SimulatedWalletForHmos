import json,sys
j=json.load(open('doc/features/AR90006/spec/reports/summary.json',encoding='utf-8-sig'))
print({'closure_status':j.get('closure_status'),'verdict':j.get('verdict'),'subject':(j.get('verifier_subject_id') or '')[:16],
 'request':(j.get('verifier_request') or '')[-60:],'report':(j.get('verifier_report') or '')[-60:],
 'mode':(j.get('verifier_closure') or {}).get('mode'),
 'signals':[s.get('id') if isinstance(s,dict) else s for s in j.get('readiness_signals') or []],
 'commit':bool(j.get('closure_commit'))})
