"""Config do dashboard de investimento — contas, tokens e parsing de funil."""
import os, re
from pathlib import Path

# Início da janela do dashboard (ano corrente).
SINCE = "2026-01-01"

# Contas de anúncio. token_env = nome da variável de ambiente / GitHub secret.
# Fallback local: .env da skill correspondente (skill_env).
ACCOUNTS = [
    {"key": "act_1725623984282551", "client": "Instituto ID", "label": "C1 (IPM)",          "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_506518827383127",  "client": "Instituto ID", "label": "C3 / Instituto ID",  "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_306533480853015",  "client": "Instituto ID", "label": "C2",                 "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_629440996401732",  "client": "Instituto ID", "label": "C4",                 "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_529640016271311",  "client": "Instituto ID", "label": "C5",                 "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_1307282709635504", "client": "Memorável",    "label": "C1",                 "token_env": "META_TOKEN_MEM", "skill_env": "meta-ads-memoravel"},
    {"key": "act_1835702343244302", "client": "Memorável",    "label": "C2",                 "token_env": "META_TOKEN_MEM", "skill_env": "meta-ads-memoravel"},
    {"key": "act_422653132521856",  "client": "Memorável",    "label": "C3",                 "token_env": "META_TOKEN_MEM", "skill_env": "meta-ads-memoravel"},
]

# Famílias na ordem preferida (extras presentes nos dados entram depois).
FAM_PREF = ["IPM", "DP100K", "IPL", "MXP", "KLT", "FA-Fp"]


def resolve_token(token_env: str, skill_env: str) -> str:
    """Lê o token do ambiente (GitHub secret) ou cai pro .env da skill (uso local)."""
    v = os.environ.get(token_env)
    if v:
        return v.strip()
    p = Path.home() / ".claude/skills" / skill_env / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line.startswith("META_ADS_TOKEN") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"Token nao encontrado: env {token_env} nem .env de {skill_env}")


def funnel_key(name: str) -> str:
    s = (name or "").strip()
    if s.lower().startswith(("post do instagram", "publicacao", "publicação")):
        return "Impulsionamentos IG"
    s = re.sub(r"^ix\.\s*", "", s)
    m = re.match(r"^\[([^\]]+)\]", s)
    key = m.group(1).strip() if m else re.split(r"\s*[-–]\s*|\[", s)[0].strip()
    m2 = re.match(r"^([A-Za-z]{2,5})[-\s]?(Le|Fp|LE|FP|le|fp)\s?0?(\d+)$", key)
    if m2:
        ph = "Le" if m2.group(2).lower() == "le" else "Fp"
        return f"{m2.group(1).upper()}-{ph}{int(m2.group(3)):02d}"
    return key


def family(funnel: str) -> str:
    if funnel.lower().startswith("impuls"):
        return "Outros"
    tok = re.split(r"[-\s]", funnel)[0].upper()
    return "FA-Fp" if tok == "FA" else tok
