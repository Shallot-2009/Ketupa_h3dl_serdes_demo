# Ketupa H3DL SerDes Demo

**PCB · Package · PCB–Package co-modeling**

**Linux x86_64 | CPython 3.12 | Native core | v1.0.1**

[简体中文](README.md) | [English (current)](README_EN.md) | [License](LICENSE)

An HFSS 3D Layout automation demo for 112G/224G SerDes channel studies, covering PCB, package, and combined PCB–package models. The data-rate labels describe the intended application; they do not claim completed electrical compliance.

**Author:** Asenjo.HB.L

**Location:** China · Shanghai

**Contact:** asenjoaupa@gmail.com · 3405802009@qq.com

**License:** Proprietary Evaluation License — public distribution with a closed native core; this is not an open-source license.

![HFSS 3D Layout — SerDes PCB–PKG Merge model, RX0 top view](assets/hfss-serdes-merge.jpg)

*Actual model view: AEDT 2026 R1, `serdes_merge_SDS_RX0_CHIP1`, RX0. Exported directly from the saved model on 2026-10-06. This is a layout view, not a field plot or solved result.*

## Quick start

Download the package for your operating system and `Ketupa-Demo-30-Day-Trial.lic` from the [Runtime 1.0.0 preview release](https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo/releases/tag/runtime-v1.0.0).

Windows: run `Ketupa-Runtime-1.0.0-Windows-x64-Setup.exe`, reopen the terminal, then run:

```powershell
ketupa license machine
ketupa license activate .\Ketupa-Demo-30-Day-Trial.lic --mac AA:BB:CC:DD:EE:FF
ketupa license status
```

Ubuntu/Debian:

```bash
sudo apt install ./ketupa-runtime-installer_1.0.0_amd64.deb
ketupa license machine
sudo ketupa license activate ./Ketupa-Demo-30-Day-Trial.lic --mac AA:BB:CC:DD:EE:FF
ketupa license status
```

Other compatible x86_64 Linux distributions:

```bash
tar -xzf Ketupa-Runtime-1.0.0-Linux-x64.tar.gz
cd Ketupa-Runtime-1.0.0-Linux-x64
sudo sh install.sh /opt/ketupa-runtime /var/lib/openketupa-license
ketupa license machine
sudo ketupa license activate ../Ketupa-Demo-30-Day-Trial.lic --mac AA:BB:CC:DD:EE:FF
ketupa license status
```

The Demo is in `serdes_linux/`. Configure `script/extractors/cds_env` as described below, then run:

```bash
cd serdes_linux
ketupa run -sh main.py -- doctor
ketupa run -sh main.py -- --dry-run
ketupa run -sh main.py
```

> The trial license is provided only to evaluate this Demo; use constitutes acceptance of the repository [LICENSE](LICENSE). The workflow calls third-party EDA software such as Ansys and Cadence. You must install that software and confirm that you hold the required legal EDA licenses. The Ketupa trial license does not include any third-party EDA license.

> The native modules in this Demo require **CPython 3.12**. Runtime 1.0.0 for Linux uses CPython 3.13 and therefore cannot directly serve as this Demo's interpreter. Point `script/extractors/cds_env` to a compatible CPython 3.12 Ketupa environment. The Windows Runtime deploys the Windows Ketupa environment, but this repository's Linux `.so` Demo does not run on Windows.

## 1. Scope and delivered files

This repository delivers a runnable Linux native demo containing **PCB, PKG, and Merge** workflows. `serdes_linux/main.py` remains editable, as do the extraction and preprocessing rules under `serdes_linux/script/`. The modeling core, workflow implementations, and resource policy are distributed as **119 CPython 3.12 native `.so` extensions** under `serdes_linux/lib/`, `serdes_linux/modules/`, and `serdes_linux/resource/`.

```text
Ketupa_h3dl_serdes_demo/
├── README.md                     Complete Chinese guide (GitHub landing page)
├── README_EN.md                  Complete English guide
├── LICENSE                       Proprietary Demo evaluation license
├── SHA256SUMS                    Release integrity manifest
├── assets/                       Actual HFSS views and a parameter-based structure diagram
└── serdes_linux/                Run all commands from this directory
    ├── main.py                   Workflow, input, mode, and concurrency settings
    ├── input/
    │   ├── PCB/                  BRD, stackup, netlist, and placement workbook
    │   ├── PKG/                  SIP/AEDB, stackup, and netlist workbook
    │   └── Connector/            Connector A3DCOMP model
    ├── script/                   Open extraction/classification/preprocessing code
    │   └── extractors/cds_env    Three tool paths configured on first deployment
    ├── modules/                  Native entry point and three workflows
    ├── lib/                      Native modeling core
    └── resource/                 Native resource and model policies
```

The public Demo inputs include the PCB and package layouts, their spreadsheets and stackups, and the connector model. No vendor software or license, core Python source, private build artifacts, historical simulation output, separate docs bundle, the other nine parent-project workflows, or Windows `.pyd` package is included.

## 2. Requirements and qualification boundary

| Item | Requirement or boundary |
|---|---|
| Platform | Linux x86_64 with compatible glibc; not Windows, ARM, PyPy, or Alpine/musl |
| Python ABI | **CPython 3.12**, preferably the existing Ketupa runtime rather than a system Python replacement |
| Launcher | Installed and authorized `ketupa` command; this repository does not contain its installer or license |
| EDA tools | Ansys Electronics Desktop with HFSS 3D Layout; Cadence SPB Extracta/Report for applicable BRD/SIP import or preprocessing |
| Python packages | `openpyxl`, `numpy`, `cryptography`, `pyedb`, `psutil`, and related dependencies checked by `doctor` |
| Resources | Concurrency is limited by current CPU and memory; the local evidence used an approximately 30 GB host and is not a universal minimum-memory guarantee |
| Version evidence | Actual building and native design validation were performed on AEDT **2026 R1**; 2025/2026 code paths exist, but this package has no AEDT 2025 machine-level regression evidence |

Confirm that `ketupa --help` works first. If the launcher is not installed, contact the author for the matching runtime. Do not substitute an unrelated product that happens to use the same command name.

## 3. Download and first-time setup

```bash
git clone https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo.git
cd Ketupa_h3dl_serdes_demo
sha256sum -c SHA256SUMS
cd serdes_linux
```

For GitHub **Code → Download ZIP**, extract the entire repository before entering `serdes_linux/`. Do not download only `main.py`; all spreadsheets, AEDB contents, and native extensions are required.

On a new workstation, edit exactly these three paths in `script/extractors/cds_env`:

```ini
PYTHON_EXE=/your/ketupa/runtime/bin/python
CADENCE_TOOLS_BIN=/your/cadence/tools/bin:/your/older/cadence/tools/bin
KETUPA_ANSYSEDT=/your/ansys/AnsysEM
```

The shipped `/home/EDA/...` values are workstation examples, not portable defaults. Separate multiple Cadence directories with `:` in preferred-to-fallback order. Do not put license files, credentials, or API keys in this file; configure vendor licensing through the normal licensed installation procedure. For normal workflow selection and input changes after setup, edit only `main.py`.

## 4. Recommended command sequence

Run every command below from `serdes_linux/`. The first `--` forwards subsequent arguments to the project entry point.

```bash
ketupa run -sh main.py -- list
ketupa run -sh main.py -- doctor
ketupa run -sh main.py -- audit
ketupa run -sh main.py -- --dry-run
ketupa run -sh main.py
```

| Command | Action | Important limitation |
|---|---|---|
| `list` | Lists PCB, PKG, and Merge | Does not build a model |
| `doctor` | Checks runtime packages, EDA tools, license reachability, and resources | Cannot guarantee success for arbitrary designs |
| `audit` | Checks architecture, configuration, port conventions, and native integrity | Does not replace AEDT validation |
| `--dry-run` | Resolves inputs, network groups, tasks, and parallel plans | Starts no modeling/solver worker and creates no solved result |
| No extra argument | Executes the configuration saved in `main.py` | Default is **Merge, Mode 0**, which builds and saves only |

Startup lines such as `Layout input: not provided` and `script default` describe outer Ketupa CLI overrides; they do not mean that `main.py` has no input. Inspect the subsequent resolved workflow, files, and groups. `[managed resource]` is masked path text, not a filename that should be created.

## 5. Select any combination by editing main.py

Change `SELECTIONS` to any of the seven nonempty combinations:

| Combination | `SELECTIONS` |
|---|---|
| PCB | `(("serdes", "pcb"),)` |
| PKG | `(("serdes", "pkg"),)` |
| Merge | `(("serdes", "merge"),)` |
| PCB + PKG | `(("serdes", "pcb"), ("serdes", "pkg"))` |
| PCB + Merge | `(("serdes", "pcb"), ("serdes", "merge"))` |
| PKG + Merge | `(("serdes", "pkg"), ("serdes", "merge"))` |
| All three | `(("serdes", "all"),)` |

Merge imports PCB and PKG itself; the two standalone workflows do **not** need to run first. Selected workflows run sequentially, while each workflow can process network groups in parallel.

`INPUTS["default"]` defines shared inputs. Add an exact-workflow override only when a value differs, for example:

```python
INPUTS["serdes-pkg"] = {
    "pkg_netlist": PKG_DIR / "netlist/another_design.xlsx",
}
```

A netlist or placement value may point to an exact Excel/CSV file or a directory containing a matching table. A layout and stackup must point to the actual item; an AEDB layout points to the directory containing `edb.def`. Layout, stackup, netlist, and placement data must all describe the same design. The default package input is AEDB, while the source SIP is retained in the Demo.

Key `RUN_OPTIONS` values:

| Setting | Meaning |
|---|---|
| `mode: 0` / `mode: 1` | Mode 0 builds and saves; Mode 1 builds, solves, and performs applicable exports |
| `dry_run: True` | Checks and plans only |
| `prefix: "ALL"` | Selects all matching nets |
| `corps: "\\"` | Does not add another grouping rule |
| `parallel_groups: ""` | Selects every matched group; `"ALL|SDS_RX0"` is a single-group example |
| `max_workers: None` | Uses the automatic resource policy; `1` limits concurrency while memory guards remain active |
| `preprocess: False` | Uses bundled workbooks; set `True` only when fresh extraction is required |
| `preprocess_entry: "sh"` | Uses the Linux preprocessing entry point |
| `signoff: False` | Does not automatically produce a signoff summary; unapproved/TBD limits are not electrical PASS |

Temporary CLI overrides do not require editing the saved configuration:

```bash
ketupa run -sh main.py -- run serdes pcb --mode 0
ketupa run -sh main.py -- run serdes pkg --mode 0
ketupa run -sh main.py -- run serdes merge --mode 0
ketupa run -sh main.py -- run-many serdes-pcb serdes-pkg --dry-run
ketupa run -sh main.py -- run-all --dry-run
ketupa run -sh main.py -- --max-workers 1 --parallel-groups 'ALL|SDS_RX0'
ketupa run -sh main.py -- run --help
```

## 6. Preprocessing, geometry, and ports

The three bundled spreadsheets and their provenance records are ready for the supplied Demo. They do not need to be regenerated before the first run. After replacing a layout, update the inputs and regenerate/review the corresponding data; never reuse a workbook from an unrelated design.

```bash
bash script/00_Preprocess.sh
# Follow the interactive signal/group/confirmation prompts.
# Or preprocess immediately before the saved workflow:
ketupa run -sh main.py -- --preprocess-first
```

`script/01_Netlist.*` performs net extraction/classification; `02_Placement.*` handles PCB placement; `extractors/` contains editable Cadence compatibility and naming rules. The rules can be extended for company-specific naming, but arbitrary unknown names are not guaranteed to be classified without ambiguity. Optional LLM integration is not required by the default workflow and must not transmit design data externally without authorization.

| Workflow | Final channel boundary | Cutout expansion |
|---|---|---|
| PCB | BGA solder ball → PCB connector | PCB `3.5mm` |
| PKG | DIE C4 bump → BGA solder ball | PKG `1mm` |
| Merge | DIE C4 bump → PCB connector, with no intermediate BGA port | PCB `3.5mm` / PKG `1mm` |

C4 uses a chip-down Flip-Chip model with **60 µm height and 65 µm radius** in the actual `sbr` parameter. Do not interpret the historical `d65um` filename as diameter evidence. BGA uses the **0.5 mm pitch** library; pitch is not ball diameter. Merge keeps the C4 reference treatment, removes intermediate BGA ports and disables the controlled BGA helper PEC sheet. Placement side/rotation data is used for alignment. The package AUTO reference policy preserves actually separate VSS and AGND nets rather than arbitrarily shorting them.

### Complete engineering gallery: Merge, PCB, package, connector, bump, and ball

Every image is expanded directly on the repository page so that the modeling boundary and interconnect structure can be inspected without opening a collapsed section. The three layout views and the connector view were exported from saved AEDT 2026 R1 projects. In the final image, the left side is an engineering illustration drawn from released model parameters and the right side is an actual orthographic HFSS view of the connector project. None of these images is a field plot or solved result.

![HFSS 3D Layout — SerDes PCB–PKG Merge model, RX0 top view](assets/hfss-serdes-merge.jpg)

**Merge — actual project top view:** `serdes_merge_SDS_RX0_CHIP1`. The channel boundary is the DIE C4 bump to the PCB connector; no intermediate port is retained on the BGA solder ball in Merge.

![HFSS 3D Layout — SerDes PCB model, RX0 top view](assets/hfss-serdes-pcb.jpg)

**PCB — actual project top view:** `serdes_pcb_SDS_RX0_CHIP1`, showing the differential-channel layout from BGA solder ball to PCB connector.

![HFSS 3D Layout — SerDes package model, RX0 top view](assets/hfss-serdes-pkg.jpg)

**PKG / package — actual project top view:** `serdes_pkg_SDS_RX0_DIE_1`, showing the package layout associated with the chip-down DIE/C4-bump port boundary and the BGA-solder-ball port boundary.

![HFSS 3D Component — 1.0 mm 110 GHz precision coaxial connector](assets/hfss-serdes-connector-3d.jpg)

**SMA-style connector — actual HFSS 3D Component view:** the Demo file is `Stripline_connector_1p0mm_110GHz.a3dcomp`, a **1.0 mm / 110 GHz precision coaxial connector model**. “SMA-style” describes its role and appearance; it must not be read as a claim that the component is a standard SMA model.

![SerDes side structure with C4 bump, BGA solder ball, PCB and coaxial connector](assets/hfss-serdes-side-structure.png)

**Side-structure overview:** the parameter-based illustration on the left explicitly shows the chip-down DIE, C4 bump (65 µm radius, 60 µm height), package substrate, 0.5 mm-pitch BGA solder ball, PCB stackup, and Merge channel boundary. The right side is an actual side screenshot of the HFSS connector model. The vertical scale is enlarged for legibility and must not be used to infer dimensions from pixels.

## 7. Output, verification, and troubleshooting

Runtime artifacts are created under `serdes_linux/output/`; old output is not part of the published repository:

```text
output/
├── tasks/<run_id>/                          Inputs, state, and event records
└── serdes_{pcb,pkg,merge}/<run_id>/
    ├── h3d_projects/                       .aedt plus associated .aedb data
    │   └── parallel_workers/               Independent per-network-group projects
    ├── logs/                               Workflow, group, and resource logs
    └── results/                            Solve/export artifacts when those stages run
```

Open the **current run ID's final `.aedt`** in AEDT and keep its `.aedb` and embedded components together. `h3d_projects/models.json` identifies the actual per-group projects. The original input layout, a cutout intermediate, and an older run are not the current final channel model. Mode 0 provides no new solved S-parameters; Mode 1 requires solver licensing and adequate resources. After a manual solve, explicitly target a saved project for export:

```bash
ketupa run -sh main.py -- export serdes merge --project /absolute/path/channel.aedt
```

**Verification scope on 2026-10-06:**

- The core contains 119 `.so` files and no core `.py/.pyc`; the native tamper-rejection test passed.
- All seven PCB/PKG/Merge selection combinations passed dry-run. Audit and input resolution passed again after relocation into this repository's `serdes_linux/` directory.
- One RX0 group in each scenario built successfully with AEDT 2026 R1. Saved four-port names, order, impedance, and references matched the corresponding source implementation; reopening each model returned `1` from `ValidateCircuit()`.
- The native default Merge workflow built both RX and TX groups through the real `ketupa run -sh main.py` launcher: 2 completed, 0 failed.
- **Not validated:** a complete Mode 1 solve, mesh convergence, electrical signoff, AEDT 2025 on an actual installation, Windows/ARM, or every Linux distribution.
- **Known advisory:** PCB/Merge connector instances J3D1/J3D2 report “does not contain any priority bodies.” Native validation passes, but that is not proof of material overlap or electrical accuracy. This release does not silently change that model physics.

| Symptom | Resolution |
|---|---|
| `pcb_netlist ... not found: [managed resource]` | Ensure all three bundled workbooks exist, restore a complete download, or preprocess the matching layout. `preprocess=False` does not regenerate missing files. |
| Native `.so` missing/import error | Use the complete directory on CPython 3.12 x86_64; this build is not for Windows or another Python ABI. |
| Extracta path/version not identified | Correct the Cadence path in `cds_env`, confirm vendor licensing, and run `doctor`. |
| `/var/lib/openketupa-license/...` permission denied | Ask the administrator to restore appropriate group/read/traverse permissions. Do not use `chmod 777` or bypass licensing. |
| Memory pressure | Use `--max-workers 1` and inspect the workload with `--dry-run` first. |
| `CONFIG NOTE ... TBD` | The electrical criterion is not approved; do not report compliance PASS. It does not necessarily prevent Mode 0 building. |

## 8. License and protection boundary

This is a **publicly downloadable proprietary Demo with a closed native core**. The [Proprietary Evaluation License](LICENSE) permits learning, research, internal non-production evaluation, and changes to exposed scripts/configuration for those purposes. Commercial production, paid delivery, hosted service use, or redistribution of modified versions requires written permission from the author. GitHub identifies the custom license as “Other”; it is not MIT, GPL, or another OSI-approved license.

Native compilation, stripped symbols, and integrity checks increase reverse-engineering cost, but **they are not cryptographic encryption and cannot guarantee absolute secrecy or irreversibility**. Users can inspect their inputs, parameters, logs, and generated projects. A public Git repository cannot hide anything committed to its history. Never commit license files, API keys, private designs, or core build source. Ansys and Cadence names and trademarks belong to their respective owners; no vendor certification, endorsement, or affiliation is implied.
