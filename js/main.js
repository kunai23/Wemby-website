/* =============================================
   WEMBANYAMA — L'Extraterrestre
   main.js — Particle cosmos, tabs, data rendering
   ============================================= */

/* ── Cosmos particle background ── */
(function () {
  const canvas = document.getElementById('cosmos');
  const ctx = canvas.getContext('2d');
  let W, H, stars = [], nebula = [];

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function initStars() {
    stars = [];
    for (let i = 0; i < 220; i++) {
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() * 1.4 + 0.2,
        a: Math.random(),
        speed: Math.random() * 0.003 + 0.001,
        phase: Math.random() * Math.PI * 2,
      });
    }
    nebula = [];
    for (let i = 0; i < 6; i++) {
      nebula.push({
        x: Math.random() * W,
        y: Math.random() * H * 0.7,
        r: Math.random() * 300 + 150,
        hue: Math.random() > 0.5 ? 270 : 190,
        a: Math.random() * 0.04 + 0.01,
      });
    }
  }

  function draw(t) {
    ctx.clearRect(0, 0, W, H);

    nebula.forEach(n => {
      const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r);
      g.addColorStop(0, `hsla(${n.hue}, 80%, 50%, ${n.a})`);
      g.addColorStop(1, `hsla(${n.hue}, 80%, 50%, 0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fill();
    });

    stars.forEach(s => {
      const alpha = 0.3 + Math.sin(t * s.speed + s.phase) * 0.3 + 0.2;
      ctx.globalAlpha = Math.min(1, alpha);
      ctx.fillStyle = '#c8b8ff';
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    });

    ctx.globalAlpha = 1;
    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', () => { resize(); initStars(); });
  resize();
  initStars();
  requestAnimationFrame(draw);
})();

/* ── Tab system ── */
(function () {
  const btns = document.querySelectorAll('.tab-btn');
  const sections = document.querySelectorAll('.tab-section');
  const ink = document.getElementById('tab-ink');

  function moveInk(btn) {
    const nav = document.querySelector('.tab-nav-inner');
    const navRect = nav.getBoundingClientRect();
    const btnRect = btn.getBoundingClientRect();
    ink.style.left  = (btnRect.left - navRect.left) + 'px';
    ink.style.width = btnRect.width + 'px';
  }

  function switchTab(name) {
    btns.forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    sections.forEach(s => s.classList.toggle('active', s.id === 'tab-' + name));
    const activeBtn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
    if (activeBtn) moveInk(activeBtn);
    if (name === 'resultats' && !window._resultsInited) initResults();
    if (name === 'playoffs') renderPlayoffs();
  }

  btns.forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));

  window.addEventListener('load', () => {
    const activeBtn = document.querySelector('.tab-btn.active');
    if (activeBtn) moveInk(activeBtn);
  });
  window.addEventListener('resize', () => {
    const activeBtn = document.querySelector('.tab-btn.active');
    if (activeBtn) moveInk(activeBtn);
  });
})();

/* ── Reveal on scroll ── */
(function () {
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
  }, { threshold: 0.15 });
  document.querySelectorAll('.reveal').forEach(el => obs.observe(el));
})();

/* ── Data loading & rendering ── */
let DATA = null;
let currentSeason = '2025-26';
let currentFilter = 'ALL';
let currentSearch = '';
let sortKey = 'date';
let sortDir = -1; // -1 = desc

async function loadData() {
  try {
    const res = await fetch('data/wemby_stats.json?t=' + Date.now());
    DATA = await res.json();
    renderAll();
  } catch (e) {
    console.error('Erreur chargement données:', e);
  }
}

function renderAll() {
  if (!DATA) return;
  renderHero();
  renderPalmares();
  renderRecords();
  renderCareerChart();
  renderRadarChart();
  renderCompareChart();
  updateLastUpdate();
}

function updateLastUpdate() {
  const el = document.getElementById('last-update');
  if (!el) return;
  const d = new Date(DATA.last_updated);
  el.textContent = d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

/* ── HERO STATS ── */
function renderHero() {
  // Toujours afficher la saison la plus récente avec des données NBA
  const nbaSeasons = DATA.career_averages.filter(s => s.league === 'NBA');
  const season = nbaSeasons.at(-1);
  if (!season) return;

  animateVal('hs-ppg', season.ppg);
  animateVal('hs-rpg', season.rpg);
  animateVal('hs-apg', season.apg);
  animateVal('hs-bpg', season.bpg);
  const el = document.getElementById('hs-fg');
  if (el) animateVal('hs-fg', season.fg_pct, '%');
  const rec = document.getElementById('hs-record');
  if (rec && season.wins !== undefined) {
    setTimeout(() => { rec.textContent = season.wins + '-' + season.losses; }, 600);
  }
}

function animateVal(id, target, suffix = '') {
  const el = document.getElementById(id);
  if (!el) return;
  const start = 0;
  const duration = 1200;
  const startTime = performance.now();
  function step(now) {
    const t = Math.min(1, (now - startTime) / duration);
    const ease = 1 - Math.pow(1 - t, 3);
    const cur = start + (target - start) * ease;
    el.textContent = (Number.isInteger(target) ? Math.round(cur) : cur.toFixed(1)) + suffix;
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* ── PALMARÈS ── */
function renderPalmares() {
  const grid = document.getElementById('palmares-grid');
  if (!grid || !DATA.palmares) return;

  const badgeMap = { NBA: 'nba', France: 'fr', Europe: 'eu', Draft: 'draft' };

  grid.innerHTML = DATA.palmares.map((p, i) => `
    <div class="palmares-card" style="animation-delay:${i * 0.07}s">
      <div class="pc-icon">${p.icon}</div>
      <div class="pc-body">
        <div class="pc-year">${p.year}</div>
        <div class="pc-title">${p.title}</div>
        <div class="pc-desc">${p.description}</div>
        <span class="pc-badge badge-${badgeMap[p.category] || 'nba'}">${p.category.toUpperCase()}</span>
      </div>
    </div>
  `).join('');
}

/* ── RECORDS ── */
function renderRecords() {
  const grid = document.getElementById('records-grid');
  if (!grid || !DATA.records) return;

  grid.innerHTML = DATA.records.map((r, i) => `
    <div class="record-card" style="animation-delay:${i * 0.06}s">
      <div>
        <div class="record-cat">${r.category}</div>
        <div class="record-val">${r.value}</div>
      </div>
      <div class="record-info">
        <div class="record-title">${r.title}</div>
        <div class="record-ctx">${r.context}</div>
      </div>
    </div>
  `).join('');
}

/* ── CAREER CHART ── */
function renderCareerChart() {
  const canvas = document.getElementById('careerChart');
  if (!canvas || !DATA.career_averages) return;
  const labels  = DATA.career_averages.map(s => s.season);
  const ppg     = DATA.career_averages.map(s => s.ppg);
  const rpg     = DATA.career_averages.map(s => s.rpg);
  const bpg     = DATA.career_averages.map(s => s.bpg);

  new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'PPG', data: ppg, borderColor: '#a855f7', backgroundColor: 'rgba(168,85,247,0.1)', tension: 0.4, fill: true, pointRadius: 5, pointBackgroundColor: '#a855f7' },
        { label: 'RPG', data: rpg, borderColor: '#00d4ff', backgroundColor: 'rgba(0,212,255,0.07)', tension: 0.4, fill: true, pointRadius: 5, pointBackgroundColor: '#00d4ff' },
        { label: 'BPG', data: bpg, borderColor: '#ffd700', backgroundColor: 'rgba(255,215,0,0.06)',  tension: 0.4, fill: true, pointRadius: 5, pointBackgroundColor: '#ffd700' },
      ],
    },
    options: chartDefaults({ yLabel: 'Statistiques' }),
  });
}

/* ── RADAR CHART ── */
function renderRadarChart() {
  const canvas = document.getElementById('radarChart');
  if (!canvas || !DATA.career_averages) return;
  const season = DATA.career_averages.find(s => s.season === '2025-26') || DATA.career_averages.at(-1);
  const norm = (v, max) => Math.min(10, (v / max) * 10);

  const actualValues = [season.ppg, season.rpg, season.apg, season.bpg, season.spg, season.fg_pct];
  const suffixes = ['', '', '', '', '', '%'];

  new Chart(canvas, {
    type: 'radar',
    data: {
      labels: [
        ['PTS', season.ppg.toFixed(1)],
        ['REB', season.rpg.toFixed(1)],
        ['AST', season.apg.toFixed(1)],
        ['BLK', season.bpg.toFixed(1)],
        ['STL', season.spg.toFixed(1)],
        ['FG%', season.fg_pct.toFixed(1) + '%'],
      ],
      datasets: [{
        label: '2025-26',
        data: [
          norm(season.ppg, 35),
          norm(season.rpg, 15),
          norm(season.apg, 8),
          norm(season.bpg, 5),
          norm(season.spg, 3),
          norm(season.fg_pct, 65),
        ],
        borderColor: '#a855f7',
        backgroundColor: 'rgba(168,85,247,0.15)',
        pointBackgroundColor: '#00d4ff',
        pointBorderColor: '#00d4ff',
        pointRadius: 5,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const val = actualValues[ctx.dataIndex];
              const suf = suffixes[ctx.dataIndex];
              return ' ' + val.toFixed(1) + suf + ' / match (saison 2025-26)';
            },
          },
          backgroundColor: 'rgba(12,6,30,0.95)',
          borderColor: 'rgba(110,50,220,0.4)',
          borderWidth: 1,
          titleColor: '#c8b8ff',
          bodyColor: '#d1d5db',
        },
      },
      scales: {
        r: {
          min: 0, max: 10,
          grid:       { color: 'rgba(255,255,255,0.08)' },
          angleLines: { color: 'rgba(255,255,255,0.08)' },
          ticks:      { display: false },
          pointLabels: {
            color: '#9ca3af',
            font: { family: 'Orbitron', size: 10 },
          },
        },
      },
    },
  });
}

/* ── COMPARE CHART ── */
function renderCompareChart() {
  const canvas = document.getElementById('compareChart');
  if (!canvas || !DATA.career_averages) return;
  const nbaSeason = DATA.career_averages.filter(s => s.league === 'NBA');
  const labels = nbaSeason.map(s => s.season);

  new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'PPG', data: nbaSeason.map(s => s.ppg), backgroundColor: 'rgba(168,85,247,0.7)', borderRadius: 6 },
        { label: 'RPG', data: nbaSeason.map(s => s.rpg), backgroundColor: 'rgba(0,212,255,0.7)',  borderRadius: 6 },
        { label: 'BPG', data: nbaSeason.map(s => s.bpg), backgroundColor: 'rgba(255,215,0,0.7)',  borderRadius: 6 },
        { label: 'APG', data: nbaSeason.map(s => s.apg), backgroundColor: 'rgba(34,197,94,0.7)',  borderRadius: 6 },
      ],
    },
    options: chartDefaults({ yLabel: 'Statistiques NBA' }),
  });
}

function chartDefaults({ yLabel = '' } = {}) {
  return {
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { labels: { color: '#9ca3af', font: { family: 'Inter', size: 11 }, boxWidth: 14 } },
      tooltip: {
        backgroundColor: 'rgba(12,6,30,0.95)',
        borderColor: 'rgba(110,50,220,0.4)',
        borderWidth: 1,
        titleColor: '#c8b8ff',
        bodyColor: '#d1d5db',
        titleFont: { family: 'Orbitron', size: 11 },
      },
    },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9ca3af', font: { family: 'Orbitron', size: 9 } } },
      y: {
        grid: { color: 'rgba(255,255,255,0.05)' },
        ticks: { color: '#9ca3af', font: { family: 'Inter', size: 10 } },
        title: { display: !!yLabel, text: yLabel, color: '#6b7280', font: { size: 10 } },
      },
    },
  };
}

/* ════════════════════════════════
   RÉSULTATS
════════════════════════════════ */
let _resultsInited = false;

function initResults() {
  if (_resultsInited) return;
  _resultsInited = true;
  window._resultsInited = true;

  document.querySelectorAll('.season-btn').forEach(b =>
    b.addEventListener('click', () => {
      document.querySelectorAll('.season-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      currentSeason = b.dataset.season;
      renderResults();
    })
  );

  document.querySelectorAll('.filter-btn').forEach(b =>
    b.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      currentFilter = b.dataset.filter;
      renderResults();
    })
  );

  document.getElementById('opp-search').addEventListener('input', e => {
    currentSearch = e.target.value.toLowerCase().trim();
    renderResults();
  });

  document.querySelectorAll('.results-table th[data-sort]').forEach(th =>
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (sortKey === key) sortDir = -sortDir;
      else { sortKey = key; sortDir = -1; }
      document.querySelectorAll('.results-table th').forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
      renderResults();
    })
  );

  if (DATA) renderResults();
}

function getFilteredGames() {
  if (!DATA || !DATA.game_logs) return [];
  const games = DATA.game_logs[currentSeason] || [];
  return games.filter(g => {
    if (currentFilter !== 'ALL' && g.wl !== currentFilter) return false;
    if (currentSearch && !g.opponent.toLowerCase().includes(currentSearch)) return false;
    return true;
  }).sort((a, b) => {
    let va, vb;
    if (sortKey === 'date') { va = new Date(a.date); vb = new Date(b.date); }
    else if (sortKey === 'wl') { va = a.wl; vb = b.wl; }
    else { va = a[sortKey] || 0; vb = b[sortKey] || 0; }
    if (va < vb) return sortDir;
    if (va > vb) return -sortDir;
    return 0;
  });
}

function fmtDate(str) {
  const d = new Date(str + 'T00:00:00');
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
}

function pct(made, att) {
  if (!att) return '—';
  return (made / att * 100).toFixed(0) + '%';
}

function renderResults() {
  if (!DATA) return;
  const games = getFilteredGames();
  const tbody = document.getElementById('results-tbody');

  const wins   = games.filter(g => g.wl === 'W').length;
  const losses = games.filter(g => g.wl === 'L').length;
  const avgPts = games.length ? (games.reduce((s, g) => s + g.pts, 0) / games.length).toFixed(1) : '—';
  const avgReb = games.length ? (games.reduce((s, g) => s + g.reb, 0) / games.length).toFixed(1) : '—';
  const avgBlk = games.length ? (games.reduce((s, g) => s + g.blk, 0) / games.length).toFixed(1) : '—';
  const allGamesCount = (DATA.game_logs[currentSeason] || []).length;

  document.getElementById('rs-gp').textContent = allGamesCount || '—';
  document.getElementById('rs-w').textContent  = wins;
  document.getElementById('rs-l').textContent  = losses;
  document.getElementById('rs-ppg').textContent = avgPts;
  document.getElementById('rs-rpg').textContent = avgReb;
  document.getElementById('rs-bpg').textContent = avgBlk;

  const allGames = DATA.game_logs[currentSeason] || [];
  if (!allGames.length) {
    const isNext = currentSeason === '2025-26';
    tbody.innerHTML = `<tr><td colspan="13" style="text-align:center;padding:48px">
      <div style="font-family:var(--font-display);font-size:12px;letter-spacing:2px;color:var(--purple-light);margin-bottom:10px">${isNext ? 'SAISON À VENIR' : 'AUCUNE DONNÉE'}</div>
      <div style="font-size:13px;color:var(--gray);max-width:400px;margin:0 auto;line-height:1.6">
        ${isNext
          ? 'La saison 2025-26 débute en <span style="color:var(--cyan)">octobre 2025</span>. Relance le script local dès les premiers matchs.'
          : 'Lance <span style="color:var(--cyan)">python scripts/fetch_local.py</span> depuis ton ordi pour charger les données.'}
      </div>
    </td></tr>`;
    return;
  }
  if (!games.length) {
    tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;padding:40px;color:#6b7280">Aucun match trouvé pour ce filtre</td></tr>';
    return;
  }

  tbody.innerHTML = games.map(g => {
    const fgPct  = pct(g.fg,  g.fga);
    const fg3Pct = pct(g.fg3, g.fg3a);
    const ftPct  = pct(g.ft,  g.fta);
    const ptsClass = g.pts >= 40 ? 'td-pts fire' : g.pts >= 30 ? 'td-pts hot' : 'td-pts';
    const blkClass = g.blk >= 5  ? 'td-blk elite' : 'td-blk';
    const pmClass  = (g.plus_minus || 0) >= 0 ? 'plus-pos' : 'plus-neg';
    const pmSign   = (g.plus_minus || 0) >= 0 ? '+' : '';
    const homeAway = g.home ? '' : '<span style="color:#6b7280;font-size:11px">@</span>';
    const score    = `${g.score_team}–${g.score_opp}`;

    return `<tr>
      <td>${fmtDate(g.date)}</td>
      <td>${homeAway} <strong style="color:#e0e0ff">${g.opponent}</strong></td>
      <td><span class="badge-${g.wl.toLowerCase()}">${g.wl}</span></td>
      <td style="color:#9ca3af;font-size:12px">${score}</td>
      <td><span class="${ptsClass}">${g.pts}</span></td>
      <td>${g.reb}</td>
      <td>${g.ast}</td>
      <td><span class="${blkClass}">${g.blk}</span></td>
      <td>${g.stl}</td>
      <td>${fgPct}</td>
      <td>${fg3Pct}</td>
      <td>${ftPct}</td>
      <td class="${pmClass}">${pmSign}${g.plus_minus || 0}</td>
    </tr>`;
  }).join('');
}

/* ════════════════════════════════
   PLAYOFFS BRACKET
════════════════════════════════ */
const TEAM_LOGOS = {
  OKC: 'okc', PHX: 'phx', LAL: 'lal', HOU: 'hou',
  SAS: 'sa',  POR: 'por', MIN: 'min', DEN: 'den',
  DET: 'det', ORL: 'orl', CLE: 'cle', TOR: 'tor',
  NYK: 'ny',  ATL: 'atl', PHI: 'phi', BOS: 'bos',
};
function teamLogo(abbr) {
  const id = TEAM_LOGOS[abbr];
  return id ? `<img class="bk-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/${id}.png" alt="${abbr}" loading="lazy">` : '';
}

const PLAYOFF_DATA = {
  west: {
    r1: [
      { t1: 'OKC', n1: 'Thunder',       s1: 4, t2: 'PHX', n2: 'Suns',          s2: 0, winner: 'OKC' },
      { t1: 'LAL', n1: 'Lakers',        s1: 4, t2: 'HOU', n2: 'Rockets',       s2: 2, winner: 'LAL' },
      { t1: 'SAS', n1: 'Spurs',         s1: 4, t2: 'POR', n2: 'Trail Blazers', s2: 1, winner: 'SAS' },
      { t1: 'MIN', n1: 'Timberwolves',  s1: 4, t2: 'DEN', n2: 'Nuggets',       s2: 2, winner: 'MIN' },
    ],
    r2: [
      { t1: 'OKC', n1: 'Thunder',      s1: 4, t2: 'LAL', n2: 'Lakers',        s2: 0, winner: 'OKC' },
      { t1: 'SAS', n1: 'Spurs',        s1: 4, t2: 'MIN', n2: 'Timberwolves',  s2: 2, winner: 'SAS' },
    ],
    cf: { t1: 'OKC', n1: 'Thunder', s1: 0, t2: 'SAS', n2: 'Spurs', s2: 0, winner: null, live: true },
  },
  east: {
    r1: [
      { t1: 'DET', n1: 'Pistons',   s1: 4, t2: 'ORL', n2: 'Magic',   s2: 3, winner: 'DET' },
      { t1: 'CLE', n1: 'Cavaliers', s1: 4, t2: 'TOR', n2: 'Raptors', s2: 3, winner: 'CLE' },
      { t1: 'NYK', n1: 'Knicks',    s1: 4, t2: 'ATL', n2: 'Hawks',   s2: 2, winner: 'NYK' },
      { t1: 'PHI', n1: '76ers',     s1: 4, t2: 'BOS', n2: 'Celtics', s2: 3, winner: 'PHI' },
    ],
    r2: [
      { t1: 'CLE', n1: 'Cavaliers', s1: 4, t2: 'DET', n2: 'Pistons', s2: 3, winner: 'CLE' },
      { t1: 'NYK', n1: 'Knicks',    s1: 4, t2: 'PHI', n2: '76ers',   s2: 0, winner: 'NYK' },
    ],
    cf: { t1: 'CLE', n1: 'Cavaliers', s1: 0, t2: 'NYK', n2: 'Knicks', s2: 0, winner: null, live: true },
  },
};

function _bkTeamRow(abbr, name, score, isWinner, done) {
  const wc = done ? (isWinner ? 'bk-w' : 'bk-l') : '';
  const spurs = abbr === 'SAS' ? ' bk-spurs' : '';
  const sc = done ? score : '–';
  return `<div class="bk-team ${wc}${spurs}">
    ${teamLogo(abbr)}
    <span class="bk-name">${name}</span>
    <span class="bk-score">${sc}</span>
  </div>`;
}

function _bkCard(m, extra) {
  const done = !!m.winner;
  const live = m.live && !done;
  const cls = live ? 'bk-live' : (done ? 'bk-done' : '');
  const badge = live
    ? `<div class="bk-badge"><span class="pulse-dot bk-pulse"></span>EN COURS</div>`
    : (done ? `<div class="bk-badge bk-result">${m.winner} wins ${Math.max(m.s1,m.s2)}-${Math.min(m.s1,m.s2)}</div>` : '');
  return `<div class="bk-card ${cls} ${extra||''}">
    ${_bkTeamRow(m.t1, m.n1, m.s1, m.winner === m.t1, done)}
    <div class="bk-sep"></div>
    ${_bkTeamRow(m.t2, m.n2, m.s2, m.winner === m.t2, done)}
    ${badge}
  </div>`;
}

function renderPlayoffs() {
  const el = document.getElementById('playoff-bracket');
  if (!el || el.dataset.init) return;
  el.dataset.init = '1';
  const P = PLAYOFF_DATA;

  const col = (matches, extra) => matches.map(m =>
    `<div class="bk-cell">${_bkCard(m, extra)}</div>`).join('');

  el.innerHTML = `
    <div class="bk-conf-headers">
      <span class="bk-conf-lbl">CONFÉRENCE OUEST</span>
      <span class="bk-conf-lbl bk-finals-lbl">FINALES NBA</span>
      <span class="bk-conf-lbl">CONFÉRENCE EST</span>
    </div>
    <div class="bk-scroll">
      <div class="bk-grid">
        <div class="bk-col" data-label="PREMIER TOUR">${col(P.west.r1)}</div>
        <div class="bk-col" data-label="DEMI-FINALES">${col(P.west.r2)}</div>
        <div class="bk-col" data-label="FINALE CONF.">${`<div class="bk-cell">${_bkCard(P.west.cf, 'bk-cf')}</div>`}</div>
        <div class="bk-col bk-finals-col" data-label="FINALES NBA">
          <div class="bk-cell">
            <div class="bk-finals-card">
              <div class="bk-finals-trophy">🏆</div>
              <div class="bk-finals-title">FINALES NBA</div>
              <div class="bk-finals-sub">À déterminer</div>
            </div>
          </div>
        </div>
        <div class="bk-col" data-label="FINALE CONF.">${`<div class="bk-cell">${_bkCard(P.east.cf, 'bk-cf')}</div>`}</div>
        <div class="bk-col" data-label="DEMI-FINALES">${col(P.east.r2)}</div>
        <div class="bk-col" data-label="PREMIER TOUR">${col(P.east.r1)}</div>
      </div>
    </div>
  `;
}

/* ── Boot ── */
window.addEventListener('DOMContentLoaded', () => {
  loadData();
});
