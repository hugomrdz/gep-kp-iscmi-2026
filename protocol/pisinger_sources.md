# Frozen Pisinger transfer sources

Retrieved on 2026-08-28 from David Pisinger's University of Copenhagen
[codes page](https://hjemmesider.diku.dk/~pisinger/codes.html). These files are
read directly as compressed tar archives; they are not extracted or edited.

| Archive | Direct source | Bytes | Supplied cases | SHA-256 |
|---|---|---:|---:|---|
| `smallcoeff_pisinger.tgz` | [small coefficient](https://hjemmesider.diku.dk/~pisinger/smallcoeff_pisinger.tgz) | 148,168,396 | 10,400 | `e31a402af0609fe053afa56533f79cd15fa54c20172345829d65245068acf63d` |
| `largecoeff_pisinger.tgz` | [large coefficient](https://hjemmesider.diku.dk/~pisinger/largecoeff_pisinger.tgz) | 324,559,299 | 16,000 | `cd4827c74bbd0b988bf5aaefe4919004730e6ddcdb66b57a1f96f9a6c812f4a8` |
| `hardinstances_pisinger.tgz` | [hard instances](https://hjemmesider.diku.dk/~pisinger/hardinstances_pisinger.tgz) | 46,359,335 | 5,400 | `e30971629f84bbd020a6de4fa9cd70e462ef6a9291ae65cb601cc79dc64bd097` |

The audit parsed 31,800 named cases. For every case it recomputed the profit and
weight of the supplied 0/1 selection, required exact equality to the stated
optimum, and required weight no greater than capacity. All certificates passed.
All 31,800 normalized instance byte sequences had different SHA-256 hashes, so
the byte-equivalent duplicate rule removed zero cases.

The canonical manifest is `results/pisinger_manifest_v2.csv`, currently
SHA-256 `87a5320f3125f9b023aa34b63b6b5b1bb496e2a9e7e9fbf3025d7c3dcc257654`.
The signed protocol lock rechecks the three archive fingerprints, exact case
counts, and manifest fingerprint before confirmatory or transfer evaluation.
