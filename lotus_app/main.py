from __future__ import annotations

import os
import base64
import hmac
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse

from .dataset import DatasetError, GoldHistory
from .research import catalog_payload
from .research.backtests import BacktestError, BacktestLibrary
from .research.experiments import ExperimentStore
from .research.replay import replay_latest


DATA_ROOT = Path(os.getenv("LOTUS_DATA_ROOT", "/home/codexops/lotus-data"))
RESEARCH_ROOT = Path(os.getenv("LOTUS_RESEARCH_ROOT", Path(__file__).resolve().parents[1] / "var" / "research"))
BACKTEST_ROOT = Path(
    os.getenv(
        "LOTUS_5LOTUS_BACKTEST_ROOT",
        str(Path(__file__).resolve().parents[2] / "5lotus" / "python-service" / "data" / "backtests"),
    )
)
BUNDLE_ROOT = Path(os.getenv("LOTUS_BUNDLE_ROOT", Path(__file__).resolve().parents[1] / "bundles"))
app = FastAPI(title="4lotus Strategy Service")

_PANEL_PASSWORD = os.getenv("LOTUS_PANEL_PASSWORD", "")

@app.middleware("http")
async def panel_auth(request: Request, call_next):
    if _PANEL_PASSWORD and not request.url.path.startswith(("/health", "/ready", "/api/")):
        header = request.headers.get("authorization", "")
        try:
            scheme, token = header.split(" ", 1)
            supplied = base64.b64decode(token).decode().split(":", 1)[1]
        except (ValueError, UnicodeDecodeError, IndexError):
            scheme, supplied = "", ""
        if scheme.lower() != "basic" or not hmac.compare_digest(supplied, _PANEL_PASSWORD):
            return JSONResponse({"detail": "authentication required"}, status_code=401, headers={"WWW-Authenticate": "Basic"})
    return await call_next(request)

NAVIGATION = (
    ("history", "/", "Histórico do ouro", "database"),
    ("strategies", "/strategies", "Estratégias", "grid"),
    ("simulator", "/growth-simulator", "Simulador de crescimento", "trend"),
    ("comparison", "/compare", "Comparar estratégias", "compare"),
)


def icon(name: str) -> str:
    paths = {
        "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
        "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
        "trend": '<path d="M4 18V6M4 18h16M7 14l4-4 3 2 5-6"/>',
        "compare": '<path d="M7 3v18M17 3v18M3 7l4-4 4 4M13 17l4 4 4-4"/>',
    }
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>'


def page(title: str, active: str, content: str, script: str = "") -> HTMLResponse:
    links = "".join(
        f'<a class="nav-link {"active" if item_id == active else ""}" href="{href}"'
        f'{" aria-current=\"page\"" if item_id == active else ""}>{icon(icon_name)}<span>{label}</span></a>'
        for item_id, href, label, icon_name in NAVIGATION
    )
    current = next(label for item_id, _, label, _ in NAVIGATION if item_id == active)
    return HTMLResponse(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>
    :root {{ --bg:#07090d; --panel:#0f141c; --panel2:#151c26; --line:#283242; --text:#edf2f7; --muted:#8c9aae; --green:#43d398; --yellow:#f6c667; --blue:#64b5ff; --red:#ff778a; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; min-width:320px; background:var(--bg); color:var(--text); font-family:Inter,ui-sans-serif,system-ui,sans-serif; }}
    .shell {{ min-height:100vh; display:grid; grid-template-columns:248px minmax(0,1fr); }} .sidebar {{ position:sticky; top:0; height:100vh; display:flex; flex-direction:column; padding:22px 14px; border-right:1px solid var(--line); background:#0a0e14; }}
    .brand {{ display:block; padding:6px 12px 26px; color:var(--text); text-decoration:none; font-size:20px; font-weight:800; letter-spacing:.08em; }} .brand small {{ display:block; margin-top:5px; color:var(--green); font-size:10px; letter-spacing:.12em; }}
    .workspace-label {{ padding:14px 12px 18px; border-top:1px solid var(--line); color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }} .workspace-label strong {{ display:block; margin-top:6px; color:var(--text); font-size:13px; letter-spacing:0; text-transform:none; }}
    .nav {{ display:grid; gap:5px; }} .nav-link {{ display:flex; align-items:center; gap:12px; min-height:44px; padding:0 12px; border-radius:6px; color:var(--muted); text-decoration:none; font-size:14px; font-weight:650; }} .nav-link:hover {{ background:#121924; color:var(--text); }} .nav-link.active {{ background:#1b2634; color:#fff; }} .nav-link svg {{ width:19px; height:19px; fill:none; stroke:currentColor; stroke-width:1.8; }}
    .sidebar-footer {{ margin-top:auto; padding:16px 12px 4px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }} .sidebar-footer strong {{ display:block; color:var(--text); margin-bottom:4px; }} .dot {{ display:inline-block; width:8px; height:8px; margin-right:7px; border-radius:50%; background:var(--green); }}
    .workspace {{ min-width:0; }} .topbar {{ height:68px; display:flex; align-items:center; padding:0 34px; border-bottom:1px solid var(--line); background:rgba(10,14,20,.82); }} .topbar span {{ display:block; color:var(--muted); font-size:12px; }} .topbar strong {{ display:block; margin-top:2px; font-size:15px; }}
    main {{ max-width:1380px; padding:34px; }} .eyebrow {{ margin:0 0 8px; color:var(--green); font-size:11px; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }} h1 {{ margin:0; font-size:30px; letter-spacing:0; }} h2 {{ margin:0; font-size:18px; }} .lead,.muted {{ color:var(--muted); }} .lead {{ margin:10px 0 0; max-width:760px; line-height:1.55; }}
    .page-head {{ display:flex; justify-content:space-between; gap:24px; align-items:start; margin-bottom:28px; }} .release {{ min-width:230px; padding:14px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--muted); font-size:12px; }} .release strong {{ display:block; margin-top:5px; color:var(--text); font-size:13px; overflow-wrap:anywhere; }}
    .stats {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:16px; }} .stat,.panel {{ border:1px solid var(--line); border-radius:7px; background:var(--panel); }} .stat {{ min-height:104px; padding:16px; }} .stat span {{ display:block; color:var(--muted); font-size:12px; }} .stat strong {{ display:block; margin-top:12px; font-size:20px; }}
    .panel {{ padding:20px; }} .toolbar {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:18px 0 14px; }} .segmented {{ display:flex; padding:3px; border:1px solid var(--line); border-radius:7px; background:#0a0e14; }} button {{ font:inherit; cursor:pointer; }} .segmented button {{ border:0; border-radius:5px; padding:7px 11px; background:transparent; color:var(--muted); font-size:12px; font-weight:700; }} .segmented button.active {{ background:#26364a; color:#fff; }}
    .backtest-panel {{ margin-bottom:16px; }} .backtest-head {{ display:flex; justify-content:space-between; align-items:start; gap:18px; }} .backtest-chart {{ display:block; width:100%; height:330px; margin-top:18px; border:1px solid #1c2532; border-radius:6px; background:#090d13; }} .backtest-stats {{ margin:16px 0 0; }}
    .tabs {{ display:flex; gap:4px; overflow-x:auto; margin-bottom:18px; padding-bottom:1px; border-bottom:1px solid var(--line); }} .tab {{ flex:0 0 auto; padding:10px 13px; border:0; border-bottom:2px solid transparent; background:transparent; color:var(--muted); font-size:13px; font-weight:700; }} .tab.active {{ border-color:var(--green); color:var(--text); }}
    .tab-panel[hidden] {{ display:none; }} .pipeline {{ border-top:1px solid var(--line); }} .stage {{ display:grid; grid-template-columns:170px minmax(0,1fr) 120px; gap:22px; align-items:center; min-height:104px; padding:18px 2px; border-bottom:1px solid var(--line); }} .stage-index {{ color:var(--muted); font-size:11px; font-weight:800; text-transform:uppercase; }} .stage h2 {{ margin-top:5px; }} .stage p {{ margin:6px 0 0; color:var(--muted); font-size:13px; line-height:1.5; }} .stage-count {{ text-align:right; }} .stage-count strong {{ display:block; font-size:23px; }} .stage-count span {{ color:var(--muted); font-size:11px; }}
    .badge {{ display:inline-flex; align-items:center; min-height:24px; padding:0 8px; border:1px solid var(--line); border-radius:4px; color:var(--muted); font-size:11px; font-weight:800; text-transform:uppercase; }} .badge.frozen {{ border-color:#27795b; color:var(--green); }} .badge.draft {{ border-color:#806936; color:var(--yellow); }} .table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:7px; }} table {{ width:100%; border-collapse:collapse; font-size:13px; }} th,td {{ padding:13px 14px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }} th {{ color:var(--muted); font-size:11px; text-transform:uppercase; }} tr:last-child td {{ border-bottom:0; }} td code {{ color:var(--blue); }}
    .research-grid {{ display:grid; grid-template-columns:minmax(0,1fr) 300px; gap:16px; }} .run-panel {{ border-left:3px solid var(--green); }} .run-panel .segmented {{ width:max-content; margin-top:16px; }} .run-status {{ min-height:58px; margin-top:16px; color:var(--muted); font-size:13px; line-height:1.6; }}
    #chart {{ display:block; width:100%; height:450px; border:1px solid #1c2532; border-radius:6px; background:#090d13; }} .chart-status {{ min-height:20px; margin:10px 0 0; color:var(--muted); font-size:12px; }}
    .empty {{ display:grid; min-height:310px; place-items:center; padding:30px; border:1px dashed #3b4758; border-radius:7px; color:var(--muted); text-align:center; }} .empty strong {{ display:block; margin-bottom:7px; color:var(--text); font-size:16px; }}
    .simulator {{ display:grid; grid-template-columns:minmax(260px,360px) minmax(0,1fr); gap:16px; }} label {{ display:grid; gap:7px; margin-top:14px; color:var(--muted); font-size:12px; }} input {{ width:100%; padding:10px; border:1px solid var(--line); border-radius:6px; background:#090d13; color:var(--text); font:inherit; }} .primary {{ margin-top:18px; padding:10px 14px; border:1px solid var(--green); border-radius:6px; background:var(--green); color:#06120d; font-weight:800; }} .projection {{ min-height:330px; }} .projection-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:20px; }}
    @media (max-width:860px) {{ .shell {{ grid-template-columns:1fr; }} .sidebar {{ position:static; height:auto; padding:14px; border-right:0; border-bottom:1px solid var(--line); }} .brand {{ padding-bottom:14px; }} .workspace-label,.sidebar-footer {{ display:none; }} .nav {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .topbar {{ height:58px; padding:0 18px; }} main {{ padding:24px 18px; }} .page-head {{ display:block; }} .release {{ margin-top:18px; }} .stats,.projection-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .simulator,.research-grid {{ grid-template-columns:1fr; }} .stage {{ grid-template-columns:120px minmax(0,1fr) 76px; gap:12px; }} .backtest-head {{ display:block; }} .backtest-head .segmented {{ margin-top:16px; }} }}
    @media (max-width:480px) {{ .nav-link {{ padding:0 8px; font-size:12px; }} .stats,.projection-grid {{ grid-template-columns:1fr; }} h1 {{ font-size:26px; }} }}
    </style></head><body><div class="shell"><aside class="sidebar"><a class="brand" href="/">LOTUS<small>Research dashboard</small></a><div class="workspace-label">Research workspace<strong>Dados publicados</strong></div><nav class="nav">{links}</nav><div class="sidebar-footer"><strong><span class="dot"></span>Somente leitura</strong>Dataset XAUUSD local</div></aside><section class="workspace"><header class="topbar"><div><span>Lotus</span><strong>{current}</strong></div></header><main>{content}</main></section></div>{script}</body></html>""")


def history() -> GoldHistory:
    return GoldHistory(DATA_ROOT)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "4lotus-strategy"}


@app.get("/ready")
def readiness() -> dict[str, object]:
    bundles = sorted(path.name for path in BUNDLE_ROOT.glob("*.json"))
    return {"status": "ready", "bundles": bundles}


@app.get("/api/bundles")
def bundles() -> dict[str, object]:
    import json

    items = []
    for path in sorted(BUNDLE_ROOT.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        items.append({key: payload.get(key) for key in ("id", "name", "version", "implementation", "sha256")})
    return {"items": items}


@app.get("/", response_class=HTMLResponse)
def gold_history_page() -> HTMLResponse:
    content = """<header class="page-head"><div><p class="eyebrow">Dataset publicado</p><h1>Histórico do ouro</h1><p class="lead">Leitura direta dos ticks XAUUSD publicados localmente, agregados em candles para visualização. Nenhuma estratégia é carregada neste ambiente.</p></div><div class="release"><span>Release atual</span><strong id="release-version">Carregando...</strong></div></header><section class="stats"><article class="stat"><span>Cobertura</span><strong id="coverage">-</strong></article><article class="stat"><span>Ticks publicados</span><strong id="ticks">-</strong></article><article class="stat"><span>Partições diárias</span><strong id="partitions">-</strong></article><article class="stat"><span>Coleta</span><strong id="collection">-</strong></article></section><section class="panel"><p class="eyebrow">XAUUSD · ticks publicados</p><h2>Preço histórico</h2><div class="toolbar"><div class="segmented" id="resolution"><button data-value="1m">1m</button><button class="active" data-value="5m">5m</button><button data-value="1h">1h</button><button data-value="1d">1d</button></div><div class="segmented" id="days"><button data-value="30">30D</button><button data-value="90">90D</button><button class="active" data-value="365">1A</button><button data-value="1095">3A</button><button data-value="1826">5A</button><button data-value="2557">7A</button></div></div><canvas id="chart" aria-label="Gráfico de preço histórico XAUUSD derivado dos ticks publicados"></canvas><p class="chart-status" id="chart-status">Carregando dados...</p></section>"""
    script = """<script>
    const state={resolution:'5m',days:365}; const qs=s=>document.querySelector(s);
    const fmt=n=>new Intl.NumberFormat('pt-BR').format(n);
    function paint(rows){const canvas=qs('#chart'),ctx=canvas.getContext('2d'),rect=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1,w=rect.width,h=rect.height;canvas.width=w*ratio;canvas.height=h*ratio;ctx.scale(ratio,ratio);ctx.clearRect(0,0,w,h);if(!rows.length){qs('#chart-status').textContent='Não há candles para esse período.';return}const pad={l:54,r:18,t:20,b:28},high=Math.max(...rows.map(r=>r.high)),low=Math.min(...rows.map(r=>r.low)),range=high-low||1,x=i=>pad.l+i*(w-pad.l-pad.r)/Math.max(rows.length-1,1),y=value=>pad.t+(high-value)*(h-pad.t-pad.b)/range;ctx.strokeStyle='#263242';ctx.lineWidth=1;ctx.fillStyle='#8c9aae';ctx.font='11px system-ui';for(let i=0;i<5;i++){const value=low+range*i/4,yy=y(value);ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText(value.toFixed(2),6,yy+4)}const width=Math.max(1,(w-pad.l-pad.r)/rows.length*.65);for(let i=0;i<rows.length;i++){const r=rows[i],xx=x(i),up=r.close>=r.open;ctx.strokeStyle=up?'#43d398':'#ff778a';ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(xx,y(r.high));ctx.lineTo(xx,y(r.low));ctx.stroke();const top=y(Math.max(r.open,r.close)),body=Math.max(1,Math.abs(y(r.open)-y(r.close)));ctx.fillRect(xx-width/2,top,width,body)}ctx.fillStyle='#8c9aae';ctx.fillText(new Date(rows[0].time).toLocaleDateString('pt-BR',{timeZone:'UTC'}),pad.l,h-9);const end=new Date(rows.at(-1).time).toLocaleDateString('pt-BR',{timeZone:'UTC'});ctx.textAlign='right';ctx.fillText(end,w-pad.r,h-9);ctx.textAlign='left';qs('#chart-status').textContent=`${fmt(rows.length)} candles exibidos · UTC · ${state.resolution}`;}
    async function load(){try{const [summary,response]=await Promise.all([fetch('/api/history/summary'),fetch(`/api/history/candles?resolution=${state.resolution}&days=${state.days}`)]);if(!summary.ok||!response.ok)throw new Error('O dataset local não está disponível.');const s=await summary.json(),rows=await response.json();qs('#release-version').textContent=s.version;qs('#coverage').textContent=`${s.coverage_start} a ${s.coverage_end}`;qs('#ticks').textContent=fmt(s.ticks);qs('#partitions').textContent=fmt(s.partitions);qs('#collection').textContent=s.collection_status==='complete'?'Completa':'Parcial';paint(rows)}catch(error){qs('#chart-status').textContent=error.message}}
    for(const group of ['resolution','days'])qs('#'+group).addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;state[group]=group==='days'?Number(button.dataset.value):button.dataset.value;if(group==='days'&&state.days>=1826){state.resolution='1d';qs('#resolution').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.value==='1d'))}qs('#'+group).querySelectorAll('button').forEach(b=>b.classList.toggle('active',b===button));load()});addEventListener('resize',()=>load());load();
    </script>"""
    return page("Lotus | Histórico do ouro", "history", content, script)


@app.get("/strategies", response_class=HTMLResponse)
def strategies_page() -> HTMLResponse:
    content = """<header class="page-head"><div><p class="eyebrow">Laboratório causal</p><h1>Estratégias</h1><p class="lead">Pesquisa sequencial de gatilhos, contexto e calendário. Cada decisão preserva o ramo escolhido e encerra sem fallback.</p></div><div class="release"><span>Referência congelada</span><strong>ZigZag Scalper V1.0</strong></div></header>
    <div class="tabs" role="tablist"><button class="tab active" data-tab="overview">Visão geral</button><button class="tab" data-tab="trigger">Gatilhos <span id="trigger-tab-count">2/4</span></button><button class="tab" data-tab="context">Contextos <span id="context-tab-count">0/8</span></button><button class="tab" data-tab="temporal">Temporais <span id="temporal-tab-count">0/12</span></button><button class="tab" data-tab="router">Roteadores <span>3/3</span></button><button class="tab" data-tab="experiments">Experimentos</button></div>
    <section class="tab-panel" data-panel="overview"><div class="panel backtest-panel"><div class="backtest-head"><div><p class="eyebrow">Backtest importado</p><h2>ZigZag Scalper V1.0</h2><p class="muted">Snapshot produzido pelo 2Lotus · curva normalizada a partir de US$ 10.000.</p></div><div class="segmented" id="backtest-days"><button data-days="365">1A</button><button data-days="1095">3A</button><button class="active" data-days="1826">5A</button><button data-days="2557">7A</button></div></div><canvas id="backtest-chart" class="backtest-chart" aria-label="Curva de patrimônio do backtest ZigZag Scalper V1.0"></canvas><div class="stats backtest-stats"><article class="stat"><span>Patrimônio final</span><strong id="backtest-equity">-</strong></article><article class="stat"><span>Operações</span><strong id="backtest-trades">-</strong></article><article class="stat"><span>Profit factor</span><strong id="backtest-pf">-</strong></article><article class="stat"><span>Período</span><strong id="backtest-period">-</strong></article></div><p class="chart-status" id="backtest-status">Carregando snapshot...</p></div><div class="research-grid"><div class="pipeline"><article class="stage"><div><span class="stage-index">Etapa 01</span><h2>Gatilho</h2></div><p><strong>V1.0 estrutural + V1.3 impulso</strong><br>Rompimentos M30 com seleção causal por ticks.</p><div class="stage-count"><strong>2 / 4</strong><span>em pesquisa</span></div></article><article class="stage"><div><span class="stage-index">Etapa 02</span><h2>Contexto</h2></div><p>Passagem neutra até uma hipótese contextual ser registrada e validada.</p><div class="stage-count"><strong>0 / 8</strong><span>disponíveis</span></div></article><article class="stage"><div><span class="stage-index">Etapa 03</span><h2>Temporal</h2></div><p>Doze políticas mensais UTC compartilham o mesmo contrato de aprovação.</p><div class="stage-count"><strong>0 / 12</strong><span>disponíveis</span></div></article><article class="stage"><div><span class="stage-index">Etapa 04</span><h2>Decisão</h2></div><p>O orquestrador entrega um candidato único e a trilha de roteamento completa.</p><div class="stage-count"><strong>3</strong><span>roteadores</span></div></article></div><aside class="panel run-panel"><p class="eyebrow">Replay em ticks</p><h2>Release atual</h2><div class="segmented" id="replay-days"><button class="active" data-days="1">1D</button><button data-days="3">3D</button><button data-days="7">7D</button></div><button class="primary" id="run-replay" type="button">Executar replay</button><div class="run-status" id="run-status">Aguardando execução.</div></aside></div></section>
    <section class="tab-panel" data-panel="trigger" hidden><div class="table-wrap"><table><thead><tr><th>ID</th><th>Componente</th><th>Versão</th><th>Estado</th><th>Hipótese</th></tr></thead><tbody id="trigger-rows"></tbody></table></div></section>
    <section class="tab-panel" data-panel="context" hidden><div class="table-wrap"><table><thead><tr><th>ID</th><th>Componente</th><th>Estado</th><th>Hipótese</th></tr></thead><tbody id="context-rows"></tbody></table></div></section>
    <section class="tab-panel" data-panel="temporal" hidden><div class="table-wrap"><table><thead><tr><th>ID</th><th>Mês UTC</th><th>Estado</th><th>Política</th></tr></thead><tbody id="temporal-rows"></tbody></table></div></section>
    <section class="tab-panel" data-panel="router" hidden><div class="table-wrap"><table><thead><tr><th>ID</th><th>Roteador</th><th>Versão</th><th>Estado</th><th>Regra</th></tr></thead><tbody id="router-rows"></tbody></table></div></section>
    <section class="tab-panel" data-panel="experiments" hidden><div class="table-wrap"><table><thead><tr><th>Execução</th><th>Período</th><th>Release</th><th>Ticks</th><th>Sinais</th><th>Uso</th></tr></thead><tbody id="experiment-rows"><tr><td colspan="6" class="muted">Nenhum experimento registrado.</td></tr></tbody></table></div></section>"""
    script = """<script>
    const labels={empty:'Vazio',draft:'Rascunho',validating:'Em validação',validated:'Validado',frozen:'Congelado',retired:'Retirado'},months=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
    const badge=status=>`<span class="badge ${status}">${labels[status]||status}</span>`;
    function row(item,kind){const empty=item.status==='empty',name=empty?'Espaço disponível':item.name,hypothesis=empty?'Hipótese ainda não registrada':item.hypothesis;if(kind==='temporal')return `<tr><td><code>${item.id}</code></td><td>${months[item.month-1]}</td><td>${badge(item.status)}</td><td>${hypothesis}</td></tr>`;return `<tr><td><code>${item.id}</code></td><td>${name}</td>${kind==='context'?'':`<td>${item.version||'-'}</td>`}<td>${badge(item.status)}</td><td>${hypothesis}</td></tr>`}
    async function loadCatalog(){const response=await fetch('/api/strategies/catalog'),data=await response.json();for(const kind of ['trigger','context','temporal','router'])document.querySelector(`#${kind}-rows`).innerHTML=data.groups[kind].map(item=>row(item,kind)).join('')}
    async function loadExperiments(){const response=await fetch('/api/research/experiments'),runs=await response.json();if(!runs.length)return;document.querySelector('#experiment-rows').innerHTML=runs.map(run=>`<tr><td><code>${run.id}</code></td><td>${run.start}<br>${run.end}</td><td>${run.dataset_version}</td><td>${new Intl.NumberFormat('pt-BR').format(run.ticks_evaluated)}</td><td>${run.signal_count}</td><td>${run.split}</td></tr>`).join('')}
    function paintBacktest(data){const canvas=document.querySelector('#backtest-chart'),ctx=canvas.getContext('2d'),rect=canvas.getBoundingClientRect(),ratio=devicePixelRatio||1,w=rect.width,h=rect.height;canvas.width=w*ratio;canvas.height=h*ratio;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,w,h);const rows=data.equity||[];if(!rows.length)return;const values=rows.map(row=>row.equity),high=Math.max(...values),low=Math.min(...values),range=high-low||1,pad={l:58,r:18,t:18,b:30},x=i=>pad.l+i*(w-pad.l-pad.r)/Math.max(1,rows.length-1),y=value=>pad.t+(high-value)*(h-pad.t-pad.b)/range;ctx.strokeStyle='#263242';ctx.fillStyle='#8c9aae';ctx.font='11px system-ui';for(let i=0;i<5;i++){const value=low+range*i/4,yy=y(value);ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText(value.toFixed(0),6,yy+4)}ctx.strokeStyle='#43d398';ctx.lineWidth=2;ctx.beginPath();rows.forEach((row,index)=>index?ctx.lineTo(x(index),y(row.equity)):ctx.moveTo(x(index),y(row.equity)));ctx.stroke();ctx.fillStyle='#8c9aae';ctx.fillText(rows[0].day,pad.l,h-9);ctx.textAlign='right';ctx.fillText(rows.at(-1).day,w-pad.r,h-9);ctx.textAlign='left'}
    async function loadBacktest(days=1826){try{const response=await fetch(`/api/strategies/backtest?strategy_id=trigger.g01&days=${days}`),data=await response.json();if(!response.ok)throw new Error(data.detail||'Snapshot indisponível.');const summary=data.summary;paintBacktest(data);document.querySelector('#backtest-equity').textContent=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(data.equity.at(-1)?.equity||10000);document.querySelector('#backtest-trades').textContent=new Intl.NumberFormat('pt-BR').format(summary.trades_count||0);document.querySelector('#backtest-pf').textContent=Number(summary.profit_factor||0).toFixed(2);document.querySelector('#backtest-period').textContent=days===1826?'5 anos':days===2557?'7 anos':days===1095?'3 anos':'1 ano';document.querySelector('#backtest-status').textContent=`${data.period_start_utc.slice(0,10)} → ${data.period_end_utc.slice(0,10)} · fonte ${data.source_project} · ${data.source_file}`;}catch(error){document.querySelector('#backtest-status').textContent=error.message}}
    document.querySelector('.tabs').addEventListener('click',event=>{const button=event.target.closest('.tab');if(!button)return;document.querySelectorAll('.tab').forEach(item=>item.classList.toggle('active',item===button));document.querySelectorAll('.tab-panel').forEach(panel=>panel.hidden=panel.dataset.panel!==button.dataset.tab)});
    document.querySelector('#backtest-days').addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;document.querySelectorAll('#backtest-days button').forEach(item=>item.classList.toggle('active',item===button));loadBacktest(Number(button.dataset.days))});addEventListener('resize',()=>loadBacktest(Number(document.querySelector('#backtest-days .active').dataset.days)));
    let replayDays=1;document.querySelector('#replay-days').addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;replayDays=Number(button.dataset.days);document.querySelectorAll('#replay-days button').forEach(item=>item.classList.toggle('active',item===button))});
    document.querySelector('#run-replay').addEventListener('click',async()=>{const button=document.querySelector('#run-replay'),status=document.querySelector('#run-status');button.disabled=true;status.textContent='Processando ticks publicados...';try{const response=await fetch(`/api/research/replay?days=${replayDays}`,{method:'POST'}),data=await response.json();if(!response.ok)throw new Error(data.detail||'Falha no replay.');status.innerHTML=`<strong>${new Intl.NumberFormat('pt-BR').format(data.signal_count)} sinais</strong><br>${new Intl.NumberFormat('pt-BR').format(data.ticks_evaluated)} ticks · ${data.start} a ${data.end}`;loadExperiments();}catch(error){status.textContent=error.message}finally{button.disabled=false}});loadCatalog();loadExperiments();loadBacktest();
    </script>"""
    return page("Lotus | Estratégias", "strategies", content, script)


@app.get("/compare", response_class=HTMLResponse)
def comparison_page() -> HTMLResponse:
    return page("Lotus | Comparar estratégias", "comparison", "<header class=\"page-head\"><div><p class=\"eyebrow\">Pesquisa</p><h1>Comparar estratégias</h1><p class=\"lead\">As comparações aparecerão quando houver componentes pesquisados neste projeto.</p></div></header><section class=\"empty\"><div><strong>Sem pares para comparar</strong>A referência V1.0 é o único gatilho registrado até agora.</div></section>")


@app.get("/growth-simulator", response_class=HTMLResponse)
def simulator_page() -> HTMLResponse:
    content = """<header class="page-head"><div><p class="eyebrow">Ferramenta independente</p><h1>Simulador de crescimento</h1><p class="lead">Projete cenários manuais. Este simulador não utiliza resultados de estratégia.</p></div></header><section class="simulator"><form class="panel" id="simulator"><h2>Premissas</h2><label>Capital inicial<input name="initial" type="number" min="1" value="10000"></label><label>Retorno mensal (%)<input name="return" type="number" step="0.1" value="2"></label><label>Horizonte (meses)<input name="months" type="number" min="1" max="240" value="24"></label><button class="primary" type="submit">Atualizar cenário</button></form><section class="panel projection"><p class="eyebrow">Projeção composta</p><h2 id="final-balance">-</h2><div class="projection-grid"><article class="stat"><span>Capital inicial</span><strong id="initial-balance">-</strong></article><article class="stat"><span>Resultado projetado</span><strong id="net-result">-</strong></article><article class="stat"><span>Retorno acumulado</span><strong id="total-return">-</strong></article></div><p class="chart-status">Estimativa matemática. Não representa previsão, evidência de backtest ou autorização operacional.</p></section></section>"""
    script = """<script>const money=value=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(value);function calculate(event){event?.preventDefault();const data=new FormData(document.querySelector('#simulator')),initial=Number(data.get('initial')),monthly=Number(data.get('return'))/100,months=Number(data.get('months'));const final=initial*Math.pow(1+monthly,months),net=final-initial;document.querySelector('#final-balance').textContent=money(final);document.querySelector('#initial-balance').textContent=money(initial);document.querySelector('#net-result').textContent=money(net);document.querySelector('#total-return').textContent=((final/initial-1)*100).toFixed(1)+'%'}document.querySelector('#simulator').addEventListener('submit',calculate);calculate()</script>"""
    return page("Lotus | Simulador de crescimento", "simulator", content, script)


@app.get("/api/history/summary")
def history_summary() -> dict[str, object]:
    try:
        return history().summary()
    except DatasetError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/history/candles")
def history_candles(
    resolution: str = Query("5m"), days: int = Query(365, ge=1, le=2557)
) -> list[dict[str, float | int]]:
    try:
        return history().candles(resolution, days)
    except DatasetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/strategies/catalog")
def strategies_catalog() -> dict[str, object]:
    return catalog_payload()


@app.get("/api/strategies/backtest")
def strategy_backtest(strategy_id: str = Query("trigger.g01"), days: int = Query(1826)) -> dict[str, object]:
    try:
        return BacktestLibrary(BACKTEST_ROOT).read(strategy_id, days)
    except BacktestError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/research/replay")
def research_replay(days: int = Query(1, ge=1, le=7)) -> dict[str, object]:
    try:
        payload = replay_latest(history(), days).as_dict()
        return ExperimentStore(RESEARCH_ROOT).save(payload)
    except DatasetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/research/experiments")
def research_experiments() -> list[dict[str, object]]:
    return ExperimentStore(RESEARCH_ROOT).list()
