#!/usr/bin/env python3
"""
context-coverage renderer -> one self-contained, theme-aware, interactive HTML.

    python render.py coverage-data.json --out coverage-report.html

No invented composite scores. The report shows directly-measured numbers
(LOC, commit dates, context line counts, LOC-per-context-line, commits-since-
context) and turns them into a short list of specific things worth checking,
plus a per-repo folder tree comparing where the code is to where the context is.
"""
import argparse
import json
import os
import sys

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  color-scheme: light;
  --plane:#f9f9f7; --surface:#fcfcfb; --surface-2:#f3f2ee;
  --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
  --blue:#2a78d6; --blue-2:#1c5cab;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
}
@media (prefers-color-scheme: dark){ :root:where(:not([data-theme="light"])){
  color-scheme: dark;
  --plane:#0d0d0d; --surface:#1a1a19; --surface-2:#242422;
  --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --blue:#3987e5; --blue-2:#86b6ef;
}}
:root[data-theme="dark"]{
  color-scheme: dark;
  --plane:#0d0d0d; --surface:#1a1a19; --surface-2:#242422;
  --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --blue:#3987e5; --blue-2:#86b6ef;
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--plane);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5;-webkit-font-smoothing:antialiased;}
.wrap{max-width:1080px;margin:0 auto;padding:32px 24px 80px}
h1{font-size:26px;font-weight:680;letter-spacing:-.02em;margin:0 0 6px}
.sub{color:var(--ink-2);font-size:14px;margin:0;max-width:76ch}
.meta{color:var(--muted);font-size:12.5px;margin-top:6px}
.themebtn{position:fixed;top:14px;right:14px;z-index:10;background:var(--surface);border:1px solid var(--border);color:var(--ink-2);border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer;font-family:inherit}
section{margin-top:30px}
h2{font-size:12px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin:0 0 4px}
.h2sub{font-size:13.5px;color:var(--ink-2);margin:0 0 16px;max-width:78ch}
/* findings (collapsible one-liners) */
details.finding{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--muted);border-radius:11px;margin-bottom:9px;overflow:hidden}
details.finding.crit{border-left-color:var(--critical)}
details.finding.warn{border-left-color:var(--warning)}
details.finding>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;padding:12px 16px}
details.finding>summary::-webkit-details-marker{display:none}
details.finding>summary:hover{background:var(--surface-2)}
.finding .num{flex:none;width:24px;height:24px;border-radius:50%;background:var(--surface-2);color:var(--ink-2);font-weight:700;font-size:12.5px;display:flex;align-items:center;justify-content:center}
.finding .ft{flex:1;font-weight:620;font-size:14px}
.finding .ft .rn{color:var(--blue)}
.finding .chev{color:var(--muted);font-size:11px;transition:transform .15s}
details.finding[open] .chev{transform:rotate(90deg)}
.finding .fbody{padding:0 16px 14px 52px}
.finding .fd{font-size:13px;color:var(--ink-2)}
.finding .fk{font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin-top:8px}
.finding .metrics{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{font-size:11px;font-weight:600;background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:2px 8px;color:var(--ink-2);font-variant-numeric:tabular-nums}
.chip b{color:var(--ink)}
/* scope panel */
details.scope{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
details.scope>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:10px;padding:12px 16px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
details.scope>summary::-webkit-details-marker{display:none}
details.scope>summary .chev{transition:transform .15s}
details.scope[open]>summary .chev{transform:rotate(90deg)}
details.scope>summary .cnt{margin-left:auto;font-size:12px;font-weight:600;letter-spacing:0;text-transform:none;color:var(--ink-2)}
.scopebody{padding:2px 16px 16px}
.btn{font-family:inherit;font-size:11.5px;font-weight:600;border:1px solid var(--border);background:var(--surface);color:var(--ink-2);border-radius:7px;padding:5px 11px;cursor:pointer}
.btn:hover{border-color:var(--blue);color:var(--ink)}
.btn.primary{background:var(--blue);color:#fff;border-color:var(--blue)}
.scoptools{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:12px}
.scoptools .lbl{font-size:11.5px;color:var(--muted);margin-right:2px}
.scoplist{max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:9px;column-gap:0}
.scoprow{display:grid;grid-template-columns:22px 1fr auto auto;gap:10px;align-items:center;padding:6px 12px;border-bottom:1px solid var(--grid);font-size:12.5px;cursor:pointer}
.scoprow:last-child{border-bottom:none}
.scoprow:hover{background:var(--surface-2)}
.scoprow input{width:15px;height:15px;accent-color:var(--blue);cursor:pointer}
.scoprow .rnm{font-weight:560;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.scoprow.off .rnm{color:var(--muted)}
.scoprow .rmeta{font-size:11px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
/* repo panel (collapsible) */
details.repo{background:var(--surface);border:1px solid var(--border);border-radius:14px;margin-top:12px;overflow:hidden}
details.repo>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;padding:15px 20px;flex-wrap:wrap}
details.repo>summary::-webkit-details-marker{display:none}
details.repo>summary:hover{background:var(--surface-2)}
details.repo>summary .chev{color:var(--muted);font-size:11px;transition:transform .15s}
details.repo[open]>summary .chev{transform:rotate(90deg)}
.repobody{padding:0 20px 20px 20px}
.reponame{font-size:18px;font-weight:680}
.repohl{font-size:12.5px;color:var(--muted);margin-left:auto;text-align:right;font-variant-numeric:tabular-nums}
.repostat{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px}
.stat{background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:6px 10px;font-size:12px;color:var(--ink-2);font-variant-numeric:tabular-nums}
.stat .v{font-weight:700;color:var(--ink);font-size:14px}
.stat.bad .v{color:var(--critical)} .stat.warn .v{color:var(--warning)} .stat.ok .v{color:var(--good-ink,#0ca30c)}
.anchors{font-size:12px;color:var(--ink-2);margin:10px 0 4px}
.anchors code{background:var(--surface-2);padding:1px 5px;border-radius:4px;font-size:11.5px}
/* indented, collapsible tree */
.tree{margin-top:12px;font-variant-numeric:tabular-nums}
.tree details.tnode{margin:0}
.tree summary{list-style:none}
.tree summary::-webkit-details-marker{display:none}
.tree summary:hover .trow{background:var(--surface-2)}
.trow{display:grid;grid-template-columns:minmax(170px,1.4fr) 3fr auto;gap:12px;align-items:center;padding:3px 4px;font-size:12.5px;border-radius:5px}
.trow.clickable{cursor:pointer}
.tname{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center}
.tchev,.tchevspace{flex:none;display:inline-block;width:12px;font-size:9px;color:var(--muted);text-align:center}
.tchev{transition:transform .15s}
details.tnode[open]>summary .tchev{transform:rotate(90deg)}
.tname .dot{flex:none;display:inline-block;width:7px;height:7px;border-radius:2px;margin:0 7px;vertical-align:middle}
.tname .own{font-size:10px;font-weight:700;color:var(--blue);margin-left:6px}
.tbarwrap{background:var(--surface-2);border-radius:4px;height:16px;position:relative;overflow:hidden}
.tbar{height:100%;border-radius:4px}
.tbarloc{position:absolute;right:6px;top:0;line-height:16px;font-size:10.5px;color:var(--ink-2)}
.tgov{font-size:11px;color:var(--muted);white-space:nowrap;text-align:right}
.tgov b{color:var(--ink-2)}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;font-size:11.5px;color:var(--ink-2)}
.legend .k{display:inline-flex;align-items:center;gap:6px}
.sw{width:12px;height:12px;border-radius:3px;display:inline-block}
table.data{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums;margin-top:6px}
table.data th{text-align:right;padding:6px 8px;font-size:11px;font-weight:640;color:var(--ink-2);border-bottom:2px solid var(--border);white-space:normal;vertical-align:bottom;line-height:1.22;max-width:66px}
table.data th.l,table.data td.l{text-align:left;max-width:none}
table.data td{padding:6px 8px;text-align:right;border-bottom:1px solid var(--grid);white-space:nowrap}
table.data th.group{text-align:left;font-size:10px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);border-bottom:none;padding-bottom:2px;max-width:none;white-space:nowrap;vertical-align:bottom}
table.data th.gsep,table.data td.gsep{border-left:1px solid var(--border)}
table.data th.gsep,table.data td.gsep{padding-left:14px}
.tag{display:inline-block;padding:1px 7px;border-radius:20px;font-size:10.5px;font-weight:640;color:#fff}
.chartbox{width:100%;overflow-x:auto}
.tt{position:fixed;pointer-events:none;background:var(--ink);color:var(--plane);padding:8px 11px;border-radius:8px;font-size:12px;z-index:50;opacity:0;transition:opacity .1s;max-width:320px;box-shadow:0 6px 22px rgba(0,0,0,.3);line-height:1.45}
.tt b{color:var(--plane)}
.foot{color:var(--muted);font-size:12px;margin-top:30px;line-height:1.6}
code{background:var(--surface-2);padding:1px 5px;border-radius:4px;font-size:12px}
</style>
</head>
<body>
<button class="themebtn" id="themebtn">◐ theme</button>
<div class="wrap">
<header>
  <h1>Context Coverage Report</h1>
  <p class="sub">Directly-measured signals on how agent context (CLAUDE.md · AGENTS.md · rules · skills) lines up with the code in each repo — no invented scores. It surfaces a short list of things worth a look, then shows the numbers behind them.</p>
  <p class="meta" id="metaline"></p>
</header>
<div id="app"></div>
<div class="foot" id="foot"></div>
</div>
<div class="tt" id="tt"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DOC=JSON.parse(document.getElementById('data').textContent);
const R=DOC.repos, M=DOC.model, SRC=DOC.source, PB=M.problem, STALE=M.stale_commits_since;
const css=k=>getComputedStyle(document.documentElement).getPropertyValue(k).trim();
const fmt=n=>n==null?'—':n.toLocaleString();
const kloc=n=>n==null?'—':n>=1e6?(n/1e6).toFixed(1)+'M':n>=1000?Math.round(n/1000)+'k':(''+n);
const el=(t,a={},kids=[])=>{const e=document.createElement(t);
  for(const k in a){if(k==='class')e.className=a[k];else if(k==='html')e.innerHTML=a[k];else if(k.slice(0,2)==='on')e[k]=a[k];else e.setAttribute(k,a[k]);}
  (Array.isArray(kids)?kids:[kids]).forEach(c=>c!=null&&c!==false&&e.append(c.nodeType?c:document.createTextNode(c)));return e;};
const est=r=>r.loc_is_estimate?'*':'';
const anyEst=R.some(r=>r.loc_is_estimate);

const tt=document.getElementById('tt');
function hover(node,html){node.style.cursor='default';
  node.addEventListener('mousemove',e=>{tt.innerHTML=typeof html==='function'?html():html;tt.style.opacity=1;
    let nx=e.clientX+14,ny=e.clientY+14;const w=tt.offsetWidth,h=tt.offsetHeight;
    if(nx+w>innerWidth-8)nx=e.clientX-w-14;if(ny+h>innerHeight-8)ny=e.clientY-h-14;tt.style.left=nx+'px';tt.style.top=ny+'px';});
  node.addEventListener('mouseleave',()=>tt.style.opacity=0);}

// ---- scope: which repos are analyzed. Starts from the collector's in_scope;
// the reader can re-dial it (cutoff / self-select / exclude) and it persists.
const SKEY='ctxcov-scope:'+(SRC.mode==='local'?SRC.path:SRC.org);
let SCOPE=new Set();
(function(){let saved=null;try{saved=JSON.parse(localStorage.getItem(SKEY)||'null');}catch(e){}
  if(Array.isArray(saved)&&saved.length)saved.forEach(n=>SCOPE.add(n));
  else R.filter(r=>r.in_scope).forEach(r=>SCOPE.add(r.name));})();
function saveScope(){try{localStorage.setItem(SKEY,JSON.stringify([...SCOPE]));}catch(e){}}
let scoped=[];
function recomputeScope(){scoped=R.filter(r=>SCOPE.has(r.name));}
document.getElementById('metaline').textContent=
  `Generated ${DOC.generated_at} · ${SRC.mode==='local'?('local: '+SRC.path):('org: '+SRC.org+' (via gh)')} · ${R.length} repositories scanned`;

// ---- governance: for a repo's dir tree, find nearest governing context ----
function annotate(repo){
  const anchors=(repo.context_anchors||[]);
  const govFor=dir=>{let best=null,bd=-1;for(const a of anchors){const ad=a.dir||'';
    if(ad===''||dir===ad||dir.startsWith(ad+'/')){const d=ad===''?0:ad.split('/').length;if(d>bd){bd=d;best=a;}}}return best;};
  (function walk(n,path){n._path=path;n._gov=govFor(path);
    n._density=n._gov?Math.round(n.loc/Math.max(n._gov.lines,1)):null;
    n._own=anchors.some(a=>(a.dir||'')===path);
    (n.children||[]).forEach(c=>walk(c,path?path+'/'+c.name:c.name));})(repo.dir_tree,'');
  return repo.dir_tree;
}
function govStatus(n){if(n._own)return'good';if(!n._gov)return'none';
  if(n._density>PB.loc_per_ctxline_bad)return'bad';if(n._density>PB.loc_per_ctxline_warn)return'warn';return'good';}
const statusCol=s=>s==='good'?css('--good'):s==='warn'?css('--warning'):s==='bad'?css('--serious'):css('--critical');
const freshColor=f=>f==='fresh'?css('--good'):f==='none'?css('--critical'):f==='stale'?css('--serious'):css('--muted');

// ============================ FINDINGS ============================
function computeFindings(){
  const F=[];
  scoped.forEach(r=>{
    const nm=r.name;
    // no context at all
    if(!r.has_context){
      F.push({repo:nm,sev:'crit',kind:'No agent context',mag:r.loc||0,
        title:`<span class="rn">${nm}</span> has no CLAUDE.md, AGENTS.md, or rules`,
        detail:`${fmt(r.loc)}${est(r)} lines of code and nothing to orient an agent that opens it.`,
        chips:[['LOC',kloc(r.loc)+est(r)],['context lines','0'],['skills',r.skills_count||0]]});
      return;
    }
    // stale: commits since context edited
    if((r.commits_since_context||0)>=STALE){
      F.push({repo:nm,sev:'warn',kind:'Context may be behind the code',mag:r.commits_since_context,
        title:`<span class="rn">${nm}</span>: ${r.commits_since_context} commits since its context was last edited`,
        detail:`Newest context file last changed ${Math.round(r.context_last_updated_days)}d ago; ${r.commits_since_context} commits have landed on the default branch since. Worth a glance to see if it drifted.`,
        chips:[['context edited',Math.round(r.context_last_updated_days)+'d ago'],['commits since',r.commits_since_context],['LOC',kloc(r.loc)+est(r)]]});
    }
    // thin whole-repo context relative to code size
    if(r.loc>=PB.dense_loc && r.loc_per_context_line!=null && r.loc_per_context_line>PB.loc_per_ctxline_bad){
      const layered=r.has_nested_or_rules;
      F.push({repo:nm,sev:'warn',kind:'Thin context for the codebase',mag:r.loc||0,
        title:`<span class="rn">${nm}</span>: ${kloc(r.loc)}${est(r)} LOC covered by only ${r.total_context_lines} lines of context`,
        detail:layered
          ? `That's ${fmt(r.loc_per_context_line)} lines of code per line of context — an agent gets little guidance per unit of code. May be fine if the code is self-explanatory.`
          : `That's the whole context — a single root ${r.has_claude_md?'CLAUDE.md':'context file'}, no nested CLAUDE.md or /rules/ for any area. May be fine if the code is self-explanatory.`,
        chips:layered
          ? [['LOC',kloc(r.loc)+est(r)],['context lines',r.total_context_lines],['LOC / ctx-line',fmt(r.loc_per_context_line)]]
          : [['LOC',kloc(r.loc)+est(r)],['context lines',r.total_context_lines],['nested / rules','none']]});
    }
    // oversized single file
    (r.context_anchors||[]).forEach(a=>{if(a.kind!=='rules'&&a.lines>PB.oversized_claude_lines)
      F.push({repo:nm,sev:'warn',kind:'Long context file',mag:a.lines,
        title:`<span class="rn">${nm}</span>: <code>/${a.path}</code> is ${a.lines} lines`,
        detail:`Over ${PB.oversized_claude_lines} lines — long enough that an agent may not attend to all of it. Consider splitting into nested per-area files.`,
        chips:[['file length',a.lines+' lines'],['repo LOC',kloc(r.loc)+est(r)]]});});
    // single root file governing a large multi-folder repo
    if(r.loc>=10000 && !r.nested_claude_count && !r.has_rules){
      annotate(r);const kids=(r.dir_tree.children||[]).filter(c=>c.loc>=PB.dense_loc);
      if(kids.length>=2)F.push({repo:nm,sev:'warn',kind:'No per-area context',mag:r.loc||0,
        title:`<span class="rn">${nm}</span>: ${kids.length} large folders, all under one root context file`,
        detail:`Folders like ${kids.slice(0,3).map(k=>'/'+k.name).join(', ')} each carry thousands of LOC but there's no nested CLAUDE.md or /rules/ for any of them.`,
        chips:[['large folders',kids.length],['nested context','0'],['root ctx lines',r.total_context_lines]]});
    }
    // skills but no root CLAUDE.md
    if((r.skills_count||0)>=3 && !r.has_claude_md){
      F.push({repo:nm,sev:'warn',kind:'Skills without a front door',mag:r.skills_count,
        title:`<span class="rn">${nm}</span>: ${r.skills_count} skills but no root CLAUDE.md`,
        detail:`Plenty of skills, but nothing at the repo root to orient an agent to them.`,
        chips:[['skills',r.skills_count],['root CLAUDE.md','none']]});
    }
  });
  const rank={crit:0,warn:1}; F.sort((a,b)=>(rank[a.sev]-rank[b.sev])||b.mag-a.mag);
  return F;
}

function buildFindings(F){
  const s=el('section');
  s.append(el('h2',{},`Things to check — ${F.length}`));
  s.append(el('p',{class:'h2sub'},'Specific places where the context and the code look out of step. Each is a prompt to look, not a verdict — some will be perfectly reasonable once you check. Ordered most-pressing first.'));
  if(!F.length){s.append(el('div',{class:'finding'},el('div',{class:'fbody'},'Nothing stood out across the analyzed repos.')));mount.append(s);return;}
  F.slice(0,10).forEach((f,i)=>{
    const d=el('details',{class:'finding '+(f.sev==='crit'?'crit':'warn')});
    const sm=el('summary');
    sm.append(el('span',{class:'num'},''+(i+1)));
    sm.append(el('span',{class:'ft',html:f.title}));
    sm.append(el('span',{class:'chev'},'▸'));
    d.append(sm);
    const b=el('div',{class:'fbody'});
    b.append(el('div',{class:'fd'},f.detail));
    const m=el('div',{class:'metrics'});
    (f.chips||[]).forEach(([k,v])=>m.append(el('span',{class:'chip',html:`${k} <b>${v}</b>`})));
    b.append(m);
    b.append(el('div',{class:'fk'},f.kind));
    d.append(b);s.append(d);
  });
  if(F.length>10)s.append(el('p',{class:'meta'},`+${F.length-10} more — see the per-repo detail below.`));
  mount.append(s);
}

// ============================ PER-REPO PANELS ============================
function buildRepos(){
  const s=el('section');
  s.append(el('h2',{},'Per-repo detail'));
  s.append(el('p',{class:'h2sub'},'For each repo: the raw numbers, where its context files live, and a folder map — every directory sized by its lines of code and colored by whether a context file actually governs it, and how thinly.'));
  scoped.slice().sort((a,b)=>(b.loc||0)-(a.loc||0)).forEach(r=>s.append(repoPanel(r)));
  mount.append(s);
}
function repoPanel(r){
  annotate(r);
  const p=el('details',{class:'repo'});
  const sm=el('summary');
  sm.append(el('span',{class:'chev'},'▸'));
  sm.append(el('span',{class:'reponame'},r.name));
  const fresh=r.freshness;
  const ftag=el('span',{class:'tag'},fresh==='fresh'?'context fresh':fresh==='stale'?'context stale':fresh==='none'?'no context':'freshness unknown');
  ftag.style.background=freshColor(fresh);
  sm.append(ftag);
  sm.append(el('span',{class:'repohl'},`${kloc(r.loc)}${est(r)} LOC · ${fmt(r.total_context_lines)} context lines`+((r.has_nested_or_rules&&r.loc_per_context_line!=null)?` · ${fmt(r.loc_per_context_line)} LOC/ctx-line`:'')));
  p.append(sm);
  const body=el('div',{class:'repobody'});
  // stat strip
  const stats=el('div',{class:'repostat'});
  const stat=(label,val,cls='')=>el('div',{class:'stat '+cls},[el('span',{class:'v'},val+' '),document.createTextNode(label)]);
  stats.append(stat('LOC'+est(r),kloc(r.loc)));
  stats.append(stat('code files',fmt(r.code_file_count)));
  stats.append(stat('commits/90d',r.commits_recent==null?'—':r.commits_recent));
  stats.append(stat('last commit',r.last_commit_days!=null?Math.round(r.last_commit_days)+'d':'—'));
  stats.append(stat('CLAUDE.md',(r.has_claude_md?r.claude_md_lines+' ln':'none')+(r.nested_claude_count?` +${r.nested_claude_count} nested`:''),r.has_claude_md?'':'bad'));
  stats.append(stat('context lines',fmt(r.total_context_lines)));
  // LOC-per-context-line only means something when context is layered; with a
  // single root file it's just total-LOC / root-file-length.
  if(r.has_nested_or_rules && r.loc_per_context_line!=null){const dens=r.loc_per_context_line;
    stats.append(stat('LOC / ctx-line',fmt(dens),dens>PB.loc_per_ctxline_bad?'bad':dens>PB.loc_per_ctxline_warn?'warn':'ok'));}
  stats.append(stat('skills',r.skills_count||0));
  if(r.commits_since_context!=null)stats.append(stat('commits since ctx',r.commits_since_context,r.commits_since_context>=STALE?'warn':'ok'));
  body.append(stats);
  // anchors
  const anchors=(r.context_anchors||[]);
  body.append(el('div',{class:'anchors',html:anchors.length
    ? 'Context files: '+anchors.map(a=>`<code>/${a.path}</code>${a.kind==='rules'?' (rules)':' ('+a.lines+' ln)'}`).join(' · ')
    : '<b>No context files.</b>'}));
  // tree
  if((r.dir_tree.children||[]).length){body.append(tree(r));
    const leg=el('div',{class:'legend'});
    [['--good','well-governed / own context'],['--warning',`sparse (>${PB.loc_per_ctxline_warn} LOC/line)`],['--serious',`very sparse (>${PB.loc_per_ctxline_bad})`],['--critical','no governing context']].forEach(([c,l])=>{
      const sw=el('span',{class:'sw'});sw.style.background=css(c);leg.append(el('span',{class:'k'},[sw,l]));});
    body.append(leg);}
  p.append(body);
  return p;
}
// indented, collapsible folder tree with inline LOC bars (max 2 levels deep)
function tree(r){
  const root=r.dir_tree, maxLoc=root.loc||1, MAXD=2;
  const box=el('div',{class:'tree'});
  function rowEl(n,depth,collapsible){
    const st=govStatus(n);
    const row=el('div',{class:'trow'+(collapsible?' clickable':'')});
    const name=el('div',{class:'tname'});name.style.paddingLeft=((depth-1)*18)+'px';
    name.append(el('span',{class:collapsible?'tchev':'tchevspace'},collapsible?'▸':''));
    const dot=el('span',{class:'dot'});dot.style.background=statusCol(st);name.append(dot);
    name.append(document.createTextNode(n.name));
    if(n._own)name.append(el('span',{class:'own'},'★ own'));
    row.append(name);
    const bw=el('div',{class:'tbarwrap'});const bar=el('div',{class:'tbar'});
    bar.style.width=Math.max(1.5,100*n.loc/maxLoc)+'%';bar.style.background=statusCol(st);bar.style.opacity=depth>1?.7:1;
    bw.append(bar);bw.append(el('div',{class:'tbarloc'},kloc(n.loc)+est(r)));row.append(bw);
    const showDens=r.has_nested_or_rules;  // ratio only meaningful with layered context
    row.append(el('div',{class:'tgov',html:n._own?'has its own context':n._gov?`gov: <b>/${n._gov.dir||'root'}</b>${showDens?` · ${fmt(n._density)}/ln`:''}`:'<b>uncovered</b>'}));
    hover(row,()=>`<b>/${n._path}</b><br>${kloc(n.loc)}${est(r)} LOC<br>${n._own?'has its own context file':n._gov?`nearest context: /${n._gov.dir||'root'} (${n._gov.lines}-line ${n._gov.kind}) — ${fmt(n._density)} LOC per context line`:'no governing context file'}`);
    return row;
  }
  function node(n,depth){
    const kids=(n.children||[]).filter(c=>c.loc>0).sort((a,b)=>b.loc-a.loc);
    if(kids.length && depth<MAXD){
      const d=el('details',{class:'tnode'});
      const sm=el('summary');sm.append(rowEl(n,depth,true));d.append(sm);
      kids.forEach(c=>d.append(node(c,depth+1)));
      return d;
    }
    return rowEl(n,depth,false);
  }
  (root.children||[]).filter(c=>c.loc>0).sort((a,b)=>b.loc-a.loc).forEach(c=>box.append(node(c,1)));
  return box;
}

// ============================ RAW TABLE (grouped) ============================
function buildTable(){
  const s=el('section');
  s.append(el('h2',{},'The numbers'));
  s.append(el('p',{class:'h2sub'},'Everything measured, grouped: the code, the context that covers it, and how fresh that context is. All directly counted (org-mode LOC is a byte-based estimate).'));
  function freshTag(r){const t=el('span',{class:'tag'},r.freshness);t.style.background=freshColor(r.freshness);return t;}
  // [key, label, align, accessor]
  const groups=[
    ['', [['name','Repo','l',r=>r.name]]],
    ['The code', [
      ['loc','Lines of code','',r=>kloc(r.loc)+est(r)],
      ['code_file_count','Code files','',r=>fmt(r.code_file_count)],
      ['commits_recent','Commits (90d)','',r=>r.commits_recent==null?'—':r.commits_recent],
      ['last_commit_days','Last commit','',r=>r.last_commit_days!=null?Math.round(r.last_commit_days)+'d ago':'—']]],
    ['The context', [
      ['claude_md_lines','CLAUDE.md lines','',r=>r.has_claude_md?r.claude_md_lines:'none'],
      ['nested_claude_count','Nested files','',r=>r.nested_claude_count||0],
      ['has_rules','Has /rules/','',r=>r.has_rules?'yes':'—'],
      ['skills_count','Skills','',r=>r.skills_count||0],
      ['total_context_lines','Total context lines','',r=>r.total_context_lines||0],
      ['loc_per_context_line','LOC per context line','',r=>(r.has_nested_or_rules&&r.loc_per_context_line!=null)?fmt(r.loc_per_context_line):'—']]],
    ['Freshness', [
      ['context_last_updated_days','Context last edited','',r=>r.context_last_updated_days!=null?Math.round(r.context_last_updated_days)+'d ago':'—'],
      ['commits_since_context','Commits since edit','',r=>r.commits_since_context==null?'—':r.commits_since_context],
      ['freshness','Status','l',r=>freshTag(r)]]],
  ];
  const tbl=el('table',{class:'data'});
  // group header row
  const gr=el('tr',{class:'grouprow'});
  groups.forEach(([label,cols],gi)=>{const th=el('th',{class:'group'+(gi>0?' gsep':''),colspan:cols.length});th.textContent=label;gr.append(th);});
  tbl.append(gr);
  // column header row
  const hr=el('tr');
  groups.forEach(([label,cols],gi)=>cols.forEach((c,ci)=>hr.append(el('th',{class:c[2]+(ci===0&&gi>0?' gsep':'')},c[1]))));
  tbl.append(hr);
  // body
  const flat=groups.flatMap(([label,cols],gi)=>cols.map((c,ci)=>[c,ci===0&&gi>0]));
  scoped.slice().sort((a,b)=>(b.loc||0)-(a.loc||0)).forEach(r=>{const tr=document.createElement('tr');
    flat.forEach(([c,sep])=>{const v=c[3](r);const td=el('td',{class:c[2]+(sep?' gsep':'')});if(v&&v.nodeType)td.append(v);else td.textContent=v;tr.append(td);});tbl.append(tr);});
  const box=el('div',{class:'chartbox'});box.append(tbl);s.append(box);mount.append(s);
}

// ============================ SCOPE PANEL ============================
// Built ONCE and never re-created, so toggling a checkbox never collapses it.
// Checkbox changes update SCOPE + the count and re-render only the report below;
// cutoff/reset redraw the checkbox list in place (the <details> stays open).
let updateScopeCount=()=>{};
function buildScope(){
  if(R.length<=1)return; // nothing to pick from (e.g. a single hand-selected repo)
  const panel=el('details',{class:'scope',open:''});
  const cnt=el('span',{class:'cnt'});
  panel.append(el('summary',{},[el('span',{class:'chev'},'▸'),document.createTextNode('Which repos to analyze'),cnt]));
  const body=el('div',{class:'scopebody'});
  const setSel=names=>{SCOPE=new Set(names);saveScope();drawList();updateScopeCount();renderReport();};
  const tools=el('div',{class:'scoptools'});
  tools.append(el('span',{class:'lbl'},'Committed within:'));
  [['30d',30],['90d',90],['6mo',180],['1yr',365],['any',0]].forEach(([l,d])=>
    tools.append(el('button',{class:'btn',onclick:()=>setSel(R.filter(r=>!r.looks_throwaway&&r.last_commit_days!=null&&(d<=0||r.last_commit_days<=d)).map(r=>r.name))},l)));
  tools.append(el('span',{style:'flex:1'}));
  tools.append(el('button',{class:'btn',onclick:()=>setSel(R.filter(r=>r.in_scope).map(r=>r.name))},'Reset to default'));
  tools.append(el('button',{class:'btn primary',onclick:exportScope},'⭳ Export selection'));
  body.append(tools);
  const list=el('div',{class:'scoplist'});body.append(list);
  panel.append(body);app.append(panel);
  updateScopeCount=()=>{cnt.textContent=`${R.filter(r=>SCOPE.has(r.name)).length} of ${R.length} selected`;};
  function drawList(){
    list.textContent='';
    R.slice().sort((a,b)=>(a.last_commit_days??1e9)-(b.last_commit_days??1e9)).forEach(r=>{
      const row=el('div',{class:'scoprow'+(SCOPE.has(r.name)?'':' off')});
      const cb=el('input',{type:'checkbox'});cb.checked=SCOPE.has(r.name);
      const flip=()=>{if(cb.checked)SCOPE.add(r.name);else SCOPE.delete(r.name);
        row.classList.toggle('off',!cb.checked);saveScope();updateScopeCount();renderReport();};
      cb.addEventListener('change',flip);
      row.addEventListener('click',e=>{if(e.target!==cb){cb.checked=!cb.checked;flip();}});
      row.append(cb,el('span',{class:'rnm'},r.name),
        el('span',{class:'rmeta'},r.last_commit_days!=null?Math.round(r.last_commit_days)+'d ago':'no commits'),
        el('span',{class:'rmeta'},kloc(r.loc)+est(r)+' LOC'));
      list.append(row);
    });
  }
  drawList();updateScopeCount();
}
function exportScope(){
  const names=[...SCOPE].sort();
  const txt=`# Re-run the scan on exactly this selection:\n`+
    `#   collect.py --org ${SRC.mode==='org'?SRC.org:'<org>'} --repos "${names.join(',')}"\n`+
    `# or as an overrides file (include forces a repo in regardless of the cutoff):\n`+
    JSON.stringify({include:names,exclude:[]},null,2)+'\n';
  const a=el('a',{href:URL.createObjectURL(new Blob([txt],{type:'text/plain'})),download:'scope-selection.txt'});
  document.body.append(a);a.click();a.remove();
}

const app=document.getElementById('app');
let mount, reportEl;
// re-renders ONLY the report sections (below the persistent scope panel)
function renderReport(){
  recomputeScope();
  reportEl.textContent='';
  mount=reportEl;
  if(!scoped.length){reportEl.append(el('section',{},el('p',{class:'h2sub'},'No repos selected — pick some in the panel above.')));return;}
  buildTable();buildFindings(computeFindings());buildRepos();
}
(function init(){
  app.textContent='';
  buildScope();                       // built once; persists across report re-renders
  reportEl=el('div');app.append(reportEl);
  renderReport();
})();
document.getElementById('foot').innerHTML=
  `<b>How each signal is measured.</b> <b>LOC</b> — lines in code files (vendored dirs pruned; org mode estimates from blob bytes${anyEst?', shown with * — use <code>--clone</code> for exact':''}). `+
  `<b>Context lines</b> — actual line counts of every CLAUDE.md / AGENTS.md / rules file. <b>LOC / ctx-line</b> — LOC ÷ context lines. `+
  `<b>Commits since context</b> — commits to the default branch since the newest context file was last edited (git history). <b>Stale</b> flags ≥ ${STALE} such commits. `+
  `A folder is flagged when it exceeds ${PB.loc_per_ctxline_bad} LOC per line of its nearest governing context. Thresholds live in <code>collect.py</code>; nothing here is a blended score.`;

document.getElementById('themebtn').addEventListener('click',()=>{const cur=document.documentElement.getAttribute('data-theme');
  const dark=cur?cur==='dark':matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.setAttribute('data-theme',dark?'light':'dark');
  renderReport();});  // scope panel is CSS-var based, so it recolors itself
</script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default="coverage-report.html")
    ap.add_argument("--title", default="Context Coverage Report")
    args = ap.parse_args()
    with open(args.data, encoding="utf-8") as f:
        doc = json.load(f)
    data_json = json.dumps(doc, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    html = HTML.replace("__DATA__", data_json).replace("__TITLE__", args.title)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {args.out} ({len(doc.get('repos', []))} repos, {os.path.getsize(args.out)//1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
