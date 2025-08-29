#!/usr/bin/env python3
"""
HR Prospect Automator - Clean & Simple
"""

import os, re, csv, time, argparse, requests, smtplib
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText

# extra tools (load if installed, warna skip kar do)
try: import spacy; SPACY_AVAILABLE=True
except: SPACY_AVAILABLE=False
try: import openai; OPENAI_AVAILABLE=True
except: OPENAI_AVAILABLE=False
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    SENDGRID_AVAILABLE=True
except: SENDGRID_AVAILABLE=False

# API keys -> env variables se lo
SERPAPI_KEY   = os.getenv("SERPAPI_API_KEY")
HUNTER_KEY    = os.getenv("HUNTER_API_KEY")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY")
SMTP_EMAIL    = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDGRID_KEY  = os.getenv("SENDGRID_API_KEY")

HEADERS = {"User-Agent": "Mozilla/5.0 HRProspector"}

# ek candidate ki info store karne ka simple structure
@dataclass
class Prospect:
    source: str
    full_name: Optional[str]
    role: Optional[str]
    location: Optional[str]
    profile_url: Optional[str]
    bio: Optional[str]
    email: Optional[str]
    company: Optional[str]
    fit: Optional[str]
    matched_skills: List[str]
    summary: Optional[str]
    snippet: Optional[str]

# safe GET request (agar error aaya toh None return karega)
def safe_get(url: str, params: Dict=None, headers: Dict=None, timeout:int=30):
    try:
        r = requests.get(url, params=params, headers=headers or HEADERS, timeout=timeout)
        return r if r.status_code == 200 else None
    except: return None

# Google search (via SerpAPI) -> profiles nikalega
def search_profiles_serpapi(query: str, location: str, limit:int=20) -> List[Dict]:
    if not SERPAPI_KEY: 
        print("[WARN] No SERPAPI key, skipping search."); return []
    q = f'("{query}" {location}) site:linkedin.com/in OR site:github.com OR site:twitter.com'
    url = "https://serpapi.com/search.json"
    params = {"engine": "google", "q": q, "api_key": SERPAPI_KEY, "num": 10}
    results, fetched = [], 0
    while fetched < limit:
        params["start"] = fetched
        resp = safe_get(url, params=params)
        if not resp: break
        for item in resp.json().get("organic_results", []):
            results.append({"title": item.get("title"), "link": item.get("link"), "snippet": item.get("snippet")})
        fetched += len(results)
        if not resp.json().get("organic_results"): break
        time.sleep(1)  # thoda delay rakho warna block ho jaoge
    return results

# github url se username nikalne ka shortcut
def extract_github_username(url: str) -> Optional[str]:
    m = re.match(r"https?://(www\.)?github\.com/([A-Za-z0-9-_.]+)", url)
    return m.group(2) if m else None

# github API se profile data pull karna
def fetch_github_profile(username: str) -> Dict:
    r = safe_get(f"https://api.github.com/users/{username}")
    return {} if not r else {
        "full_name": r.json().get("name"),
        "bio": r.json().get("bio"),
        "company": r.json().get("company"),
        "email": r.json().get("email"),
        "location": r.json().get("location")
    }

# hunter.io se email guess karna (agar key mili toh)
def hunter_email_finder(full_name: str, domain: str) -> Optional[str]:
    if not HUNTER_KEY: return None
    r = safe_get("https://api.hunter.io/v2/email-finder",
                 {"full_name": full_name, "domain": domain, "api_key": HUNTER_KEY})
    return r.json().get("data", {}).get("email") if r else None

# snippet se company domain guess karne ka chhota hack
def guess_company_domain(text: str) -> Optional[str]:
    m = re.search(r"([A-Za-z0-9-]+\.[A-Za-z]{2,})", text or "")
    if not m: return None
    domain = m.group(1).lower()
    if any(bad in domain for bad in ["linkedin.com","github.com","twitter.com","gmail.com"]):
        return None
    return domain

# candidate bio analyse karna -> role + skills match check
nlp = None
if SPACY_AVAILABLE:
    try: nlp = spacy.load("en_core_web_sm")
    except: nlp = None

def analyze_bio(bio: str, role: str, skills: List[str]) -> Dict:
    if not bio: return {"fit":"unknown","matched_skills":[],"summary":""}
    if not nlp:  # agar spacy nahi mila toh simple keyword check
        text = bio.lower()
        matched = [s for s in skills if s.lower() in text]
        role_found = role.lower() in text
        fit = "good" if role_found and matched else ("partial" if matched else "unclear")
        return {"fit": fit, "matched_skills": matched, "summary": bio[:200]}
    doc = nlp(bio)
    matched = [s for s in skills if s.lower() in bio.lower()]
    role_found = role.lower() in bio.lower()
    fit = "good" if role_found and matched else ("partial" if matched else "unclear")
    summary = list(doc.sents)[0].text if list(doc.sents) else bio[:160]
    return {"fit": fit, "matched_skills": matched, "summary": summary}

# Gmail SMTP se email bhejna
def send_email_smtp(sender: str, pwd: str, to: str, sub: str, body: str) -> bool:
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = sub, sender, to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pwd)
            server.sendmail(sender, to, msg.as_string())
        return True
    except Exception as e:
        print("[SMTP ERROR]", e); return False

# pura pipeline: profiles dhundo -> filter karo -> Prospect banao
def build_and_filter_prospects(role:str, skills_csv:str, location:str, limit:int=30) -> List[Prospect]:
    skills = [s.strip() for s in skills_csv.split(",") if s.strip()]
    results = search_profiles_serpapi(role, location, limit)
    prospects = []
    for r in results:
        link, title, snippet = r.get("link",""), r.get("title",""), r.get("snippet","")
        full_name, role_guess, bio_text, email, company, loc = None, None, snippet, None, None, None

        if "github.com" in link:  # agar github profile hai toh detail pull kar lo
            gh = fetch_github_profile(extract_github_username(link))
            full_name, bio_text, email, company, loc = gh.get("full_name"), gh.get("bio"), gh.get("email"), gh.get("company"), gh.get("location")

        if not full_name and title:  # title se naam/role guess karna
            parts = re.split(r"[-|•]", title)
            full_name = parts[0].strip()
            if len(parts) > 1: role_guess = parts[1].strip()

        if not email and full_name:  # email guess karo hunter se
            domain = guess_company_domain(snippet)
            if domain: email = hunter_email_finder(full_name, domain)

        analysis = analyze_bio(bio_text or "", role, skills)
        if analysis["fit"] in ("good","partial"):  # sirf relevant candidates rakho
            prospects.append(Prospect("serpapi", full_name, role_guess or role, loc or location,
                                      link, bio_text, email, company, analysis["fit"],
                                      analysis["matched_skills"], analysis["summary"], snippet))
    return prospects

# list ko CSV file me save karna
def save_prospects_csv(file:str, prospects:List[Prospect]):
    with open(file,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(prospects[0]).keys()))
        w.writeheader()
        for p in prospects: w.writerow(asdict(p))

# command line entry point
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role")
    parser.add_argument("--skills", default="")
    parser.add_argument("--location", default="India")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--out", default="prospects.csv")
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()

    print("[*] Finding profiles...")
    prospects = build_and_filter_prospects(args.role, args.skills, args.location, args.limit)
    print(f"[*] Found {len(prospects)} prospects. Saving to {args.out}")
    save_prospects_csv(args.out, prospects)

    if args.send:
        for p in prospects:
            if not p.email: continue
            body = f"Hi {p.full_name},\nWe are hiring {args.role}. Let's connect!"
            send_email_smtp(SMTP_EMAIL, SMTP_PASSWORD, p.email, f"Opportunity: {args.role}", body)
            time.sleep(1)

if _name_ == "_main_":
    main()