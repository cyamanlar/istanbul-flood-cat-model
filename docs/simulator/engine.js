// Istanbul flood cat model - browser engine (simplified portfolio model)
// Same GEV parameters, portfolio, rainfall-depth transfer and JRC damage
// curves as the Python model; mean damage ratio, 10,000 simulated years.
const FloodEngine = (function () {
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function erf(x) {
    const s = x < 0 ? -1 : 1; x = Math.abs(x);
    const t = 1 / (1 + 0.3275911 * x);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return s * y;
  }
  const normCdf = z => 0.5 * (1 + erf(z / Math.SQRT2));
  function hav(la1, lo1, la2, lo2) {
    const r = 6371, p1 = la1 * Math.PI / 180, p2 = la2 * Math.PI / 180;
    const dp = p2 - p1, dl = (lo2 - lo1) * Math.PI / 180;
    const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
    return 2 * r * Math.asin(Math.sqrt(a));
  }
  function cholesky(A, n) {
    const L = new Float64Array(n * n);
    for (let i = 0; i < n; i++) for (let j = 0; j <= i; j++) {
      let s = A[i * n + j];
      for (let k = 0; k < j; k++) s -= L[i * n + k] * L[j * n + k];
      L[i * n + j] = i === j ? Math.sqrt(Math.max(s, 1e-12)) : s / L[j * n + j];
    }
    return L;
  }
  function gevQ(F, xi, al, k) {
    F = Math.min(Math.max(F, 1e-12), 1 - 1e-12);
    const y = -Math.log(F);
    return Math.abs(k) < 1e-8 ? xi - al * Math.log(y) : xi + al * (1 - Math.pow(y, k)) / k;
  }

  function create(D, nYears) {
    nYears = nYears || 10000;
    const C = D.cells, nc = C.lat.length, nl = D.loc.cell.length;
    const curves = [D.curves.res, D.curves.com, D.curves.ind], dep = D.curves.depth;
    const state = { nYears, Q: null, corr: null };

    function buildEventSet(corrKm) {
      if (state.corr === corrKm && state.Q) return;
      const A = new Float64Array(nc * nc);
      for (let i = 0; i < nc; i++) for (let j = 0; j < nc; j++)
        A[i * nc + j] = Math.exp(-hav(C.lat[i], C.lon[i], C.lat[j], C.lon[j]) / corrKm) + (i === j ? 1e-9 : 0);
      const L = cholesky(A, nc), rnd = mulberry32(20261122);
      const Q = new Float32Array(nYears * nc), z = new Float64Array(nc);
      for (let y = 0; y < nYears; y++) {
        for (let i = 0; i < nc; i += 2) {
          const u1 = Math.max(rnd(), 1e-12), u2 = rnd(), r = Math.sqrt(-2 * Math.log(u1));
          z[i] = r * Math.cos(2 * Math.PI * u2); if (i + 1 < nc) z[i + 1] = r * Math.sin(2 * Math.PI * u2);
        }
        for (let i = 0; i < nc; i++) {
          let s = 0; for (let k = 0; k <= i; k++) s += L[i * nc + k] * z[k];
          Q[y * nc + i] = gevQ(normCdf(s), C.xi[i], C.alpha[i], C.k[i]);
        }
      }
      state.Q = Q; state.corr = corrKm;
    }

    function interp(x, ys) {
      if (x <= 0) return 0;
      for (let i = 1; i < dep.length; i++) if (x <= dep[i]) {
        const t = (x - dep[i - 1]) / (dep[i] - dep[i - 1]); return ys[i - 1] + t * (ys[i] - ys[i - 1]);
      }
      return ys[ys.length - 1];
    }

    // p: {warming, ccRate, bias, corrKm, drainProne, floodplain, floorRaise, deductible}
    function run(p) {
      buildEventSet(p.corrKm);
      const V = D.meta.vuln, cap = D.meta.cap_mm;
      const scale = (p.bias / D.meta.bias_factor_base) * Math.pow(1 + p.ccRate, p.warming);
      const Lc = D.loc, nd = D.districts.length;
      // flood-prone flags under the floodplain-exposure multiplier
      const prone = new Uint8Array(nl), amp = new Float64Array(nl);
      for (let l = 0; l < nl; l++) {
        const base = Lc.prone[l] === 1, share = D.prone_share[D.districts[Lc.dist[l]]];
        let pr = base;
        if (p.floodplain > 1 && !base) pr = Lc.u[l] < share * (p.floodplain - 1);
        if (p.floodplain < 1 && base) pr = Lc.u[l] < p.floodplain;
        prone[l] = pr ? 1 : 0; amp[l] = base ? Lc.amp[l] : 1;
      }
      const ffh = D.curves.ffh.map(v => v + p.floorRaise);
      const ann = new Float64Array(nYears), byD = new Float64Array(nd);
      const P = new Float64Array(nc);
      for (let y = 0; y < nYears; y++) {
        for (let c = 0; c < nc; c++) P[c] = Math.min(cap, state.Q[y * nc + c] * scale);
        let tot = 0;
        for (let l = 0; l < nl; l++) {
          const pc = P[Lc.cell[l]];
          let h;
          if (prone[l]) h = pc > p.drainProne ? V.prone.coef_m_per_mm * (pc - p.drainProne) * amp[l] : 0;
          else h = pc > V.standard.drainage_capacity_mm ? V.standard.coef_m_per_mm * (pc - V.standard.drainage_capacity_mm) : 0;
          if (h <= 0) continue;
          const o = Lc.occ[l], dr = interp(h - ffh[o], curves[o]) - p.deductible;
          if (dr <= 0) continue;
          const loss = Lc.tiv[l] * 1e3 * Math.min(dr, 1);
          tot += loss; byD[Lc.dist[l]] += loss;
        }
        ann[y] = tot;
      }
      const sorted = Float64Array.from(ann).sort().reverse();
      const q = rp => sorted[Math.max(0, Math.round(nYears / rp) - 1)];
      const nTail = Math.round(nYears * 0.005);
      let tv = 0; for (let i = 0; i < nTail; i++) tv += sorted[i];
      let aal = 0; for (let y = 0; y < nYears; y++) aal += ann[y];
      // 2009-style footprint (stylised, station scale) under warming only
      let s09 = 0;
      for (let l = 0; l < nl; l++) {
        const c = Lc.cell[l], la = C.lat[c], lo = C.lon[c];
        let pc = 40;
        if (lo <= 29.0) pc = 120;
        if (lo >= 28.5 && lo <= 28.75 && la >= 40.75 && la <= 41.25) pc = 230;
        if (lo >= 28.25 && lo < 28.5 && la >= 40.75 && la <= 41.25) pc = 180;
        pc = Math.min(cap, pc * Math.pow(1 + p.ccRate, p.warming));
        const h = prone[l] ? (pc > p.drainProne ? V.prone.coef_m_per_mm * (pc - p.drainProne) * amp[l] : 0)
          : (pc > V.standard.drainage_capacity_mm ? V.standard.coef_m_per_mm * (pc - V.standard.drainage_capacity_mm) : 0);
        if (h <= 0) continue;
        const o = Lc.occ[l], dr = interp(h - ffh[o], curves[o]) - p.deductible;
        if (dr > 0) s09 += Lc.tiv[l] * 1e3 * Math.min(dr, 1);
      }
      return {
        aal: aal / nYears, l200: q(200), tvar: tv / nTail, s09,
        rp: { 10: q(10), 25: q(25), 50: q(50), 100: q(100), 200: q(200), 500: q(500) },
        ep: sorted, byDistrict: Array.from(byD, v => v / nYears), tiv: D.meta.tiv_total
      };
    }
    return { run, nYears };
  }
  return { create };
})();
if (typeof module !== "undefined") module.exports = FloodEngine;
