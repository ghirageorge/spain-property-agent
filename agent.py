# ============================================================
# AGENT IMOBILIAR AI — SPANIA
# agent.py — script principal
#
# Flux:
#   1. Citeste emailurile noi de la Idealista / Habitaclia (Gmail)
#   2. Extrage link-urile de anunturi
#   3. Descarca textul fiecarui anunt
#   4. Evalueaza cu Claude API folosind criteria.py
#   5. Trimite email digest sortat catre tine
#
# Rulare manuala:  python agent.py
# Rulare automata: GitHub Actions (vezi .github/workflows/daily.yml)
# ============================================================

import os
import re
import json
import time
import base64
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

from criteria import build_prompt, BUDGET, SCORING

# ============================================================
# CONFIGURARE
# ============================================================

# Adrese de email care primesc digestul zilnic.
# Seteaza MY_EMAILS in GitHub Secrets cu adresele separate prin virgula:
# ex: "george.ghira@bertelsmann.de,altaadresa@gmail.com"
MY_EMAILS = os.environ.get("MY_EMAILS", "george.ghira@bertelsmann.de")
RECIPIENT_LIST = [e.strip() for e in MY_EMAILS.split(",") if e.strip()]

# Expeditorii de alerte imobiliare — filtram emailurile de la acestia
ALERT_SENDERS = [
    "noresponder@idealista.com",
    "alertas@idealista.com",
    "noreply@habitaclia.com",
    "alertas@email.habitaclia.com",
    "novedades.fotocasa@novedades.fotocasa.es",
    "enviosfotocasa@fotocasa.es",
]

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

# Gmail OAuth credentials (din environment variables / GitHub Secrets)
GMAIL_CLIENT_ID     = os.environ.get("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN = os.environ.get("GMAIL_REFRESH_TOKEN", "")

# Fisier local pentru a evita evaluarea acelorasi anunturi de doua ori
SEEN_URLS_FILE = "seen_urls.json"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ============================================================
# GMAIL — TOKEN SI ACCES
# ============================================================

def get_gmail_access_token() -> str:
    """Obtine un access token Gmail folosind refresh token OAuth2."""
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id":     GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "refresh_token": GMAIL_REFRESH_TOKEN,
            "grant_type":    "refresh_token",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def gmail_search(access_token: str, query: str, max_results: int = 20) -> list:
    """Cauta emailuri in Gmail si returneaza lista de message IDs."""
    resp = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"q": query, "maxResults": max_results},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("messages", [])


def gmail_get_message(access_token: str, msg_id: str) -> dict:
    """Descarca un email complet dupa ID."""
    resp = requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"format": "full"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def decode_email_body(message: dict) -> str:
    """Extrage textul / HTML din corpul emailului Gmail."""
    parts = message.get("payload", {}).get("parts", [])

    # Email simplu fara parts
    if not parts:
        body_data = message.get("payload", {}).get("body", {}).get("data", "")
        if body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
        return ""

    # Email multipart — cautam HTML > plain text
    for part in parts:
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return ""


def gmail_mark_as_read(access_token: str, msg_id: str):
    """Marcheaza emailul ca citit dupa procesare."""
    requests.post(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}/modify",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"removeLabelIds": ["UNREAD"]},
        timeout=10,
    )


def gmail_send(access_token: str, to: str, subject: str, html_body: str):
    """Trimite un email HTML prin Gmail API."""
    msg = MIMEMultipart("alternative")
    msg["To"]      = to
    msg["From"]    = RECIPIENT_LIST[0]
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    resp = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"raw": raw},
        timeout=15,
    )
    resp.raise_for_status()
    log.info("Email digest trimis catre %s", to)


# ============================================================
# EXTRAGERE LINK-URI DIN EMAILURI ALERTA
# ============================================================

# Patternuri URL pentru fiecare portal
URL_PATTERNS = [
    r"https?://www\.idealista\.com/inmueble/\d+/?",
    r"https?://www\.habitaclia\.com/[^\"'\s>]+(?:inmueble|habitatge|piso|casa)[^\"'\s>]*",
    r"https?://[^\"'\s>]*habitaclia\.com[^\"'\s>]*\d{6,}[^\"'\s>]*",
]

def extract_listing_urls(html_body: str) -> list[str]:
    """Extrage URL-urile de anunturi dintr-un email de alerta."""
    urls = set()
    for pattern in URL_PATTERNS:
        found = re.findall(pattern, html_body, re.IGNORECASE)
        urls.update(found)

    # Curata URL-urile de parametri de tracking
    clean = []
    for url in urls:
        base = url.split("?")[0].rstrip("/")
        clean.append(base)

    return list(set(clean))


# ============================================================
# SCRAPING ANUNT
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

def scrape_listing(url: str) -> str:
    """
    Descarca pagina anuntului si extrage textul relevant.
    Returneaza un string curat cu informatiile anuntului.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Nu am putut descarca %s: %s", url, e)
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Eliminam elementele inutile
    for tag in soup(["script", "style", "nav", "footer", "header", "iframe"]):
        tag.decompose()

    # Idealista: sectiunile relevante
    relevant_sections = []

    # Titlu
    for sel in ["h1", ".main-info__title", ".listing-title"]:
        el = soup.select_one(sel)
        if el:
            relevant_sections.append("TITLU: " + el.get_text(strip=True))
            break

    # Pret
    for sel in [".info-data-price", ".price", "[class*='price']"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if any(c.isdigit() for c in text):
                relevant_sections.append("PRET: " + text)
                break

    # Caracteristici principale (dormitoare, mp, etaj)
    for sel in [".info-features", ".details-property", ".listing-features"]:
        el = soup.select_one(sel)
        if el:
            relevant_sections.append("CARACTERISTICI: " + el.get_text(" | ", strip=True))
            break

    # Descriere
    for sel in [".comment", ".adCommentsLanguage", ".description", "[class*='description']"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)[:1500]  # max 1500 caractere
            relevant_sections.append("DESCRIERE: " + text)
            break

    # Locatie
    for sel in [".main-info__address", ".address", "[class*='location']", "[class*='address']"]:
        el = soup.select_one(sel)
        if el:
            relevant_sections.append("LOCATIE: " + el.get_text(strip=True))
            break

    # Daca nu am gasit nimic structurat, luam tot textul paginii (primele 2000 caractere)
    if len(relevant_sections) < 2:
        full_text = soup.get_text(" ", strip=True)
        relevant_sections = [full_text[:2000]]

    result = "\n".join(relevant_sections)
    result += f"\n\nURL: {url}"
    return result


# ============================================================
# EVALUARE CU CLAUDE
# ============================================================

def evaluate_listing(listing_text: str, source_url: str) -> dict | None:
    """
    Trimite anuntul la Claude pentru evaluare.
    Returneaza un dict cu scorul si toate detaliile.
    """
    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY lipseste din environment variables!")
        return None

    prompt = build_prompt(listing_text, source_url)

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      CLAUDE_MODEL,
                "max_tokens": 1000,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Eroare Claude API pentru %s: %s", source_url, e)
        return None

    raw_text = resp.json()["content"][0]["text"]

    # Curata JSON (uneori Claude adauga backticks)
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)

    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        log.error("JSON invalid de la Claude pentru %s: %s", source_url, e)
        log.debug("Raw response: %s", raw_text[:300])
        return None


# ============================================================
# GESTIUNE URL-URI VAZUTE (evita duplicate)
# ============================================================

def load_seen_urls() -> set:
    if os.path.exists(SEEN_URLS_FILE):
        with open(SEEN_URLS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_urls(urls: set):
    with open(SEEN_URLS_FILE, "w") as f:
        json.dump(list(urls), f, indent=2)


# ============================================================
# GENERARE EMAIL HTML DIGEST
# ============================================================

def score_color(score: int) -> tuple[str, str]:
    """Returneaza (culoare_border, culoare_badge) in functie de scor."""
    if score >= 8:
        return "#1D9E75", "#E1F5EE", "#0F6E56"
    elif score >= 5:
        return "#BA7517", "#FAEEDA", "#854F0B"
    else:
        return "#A32D2D", "#FCEBEB", "#A32D2D"


def category_label(category: str) -> str:
    return {
        "top":    "Merita atentie",
        "medium": "Cu rezerve",
        "low":    "De evitat",
    }.get(category, "Necunoscut")


def render_tag(text: str, kind: str) -> str:
    colors = {
        "ok":   ("background:#E1F5EE", "color:#0F6E56"),
        "warn": ("background:#FAEEDA", "color:#854F0B"),
        "bad":  ("background:#FCEBEB", "color:#A32D2D"),
        "info": ("background:#E6F1FB", "color:#185FA5"),
    }
    bg, fg = colors.get(kind, colors["info"])
    return (
        f'<span style="font-size:11px;padding:3px 8px;border-radius:4px;'
        f'font-weight:500;{bg};{fg};margin-right:4px;margin-bottom:4px;'
        f'display:inline-block">{text}</span>'
    )


def render_criteria_check(label: str, ok: bool) -> str:
    icon  = "✓" if ok else "✗"
    color = "#1D9E75" if ok else "#A32D2D"
    return (
        f'<span style="font-size:12px;color:{color};margin-right:12px">'
        f'{icon} {label}</span>'
    )


def render_listing_card(ev: dict) -> str:
    score    = ev.get("score", 0)
    colors   = score_color(score)
    border_c = colors[0]
    badge_bg = colors[1]
    badge_fg = colors[2]

    tags_html = ""
    for t in ev.get("tags_positive", []):
        tags_html += render_tag(t, "ok")
    for t in ev.get("tags_warning", []):
        tags_html += render_tag(t, "warn")
    for t in ev.get("tags_negative", []):
        tags_html += render_tag(t, "bad")

    criteria = ev.get("criteria_met", {})
    crit_html = ""
    crit_map = [
        ("budget_ok",          "Sub buget"),
        ("bedrooms_ok",        "2+ dormitoare"),
        ("beach_distance_ok",  "Plaja <10km"),
        ("building_age_ok",    "Cladire moderna"),
        ("no_okupa_risk",      "Fara okupa"),
        ("no_flood_risk",      "Fara inundatii"),
        ("natural_element",    "Element natural"),
        ("airbnb_potential",   "Airbnb ok"),
    ]
    for key, label in crit_map:
        if key in criteria:
            crit_html += render_criteria_check(label, criteria[key])

    price_str = f"{ev.get('price_eur', '?'):,} €".replace(",", ".")
    url       = ev.get("source_url", "#")
    dist      = ev.get("distance_beach_km")
    dist_str  = f"{dist} km de plaja" if dist else ""
    bedrooms  = ev.get("bedrooms")
    bed_str   = f"{bedrooms} dormitoare" if bedrooms else ""
    meta_parts = [x for x in [ev.get("location",""), dist_str, bed_str] if x]
    meta_str  = " · ".join(meta_parts)

    return f"""
<div style="background:#fff;border-radius:12px;border:0.5px solid #e0e0e0;
            border-left:3px solid {border_c};border-radius:0 12px 12px 0;
            padding:16px 20px;margin-bottom:10px;font-family:sans-serif">

  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:8px">
    <div>
      <div style="font-size:14px;font-weight:500;color:#111;line-height:1.4;margin-bottom:4px">
        {ev.get("title_ro","Anunt")}
      </div>
      <div style="font-size:12px;color:#666;margin-bottom:6px">
        📍 {meta_str}
      </div>
      <div style="font-size:15px;font-weight:500;color:#111">{price_str}</div>
    </div>
    <div style="flex-shrink:0;width:42px;height:42px;border-radius:50%;
                background:{badge_bg};color:{badge_fg};display:flex;
                align-items:center;justify-content:center;
                font-size:16px;font-weight:500">{score}</div>
  </div>

  <div style="margin-bottom:8px">{tags_html}</div>

  <div style="margin-bottom:8px;line-height:1.8">{crit_html}</div>

  <div style="font-size:13px;color:#444;line-height:1.5;border-top:0.5px solid #eee;
              padding-top:8px;margin-top:4px">
    <strong style="color:#111">Concluzie:</strong> {ev.get("verdict_ro","")}
  </div>

  <div style="margin-top:10px">
    <a href="{url}" style="font-size:13px;color:#185FA5;text-decoration:none">
      Deschide anuntul ↗
    </a>
  </div>
</div>
"""


def build_digest_email(evaluations: list[dict], date_str: str) -> str:
    """Construieste HTML-ul complet al emailului digest."""

    top    = [e for e in evaluations if e.get("category") == "top"]
    medium = [e for e in evaluations if e.get("category") == "medium"]
    low    = [e for e in evaluations if e.get("category") == "low"]

    def section(title: str, icon: str, items: list, color: str) -> str:
        if not items:
            return ""
        cards = "".join(render_listing_card(e) for e in items)
        return f"""
<div style="font-size:11px;font-weight:500;color:#888;text-transform:uppercase;
            letter-spacing:0.05em;margin:20px 0 8px">
  {icon} {title}
</div>
{cards}"""

    top_section    = section("Merita atentie",    "🟢", top,    "#1D9E75")
    medium_section = section("Cu rezerve",        "🟡", medium, "#BA7517")
    low_section    = section("De evitat",         "🔴", low,    "#A32D2D")

    total = len(evaluations)

    return f"""
<!DOCTYPE html>
<html lang="ro">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:sans-serif">

<div style="max-width:620px;margin:24px auto;padding:0 12px">

  <!-- Header -->
  <div style="background:#fff;border-radius:12px;border:0.5px solid #e0e0e0;
              padding:20px 24px;margin-bottom:12px">
    <div style="font-size:12px;color:#888;margin-bottom:4px">{date_str}</div>
    <div style="font-size:16px;font-weight:500;color:#111">
      🏠 Alerte imobiliare Spania — {total} anunturi evaluate azi
    </div>
  </div>

  <!-- Sumar -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">
    <div style="background:#E1F5EE;border-radius:8px;padding:12px 16px;text-align:center">
      <div style="font-size:22px;font-weight:500;color:#0F6E56">{len(top)}</div>
      <div style="font-size:12px;color:#0F6E56;margin-top:2px">Merita atentie</div>
    </div>
    <div style="background:#FAEEDA;border-radius:8px;padding:12px 16px;text-align:center">
      <div style="font-size:22px;font-weight:500;color:#854F0B">{len(medium)}</div>
      <div style="font-size:12px;color:#854F0B;margin-top:2px">Cu rezerve</div>
    </div>
    <div style="background:#FCEBEB;border-radius:8px;padding:12px 16px;text-align:center">
      <div style="font-size:22px;font-weight:500;color:#A32D2D">{len(low)}</div>
      <div style="font-size:12px;color:#A32D2D;margin-top:2px">De evitat</div>
    </div>
  </div>

  <!-- Anunturi -->
  {top_section}
  {medium_section}
  {low_section}

  <!-- Footer -->
  <div style="font-size:12px;color:#888;margin-top:20px;padding-top:16px;
              border-top:0.5px solid #ddd;line-height:1.7">
    <strong style="color:#555">Criterii aplicate:</strong>
    Costa Blanca / Costa del Sol · sub 100.000 € · apartament sau casa ·
    min. 2 dormitoare · max. 10 km de plaja · liber (fara okupa) ·
    cladire post-1990 sau renovata · potential airbnb · element natural · zona sigura
    <br><br>
    Urmatorul digest: maine 08:00 · Agent imobiliar AI personal
  </div>

</div>
</body>
</html>
"""


# ============================================================
# FLUX PRINCIPAL
# ============================================================

def run():
    log.info("=== Agent imobiliar pornit ===")
    date_str = datetime.now(timezone.utc).strftime("%A, %d %B %Y, %H:%M UTC")

    # 1. Autentificare Gmail
    log.info("Obtinem access token Gmail...")
    try:
        token = get_gmail_access_token()
    except Exception as e:
        log.error("Eroare autentificare Gmail: %s", e)
        return

    # 2. Cauta emailuri noi de la portalurile imobiliare
    sender_query = " OR ".join(f"from:{s}" for s in ALERT_SENDERS)
    query = f"({sender_query}) is:unread"
    log.info("Caut emailuri noi: %s", query)

    messages = gmail_search(token, query, max_results=30)
    log.info("Gasit %d emailuri noi", len(messages))

    if not messages:
        log.info("Niciun email nou de procesat. Ne oprim.")
        return

    # 3. Extrage toate URL-urile de anunturi
    seen_urls = load_seen_urls()
    new_urls  = []

    for msg_meta in messages:
        msg  = gmail_get_message(token, msg_meta["id"])
        body = decode_email_body(msg)
        urls = extract_listing_urls(body)

        for url in urls:
            if url not in seen_urls:
                new_urls.append(url)
                seen_urls.add(url)

        gmail_mark_as_read(token, msg_meta["id"])

    log.info("URL-uri noi de evaluat: %d", len(new_urls))

    if not new_urls:
        log.info("Toate anunturile au fost deja evaluate. Ne oprim.")
        return

    # 4. Scraping + evaluare Claude pentru fiecare URL
    evaluations = []

    for i, url in enumerate(new_urls, 1):
        log.info("[%d/%d] Procesez: %s", i, len(new_urls), url)

        # Scraping
        listing_text = scrape_listing(url)
        if not listing_text:
            log.warning("Nu am putut extrage textul anuntului. Sar peste.")
            continue

        # Evaluare Claude
        result = evaluate_listing(listing_text, url)
        if result:
            result["source_url"] = url
            evaluations.append(result)
            log.info(
                "  Scor: %s/10 | Categorie: %s | %s",
                result.get("score"),
                result.get("category"),
                result.get("title_ro", "")[:50],
            )
        else:
            log.warning("  Evaluare esuata pentru %s", url)

        # Pauza intre cereri (evita rate limiting)
        if i < len(new_urls):
            time.sleep(2)

    # 5. Salveaza URL-urile vazute
    save_seen_urls(seen_urls)

    if not evaluations:
        log.info("Nicio evaluare reusita. Nu trimitem email.")
        return

    # 6. Sorteaza: top > medium > low, apoi dupa scor descrescator
    category_order = {"top": 0, "medium": 1, "low": 2}
    evaluations.sort(
        key=lambda e: (
            category_order.get(e.get("category", "low"), 3),
            -e.get("score", 0),
        )
    )

    # 7. Construieste si trimite emailul digest
    log.info("Construiesc emailul digest cu %d anunturi...", len(evaluations))
    html_body = build_digest_email(evaluations, date_str)

    subject = (
        f"🏠 Alerte Spania — {len(evaluations)} anunturi evaluate "
        f"({sum(1 for e in evaluations if e.get('category')=='top')} de urmarit)"
    )

    sent, failed = 0, 0
    for recipient in RECIPIENT_LIST:
        try:
            gmail_send(token, recipient, subject, html_body)
            log.info("Digest trimis catre %s", recipient)
            sent += 1
        except Exception as e:
            log.error("Eroare la trimiterea catre %s: %s", recipient, e)
            failed += 1

    if sent:
        log.info("=== Digest trimis cu succes catre %d destinatar(i)! ===", sent)
    if failed:
        log.warning("Eroare la %d destinatar(i).", failed)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run()