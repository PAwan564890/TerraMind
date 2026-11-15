"""Real HTTP verification; NEVER mocks a model. Defaults to recorded weather.

--require-llm fails rather than claiming success when live generation is disabled.
"""
import argparse
import math
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit_app.api_client import APIClient


def pacing_seconds(raw):
    try: value = float(raw)
    except ValueError: raise argparse.ArgumentTypeError('Pacing must be seconds from 0 to 60.') from None
    if not math.isfinite(value) or not 0 <= value <= 60:
        raise argparse.ArgumentTypeError('Pacing must be seconds from 0 to 60.')
    return value


class VerificationPacer:
    """Minimum interval between potential LLM call starts; verification only."""
    def __init__(self, seconds, clock=None, sleep=None):
        self.seconds = seconds
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.last_start = None

    def wait(self):
        if self.last_start is not None:
            delay = self.seconds-(self.clock()-self.last_start)
            if delay > 0: self.sleep(delay)
        self.last_start = self.clock()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api-url',default='http://127.0.0.1:8000')
    parser.add_argument('--source',choices=['snapshot','live'],default='snapshot')
    parser.add_argument('--mode',choices=['demo','trained'],default='demo')
    parser.add_argument('--require-llm',action='store_true')
    parser.add_argument('--min-interval-seconds',type=pacing_seconds,default=0.0,
        help='Optional verification-only pacing between LLM call starts (0–60 seconds; default 0).')
    args=parser.parse_args()
    client=APIClient(args.api_url)
    print('NLP mode:',args.mode,'| Environmental source:',args.source)
    configured=client.system().get('genai',{}).get('configured',False)
    print('Provider configured:',configured)
    print('Verification pacing seconds:',args.min_interval_seconds)
    pacer=VerificationPacer(args.min_interval_seconds if configured else 0)
    text='Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.'
    for language in ['en','hi','ne']:
        pacer.wait()
        result=client.run(text,'verify-genai-'+language,args.mode,args.source,language)
        assert result['environment']['status']=='ok', result['environment']['message']
        assert len(result['environment']['results'][0]['daily'])==7
        assert result['context_id']
        explanation=result['explanation']
        print(language,'environment PASS; GenAI status:',explanation['status'])
        if explanation['status']=='disabled':
            assert explanation['text'] is None
            if args.require_llm:
                raise SystemExit('LIVE LLM NOT VERIFIED: configure provider, model and credentials in the backend process, then restart.')
            print('SKIP live LLM: no credentials/provider; real data and analytics verified.')
        else:
            assert explanation['status']=='ok', explanation['message']
            assert explanation['text'] and explanation['sources'] and explanation['claims']
            assert explanation['language']==language
            for question,metric in [
                ('Explain the mean daily temperature in these stored results.','temperature_mean_c'),
                ('Explain the rainfall summary in these stored results.','rainfall_total_mm'),
            ]:
                pacer.wait()
                followup=client.explain('verify-genai-'+language,result['context_id'],question,language)
                print(language,metric,'follow-up status:',followup['status'])
                assert followup['status']=='ok', f"{metric}: {followup['status']}: {followup['message']}"
                assert followup['text'] and followup['sources'] and followup['language']==language
                assert followup['claims'] and all(c['metric']==metric for c in followup['claims'])
                assert followup['provider'] and followup['model'], 'A deterministic fallback is not live LLM verification.'
            refused=client.explain('verify-genai-'+language,result['context_id'],
                'What was the humidity in these stored results?',language)
            assert refused['status']=='unsupported' and refused['text'] is None
            print(language,'LIVE LLM grounded temperature/rainfall follow-ups PASS; absent humidity rejected')
    print('HTTP verification finished. Disabled/skipped generation is not a live LLM pass.')


if __name__=='__main__':
    main()
