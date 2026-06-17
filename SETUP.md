# ============================================================
# GHID SETUP — Agent Imobiliar AI Spania
# ============================================================

## STRUCTURA PROIECT

```
spain_property_agent/
├── agent.py          ← scriptul principal
├── criteria.py       ← criteriile tale de evaluare
├── seen_urls.json    ← generat automat (evita duplicate)
├── requirements.txt
└── .github/
    └── workflows/
        └── daily.yml ← rulare automata GitHub Actions
```

---

## PAS 1 — Credentiale Gmail (OAuth2)

Agentul citeste emailurile tale si trimite digestul prin Gmail API.

### 1.1 Creeaza un proiect Google Cloud
1. Du-te la https://console.cloud.google.com
2. Creeaza un proiect nou: "Agent Imobiliar"
3. Activeaza **Gmail API**: APIs & Services → Enable APIs → cauta "Gmail API"

### 1.2 Creeaza credentiale OAuth2
1. APIs & Services → Credentials → Create Credentials → OAuth Client ID
2. Application type: **Desktop App**
3. Descarca fisierul JSON cu credentialele

### 1.3 Obtine Refresh Token (o singura data)
Ruleaza local:

```python
# get_token.py — ruleaza o singura data pe calculatorul tau
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

print("CLIENT_ID:",     creds.client_id)
print("CLIENT_SECRET:", creds.client_secret)
print("REFRESH_TOKEN:", creds.refresh_token)
```

Instalare: `pip install google-auth-oauthlib`

### 1.4 Salveaza valorile obtinute
Le vei folosi in Pasul 3 ca GitHub Secrets.

---

## PAS 2 — Cheie API Anthropic

1. Du-te la https://console.anthropic.com
2. API Keys → Create Key
3. Copiaza cheia (incepe cu `sk-ant-...`)

---

## PAS 3 — GitHub Repository + Secrets

### 3.1 Creeaza repository
```bash
git init spain_property_agent
cd spain_property_agent
git add .
git commit -m "initial commit"
git remote add origin https://github.com/TU/spain-property-agent.git
git push -u origin main
```

### 3.2 Adauga Secrets in GitHub
GitHub → repository → Settings → Secrets and variables → Actions → New secret

| Nume secret          | Valoare                        |
|----------------------|-------------------------------|
| `ANTHROPIC_API_KEY`  | sk-ant-...                    |
| `GMAIL_CLIENT_ID`    | ...apps.googleusercontent.com |
| `GMAIL_CLIENT_SECRET`| GOCSPX-...                   |
| `GMAIL_REFRESH_TOKEN`| 1//...                        |
| `MY_EMAIL`           | george.ghira@bertelsmann.de   |

---

## PAS 4 — Test local (optional)

```bash
# Seteaza variabilele de environment local
export ANTHROPIC_API_KEY="sk-ant-..."
export GMAIL_CLIENT_ID="..."
export GMAIL_CLIENT_SECRET="..."
export GMAIL_REFRESH_TOKEN="..."
export MY_EMAIL="george.ghira@bertelsmann.de"

# Ruleaza
pip install requests beautifulsoup4
python agent.py
```

---

## PAS 5 — Activare rulare automata

Dupa ce ai facut push pe GitHub, workflow-ul ruleaza automat:
- **Zilnic la 08:00** ora Romaniei
- **Manual** oricand: GitHub → Actions → "Agent Imobiliar Zilnic" → Run workflow

---

## MODIFICARI ULTERIOARE

Toate criteriile se modifica **doar in `criteria.py`**:
- Schimba bugetul: `BUDGET["max_price_eur"]`
- Adauga zone noi: `LOCATION["preferred_areas"]`
- Modifica scorul minim: `SCORING["thresholds"]`

`agent.py` nu trebuie modificat niciodata.

---

## COST ESTIMAT

| Componenta        | Cost                        |
|-------------------|-----------------------------|
| Claude API        | ~0.002 € / anunt evaluat    |
| 10 anunturi/zi    | ~0.02 € / zi = ~0.60 € / luna |
| Gmail API         | Gratuit                     |
| GitHub Actions    | Gratuit (2000 min/luna)     |
| **TOTAL**         | **< 1 € / luna**            |
