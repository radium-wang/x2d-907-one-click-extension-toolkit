"""Desktop presentation only; camera protocol values and payloads stay unchanged."""
import json, os
from pathlib import Path
D=Path(__file__).resolve().parent
CATALOG=json.loads((D/'translations.json').read_text(encoding='utf-8'))
TRADITIONAL=json.loads((D/'translations_zh_hant.json').read_text(encoding='utf-8'))
CATALOGS={'en':CATALOG,'zh-Hant':TRADITIONAL}
# Deterministic longest-first replacement of canonical diagnostic fragments.
FRAGMENTS={language:sorted(catalog,key=lambda key:(-len(key),key)) for language,catalog in CATALOGS.items()}

def translate(text, language='zh'):
    if language not in CATALOGS or not text: return text
    catalog=CATALOGS[language]
    if text in catalog: return catalog[text]
    for key in FRAGMENTS[language]:
        if key in text: text=text.replace(key,catalog[key])
    return text

class Localizer:
    def __init__(self, preferences):
        self.preferences=Path(preferences)
        try: language=json.loads(self.preferences.read_text(encoding='utf-8')).get('language')
        except (OSError,ValueError,AttributeError): language='zh'
        self.language=language if language in ('zh','zh-Hant','en') else 'zh'
    def text(self, text): return translate(text,self.language)
    def select(self, language):
        if language not in ('zh','zh-Hant','en'): raise ValueError('Unsupported language')
        self.language=language
        try:
            self.preferences.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.preferences.with_suffix('.tmp')
            temporary.write_text(json.dumps({'language':language})+'\n',encoding='utf-8')
            os.replace(temporary,self.preferences)
        except OSError:
            # Language can still change for this session if preferences cannot be saved.
            pass
