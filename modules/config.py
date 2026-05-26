APP_TITLE = "Ultimate Research AI Assistant"
APP_ICON = "🌐"
DEFAULT_TIMEOUT = 10
MAX_WEB_RESULTS = 12
MAX_PDF_RESULTS = 8
MAX_IMAGE_RESULTS = 12
MAX_SOURCE_CHARS = 18000
MAX_TOTAL_CONTEXT_CHARS = 80000
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

STOPWORDS = set('''
a an and are as at be by for from has have he in is it its of on or that the to was were will with you your i we they them this those these can could should would about into over under than then there their if but not no yes do does did done using use used more most many much such also other some any all each when where what why how who whom whose which write give explain define equation equations motion law formula formulas method methods available calculate calculation based best detailed everything all applicable expression expressions figure figures image images report pdf online google internet source sources
'''.split())

GEOTECH_TERMS = set('''
geotechnical soil soils earth pressure retaining wall lateral active passive rest at-rest rankine coulomb mononobe okabe surcharge backfill cohesion friction angle phi ka kp ko wall drainage excavation foundation shoring sheet pile basement bearing settlement slope stability
'''.split())

ACADEMIC_DOMAINS = [
    ".edu", ".gov", "usace", "fhwa", "dot", "geotech", "geoengineer", "researchgate", "sciencedirect", "springer", "asce", "mdpi", "nptel", "mit", "stanford", "berkeley"
]
