"""Puxa o spend diário por campanha de todas as contas (Meta Ads API),
agrupa por funil/dia e escreve data.json no schema do dashboard.

Rodável local (usa .env das skills) ou no GitHub Actions (usa secrets
META_TOKEN_ID / META_TOKEN_MEM). Reescreve só data.json — index.html é estático.
"""
import os, sys, json, time, warnings, collections
warnings.filterwarnings("ignore")
from datetime import date
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TODAY = date.today() if not os.environ.get("TZ_SP") else None
    today = __import__("datetime").datetime.now(ZoneInfo("America/Sao_Paulo")).date()
except Exception:
    today = date.today()

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

from config import ACCOUNTS, FAM_PREF, SINCE, resolve_token, funnel_key, family

OUT = Path(__file__).parent / "data.json"
UNTIL = today.isoformat()
FIELDS = ["campaign_name", "spend"]
BASE_PARAMS = {"level": "campaign", "time_increment": 1, "limit": 500}


def _month_windows(since: str, until: str):
    """Gera janelas mensais (since,until) cobrindo [since, until].

    Puxar o ano inteiro com time_increment=1 num request só estoura o endpoint
    síncrono nas contas pesadas (error_subcode 99 / cursor expirado) e a conta
    inteira some do data.json. Fatiar por mês mantém cada request pequeno.
    """
    from datetime import date as _d
    y, m = int(since[:4]), int(since[5:7])
    yN, mN = int(until[:4]), int(until[5:7])
    while (y, m) <= (yN, mN):
        first = _d(y, m, 1)
        nm_y, nm_m = (y + 1, 1) if m == 12 else (y, m + 1)
        last = _d.fromordinal(_d(nm_y, nm_m, 1).toordinal() - 1)
        yield max(first.isoformat(), since), min(last.isoformat(), until)
        y, m = nm_y, nm_m


def pull_account(acct_id: str):
    """Retorna (rows, erros): rows = (funnel, date, spend) com spend>0, mês a mês."""
    rows, errs = [], []
    for s, u in _month_windows(SINCE, UNTIL):
        params = dict(BASE_PARAMS, time_range={"since": s, "until": u})
        last_err = None
        for attempt in range(3):  # retry em 500 / cursor transitório
            try:
                win = []
                cursor = AdAccount(acct_id).get_insights(fields=FIELDS, params=params)
                for it in cursor:
                    sp = float(it.get("spend", 0) or 0)
                    if sp <= 0:
                        continue
                    win.append((funnel_key(it.get("campaign_name", "")), it.get("date_start"), sp))
                rows.extend(win)
                last_err = None
                break
            except Exception as e:
                last_err = e
                time.sleep(3 * (attempt + 1))
        if last_err is not None:
            errs.append(f"{acct_id} {s}->{u}: {str(last_err)[:200]}")
    return rows, errs


def main():
    # agrega (acct_key -> {(funnel,date): spend})
    per_acct = collections.OrderedDict((a["key"], collections.defaultdict(float)) for a in ACCOUNTS)
    fam_of = {}
    dmin, dmax = "9999-99-99", "0000-00-00"

    last_token = None
    failures = []
    for a in ACCOUNTS:
        token = resolve_token(a["token_env"], a["skill_env"])
        if token != last_token:
            FacebookAdsApi.init(access_token=token)
            last_token = token
        try:
            rows, errs = pull_account(a["key"])
        except Exception as e:
            print(f"WARN {a['key']} ({a['label']}): {e}", file=sys.stderr)
            rows, errs = [], [f"{a['key']}: {str(e)[:200]}"]
        for e in errs:
            print(f"    WARN {a['client']} {a['label']} | {e}", file=sys.stderr)
        failures.extend(errs)
        for fk, d, sp in rows:
            per_acct[a["key"]][(fk, d)] += sp
            fam_of[fk] = family(fk)
            if d and d < dmin: dmin = d
            if d and d > dmax: dmax = d
        print(f"  {a['label']:<18} {a['key']}: {len(rows)} linhas", file=sys.stderr)

    # Falha de coleta some com a conta inteira do dashboard (foi o que aconteceu
    # com a C1 do Instituto ID). Melhor abortar e manter o data.json anterior,
    # completo, do que publicar um recorte parcial que parece dado real.
    if failures:
        print(f"ABORT: {len(failures)} janela(s) falharam; data.json NAO foi reescrito.", file=sys.stderr)
        sys.exit(1)

    # mantém só contas com verba, reindexando
    funded = [a for a in ACCOUNTS if per_acct[a["key"]]]
    idx_of = {a["key"]: i for i, a in enumerate(funded)}
    records = []
    for a in funded:
        ai = idx_of[a["key"]]
        for (fk, d), sp in per_acct[a["key"]].items():
            records.append([ai, fk, d, round(sp, 2)])
    records.sort(key=lambda r: (r[0], r[2], r[1]))

    present = sorted(set(fam_of.values()))
    fam_order = [f for f in FAM_PREF if f in present] + [f for f in present if f not in FAM_PREF]

    bounds_min = SINCE
    bounds_max = dmax if dmax != "0000-00-00" else UNTIL
    if bounds_max < UNTIL:
        bounds_max = UNTIL  # estende o eixo até hoje

    out = {
        "generated": today.strftime("%d/%m/%Y"),
        "bounds": {"min": bounds_min, "max": bounds_max},
        "accounts": [{"key": a["key"], "client": a["client"], "label": a["label"]} for a in funded],
        "fam_of": fam_of,
        "fam_order": fam_order,
        "records": records,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    tot = sum(r[3] for r in records)
    print(f"OK data.json | contas={len(funded)} funis={len(present)} registros={len(records)} "
          f"total=R$ {tot:,.2f} | {bounds_min}->{bounds_max} | gerado {out['generated']}", file=sys.stderr)


if __name__ == "__main__":
    main()
