#!/usr/bin/env python3
"""
Calculate 3GPP TS 38.104 SSB ARFCN and GSCN for Band 2, DL ARFCN 386000.
"""

dl_arfcn = 386000
# FR1: F_REF = 0 + 5 kHz * dl_arfcn
f_dl_khz = 5 * dl_arfcn
f_dl_mhz = f_dl_khz / 1000.0

print(f"Carrier DL Center: {f_dl_mhz:.3f} MHz (ARFCN {dl_arfcn})")

# Band 2 SS raster: TS 38.101-1 Table 5.4.3.3-1: GSCN 4829 to 4969
# TS 38.104 Table 5.4.3.1-1: SS_REF = N * 1200 kHz + M * 50 kHz
# GSCN = 3*N + (M - 3)/2, where M in {1, 3, 5}
candidates = []
for gscn in range(4829, 4970):
    for M in [1, 3, 5]:
        val = gscn - (M - 3) // 2
        if val % 3 == 0:
            N = val // 3
            f_ssb_khz = N * 1200 + M * 50
            f_ssb_mhz = f_ssb_khz / 1000.0
            ssb_arfcn = f_ssb_khz // 5
            # 20 MHz carrier spans [1920.46, 1939.54] MHz
            # SSB is 20 RBs = 20 * 12 * 15 kHz = 3.6 MHz wide
            if abs(f_ssb_mhz - f_dl_mhz) <= 8.0:
                diff_mhz = f_ssb_mhz - f_dl_mhz
                candidates.append((abs(diff_mhz), gscn, N, M, f_ssb_mhz, ssb_arfcn, diff_mhz))

candidates.sort()
print(f"\nClosest SSB candidates within 20 MHz carrier:")
for diff_abs, gscn, N, M, f_ssb_mhz, ssb_arfcn, diff_mhz in candidates[:10]:
    print(f"  GSCN: {gscn} | N: {N} | M: {M} | F_SSB: {f_ssb_mhz:.3f} MHz | SSB_ARFCN: {ssb_arfcn} | offset: {diff_mhz:+.3f} MHz")
