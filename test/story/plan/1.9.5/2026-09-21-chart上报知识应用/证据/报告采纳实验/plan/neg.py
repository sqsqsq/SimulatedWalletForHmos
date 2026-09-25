import json, pathlib, sys
mode=sys.argv[1]
j=json.load(open('doc/features/ISSUE-206/plan/reports/summary.json',encoding='utf-8-sig'))
new=j['verifier_subject_id']; old='6f4d2d820690386873738fac09fd9486a7010a309f6559fc520758d22bc07834'
t=pathlib.Path(f'doc/features/ISSUE-206/plan/reports/verifier.report.{old}.md').read_text(encoding='utf-8')
if mode=='wrong':   # 报告写到当前路径，但终态块回显的是旧 subject
    body=t
else:               # subject 对，但判 FAIL
    body=t.replace(old,new).replace('verdict: PASS','verdict: FAIL').replace('blocker_count: 0','blocker_count: 1')
pathlib.Path(j['verifier_report']).write_text(body,encoding='utf-8')
print(mode, 'report ->', j['verifier_report'][-20:])
