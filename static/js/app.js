// Star rating initializer (public feedback forms)
window.initStars = function() {
  document.querySelectorAll('.star-input').forEach(container => {
    const inputName = container.dataset.target;
    const hidden = container.querySelector('input[name="'+inputName+'"]');
    const stars = container.querySelectorAll('.bi');
    const set = (val) => {
      hidden.value = val;
      stars.forEach((s, idx) => {
        if (idx < val) { s.classList.remove('bi-star'); s.classList.add('bi-star-fill', 'text-warning'); }
        else { s.classList.add('bi-star'); s.classList.remove('bi-star-fill', 'text-warning'); }
      });
    };
    stars.forEach(star => star.addEventListener('click', () => set(parseInt(star.dataset.value))));
    set(parseInt(hidden.value || '0'));
  });
}

// Theme controls (gradient hue + intensity)
function initThemeControls(){
  const root = document.documentElement;
  const hueEl = document.getElementById('hueRange');
  const intEl = document.getElementById('intensityRange');
  if (!hueEl || !intEl) return;

  const savedHue = localStorage.getItem('theme.hue');
  const savedInt = localStorage.getItem('theme.intensity');
  if (savedHue) root.style.setProperty('--hue', savedHue);
  if (savedInt) root.style.setProperty('--intensity', savedInt);
  if (savedHue) hueEl.value = parseInt(savedHue, 10);
  if (savedInt) intEl.value = parseInt(String(savedInt).replace('%',''), 10);

  const apply = () => {
    const hue = hueEl.value;
    const intensity = intEl.value + '%';
    root.style.setProperty('--hue', hue);
    root.style.setProperty('--intensity', intensity);
    localStorage.setItem('theme.hue', hue);
    localStorage.setItem('theme.intensity', intensity);
  };
  hueEl.addEventListener('input', apply);
  intEl.addEventListener('input', apply);
}

// Charts: global defaults and subtle shadows/gradient fills
function initChartsDefaults(){
  if (!window.Chart) return;
  const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = '#111111';
  Chart.defaults.borderColor = 'rgba(0,0,0,0.12)';
  Chart.defaults.elements.line.tension = 0.35;
  Chart.defaults.elements.line.borderWidth = 2.5;
  Chart.defaults.elements.point.radius = 0;
  Chart.defaults.plugins.legend.labels.color = '#111111';
  // Set per-scale defaults (Chart.js v4)
  if (Chart.defaults.scales){
    Chart.defaults.scales.linear = Chart.defaults.scales.linear || {};
    Chart.defaults.scales.category = Chart.defaults.scales.category || {};
    Chart.defaults.scales.linear.grid = { color: 'rgba(0,0,0,0.12)' };
    Chart.defaults.scales.linear.ticks = { color: '#111111' };
    Chart.defaults.scales.category.grid = { color: 'rgba(0,0,0,0.08)' };
    Chart.defaults.scales.category.ticks = { color: '#111111' };
  }

  // Create gradient fill lazily per chart area
  const makeGradient = (ctx, area) => {
    const g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
    const a = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
    // if accent is hsl(...), convert to hsla with alpha
    const hsla = a.startsWith('hsl(') ? a.replace('hsl', 'hsla').replace(')', ', 0.35)') : 'rgba(255,255,255,0.35)';
    g.addColorStop(0, hsla);
    g.addColorStop(1, 'rgba(255,255,255,0.02)');
    return g;
  };

  // Plugin: apply drop shadow and gradient fills for line/area charts
  const luxPlugin = {
    id: 'lux-look',
    beforeDatasetsDraw(chart){
      const {ctx, chartArea} = chart;
      if (!chartArea) return;
      chart.data.datasets.forEach(ds => {
        if (chart.config.type === 'line' || ds.type === 'line'){
          if (!ds.borderColor) ds.borderColor = accent;
          if ((ds.fill === true || ds.fill === 'origin') && !ds.backgroundColor){
            ds.backgroundColor = makeGradient(ctx, chartArea);
          }
        }
      });
    },
    afterDatasetsDraw(chart){
      const {ctx} = chart;
      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,0.35)';
      ctx.shadowBlur = 12;
      ctx.shadowOffsetY = 4;
      ctx.restore();
    }
  };
  try { Chart.register(luxPlugin); } catch(e) { /* ignore double registration */ }
}

// Subtle float-in animation for cards
function animateCards(){
  const cards = document.querySelectorAll('.card');
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('float-in') });
  }, { threshold: 0.12 });
  cards.forEach(c => obs.observe(c));
}

// XP ring helper: ensure CSS var is set at load
function initXpRing(){
  document.querySelectorAll('.xp-ring[data-progress]')?.forEach(el => {
    const p = parseInt(el.getAttribute('data-progress') || '0', 10);
    el.style.setProperty('--p', p);
  });
}

// Theme toggle (light/dark) with persistence
function applyTheme(mode){
  const dark = (mode === 'dark');
  document.body.classList.toggle('theme-dark', dark);
  try { localStorage.setItem('theme.mode', dark ? 'dark' : 'light'); } catch(e){}
  const icon = document.getElementById('themeToggleIcon');
  if (icon){ icon.className = dark ? 'bi bi-sun-fill' : 'bi bi-moon-stars'; }
}

function initThemeToggle(){
  let mode = 'light';
  try { mode = localStorage.getItem('theme.mode') || 'light'; } catch(e){}
  applyTheme(mode);
  const btn = document.getElementById('themeToggle');
  if (btn){
    btn.addEventListener('click', () => {
      const next = document.body.classList.contains('theme-dark') ? 'light' : 'dark';
      applyTheme(next);
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Apply saved theme first
  initThemeToggle();
  // Color palette controls removed from UI
  initChartsDefaults();
  animateCards();
  initXpRing();
  const fab = null;
  const panel = null;

  // Button ripple
  document.body.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn');
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const circle = document.createElement('span');
    const size = Math.max(rect.width, rect.height);
    circle.style.width = circle.style.height = size + 'px';
    circle.style.left = (e.clientX - rect.left - size/2) + 'px';
    circle.style.top = (e.clientY - rect.top - size/2) + 'px';
    circle.className = 'ripple';
    btn.appendChild(circle);
    setTimeout(() => circle.remove(), 600);
  });
  // Draggable FAB
  if (fab){
    const savedPos = JSON.parse(localStorage.getItem('theme.fab.pos') || 'null');
    if (savedPos){
      fab.style.left = savedPos.x + 'px';
      fab.style.top = savedPos.y + 'px';
      fab.style.right = 'auto'; fab.style.bottom = 'auto';
    }
    let dragging = false, offsetX = 0, offsetY = 0;
    const onDown = (ev) => {
      dragging = true;
      const e = ev.touches ? ev.touches[0] : ev;
      const rect = fab.getBoundingClientRect();
      offsetX = e.clientX - rect.left;
      offsetY = e.clientY - rect.top;
      ev.preventDefault();
    };
    const onMove = (ev) => {
      if (!dragging) return;
      const e = ev.touches ? ev.touches[0] : ev;
      let x = e.clientX - offsetX;
      let y = e.clientY - offsetY;
      const vw = window.innerWidth, vh = window.innerHeight;
      const w = fab.offsetWidth, h = fab.offsetHeight;
      x = Math.max(8, Math.min(vw - w - 8, x));
      y = Math.max(8, Math.min(vh - h - 8, y));
      fab.style.left = x + 'px';
      fab.style.top = y + 'px';
      fab.style.right = 'auto'; fab.style.bottom = 'auto';
    };
    const onUp = () => {
      if (!dragging) return;
      dragging = false;
      const rect = fab.getBoundingClientRect();
      localStorage.setItem('theme.fab.pos', JSON.stringify({x: rect.left, y: rect.top}));
    };
    fab.addEventListener('mousedown', onDown);
    fab.addEventListener('touchstart', onDown, {passive:false});
    window.addEventListener('mousemove', onMove);
    window.addEventListener('touchmove', onMove, {passive:false});
    window.addEventListener('mouseup', onUp);
    window.addEventListener('touchend', onUp);
  }

  // Admin charts auto-refresh
  initAdminCharts();
});

// Admin dashboard live charts
function initAdminCharts(){
  const tipsEl = document.getElementById('tipsChart');
  const staffEl = document.getElementById('staffChart');
  if (!tipsEl || !staffEl || !window.Chart) return;

  let tipsChart = null;
  let staffChart = null;
  // Monthly view only (current vs previous)

  const money = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' });
  const fmtCents = (c) => money.format((c || 0) / 100);

  const getCard = (canvas) => canvas.closest('.chart-card') || canvas.parentElement;
  const setLoading = (canvas, on) => {
    const card = getCard(canvas);
    if (!card) return;
    card.style.position = 'relative';
    let overlay = card.querySelector('.chart-loading');
    if (on){
      if (!overlay){
        overlay = document.createElement('div');
        overlay.className = 'chart-loading skeleton';
        overlay.style.position = 'absolute';
        overlay.style.inset = '12px 12px 28px 12px';
        overlay.style.borderRadius = '12px';
        card.appendChild(overlay);
      }
    } else if (overlay){
      overlay.remove();
    }
  };

  const buildOrUpdate = (payload) => {
    const labels = payload.daily_labels || [];
    const current = (payload.daily_current || []);
    const previous = (payload.daily_previous || []);
    const staff_labels = payload.staff_labels || [];
    const staff_totals = (payload.staff_totals || []);

    if (tipsChart){ tipsChart.destroy(); tipsChart = null; }
    tipsChart = new Chart(tipsEl, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Mes actual',
            data: current,
            borderColor: 'rgba(255,140,64,1)',
            backgroundColor: 'rgba(255,140,64,0.25)',
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 5,
            borderWidth: 2.5,
          },
          {
            label: 'Mes anterior',
            data: previous,
            borderColor: 'rgba(160,164,171,0.9)',
            backgroundColor: 'rgba(160,164,171,0.20)',
            fill: true,
            pointRadius: 0,
            borderDash: [6,4],
            borderWidth: 2,
          }
        ]
      },
      options: {
        interaction: { intersect: false, mode: 'index' },
        scales: {
          y: { beginAtZero: true, grace: '10%', ticks: { callback: (v)=> fmtCents(v) } },
          x: { ticks: { callback: (v, i) => labels[i] } }
        },
        plugins: {
          legend: { display: true },
          tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmtCents(ctx.parsed.y)}` } }
        }
      }
    });

    if (staffChart){ staffChart.destroy(); staffChart = null; }
    // Build a vertical orange gradient for bars
    const ctx = staffEl.getContext('2d');
    const area = { top: 0, bottom: staffEl.height };
    const grad = ctx.createLinearGradient(0, 0, 0, staffEl.height);
    grad.addColorStop(0, 'rgba(255,140,64,0.85)');
    grad.addColorStop(1, 'rgba(255,140,64,0.35)');
    staffChart = new Chart(staffEl, {
      type: 'bar',
      data: {
        labels: staff_labels,
        datasets: [{
          label: 'Propinas por trabajador',
          data: staff_totals,
          backgroundColor: grad,
          borderColor: 'rgba(255,140,64,1)',
          borderWidth: 1.5,
          borderRadius: 10,
          barPercentage: 0.7,
          categoryPercentage: 0.7,
        }]
      },
      options: {
        scales: {
          y: { beginAtZero: true, ticks: { callback: (v)=> fmtCents(v) }, grid: { color: 'rgba(0,0,0,0.12)' } },
          x: { grid: { color: 'rgba(0,0,0,0.08)' } }
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => fmtCents(ctx.parsed.y) } }
        }
      }
    });
  };

  const fetchData = async () => {
    setLoading(tipsEl, true); setLoading(staffEl, true);
    try{
      const res = await fetch(`/dashboard/restaurant/data`, { headers: { 'Accept': 'application/json' } });
      if (!res.ok) throw new Error('HTTP '+res.status);
      const json = await res.json();
      buildOrUpdate(json);
    }catch(err){
      console.error('Chart data error', err);
    } finally {
      setLoading(tipsEl, false); setLoading(staffEl, false);
    }
  };

  // Use initial embedded data as immediate fallback
  try{
    const seedEl = document.getElementById('initialChartsData');
    if (seedEl && seedEl.textContent){
      const initial = JSON.parse(seedEl.textContent);
      buildOrUpdate(initial);
    }
  }catch(e){ /* ignore */ }
  fetchData();
  setInterval(fetchData, 10000);
}
