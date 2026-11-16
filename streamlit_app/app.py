"""Run from repository root: python -m streamlit run streamlit_app/app.py."""
import uuid
import pandas as pd
import streamlit as st
from streamlit_app.api_client import APIClient, APIError
from streamlit_app.config import API_URL, EXAMPLES

st.set_page_config(page_title='TerraMind · Sikkim Environment', page_icon='🌏', layout='wide')
st.markdown('''<style>
.block-container {max-width:1280px;padding-top:2rem;}
[data-testid="stMetric"] {background:#eef6f4;border-radius:10px;padding:16px;}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"] {color:#173e37;}
</style>''', unsafe_allow_html=True)
client = APIClient(API_URL)
if 'session_id' not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex

st.title('🌏 TerraMind')
st.caption('AI-Powered Earth System Digital Twin · Academic prototype')
st.markdown('Explore Sikkim’s weather through environmental questions in **English, Hindi and Nepali**. Inspect the language processing, data provenance and calculated summaries at each step.')

with st.sidebar:
    st.header('System information')
    try:
        health, system = client.health(), client.system()
        st.success('FastAPI connected')
        st.write('Trained models:', 'Loaded' if health['models_loaded'] else 'Unavailable')
        modes = ['Trained NLP'] + (['Rule demonstration'] if system['demo_enabled'] else [])
        selected_mode = st.selectbox('NLP mode', modes, index=0 if health['models_loaded'] else len(modes)-1)
        with st.expander('Model loading detail'):
            st.json(health)
    except APIError as error:
        health, system = {}, {}
        st.error(str(error))
        selected_mode = st.selectbox('NLP mode', ['Trained NLP'])
    selected_source = st.selectbox('Environmental data', ['Live Open-Meteo', 'Recorded snapshot · 1–7 Jan 2025'])
    source_mode = 'live' if selected_source.startswith('Live') else 'snapshot'
    explanation_language = st.selectbox('Explanation language', ['Automatic', 'English', 'Hindi', 'Nepali'])
    language_code = {'Automatic':None, 'English':'en', 'Hindi':'hi', 'Nepali':'ne'}[explanation_language]
    st.caption('GenAI: ' + ('configured' if system.get('genai', {}).get('configured') else 'not configured — data and analytics still work'))
    mode = 'demo' if selected_mode == 'Rule demonstration' else 'trained'
    st.caption('Supported data points: ' + (', '.join(system.get('towns', {}).values()) or 'Not exposed by backend') + '. Dates use Asia/Kolkata. Historical results are ERA5 reanalysis; current/recent results are weather model estimates.')
    if st.button('New conversation'):
        st.session_state.session_id = uuid.uuid4().hex
        st.session_state.pop('result', None)
        st.session_state.pop('followup_explanation', None)
        st.rerun()
    st.markdown('[Open-Meteo](https://open-meteo.com/) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)')
    st.caption('No disaster forecasting, causal explanation, or complete digital twin. Native-script language coverage is limited; rule demo has no measured confidence.')

if mode == 'demo':
    st.warning('RULE DEMONSTRATION — language detection, intent and entity spans use deterministic rules. This is not trained-model inference. Normalization, context and validation reuse the existing backend.')
if source_mode == 'snapshot':
    st.info('RECORDED DATA — real ERA5 data previously retrieved from Open-Meteo, covering 2025-01-01 through 2025-01-07 only. Select the first or comparison example. No live call will be made.')

st.header('Environmental question')
st.caption('Include a town, temperature or rainfall, and a period. “Last 7 days” means seven completed local calendar days. For a reliable historical demonstration, use the first example.')
def use_example():
    st.session_state.question = st.session_state.example

example = st.selectbox('Example question', EXAMPLES, key='example', on_change=use_example)
with st.form('question_form'):
    question = st.text_area('Your question', value=example, max_chars=500, height=100, key='question')
    submitted = st.form_submit_button('Analyze and retrieve', type='primary')
if submitted:
    # Clear old results first: a failed request must never display previous data.
    st.session_state.pop('result', None)
    st.session_state.pop('followup_explanation', None)
    try:
        with st.spinner('Analyzing question and retrieving environmental data…'):
            st.session_state.result = client.run(question, st.session_state.session_id, mode, source_mode, language_code)
    except APIError as error:
        st.error(str(error))

result = st.session_state.get('result')
if result:
    st.caption(f"Results for: {result['question']} · NLP: {result['mode']} · Data: {result['source_mode']}")
    analysis = result['analysis']
    st.header('NLP analysis')
    left, middle, right = st.columns(3)
    left.metric('Detected language', {'en':'English', 'hi':'Hindi', 'ne':'Nepali'}.get(analysis['language']['code'], '?'))
    middle.metric('Intent', analysis['intent']['label'])
    right.metric('Status', analysis['status'].replace('_', ' ').title())
    if result['mode'] == 'demo':
        st.caption('Confidence: unmeasured; schema values of 0 are placeholders, not model probabilities.')
    else:
        st.caption(f"Language confidence: {analysis['language']['confidence']:.2f} · Intent confidence: {analysis['intent']['confidence']:.2f}")
    with st.expander('Extracted entities and structured query', expanded=True):
        if analysis['entities']:
            st.dataframe(pd.DataFrame(analysis['entities']), use_container_width=True, hide_index=True)
        st.json(analysis.get('structured_query'))
    if analysis.get('clarification'):
        clarification = analysis['clarification']
        st.info(f"Clarification required: {clarification['message_key']} · Missing fields: {', '.join(clarification['missing_fields']) or 'see supported question examples'}")
    if analysis['status'] == 'out_of_domain':
        st.info('This question is outside the supported environmental vocabulary. Try one of the examples.')
    with st.expander('Processing notes'):
        st.write(analysis.get('warnings', []))
    environment = result.get('environment')
    if environment:
        st.header('Environmental data & analytics')
        if environment['status'] != 'ok':
            st.warning(environment['message'])
            for error in environment.get('errors', []):
                st.error(error)
        # A partial result may be shown, but never a complete comparison.
        for weather in environment['results']:
            st.subheader(weather['location_name'])
            st.caption(f"{weather['start']} → {weather['end']} · {weather['timezone']} · {weather['data_kind'].replace('_', ' ')}")
            st.markdown(f"Source: [{weather['source']}]({weather['source_url']})")
            st.caption(f"Retrieved at: {weather['retrieved_at']} · Requested point: {weather['requested_latitude']}, {weather['requested_longitude']} · Returned grid: {weather['grid_latitude']}, {weather['grid_longitude']}")
            for warning in weather['warnings']:
                st.caption(warning)
            if weather.get('current'):
                st.write('Current model estimate (separate from daily summaries)', weather['current'])
            summary = weather['summary']
            def number(value, suffix):
                return 'Missing' if value is None else f'{value:.1f} {suffix}'
            cols = st.columns(4)
            cols[0].metric('Mean daily temperature', number(summary['temperature_mean_c'], '°C'))
            cols[1].metric('Minimum / maximum', f"{number(summary['temperature_min_c'], '°C')} / {number(summary['temperature_max_c'], '°C')}")
            cols[2].metric('Rainfall sum' + ('' if summary['totals_complete'] else ' (partial)'), number(summary['rainfall_total_mm'], 'mm'))
            cols[3].metric('Total precipitation' + ('' if summary['totals_complete'] else ' (partial)'), number(summary['precipitation_total_mm'], 'mm'))
            frame = pd.DataFrame(weather['daily']).set_index('date')
            frame.index = pd.to_datetime(frame.index)
            c1, c2 = st.columns(2)
            with c1:
                st.write('Temperature time series · °C')
                st.line_chart(frame[['temperature_mean_c', 'temperature_min_c', 'temperature_max_c']])
            with c2:
                st.write('Daily rainfall · mm (total precipitation includes snow)')
                st.bar_chart(frame[['rainfall_mm']])
            st.caption(summary['interpretation'])
            with st.expander('Daily values and data coverage'):
                st.dataframe(frame, use_container_width=True)
                st.json(summary['valid_days'])
            st.caption(weather['attribution'])
        if environment['status'] == 'ok' and len(environment['results']) > 1:
            st.subheader('Town comparison · same requested period')
            st.dataframe(pd.DataFrame([{'Town': w['location_name'], 'Mean temperature °C':w['summary']['temperature_mean_c'],
                'Rainfall mm':w['summary']['rainfall_total_mm'], 'Precipitation mm':w['summary']['precipitation_total_mm'],
                'Complete totals':w['summary']['totals_complete']} for w in environment['results']]), hide_index=True, use_container_width=True)
            st.caption('Descriptive comparison only. Inspect coverage before comparing partial totals; mountain grid estimates may differ substantially from local conditions.')

    if environment and environment['results']:
        st.header('AI-generated explanation')
        st.caption('Optional LLM-selected facts, validated and rendered with language templates. Numerical calculations and source attribution come from the backend. This section is separate from NLP and environmental evidence.')

        def show_explanation(explanation):
            if explanation and explanation['status'] == 'ok':
                # Plain text only: model-originated HTML/markdown is never rendered.
                st.text(explanation['text'])
                st.caption('Validated explanation · ' + explanation.get('model', ''))
            elif explanation:
                st.info(explanation['message'])

        show_explanation(result.get('explanation'))
        if result.get('context_id'):
            st.caption('Follow-ups use only this stored environmental result, expiring after 15 minutes. For new locations, dates or measurements submit a new environmental question above.')
            with st.form('explanation_followup'):
                followup = st.text_input('Follow-up about these results', max_chars=500,
                    placeholder='Explain the rainfall summary / वर्षा का सारांश समझाएँ / वर्षाको सारांश बुझाउनुहोस्')
                ask_followup = st.form_submit_button('Explain stored results')
            if ask_followup:
                st.session_state.pop('followup_explanation', None)
                try:
                    with st.spinner('Validating an explanation against stored environmental context…'):
                        st.session_state.followup_explanation = client.explain(st.session_state.session_id,
                            result['context_id'], followup, language_code or analysis['language']['code'])
                except APIError as error:
                    st.info(str(error) + ' Environmental results above remain available.')
            if st.session_state.get('followup_explanation'):
                st.subheader('Contextual follow-up explanation')
                show_explanation(st.session_state.followup_explanation)
