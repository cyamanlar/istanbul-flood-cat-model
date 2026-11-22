"""
Spatial scale of the 8-9 September 2009 storm from the MGM Istanbul (Catalca)
C-band radar (review point: is a 60 km correlation length realistic?).

Input: MGM radar GeoTIFFs (max-reflectivity product, ~7-min scans), obtained
for research through the ITU department; not redistributed (MGM licence).
    python scripts/radar_2009_footprint.py <folder with IST_RADAR_MAX... GeoTIFFs>
Method: dBZ -> rain rate with Marshall-Palmer Z = 200 R^1.6 (15-55 dBZ),
accumulated over 8-9 Sep, 2 km blocks, 5-110 km range; spatial
autocorrelation of log(1 + P); e-folding distance.
Caveats: column-maximum reflectivity overestimates surface rain and includes
sea clutter, so only the spatial structure is used, not the amounts. The
RAIN1/RAINN accumulation GeoTIFFs in the same delivery could not be decoded
(values capped at 0.254 with alternating no-data pixels) and were not used.
Output: outputs/tables/radar_2009_correlation.csv
"""
import sys, glob, os
import numpy as np, pandas as pd, rasterio
F = sorted(glob.glob(os.path.join(sys.argv[1], "*MAX*", "*.tif")))
ts = lambda f: pd.Timestamp("20" + os.path.basename(f)[3:9] + " " + os.path.basename(f)[9:11] + ":" + os.path.basename(f)[11:13])
P, prev = None, None
for f in F:
    t = ts(f)
    if not (pd.Timestamp("2009-09-08") <= t < pd.Timestamp("2009-09-10")):
        continue
    with rasterio.open(f) as r:
        z = r.read(1).astype("float32")
    z = np.clip(np.where(np.isfinite(z), z, 0), 0, 55); z[z < 15] = 0
    R = np.where(z > 0, (10 ** (z / 10) / 200.0) ** (1 / 1.6), 0)
    dt = 5 / 60 if prev is None else min((t - prev).total_seconds() / 3600, 0.25); prev = t
    P = R * dt if P is None else P + R * dt
ny, nx = P.shape; yy, xx = np.mgrid[0:ny, 0:nx]; dkm = np.hypot(yy - ny / 2, xx - nx / 2) * 0.3333
P = np.where((dkm < 110) & (dkm > 5), P, np.nan)
b = 6; Pc = np.nanmean(P[:ny // b * b, :nx // b * b].reshape(ny // b, b, nx // b, b), axis=(1, 3))
X = np.log1p(Pc); m = np.isfinite(X); X = np.where(m, X - np.nanmean(X), 0); M = m.astype(float)
s = [2 * X.shape[0], 2 * X.shape[1]]; f2, if2 = np.fft.fft2, np.fft.ifft2
num = np.real(if2(np.abs(f2(X, s)) ** 2)); den = np.real(if2(np.abs(f2(M, s)) ** 2))
C = np.fft.fftshift(num / np.maximum(den, 1) / (X[m] ** 2).mean()); D = np.fft.fftshift(den)
cy, cx = np.array(C.shape) // 2; Y, Xg = np.mgrid[0:C.shape[0], 0:C.shape[1]]; d = np.hypot(Y - cy, Xg - cx) * b * 0.3333
rows = [dict(distance_km=a + 2, correlation=float(np.nanmean(C[(d >= a) & (d < a + 4) & (D > 200)]))) for a in range(0, 100, 4)]
out = pd.DataFrame(rows); out.to_csv("outputs/tables/radar_2009_correlation.csv", index=False)
e = out[out.correlation < np.exp(-1)].distance_km.min()
print(out.round(2).head(15).to_string(index=False)); print("e-folding distance ~", e, "km")
