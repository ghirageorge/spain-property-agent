# ============================================================
# CRITERII EVALUARE PROPRIETATI SPANIA
# Agent imobiliar AI personal — George Ghira
# ============================================================
# Acest fisier defineste toate regulile de evaluare.
# Modifica valorile dupa preferintele tale fara a atinge
# restul codului din agent.py
# ============================================================

# ------------------------------------------------------------
# 1. SCOP PRINCIPAL
# ------------------------------------------------------------
PURPOSE = """
Proprietatea este destinata:
- Baza europeana pentru vacante de familie (2 adulti + 2 copii)
- Posibila resedinta la pensionare
- Inchiriere turistica (Airbnb / Booking) in perioadele neutilizate
- Inchiriere pe termen lung ca alternativa

Prioritate: uzul personal si valoarea pe termen lung > randament imediat.
"""

# ------------------------------------------------------------
# 2. BUGET
# ------------------------------------------------------------
BUDGET = {
    "max_price_eur": 100_000,

    # Exceptie okupa: daca pretul e sub acest prag SI proprietatea
    # pare interesanta (langa mare, suprafata buna), evalueaz-o
    # oricum cu avertisment explicit
    "okupa_exception_threshold_eur": 15_000,
}

# ------------------------------------------------------------
# 3. TIP PROPRIETATE ACCEPTAT
# ------------------------------------------------------------
PROPERTY_TYPES = {
    "accepted": ["apartament", "casa", "vila", "bungalow", "duplex"],
    "rejected": ["teren", "comercial", "depozit", "garaj", "studio"],
    # Studio = 1 camera, sub minimul de dormitoare
}

# ------------------------------------------------------------
# 4. CERINTE SPATIU
# ------------------------------------------------------------
SPACE_REQUIREMENTS = {
    "min_bedrooms": 2,          # minim 2 dormitoare
    "min_bathrooms": 1,
    "living_room_required": True,
    "min_sqm": 50,              # suprafata minima utila (mp)

    # Elemente optionale dar pozitive (cresc scorul)
    "bonus_features": [
        "terasa",
        "balcon",
        "gradina",
        "parcare",
        "piscina",
        "vedere la mare",
        "aer conditionat",
        "lift",
    ],
}

# ------------------------------------------------------------
# 5. LOCATIE — ZONE ACCEPTATE
# ------------------------------------------------------------
LOCATION = {
    # Zone principale (Costa Blanca Nord→Sud + Costa del Sol)
    "preferred_areas": [
        "Alicante",
        "Torrevieja",
        "Santa Pola",
        "Guardamar del Segura",
        "Benidorm",
        "Altea",
        "Calpe",
        "Denia",
        "Javea",         # Xàbia
        "La Mata",
        "Los Montesinos",
        "Orihuela Costa",
        "Campoamor",
        "Punta Prima",
        # Costa del Sol
        "Malaga",
        "Marbella",
        "Fuengirola",
        "Torremolinos",
        "Nerja",
        "Estepona",
        "Benalmadena",
    ],

    # Distanta maxima fata de plaja (km)
    "max_distance_beach_km": 10,

    # Distanta ideala (sub aceasta = bonus la scor)
    "ideal_distance_beach_km": 2,

    # Distanta maxima fata de un oras / centru cu servicii
    "max_distance_town_center_km": 5,

    # Zone de evitat explicit
    "avoid_areas": [
        "Algorfa",          # zona rurala izolata, departe de mare
        "Crevillente",
        "Elche interior",
        "Murcia interior",
    ],
}

# ------------------------------------------------------------
# 6. ELEMENTE NATURALE DORITE (cresc scorul)
# ------------------------------------------------------------
NATURAL_ELEMENTS = {
    # Cel putin unul din acestea e de dorit
    "desired": [
        "plaja",
        "mare",
        "vedere la mare",
        "rasarit",
        "apus",
        "parc",
        "padure",
        "laguna",
        "delta",
        "parcul natural",
        "promenada",
        "pietonal",
        "malul marii",
        "paseo maritimo",
        "passeig maritim",
    ],

    # Cuvinte cheie in anunt care confirma prezenta elementului natural
    "keywords_es": [
        "vistas al mar", "primera linea", "frente al mar",
        "cerca del mar", "paseo maritimo", "parque natural",
        "laguna", "bosque", "amanecer", "atardecer",
        "orientacion este", "orientacion oeste",
    ],
}

# ------------------------------------------------------------
# 7. STARE CLADIRE / PROPRIETATE
# ------------------------------------------------------------
BUILDING_CONDITION = {
    # Anul minim de constructie acceptat (sau sa fie renovata)
    "min_build_year": 1990,

    # Daca nu se cunoaste anul, anuntul trebuie sa mentioneze renovare
    "renovation_keywords_es": [
        "reformado", "reformada", "renovado", "renovada",
        "nuevo", "nueva", "reciente", "moderno", "moderna",
        "rehabilitado", "rehabilitada",
    ],

    # Semnale negative pentru starea cladirii
    "bad_condition_keywords_es": [
        "para reformar", "a reformar", "necesita reforma",
        "reformar", "en mal estado", "deteriorado",
        "ruina", "ruinoso",
    ],
}

# ------------------------------------------------------------
# 8. RISCURI DE EVITAT (scad scorul sau resping automat)
# ------------------------------------------------------------
RISKS = {
    # --- Risc OKUPA ---
    "okupa_keywords_es": [
        "ocupado", "ocupada", "inquilino actual",
        "con inquilino", "ocupantes", "procedimiento judicial",
        "desahucio pendiente", "en proceso de desocupacion",
    ],

    # --- Risc inundatii ---
    "flood_risk_keywords_es": [
        "zona inundable", "riesgo de inundacion",
        "DANA", "rambla", "torrente",
    ],
    # Verifica si zona e in DANA flood map (Valencia 2024 a aratat riscul)
    "check_flood_zone": True,

    # --- Zona periculoasa / degradata ---
    "bad_neighborhood_keywords_es": [
        "zona conflictiva", "barrio degradado",
        "alta densidad", "problemas sociales",
    ],

    # --- Semne de risc general ---
    "general_risk_signals": [
        "fara fotografii interioare",       # lipsa poze = ascunde ceva
        "pret mult sub media zonei",        # >30% sub medie = suspicion
        "anunt vechi pe piata (>180 zile)", # nimeni nu vrea = ceva e gresit
        "suprafata nedeclarata",
    ],

    # --- Cutremure: zone cu risc seismic mai ridicat in Spania ---
    # Nota: Spania nu e zona seismica majora, dar exista zone
    "seismic_risk_areas": [
        "Granada", "Almeria", "Murcia", "Lorca",
    ],
}

# ------------------------------------------------------------
# 9. POTENTIAL INCHIRIERE
# ------------------------------------------------------------
RENTAL_POTENTIAL = {
    # Factori care cresc potentialul airbnb / inchiriere turistica
    "positive_factors": [
        "langa plaja",
        "in oras / centru",
        "piscina in comunitate",
        "parcare inclusa",
        "aer conditionat",
        "zona turistica cunoscuta",
        "licenta turistica existenta",
        "proximitate transport",
    ],

    # Factori care scad potentialul
    "negative_factors": [
        "zona rurala izolata",
        "fara transport public",
        "departe de plaja (>5km)",
        "comunitate numai rezidenti locali",
        "restrictii airbnb in comunitate",
    ],

    # Unele comunidades autonome au restrictii airbnb
    "airbnb_restricted_areas_note": (
        "Comunitat Valenciana si Andaluzia permit airbnb cu licenta turistica. "
        "Verifica daca proprietatea are sau poate obtine VFT (Vivienda de Uso Turistico)."
    ),
}

# ------------------------------------------------------------
# 10. SISTEM DE SCORARE
# ------------------------------------------------------------
SCORING = {
    # Scor maxim posibil: 10

    # Criterii OBLIGATORII — daca nu sunt indeplinite, scorul max e 4
    "mandatory_criteria": [
        "pret sub buget",
        "min 2 dormitoare",
        "tip proprietate acceptat",
        "distanta plaja sub 10km",
        "nu okupa (sau pret sub pragul exceptie)",
        "nu zona inundabila",
    ],

    # Greutati pentru scorul final (suma = 10 puncte)
    "weights": {
        "locatie_si_distanta_plaja":    2.5,   # cel mai important
        "stare_proprietate":            1.5,
        "raport_pret_mp_zona":          1.5,
        "elemente_naturale_vedere":     1.5,
        "potential_inchiriere":         1.0,
        "spatiu_si_dotari":             1.0,
        "risc_zero":                    1.0,   # 0 daca exista risc major
    },

    # Praguri interpretare scor
    "thresholds": {
        "top":    (8, 10),   # Merita atentie — vizita recomandata
        "medium": (5,  7),   # Cu rezerve — verifica inainte
        "low":    (0,  4),   # De evitat
    },
}

# ------------------------------------------------------------
# 11. PROMPT TEMPLATE PENTRU CLAUDE
# ------------------------------------------------------------
# Acesta e promptul injectat pentru fiecare anunt evaluat.
# {listing_text} va fi inlocuit cu textul anuntului extras.

EVALUATION_PROMPT_TEMPLATE = """
Esti un agent imobiliar AI care evalueaza anunturi imobiliare din Spania
pentru un cumparator roman cu urmatoarele criterii stricte.

=== SCOPUL CUMPARATORULUI ===
{purpose}

=== BUGET ===
Maximum: {max_price} EUR
Exceptie okupa: daca pretul e sub {okupa_exception} EUR si proprietatea
e interesanta (langa mare), evalueaz-o oricum cu AVERTISMENT EXPLICIT.

=== CRITERII OBLIGATORII ===
- Tip: apartament sau casa (nu studio, nu teren, nu comercial)
- Minim 2 dormitoare + living + baie
- Distanta maxima fata de plaja: {max_beach_km} km
- Cladire post-{min_build_year} sau renovata recent
- Proprietate LIBERA (nu ocupata / okupa)
- Nu zona inundabila (verifica DANA / rambla)
- Nu zona periculoasa / degradata

=== ZONE PREFERATE ===
Costa Blanca: Alicante, Torrevieja, Santa Pola, Guardamar,
Benidorm, Altea, Calpe, Denia, Orihuela Costa, La Mata
Costa del Sol: Malaga, Marbella, Fuengirola, Torremolinos, Nerja

=== ELEMENTE POZITIVE (cresc scorul) ===
- Langa plaja (sub 2 km = bonus mare)
- Vedere la mare, rasarit, sau apus
- Promenada pietonala in zona
- Element natural: laguna, parc, padure, parcul natural
- Terasa / balcon / gradina
- Potential airbnb (zona turistica, licenta VFT)

=== SEMNALE DE RISC (scad scorul sau resping) ===
- "ocupado", "inquilino actual", "con inquilino" → risc okupa
- "para reformar", "a reformar" → renovare costisitoare necesara
- Fara fotografii interioare → ascunde ceva
- Pret mult sub media zonei fara explicatie → investigheaza
- Zona rurala interioara, departe de mare → nu se potriveste

=== ANUNTUL DE EVALUAT ===
{listing_text}

=== FORMAT RASPUNS (JSON strict, fara text in afara JSON) ===
{{
  "score": <1-10>,
  "category": <"top" | "medium" | "low">,
  "title_ro": "<titlu scurt in romana, max 60 caractere>",
  "price_eur": <numar>,
  "location": "<oras / zona>",
  "distance_beach_km": <numar sau null>,
  "bedrooms": <numar sau null>,
  "build_year": <numar sau null>,
  "tags_positive": ["<tag1>", "<tag2>"],
  "tags_warning": ["<tag1>"],
  "tags_negative": ["<tag1>"],
  "criteria_met": {{
    "budget_ok": <true/false>,
    "bedrooms_ok": <true/false>,
    "beach_distance_ok": <true/false>,
    "building_age_ok": <true/false>,
    "no_okupa_risk": <true/false>,
    "no_flood_risk": <true/false>,
    "natural_element": <true/false>,
    "airbnb_potential": <true/false>
  }},
  "verdict_ro": "<2-3 propozitii in romana: ce e bun, ce e rau, recomandare>",
  "source_url": "<url anunt>"
}}
"""

def build_prompt(listing_text: str, source_url: str = "") -> str:
    """
    Construieste promptul final pentru Claude,
    injectand criteriile si textul anuntului.
    """
    listing_with_url = listing_text
    if source_url:
        listing_with_url += f"\n\nURL anunt: {source_url}"

    return EVALUATION_PROMPT_TEMPLATE.format(
        purpose=PURPOSE.strip(),
        max_price=BUDGET["max_price_eur"],
        okupa_exception=BUDGET["okupa_exception_threshold_eur"],
        max_beach_km=LOCATION["max_distance_beach_km"],
        min_build_year=BUILDING_CONDITION["min_build_year"],
        listing_text=listing_with_url,
    )


# ------------------------------------------------------------
# TEST RAPID — ruleaza direct: python criteria.py
# ------------------------------------------------------------
if __name__ == "__main__":
    sample_listing = """
    Apartamento 2 dormitorios en Torrevieja, zona La Mata.
    Precio: 87.500 EUR. Reformado en 2021. Libre. 
    A 300 metros de la playa. Orientacion este-oeste.
    Comunidad con piscina. Posibilidad licencia turistica VFT.
    Edificio de 2005. Teraza con vistas al mar.
    """
    prompt = build_prompt(sample_listing, "https://idealista.com/inmueble/12345678/")
    print("=== PROMPT GENERAT ===")
    print(prompt[:800], "...")
    print(f"\nLungime totala prompt: {len(prompt)} caractere")
    print("\ncriteria.py OK — gata de integrat in agent.py")
