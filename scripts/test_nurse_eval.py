import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("1. Switching job profile to ICU Registered Nurse (Hospital)...")
req_switch = urllib.request.Request(
    'http://localhost:8990/api/load_sample_jd',
    data=json.dumps({'key': 'icu_nurse'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req_switch) as resp:
    p_data = json.loads(resp.read().decode('utf-8'))
    print("   Active Role:", p_data['profile']['title'])
    print("   Knockouts:", [k['name'] for k in p_data['profile']['knockouts']])

print("\n2. Evaluating Sarah Jenkins (Certified Nursing Assistant)...")
req_eval = urllib.request.Request(
    'http://localhost:8990/api/evaluate_sample',
    data=json.dumps({'key': 'sarah_cna'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req_eval) as resp:
    res = json.loads(resp.read().decode('utf-8'))['result']
    print(f"   Candidate: {res['candidate_name']} | Status: {res['status']}")
    for v in res['knockout_violations']:
        print(f"   ❌ {v['criterion_name']}: {v['deficit_reason']}")
        print(f"      Evidence: {v['resume_evidence']}")

# Switch back to senior_go
urllib.request.urlopen(urllib.request.Request(
    'http://localhost:8990/api/load_sample_jd',
    data=json.dumps({'key': 'senior_go'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
))
