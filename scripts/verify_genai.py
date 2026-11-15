"""Real HTTP verification; NEVER mocks a model. Defaults to recorded weather.

--require-llm fails rather than claiming success when live generation is disabled.
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit_app.api_client import APIClient


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api-url',default='http://127.0.0.1:8000')
    parser.add_argument('--source',choices=['snapshot','live'],default='snapshot')
    parser.add_argument('--mode',choices=['demo','trained'],default='demo')
    parser.add_argument('--require-llm',action='store_true')
    args=parser.parse_args()
    client=APIClient(args.api_url)
    print('Provider configured:',client.system().get('genai',{}).get('configured',False))
    text='Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.'
    for language in ['en','hi','ne']:
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
            followup=client.explain('verify-genai-'+language,result['context_id'],'Explain the mean daily temperature in these stored results.',language)
            assert followup['status']=='ok',followup['message']
            print(language,'LIVE LLM grounded explanation and follow-up PASS')
    print('HTTP verification finished. Disabled/skipped generation is not a live LLM pass.')


if __name__=='__main__':
    main()
