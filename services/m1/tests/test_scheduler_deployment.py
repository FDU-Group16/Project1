"""Exercise the actual release health gate; only Docker/curl are boundary fixtures."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
FAKE=r'''
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['CALL_LOG'],'a') as f: f.write(json.dumps([Path(sys.argv[0]).name,args])+'\n')
if Path(sys.argv[0]).name=='curl': sys.exit(0)
if args[-2:]==['config','--services']:
 print('postgres\nm1-api\nweb'+ ('\nm1-scheduler' if os.environ['HAS_SCHEDULER']=='1' else ''))
elif args[-3:]==['port','web','80']: print('127.0.0.1:8080')
elif '--healthcheck' in args: sys.exit(int(os.environ['WORKER_EXIT']))
'''


class SchedulerDeployment(unittest.TestCase):
    def check_release(self,defined,exit_code):
        with tempfile.TemporaryDirectory(prefix='m1-release-test-') as temp:
            base=Path(temp);bin_dir=base/'bin';bin_dir.mkdir()
            deploy=base/'deployment';release=deploy/'releases'/('a'*40);release.mkdir(parents=True)
            (release/'compose.staging.yaml').write_text('services: {}\n')
            (deploy/'.env').write_text('')
            for name in ['docker','curl']:
                path=bin_dir/name;path.write_text('#!'+sys.executable+'\n'+FAKE);path.chmod(0o755)
            log=base/'calls';log.write_text('')
            env={**os.environ,'PATH':str(bin_dir)+os.pathsep+os.environ['PATH'],
                 'STAGING_DEPLOYMENT_ROOT':str(deploy),'CALL_LOG':str(log),
                 'HAS_SCHEDULER':str(int(defined)),'WORKER_EXIT':str(exit_code)}
            result=subprocess.run(['bash',str(ROOT/'scripts/activate-staging.sh'),'a'*40,'--check'],
                env=env,capture_output=True,text=True,timeout=5)
            return result.returncode,log.read_text()

    def test_dead_worker_blocks_release_even_when_apis_and_postgres_are_live(self):
        code,calls=self.check_release(True,1)
        self.assertNotEqual(code,0)
        self.assertIn('--healthcheck',calls)

    def test_healthy_worker_allows_release(self):
        code,calls=self.check_release(True,0)
        self.assertEqual(code,0)
        self.assertIn('--healthcheck',calls)

    def test_legacy_release_can_still_be_checked_during_rollback(self):
        code,calls=self.check_release(False,1)
        self.assertEqual(code,0)
        self.assertNotIn('--healthcheck',calls)


if __name__=='__main__': unittest.main()
