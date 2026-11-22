"""Uncertainty and sensitivity runs for the portfolio model -> outputs/tables/sensitivity_uncertainty.csv

    python scripts/sensitivity_uncertainty.py
"""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json,sys,os,numpy as np,pandas as pd
sys.path.insert(0,'.')
from src import exposure,financial,hazard
base=json.load(open('config.json'))
def run(mod,label,years=None):
    cfg=json.loads(json.dumps(base)); mod(cfg)
    if years: cfg['n_sim_years']=years
    rng=np.random.default_rng(cfg['random_seed']); cells=hazard.grid_cells()
    am,_=hazard.load_annual_max(cfg,cells,rng); gev=hazard.fit_cells(am,regional_shape=cfg['hazard'].get('regional_shape',True))
    ev=hazard.simulate_event_set(gev,cfg['n_sim_years'],cfg['hazard']['corr_length_km'],rng,cfg['hazard'].get('max_daily_rain_mm',400.0))
    loc=exposure.build_portfolio(cfg,cells,np.random.default_rng(cfg.get('exp_seed',base['random_seed']+100)))
    r=financial.run_losses(ev,gev,loc,cfg,np.random.default_rng(cfg['random_seed']+1)); s=financial.summarise(r,loc.TIV.sum())
    return dict(case=label,AAL_m=round(s['AAL_gross_EUR']/1e6,2),L200_m=round(s['VaR_99_5_1in200_EUR']/1e6,1),TVaR995_m=round(s['TVaR_99_5_EUR']/1e6,1))
def setp(path,val):
    def f(c):
        d=c
        for k in path[:-1]: d=d[k]
        d[path[-1]]=val
    return f
CASES = {
 'base': (lambda c: None, 'Base (50,000 years)', None),
 'corr30': (setp(['hazard','corr_length_km'],30), 'Correlation length 30 km', None),
 'corr120': (setp(['hazard','corr_length_km'],120), 'Correlation length 120 km', None),
 'drain56': (setp(['vulnerability','prone','drainage_capacity_mm'],56), 'Drainage capacity, flood-prone zone 56 mm (-20%)', None),
 'drain84': (setp(['vulnerability','prone','drainage_capacity_mm'],84), 'Drainage capacity, flood-prone zone 84 mm (+20%)', None),
 'coef_lo': (setp(['vulnerability','prone','coef_m_per_mm'],0.0064), 'Depth coefficient -20%', None),
 'coef_hi': (setp(['vulnerability','prone','coef_m_per_mm'],0.0096), 'Depth coefficient +20%', None),
 'cv0': (setp(['vulnerability','secondary_uncertainty_cv'],0.0), 'No secondary uncertainty', None),
 'cv08': (setp(['vulnerability','secondary_uncertainty_cv'],0.8), 'Secondary uncertainty CV 0.8', None),
 'seed1': (setp(['random_seed'],2027), 'Hazard sampling, seed 2027', None),
 'seed2': (setp(['random_seed'],2028), 'Hazard sampling, seed 2028', None),
 'seed3': (setp(['random_seed'],2029), 'Hazard sampling, seed 2029', None),
 'exp1': (setp(['exp_seed'],5001), 'Portfolio realisation 1', None),
 'exp2': (setp(['exp_seed'],5002), 'Portfolio realisation 2', None),
 'exp3': (setp(['exp_seed'],5003), 'Portfolio realisation 3', None),
 'exp4': (setp(['exp_seed'],5004), 'Portfolio realisation 4', None),
 'exp5': (setp(['exp_seed'],5005), 'Portfolio realisation 5', None),
 'cap300': (setp(['hazard','max_daily_rain_mm'],300), 'Rainfall cap 300 mm/day', None),
 'cap600': (setp(['hazard','max_daily_rain_mm'],600), 'Rainfall cap 600 mm/day', None),
 'localk': (setp(['hazard','regional_shape'],False), 'Cell-by-cell GEV shape (no regional shape)', None),
 'bias_p05': (setp(['hazard','bias_multiplier'],0.89), 'ERA5 bias factors at P5 (x0.89)', None),
 'bias_p95': (setp(['hazard','bias_multiplier'],1.13), 'ERA5 bias factors at P95 (x1.13)', None),
 'corr20': (setp(['hazard','corr_length_km'],20), 'Correlation length 20 km (radar, 2009 event)', None),
 'corr60': (setp(['hazard','corr_length_km'],60), 'Correlation length 60 km (v0.2 value)', None),
 'v02_bias': (lambda c: (c['hazard'].pop('bias_correction',None), c['hazard'].__setitem__('bias_correction_factor',1.8)), 'v0.2 uniform bias 1.8 (40 km)', None),
 'v02_all': (lambda c: (c['hazard'].pop('bias_correction',None), c['hazard'].__setitem__('bias_correction_factor',1.8), c['hazard'].__setitem__('corr_length_km',60)), 'v0.2 settings (uniform 1.8, 60 km)', None),
 'y10k': (lambda c: None, '10,000 years', 10000),
}
if __name__ == '__main__':
    out = 'outputs/tables/sensitivity_uncertainty.csv'
    keys = sys.argv[1:] or list(CASES)
    old = pd.read_csv(out) if os.path.exists(out) and sys.argv[1:] else pd.DataFrame()
    rows = [run(*CASES[k]) for k in keys]
    t = pd.concat([old[~old.case.isin([r['case'] for r in rows])] if len(old) else old, pd.DataFrame(rows)], ignore_index=True)
    t.to_csv(out, index=False); print(t.to_string(), flush=True)
