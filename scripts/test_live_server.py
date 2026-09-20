import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def test_eval(key):
    req = urllib.request.Request(
        'http://localhost:8990/api/evaluate_sample',
        data=json.dumps({'key': key}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8')).get('result', {})
        print(f"{res.get('candidate_name'):<16} | Status: {res.get('status'):<14} | Score: {res.get('overall_match_score')}% | Tenure: {res.get('total_calendar_years')}y")
        if res.get('knockout_violations'):
            for v in res['knockout_violations']:
                print(f"   ❌ {v.get('criterion_name')}: {v.get('deficit_reason')}")
        print()

print("Testing live API evaluations against Senior Go Engineer (Stripe):")
print("-" * 80)
test_eval('elena_qualified')
test_eval('alex_junior')
test_eval('rajesh_visa')
