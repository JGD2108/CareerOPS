import requests
try:
    r = requests.get('http://127.0.0.1:8000/api/v1/emails')
    print('status', r.status_code)
    if r.status_code==200:
        data = r.json()
        total = len(data)
        job_categories = ['application_confirmation','interview_invitation','coding_assessment','recruiter_follow_up','rejection','offer','documents_requested','form_pending','job_alert']
        job_inbox = [e for e in data if e.get('application_id') or e.get('category') in job_categories]
        print('total emails:', total)
        print('job inbox count:', len(job_inbox))
        print('\nSample non-job emails (first 10):')
        non_job = [e for e in data if e not in job_inbox]
        for e in non_job[:10]:
            print('-', e.get('subject')[:80] if e.get('subject') else '<no subject>', '|', e.get('from_email'), '|', e.get('category'))
    else:
        print(r.text)
except Exception as e:
    print(f"Error: {e}")
