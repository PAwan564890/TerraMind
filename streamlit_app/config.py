import os

API_URL = os.environ.get('TERRAMIND_API_URL', 'http://127.0.0.1:8000').rstrip('/')
EXAMPLES = [
    'Show temperature and rainfall in Gangtok from 2025-01-01 to 2025-01-07.',
    'गंगटोक में पिछले 7 दिनों का तापमान और बारिश दिखाओ।',
    'गान्तोकमा पछिल्ला 7 दिनको तापक्रम र वर्षा देखाउनुहोस्।',
    'Compare temperature and rainfall in Gangtok and Namchi from 2025-01-01 to 2025-01-07.',
    'What is the temperature in Mangan today?',
]
