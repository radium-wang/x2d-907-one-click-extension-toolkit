"""Desktop presentation only; camera protocol values and payloads stay unchanged."""
import json, os
from pathlib import Path
D=Path(__file__).resolve().parent
CATALOG=json.loads((D/'translations.json').read_text(encoding='utf-8'))
# Deterministic longest-first replacement of canonical diagnostic fragments.
FRAGMENTS=sorted(CATALOG,key=lambda key:(-len(key),key))

def translate(text, language='zh'):
    if language!='en' or not text: return text
    if text in CATALOG: return CATALOG[text]
    for key in FRAGMENTS:
        if key in text: text=text.replace(key,CATALOG[key])
    return text

class Localizer:
    def __init__(self, preferences):
        self.preferences=Path(preferences)
        try: language=json.loads(self.preferences.read_text(encoding='utf-8')).get('language')
        except (OSError,ValueError,AttributeError): language='zh'
        self.language=language if language in ('zh','en') else 'zh'
    def text(self, text): return translate(text,self.language)
    def select(self, language):
        if language not in ('zh','en'): raise ValueError('Unsupported language')
        self.language=language
        try:
            self.preferences.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.preferences.with_suffix('.tmp')
            temporary.write_text(json.dumps({'language':language})+'\n',encoding='utf-8')
            os.replace(temporary,self.preferences)
        except OSError:
            # Language can still change for this session if preferences cannot be saved.
            pass
