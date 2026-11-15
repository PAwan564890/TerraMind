"""Exercise the real HTTP workflow; start FastAPI first. No mocked retrieval."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit_app.api_client import APIClient


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api-url',default='http://127.0.0.1:8000')
    parser.add_argument('--source',choices=['live','snapshot'],default='snapshot')
    parser.add_argument('--mode',choices=['trained','demo'],default='demo')
    args=parser.parse_args()
    client=APIClient(args.api_url)
    print('Health:',client.health())
    questions=[
        ('en','Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.'),
        ('hi','गंगटोक में 2025-01-01 से 2025-01-07 तक तापमान और बारिश दिखाओ।'),
        ('ne','गान्तोकमा 2025-01-01 देखि 2025-01-07 सम्म तापक्रम र वर्षा देखाउनुहोस्।'),
    ]
    for language,text in questions:
        r=client.run(text,'verify-'+language,args.mode,args.source)
        assert r['analysis']['language']['code']==language, r['analysis']
        assert r['analysis']['status']=='ok', r['analysis']
        assert r['environment']['status']=='ok', r['environment']
        weather=r['environment']['results'][0]
        assert len(weather['daily'])==7
        assert weather['summary']['temperature_mean_c'] is not None
        assert weather['retrieved_at'] and weather['source_url']
        print(language,'PASS',weather['data_kind'],weather['summary'])


if __name__=='__main__':
    main()
