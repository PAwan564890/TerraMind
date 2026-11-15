"""Streamlit AppTest against a RUNNING real FastAPI server (not mocked HTTP).

Run from repository root: python scripts/verify_dashboard.py
Requires TERRAMIND_DEMO=1 on the backend. Includes one live network request.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest
from streamlit_app.config import EXAMPLES


def main():
    app=AppTest.from_file('streamlit_app/app.py',default_timeout=90).run()
    def select(label,value):
        next(w for w in app.selectbox if w.label==label).select(value).run()
    def submit():
        next(w for w in app.button if w.label=='Analyze and retrieve').click().run()
        assert not app.exception, app.exception
    select('NLP mode','Rule demonstration')
    select('Environmental data','Recorded snapshot · 1–7 Jan 2025')
    submit()
    assert not app.error and len(app.metric)==7
    assert len(app.get('arrow_vega_lite_chart'))==2
    print('PASS snapshot dashboard, metrics and two charts')
    select('Example question',EXAMPLES[3])
    submit()
    assert not app.error
    assert any('Town comparison' in w.value for w in app.subheader)
    print('PASS two-town comparison')
    select('Environmental data','Live Open-Meteo')
    select('Example question',EXAMPLES[2])
    submit()
    assert not app.error
    assert next(w for w in app.metric if w.label=='Detected language').value=='Nepali'
    assert any(w.label=='Mean daily temperature' for w in app.metric)
    print('PASS live Nepali query through Streamlit -> HTTP FastAPI -> Open-Meteo')
    app.text_area[0].input('???').run()
    submit()
    assert not app.metric and app.error
    print('PASS failed input clears previous data')


if __name__=='__main__':
    main()
