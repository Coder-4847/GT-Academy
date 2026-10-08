"""Manage this project's GitHub Pages deployment using the existing Git credential helper."""
import argparse
import json
import os
import subprocess
from urllib.request import Request,urlopen
from urllib.error import HTTPError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('enable','status','dispatch'))
    args=parser.parse_args()
    result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,timeout=30,
                          env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never'))
    fields=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    if not fields.get('password'):raise SystemExit('Sign in to GitHub through Git Credential Manager first.')
    def api(path,method='GET',body=None):
        request=Request('https://api.github.com/repos/Coder-4847/GT-Academy'+path,method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization':'Bearer '+fields['password'],'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'GT-Academy-deployment'})
        with urlopen(request,timeout=40) as response:
            text=response.read();return json.loads(text) if text else {}
    if args.action=='enable':
        try: api('/pages','POST',{'build_type':'workflow'})
        except HTTPError as error:
            if error.code!=409:raise
            api('/pages','PUT',{'build_type':'workflow'})
        print('GitHub Pages configured for Actions deployment.')
    elif args.action=='dispatch':
        api('/actions/workflows/pages.yml/dispatches','POST',{'ref':'main'})
        print('Pages deployment requested for main.')
    else:
        runs=api('/actions/workflows/pages.yml/runs?per_page=3')
        print(json.dumps([dict(id=r['id'],status=r['status'],conclusion=r['conclusion'],url=r['html_url'],sha=r['head_sha']) for r in runs['workflow_runs']],indent=2))
        try:
            pages=api('/pages');print(json.dumps({k:pages.get(k) for k in ('html_url','status','build_type')}))
        except HTTPError as error: print(f'Pages status: HTTP {error.code}')


if __name__=='__main__':main()
