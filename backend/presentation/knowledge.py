"""Small reviewed reference catalogue, not generated prose or measured results.

No network/LLM calls at answer time. Whole-question matching never turns a
location-specific measurement request into a general knowledge answer.
"""
import re
import unicodedata
from pydantic import BaseModel
from backend.genai.schema import Language


class Reference(BaseModel):
    name: str
    url: str


class Knowledge(BaseModel):
    topic: str
    title: str
    text: str
    language: Language
    label: str = 'General environmental knowledge · curated reference summary · not measured data or trained NLP inference'
    sources: list[Reference]


OPEN_METEO = Reference(name='Open-Meteo historical weather documentation', url='https://open-meteo.com/en/docs/historical-weather-api')
NASA = Reference(name='NASA: What is climate change?', url='https://science.nasa.gov/climate-change/what-is-climate-change/')
GREENHOUSE = Reference(name='NASA: What is the greenhouse effect?', url='https://science.nasa.gov/climate-change/faq/what-is-the-greenhouse-effect/')
WMO = Reference(name='World Meteorological Organization: Climate', url='https://wmo.int/themes/climate')
# Language variants are reviewed summaries, not dynamically generated translations.
CATALOGUE = {
 'era5': ('ERA5 reanalysis',OPEN_METEO,[
  'ERA5 is a historical reanalysis from ECMWF/Copernicus. It combines observations with a physical weather model to estimate past atmospheric conditions on a grid. A grid estimate is not a local weather-station measurement; terrain and grid resolution affect interpretation.',
  'ERA5, ECMWF/Copernicus का ऐतिहासिक पुनर्विश्लेषण है। यह प्रेक्षणों और भौतिक मौसम मॉडल को मिलाकर ग्रिड पर पिछले वायुमंडलीय हालात का अनुमान बनाता है। ग्रिड का अनुमान स्थानीय मौसम स्टेशन का मापन नहीं है; भूभाग और ग्रिड का आकार महत्वपूर्ण हैं।',
  'ERA5, ECMWF/Copernicus को ऐतिहासिक पुनर्विश्लेषण हो। यसले अवलोकन र भौतिक मौसम मोडेल मिलाएर ग्रिडमा विगतको वायुमण्डलीय अवस्थाको अनुमान गर्छ। ग्रिडको अनुमान स्थानीय मौसम स्टेशनको मापन होइन; भूभाग र ग्रिडको आकारले व्याख्यामा प्रभाव पार्छन्।']),
 'rainfall_precipitation': ('Rainfall and precipitation',OPEN_METEO,[
  'Rainfall refers to liquid rain. Total precipitation includes rain and other forms such as snow, expressed as water equivalent. They are different quantities and must not be substituted. TerraMind uses historical rain_sum for rainfall and precipitation_sum for total precipitation; weather-model rainfall includes rain plus showers.',
  'बारिश तरल वर्षा है। कुल वर्षण में बारिश और बर्फ जैसे अन्य रूप भी जल-समतुल्य मात्रा में शामिल हैं। ये अलग राशियाँ हैं। TerraMind में ऐतिहासिक बारिश rain_sum और कुल वर्षण precipitation_sum हैं; मौसम मॉडल की बारिश में rain और showers शामिल हैं।',
  'वर्षा तरल पानीको रूपमा पर्ने झरी हो। कुल वर्षणमा वर्षा र हिउँजस्ता अन्य रूपको पानी बराबरको मात्रा समावेश हुन्छ। यी फरक परिमाण हुन्। TerraMind मा ऐतिहासिक वर्षा rain_sum र कुल वर्षण precipitation_sum हुन्; मौसम मोडेलको वर्षामा rain र showers जोडिन्छन्।']),
 'precipitation': ('Precipitation',OPEN_METEO,[
  'Precipitation is water falling from the atmosphere, including rain and snow. A precipitation total describes an accumulation over a stated period, in millimetres of water equivalent. It is not interchangeable with a rainfall-only total.',
  'वर्षण वायुमंडल से गिरने वाला पानी है, जिसमें बारिश और बर्फ शामिल हैं। कुल वर्षण किसी स्पष्ट अवधि की जल-समतुल्य मात्रा मिलीमीटर में बताता है। यह केवल बारिश के योग के समान नहीं है।',
  'वर्षण वायुमण्डलबाट पर्ने पानी हो, जसमा वर्षा र हिउँ पर्छन्। कुल वर्षणले तोकिएको अवधिको पानी बराबरको मात्रा मिलिमिटरमा जनाउँछ। यो वर्षाको मात्र योगसँग समान हुँदैन।']),
 'weather_climate': ('Weather and climate',WMO,[
  'Weather describes atmospheric conditions over short periods. Climate describes their long-term patterns and variability, commonly using multi-decade records. A retrieved week can describe weather variation; it cannot establish a climate-change trend.',
  'मौसम कम समय की वायुमंडलीय स्थिति है। जलवायु लंबे समय के पैटर्न और परिवर्तनशीलता का वर्णन करती है, आम तौर पर कई दशकों के रिकॉर्ड से। एक सप्ताह का डेटा जलवायु परिवर्तन का रुझान साबित नहीं करता।',
  'मौसम छोटो अवधिको वायुमण्डलीय अवस्था हो। जलवायुले लामो समयका ढाँचा र परिवर्तनशीलता जनाउँछ, प्रायः धेरै दशकको अभिलेखबाट। एक हप्ताको तथ्याङ्कले जलवायु परिवर्तनको प्रवृत्ति प्रमाणित गर्दैन।']),
 'climate_change': ('Climate change',NASA,[
  'Climate change is a long-term change in average conditions and their variability. Current global warming is primarily driven by human greenhouse-gas emissions. A single town-point week does not establish a local long-term trend or attribute a particular event to climate change.',
  'जलवायु परिवर्तन औसत स्थितियों और उनकी परिवर्तनशीलता में दीर्घकालीन बदलाव है। वर्तमान वैश्विक तापवृद्धि का प्रमुख कारण मानवजनित ग्रीनहाउस गैस उत्सर्जन है। किसी शहर के एक सप्ताह के डेटा से दीर्घकालीन स्थानीय रुझान या किसी घटना का कारण साबित नहीं होता।',
  'जलवायु परिवर्तन औसत अवस्था र त्यसको परिवर्तनशीलतामा दीर्घकालीन बदलाव हो। हालको विश्वव्यापी तापवृद्धिको मुख्य कारण मानवजनित हरितगृह ग्यास उत्सर्जन हो। एउटा नगरको एक हप्ताको तथ्याङ्कले स्थानीय दीर्घकालीन प्रवृत्ति वा कुनै घटनाको कारण प्रमाणित गर्दैन।']),
 'greenhouse': ('Greenhouse effect',GREENHOUSE,[
  'Greenhouse gases absorb and re-emit infrared radiation, reducing heat loss to space and warming the surface and lower atmosphere. This natural effect makes Earth warmer; increased greenhouse-gas concentrations strengthen it. This is general science, not a causal diagnosis of the retrieved town data.',
  'ग्रीनहाउस गैसें अवरक्त विकिरण को अवशोषित और पुनः उत्सर्जित करती हैं, जिससे अंतरिक्ष में ऊष्मा का निकलना कम होता है। यह प्राकृतिक प्रभाव पृथ्वी को गर्म रखता है; गैसों की बढ़ती सांद्रता इसे मजबूत करती है। यह सामान्य विज्ञान है, किसी शहर के डेटा की कारणात्मक व्याख्या नहीं।',
  'हरितगृह ग्यासले अवरक्त विकिरण अवशोषण र पुनः उत्सर्जन गरेर अन्तरिक्षमा ताप बाहिरिने दर घटाउँछन्। यस प्राकृतिक प्रभावले पृथ्वीलाई न्यानो राख्छ; ग्यासको बढ्दो सान्द्रताले यसलाई बलियो बनाउँछ। यो सामान्य विज्ञान हो, नगरको तथ्याङ्कको कारणात्मक विश्लेषण होइन।']),
 'temperature_height': ('Air temperature at 2 metres',OPEN_METEO,[
  'The Open-Meteo temperature_2m field represents air temperature at 2 metres above ground. A specified height makes the variable interpretable and comparable; it differs from land-surface temperature and from temperatures at other heights. TerraMind uses model/reanalysis estimates, not a sensor installed at the requested point.',
  'Open-Meteo का temperature_2m जमीन से 2 मीटर ऊपर हवा का तापमान है। स्पष्ट ऊँचाई से राशियों की तुलना संभव होती है; यह जमीन की सतह या दूसरी ऊँचाई के तापमान से अलग है। TerraMind मॉडल या पुनर्विश्लेषण के अनुमान दिखाता है, स्थानीय सेंसर का मापन नहीं।',
  'Open-Meteo को temperature_2m जमिनबाट 2 मिटर माथिको हावाको तापक्रम हो। तोकिएको उचाइले परिमाण बुझ्न र तुलना गर्न मद्दत गर्छ; यो भू-सतह वा अन्य उचाइको तापक्रमभन्दा फरक हुन्छ। TerraMind ले मोडेल वा पुनर्विश्लेषणको अनुमान देखाउँछ, स्थानीय सेन्सरको मापन होइन।']),
}
TOPICS = {
 'era5': r'era5(?: reanalysis)?',
 'rainfall_precipitation': r'(?:the )?difference between (?:rainfall|rain) and precipitation',
 'precipitation': r'precipitation', 'weather_climate':r'(?:the )?difference between weather and climate',
 'climate_change':r'climate change','greenhouse':r'(?:the )?greenhouse effect',
 'temperature_height':r'(?:why (?:is )?(?:air )?temperature (?:is )?measured at (?:2|two) (?:metres|meters)|temperature at (?:2|two) (?:metres|meters))',
}
NATIVE = {
 'era5 पुनर्विश्लेषण क्या है':('era5','hi'), 'era5 पुनर्विश्लेषण भनेको के हो':('era5','ne'),
 'बारिश और वर्षण में क्या अंतर है':('rainfall_precipitation','hi'), 'वर्षा र वर्षणमा के फरक छ':('rainfall_precipitation','ne'),
 'जलवायु परिवर्तन क्या है':('climate_change','hi'), 'जलवायु परिवर्तन भनेको के हो':('climate_change','ne'),
 'ग्रीनहाउस प्रभाव क्या है':('greenhouse','hi'),'हरितगृह प्रभाव भनेको के हो':('greenhouse','ne'),
 'मौसम और जलवायु में क्या अंतर है':('weather_climate','hi'),'मौसम र जलवायुमा के फरक छ':('weather_climate','ne'),
 'वर्षण क्या है':('precipitation','hi'),'वर्षण भनेको के हो':('precipitation','ne'),
 'तापमान 2 मीटर पर क्यों मापा जाता है':('temperature_height','hi'),
 'तापक्रम 2 मिटरमा किन मापन गरिन्छ':('temperature_height','ne'),
}


def key_of(question):
    return ' '.join(unicodedata.normalize('NFC',question).casefold().split()).rstrip(' .?!।')


def knowledge_answer(question, language='en'):
    key = key_of(question)
    native = NATIVE.get(key)
    topic = native[0] if native else None
    if native and language == 'auto':
        language = native[1]
    if not topic:
        for candidate, pattern in TOPICS.items():
            if re.fullmatch(rf'(?:please )?(?:(?:what is|what does|explain|describe|tell me about) )?{pattern}(?: mean)?',key):
                topic = candidate
                break
    if topic is None:
        return None
    language = 'en' if language == 'auto' else language
    title,source,text = CATALOGUE[topic]
    return Knowledge(topic=topic,title=title,text=text[['en','hi','ne'].index(language)],language=language,sources=[source])
