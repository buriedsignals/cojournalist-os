"""
Shared locale constants for language detection, query generation, and news search.

PURPOSE: Single source of truth for all locale-related data. Pure data module
with no business logic — only constants and mappings.

DEPENDS ON: (no imports — pure data)
USED BY: services/query_generator.py, services/news_utils.py,
    services/email_translations.py, services/atomic_unit_service.py

Contents:
- COUNTRY_PRIMARY_LANGUAGE: ISO 3166-1 -> ISO 639-1 (240+ countries)
- LANGUAGE_NAMES: ISO 639-1 -> English name (50+ languages)
- FALLBACK_NEWS_TERMS / FALLBACK_GOV_TERMS: per-language search terms
- LOCAL_DOMAIN_REGISTRY: country -> local TLDs (e.g., "CH" -> [".ch"])
"""

# Complete ISO 3166-1 -> ISO 639-1 country-to-language mapping
# Source: pycountry / ISO 3166-1 + ISO 639-1
# This is authoritative UN/ISO data - no maintenance needed
# Maps country code to primary/official language
COUNTRY_PRIMARY_LANGUAGE = {
    # A
    "AD": "ca",  # Andorra - Catalan
    "AE": "ar",  # UAE - Arabic
    "AF": "fa",  # Afghanistan - Dari/Persian
    "AG": "en",  # Antigua and Barbuda
    "AI": "en",  # Anguilla
    "AL": "sq",  # Albania - Albanian
    "AM": "hy",  # Armenia - Armenian
    "AO": "pt",  # Angola - Portuguese
    "AR": "es",  # Argentina - Spanish
    "AS": "en",  # American Samoa
    "AT": "de",  # Austria - German
    "AU": "en",  # Australia
    "AW": "nl",  # Aruba - Dutch
    "AX": "sv",  # Aland Islands - Swedish
    "AZ": "az",  # Azerbaijan - Azerbaijani
    # B
    "BA": "bs",  # Bosnia - Bosnian
    "BB": "en",  # Barbados
    "BD": "bn",  # Bangladesh - Bengali
    "BE": "nl",  # Belgium - Dutch (Flemish majority)
    "BF": "fr",  # Burkina Faso - French
    "BG": "bg",  # Bulgaria - Bulgarian
    "BH": "ar",  # Bahrain - Arabic
    "BI": "fr",  # Burundi - French
    "BJ": "fr",  # Benin - French
    "BL": "fr",  # Saint Barthelemy - French
    "BM": "en",  # Bermuda
    "BN": "ms",  # Brunei - Malay
    "BO": "es",  # Bolivia - Spanish
    "BQ": "nl",  # Caribbean Netherlands - Dutch
    "BR": "pt",  # Brazil - Portuguese
    "BS": "en",  # Bahamas
    "BT": "dz",  # Bhutan - Dzongkha
    "BW": "en",  # Botswana
    "BY": "be",  # Belarus - Belarusian
    "BZ": "en",  # Belize
    # C
    "CA": "en",  # Canada - English (French in Quebec detected by LLM)
    "CC": "en",  # Cocos Islands
    "CD": "fr",  # DR Congo - French
    "CF": "fr",  # Central African Republic - French
    "CG": "fr",  # Congo - French
    "CH": "de",  # Switzerland - German (largest)
    "CI": "fr",  # Cote d'Ivoire - French
    "CK": "en",  # Cook Islands
    "CL": "es",  # Chile - Spanish
    "CM": "fr",  # Cameroon - French
    "CN": "zh",  # China - Chinese
    "CO": "es",  # Colombia - Spanish
    "CR": "es",  # Costa Rica - Spanish
    "CU": "es",  # Cuba - Spanish
    "CV": "pt",  # Cape Verde - Portuguese
    "CW": "nl",  # Curacao - Dutch
    "CX": "en",  # Christmas Island
    "CY": "el",  # Cyprus - Greek
    "CZ": "cs",  # Czechia - Czech
    # D
    "DE": "de",  # Germany - German
    "DJ": "fr",  # Djibouti - French
    "DK": "da",  # Denmark - Danish
    "DM": "en",  # Dominica
    "DO": "es",  # Dominican Republic - Spanish
    "DZ": "ar",  # Algeria - Arabic
    # E
    "EC": "es",  # Ecuador - Spanish
    "EE": "et",  # Estonia - Estonian
    "EG": "ar",  # Egypt - Arabic
    "EH": "ar",  # Western Sahara - Arabic
    "ER": "ti",  # Eritrea - Tigrinya
    "ES": "es",  # Spain - Spanish
    "ET": "am",  # Ethiopia - Amharic
    # F
    "FI": "fi",  # Finland - Finnish
    "FJ": "en",  # Fiji
    "FK": "en",  # Falkland Islands
    "FM": "en",  # Micronesia
    "FO": "fo",  # Faroe Islands - Faroese
    "FR": "fr",  # France - French
    # G
    "GA": "fr",  # Gabon - French
    "GB": "en",  # United Kingdom
    "GD": "en",  # Grenada
    "GE": "ka",  # Georgia - Georgian
    "GF": "fr",  # French Guiana - French
    "GG": "en",  # Guernsey
    "GH": "en",  # Ghana
    "GI": "en",  # Gibraltar
    "GL": "kl",  # Greenland - Greenlandic
    "GM": "en",  # Gambia
    "GN": "fr",  # Guinea - French
    "GP": "fr",  # Guadeloupe - French
    "GQ": "es",  # Equatorial Guinea - Spanish
    "GR": "el",  # Greece - Greek
    "GT": "es",  # Guatemala - Spanish
    "GU": "en",  # Guam
    "GW": "pt",  # Guinea-Bissau - Portuguese
    "GY": "en",  # Guyana
    # H
    "HK": "zh",  # Hong Kong - Chinese
    "HN": "es",  # Honduras - Spanish
    "HR": "hr",  # Croatia - Croatian
    "HT": "fr",  # Haiti - French
    "HU": "hu",  # Hungary - Hungarian
    # I
    "ID": "id",  # Indonesia - Indonesian
    "IE": "en",  # Ireland
    "IL": "he",  # Israel - Hebrew
    "IM": "en",  # Isle of Man
    "IN": "hi",  # India - Hindi
    "IO": "en",  # British Indian Ocean Territory
    "IQ": "ar",  # Iraq - Arabic
    "IR": "fa",  # Iran - Persian
    "IS": "is",  # Iceland - Icelandic
    "IT": "it",  # Italy - Italian
    # J
    "JE": "en",  # Jersey
    "JM": "en",  # Jamaica
    "JO": "ar",  # Jordan - Arabic
    "JP": "ja",  # Japan - Japanese
    # K
    "KE": "sw",  # Kenya - Swahili
    "KG": "ky",  # Kyrgyzstan - Kyrgyz
    "KH": "km",  # Cambodia - Khmer
    "KI": "en",  # Kiribati
    "KM": "ar",  # Comoros - Arabic
    "KN": "en",  # Saint Kitts and Nevis
    "KP": "ko",  # North Korea - Korean
    "KR": "ko",  # South Korea - Korean
    "KW": "ar",  # Kuwait - Arabic
    "KY": "en",  # Cayman Islands
    "KZ": "kk",  # Kazakhstan - Kazakh
    # L
    "LA": "lo",  # Laos - Lao
    "LB": "ar",  # Lebanon - Arabic
    "LC": "en",  # Saint Lucia
    "LI": "de",  # Liechtenstein - German
    "LK": "si",  # Sri Lanka - Sinhala
    "LR": "en",  # Liberia
    "LS": "en",  # Lesotho
    "LT": "lt",  # Lithuania - Lithuanian
    "LU": "fr",  # Luxembourg - French (most used)
    "LV": "lv",  # Latvia - Latvian
    "LY": "ar",  # Libya - Arabic
    # M
    "MA": "ar",  # Morocco - Arabic
    "MC": "fr",  # Monaco - French
    "MD": "ro",  # Moldova - Romanian
    "ME": "sr",  # Montenegro - Serbian
    "MF": "fr",  # Saint Martin - French
    "MG": "fr",  # Madagascar - French
    "MH": "en",  # Marshall Islands
    "MK": "mk",  # North Macedonia - Macedonian
    "ML": "fr",  # Mali - French
    "MM": "my",  # Myanmar - Burmese
    "MN": "mn",  # Mongolia - Mongolian
    "MO": "zh",  # Macau - Chinese
    "MP": "en",  # Northern Mariana Islands
    "MQ": "fr",  # Martinique - French
    "MR": "ar",  # Mauritania - Arabic
    "MS": "en",  # Montserrat
    "MT": "mt",  # Malta - Maltese
    "MU": "en",  # Mauritius
    "MV": "dv",  # Maldives - Dhivehi
    "MW": "en",  # Malawi
    "MX": "es",  # Mexico - Spanish
    "MY": "ms",  # Malaysia - Malay
    "MZ": "pt",  # Mozambique - Portuguese
    # N
    "NA": "en",  # Namibia
    "NC": "fr",  # New Caledonia - French
    "NE": "fr",  # Niger - French
    "NF": "en",  # Norfolk Island
    "NG": "en",  # Nigeria
    "NI": "es",  # Nicaragua - Spanish
    "NL": "nl",  # Netherlands - Dutch
    "NO": "no",  # Norway - Norwegian
    "NP": "ne",  # Nepal - Nepali
    "NR": "en",  # Nauru
    "NU": "en",  # Niue
    "NZ": "en",  # New Zealand
    # O
    "OM": "ar",  # Oman - Arabic
    # P
    "PA": "es",  # Panama - Spanish
    "PE": "es",  # Peru - Spanish
    "PF": "fr",  # French Polynesia - French
    "PG": "en",  # Papua New Guinea
    "PH": "tl",  # Philippines - Filipino/Tagalog
    "PK": "ur",  # Pakistan - Urdu
    "PL": "pl",  # Poland - Polish
    "PM": "fr",  # Saint Pierre and Miquelon - French
    "PN": "en",  # Pitcairn
    "PR": "es",  # Puerto Rico - Spanish
    "PS": "ar",  # Palestine - Arabic
    "PT": "pt",  # Portugal - Portuguese
    "PW": "en",  # Palau
    "PY": "es",  # Paraguay - Spanish
    # Q
    "QA": "ar",  # Qatar - Arabic
    # R
    "RE": "fr",  # Reunion - French
    "RO": "ro",  # Romania - Romanian
    "RS": "sr",  # Serbia - Serbian
    "RU": "ru",  # Russia - Russian
    "RW": "rw",  # Rwanda - Kinyarwanda
    # S
    "SA": "ar",  # Saudi Arabia - Arabic
    "SB": "en",  # Solomon Islands
    "SC": "fr",  # Seychelles - French
    "SD": "ar",  # Sudan - Arabic
    "SE": "sv",  # Sweden - Swedish
    "SG": "en",  # Singapore
    "SH": "en",  # Saint Helena
    "SI": "sl",  # Slovenia - Slovenian
    "SJ": "no",  # Svalbard - Norwegian
    "SK": "sk",  # Slovakia - Slovak
    "SL": "en",  # Sierra Leone
    "SM": "it",  # San Marino - Italian
    "SN": "fr",  # Senegal - French
    "SO": "so",  # Somalia - Somali
    "SR": "nl",  # Suriname - Dutch
    "SS": "en",  # South Sudan
    "ST": "pt",  # Sao Tome - Portuguese
    "SV": "es",  # El Salvador - Spanish
    "SX": "nl",  # Sint Maarten - Dutch
    "SY": "ar",  # Syria - Arabic
    "SZ": "en",  # Eswatini
    # T
    "TC": "en",  # Turks and Caicos
    "TD": "fr",  # Chad - French
    "TF": "fr",  # French Southern Territories
    "TG": "fr",  # Togo - French
    "TH": "th",  # Thailand - Thai
    "TJ": "tg",  # Tajikistan - Tajik
    "TK": "en",  # Tokelau
    "TL": "pt",  # Timor-Leste - Portuguese
    "TM": "tk",  # Turkmenistan - Turkmen
    "TN": "ar",  # Tunisia - Arabic
    "TO": "en",  # Tonga
    "TR": "tr",  # Turkey - Turkish
    "TT": "en",  # Trinidad and Tobago
    "TV": "en",  # Tuvalu
    "TW": "zh",  # Taiwan - Chinese
    "TZ": "sw",  # Tanzania - Swahili
    # U
    "UA": "uk",  # Ukraine - Ukrainian
    "UG": "en",  # Uganda
    "US": "en",  # United States
    "UY": "es",  # Uruguay - Spanish
    "UZ": "uz",  # Uzbekistan - Uzbek
    # V
    "VA": "it",  # Vatican - Italian
    "VC": "en",  # Saint Vincent
    "VE": "es",  # Venezuela - Spanish
    "VG": "en",  # British Virgin Islands
    "VI": "en",  # US Virgin Islands
    "VN": "vi",  # Vietnam - Vietnamese
    "VU": "en",  # Vanuatu
    # W
    "WF": "fr",  # Wallis and Futuna - French
    "WS": "sm",  # Samoa - Samoan
    # X - (none)
    # Y
    "YE": "ar",  # Yemen - Arabic
    "YT": "fr",  # Mayotte - French
    # Z
    "ZA": "en",  # South Africa (English most used for news)
    "ZM": "en",  # Zambia
    "ZW": "en",  # Zimbabwe
}


# Language code to full name (for LLM prompts and fallbacks)
LANGUAGE_NAMES = {
    "am": "Amharic",
    "ar": "Arabic",
    "az": "Azerbaijani",
    "be": "Belarusian",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "bs": "Bosnian",
    "ca": "Catalan",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "dv": "Dhivehi",
    "dz": "Dzongkha",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fo": "Faroese",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "hy": "Armenian",
    "id": "Indonesian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "ka": "Georgian",
    "kk": "Kazakh",
    "kl": "Greenlandic",
    "km": "Khmer",
    "ko": "Korean",
    "ky": "Kyrgyz",
    "lo": "Lao",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mk": "Macedonian",
    "mn": "Mongolian",
    "ms": "Malay",
    "mt": "Maltese",
    "my": "Burmese",
    "nb": "Norwegian",
    "ne": "Nepali",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "rw": "Kinyarwanda",
    "si": "Sinhala",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sm": "Samoan",
    "so": "Somali",
    "sq": "Albanian",
    "sr": "Serbian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tg": "Tajik",
    "th": "Thai",
    "ti": "Tigrinya",
    "tk": "Turkmen",
    "tl": "Filipino",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "uz": "Uzbek",
    "vi": "Vietnamese",
    "zh": "Chinese",
}


# Fallback local news terms (used if LLM fails)
FALLBACK_NEWS_TERMS = {
    "en": ["news", "local news", "today", "community", "blog", "events"],
    "de": ["Nachrichten", "aktuell", "lokale Nachrichten", "Verein", "Blog", "Veranstaltungen"],
    "fr": ["actualités", "nouvelles locales", "infos", "association", "blog", "événements"],
    "es": ["noticias", "noticias locales", "actualidad", "asociación", "blog", "eventos"],
    "it": ["notizie", "notizie locali", "attualità", "associazione", "blog", "eventi"],
    "nl": ["nieuws", "lokaal nieuws", "actueel", "vereniging", "blog", "evenementen"],
    "pt": ["notícias", "notícias locais", "atualidades", "associação", "blog", "eventos"],
    "ja": ["ニュース", "地元ニュース", "最新", "コミュニティ", "ブログ"],
    "pl": ["wiadomości", "lokalne wiadomości", "aktualności", "stowarzyszenie", "blog"],
    "sv": ["nyheter", "lokala nyheter", "aktuellt", "förening", "blogg", "evenemang"],
    "no": ["nyheter", "lokale nyheter", "aktuelt", "forening", "blogg", "arrangementer"],
    "da": ["nyheder", "lokale nyheder", "aktuelt", "forening", "blog", "begivenheder"],
    "zh": ["新闻", "本地新闻", "最新", "社区", "博客"],
    "ko": ["뉴스", "지역 뉴스", "최신", "커뮤니티", "블로그"],
    "ar": ["أخبار", "أخبار محلية", "اليوم", "مجتمع", "مدونة"],
    "ru": ["новости", "местные новости", "сегодня", "сообщество", "блог"],
    "tr": ["haberler", "yerel haberler", "güncel", "dernek", "blog", "etkinlikler"],
}

# Fallback government/municipal terms (used if LLM fails)
FALLBACK_GOV_TERMS = {
    "en": ["city council", "city hall", "mayor", "municipal", "local government"],
    "de": ["Gemeinderat", "Stadtrat", "Stadtverwaltung", "Bürgermeister", "Stadtpolitik"],
    "fr": ["conseil municipal", "mairie", "maire", "séance du conseil", "politique locale"],
    "es": ["ayuntamiento", "consejo municipal", "alcalde", "política municipal"],
    "it": ["consiglio comunale", "comune", "sindaco", "giunta comunale"],
    "nl": ["gemeenteraad", "gemeente", "burgemeester", "gemeentepolitiek"],
    "pt": ["câmara municipal", "prefeitura", "prefeito", "vereadores"],
    "ja": ["市議会", "市役所", "市長", "市政"],
    "pl": ["rada miejska", "urząd miasta", "burmistrz", "polityka lokalna"],
    "sv": ["kommunfullmäktige", "kommun", "kommunpolitik"],
    "no": ["kommunestyret", "kommune", "ordfører", "lokalpolitikk"],
    "da": ["kommunalbestyrelse", "kommune", "borgmester", "lokalpolitik"],
    "zh": ["市政府", "市议会", "市长", "地方政策"],
    "ko": ["시의회", "시청", "시장", "지방정치"],
    "ar": ["مجلس المدينة", "البلدية", "رئيس البلدية"],
    "ru": ["городской совет", "мэрия", "мэр", "местная политика"],
    "tr": ["belediye meclisi", "belediye", "belediye başkanı"],
}

# Fallback local domains by country (TLD + major news sites)
LOCAL_DOMAIN_REGISTRY = {
    "CH": [".ch", "20min.ch", "blick.ch", "srf.ch", "nzz.ch", "tagesanzeiger.ch"],
    "DE": [".de", "bild.de", "spiegel.de", "zeit.de", "tagesschau.de", "faz.net"],
    "AT": [".at", "orf.at", "krone.at", "kurier.at", "derstandard.at"],
    "FR": [".fr", "lemonde.fr", "lefigaro.fr", "franceinfo.fr", "liberation.fr"],
    "IT": [".it", "corriere.it", "repubblica.it", "ansa.it", "lastampa.it"],
    "ES": [".es", "elpais.com", "elmundo.es", "abc.es", "lavanguardia.com"],
    "NL": [".nl", "nos.nl", "nu.nl", "rtv.nl", "telegraaf.nl"],
    "BE": [".be", "rtbf.be", "lesoir.be", "standaard.be", "hln.be"],
    "PT": [".pt", "publico.pt", "jn.pt", "tsf.pt", "rtp.pt"],
    "PL": [".pl", "tvn24.pl", "onet.pl", "wp.pl", "gazeta.pl"],
    "SE": [".se", "svt.se", "aftonbladet.se", "dn.se", "expressen.se"],
    "NO": [".no", "nrk.no", "vg.no", "dagbladet.no", "aftenposten.no"],
    "DK": [".dk", "dr.dk", "politiken.dk", "bt.dk", "ekstrabladet.dk"],
    "BR": [".br", "globo.com", "uol.com.br", "folha.uol.com.br"],
    "MX": [".mx", "milenio.com", "eluniversal.com.mx", "excelsior.com.mx"],
    "AR": [".ar", "clarin.com", "lanacion.com.ar", "infobae.com"],
    "JP": [".jp", "nhk.or.jp", "asahi.com", "mainichi.jp"],
    "CA": [".ca", "cbc.ca", "globalnews.ca", "thestar.com", "nationalpost.com",
           "lapresse.ca", "ledevoir.com", "journaldemontreal.com",
           "ici.radio-canada.ca", "tvanouvelles.ca"],  # Includes French-Canadian sources
    "US": [".com", "nytimes.com", "washingtonpost.com", "cnn.com", "npr.org"],
    "GB": [".co.uk", "bbc.co.uk", "theguardian.com", "telegraph.co.uk"],
    "AU": [".au", "abc.net.au", "smh.com.au", "theaustralian.com.au"],
    "CN": [".cn", "xinhuanet.com", "people.com.cn", "chinadaily.com.cn"],
    "RU": [".ru", "ria.ru", "tass.com", "rbc.ru"],
    "TR": [".tr", "hurriyet.com.tr", "milliyet.com.tr", "ntv.com.tr"],
    "KR": [".kr", "chosun.com", "donga.com", "joins.com"],
}
