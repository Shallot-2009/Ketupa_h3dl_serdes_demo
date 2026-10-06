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

Use the [matching launch-v1 Linux Runtime update](https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo/releases/tag/serdes-v1.0.1-launch-v1). The approximately 4.5 MiB delta requires Runtime 1.0.0 build `20261006T120047Z` and produces exactly the same file hashes as the qualified full Runtime, without removing functionality. Older Runtimes need this authorization-interface update even if they use Python 3.12. Obtain a legitimate license separately; no license or activation data is included.

```bash
sha256sum -c Ketupa-Runtime-1.0.0-launch-v1-cp312-update.tar.gz.sha256
tar -xzf Ketupa-Runtime-1.0.0-launch-v1-cp312-update.tar.gz
cd Ketupa-Runtime-1.0.0-launch-v1-cp312-update
sudo python3 -I runtime_update.py --user "$USER" --check-only
sudo python3 -I runtime_update.py --user "$USER"
ketupa license machine
# Activate only on a new machine; do not reactivate an already valid license.
sudo ketupa license activate /absolute/path/to/your-authorized.lic --mac YOUR_MAC
ketupa license status
```

**New machines without a Runtime:** download `Ketupa-Runtime-1.0.0-Linux-x64.tar.gz` from the [base Runtime 1.0.0 release](https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo/releases/tag/runtime-v1.0.0), verify SHA-256 `4324c26b0d6e47da63892eef59a910c0f8b7bf66388799171245a3dd1d170b65`, install it, then apply the update above:

```bash
tar -xzf Ketupa-Runtime-1.0.0-Linux-x64.tar.gz
sudo mkdir -p /home/EDA
sudo ./Ketupa-Runtime-1.0.0-Linux-x64/install /home/EDA/openketupa-runtime-linux --add-path
```

The updater materializes and verifies a complete environment before replacing the installation, retaining the old Runtime backup and activation. Mismatched baselines or services owned by another installation are rejected. Here `python3` runs only the public installer; it does not bypass project authorization.

The Demo is in `serdes_linux/`. Configure `script/extractors/cds_env` as described below, then run:

```bash
cd serdes_linux
ketupa run -sh main.py -- doctor
ketupa run -sh main.py -- preprocess serdes all -- --force
ketupa run -sh main.py -- --dry-run
ketupa run -sh main.py
```

> The trial license is provided only to evaluate this Demo; use constitutes acceptance of the repository [LICENSE](LICENSE). The workflow calls third-party EDA software such as Ansys and Cadence. You must install that software and confirm that you hold the required legal EDA licenses. The Ketupa trial license does not include any third-party EDA license.

> This Demo requires **Linux x86_64, CPython 3.12.15 and ketupa-launch-v1**. The default Runtime path is `/home/EDA/openketupa-runtime-linux`. The system installer uses Python 3.11+; protected modeling requires the licensed `ketupa` launcher. Log in again after group membership changes. Windows installers are not updated in this revision and cannot load the Linux `.so` files.

## 1. Scope and delivered files

This repository delivers a Linux native demo containing **PCB, PKG, and Merge** workflows. `serdes_linux/main.py` remains editable, as do the extraction and preprocessing rules under `serdes_linux/script/`. The modeling core, workflow implementations, and resource policy are distributed as **142 CPython 3.12 native `.so` extensions**, each with an independent native authorization check, under `serdes_linux/lib/`, `serdes_linux/modules/`, and `serdes_linux/resource/`.

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
    │   ├── PCB/                  BRD and stackup; workbooks generated on first use
    │   ├── PKG/                  SIP/AEDB and stackup; workbook generated on first use
    │   └── Connector/            Connector A3DCOMP model
    ├── script/                   Open extraction/classification/preprocessing code
    │   └── extractors/cds_env    Three tool paths configured on first deployment
    ├── modules/                  Native entry point and three workflows
    ├── lib/                      Native modeling core
    └── resource/                 Native resource and model policies
```

The public Demo inputs include the PCB and package layouts, stackups, and connector model. The 2026-10-07 main-branch update intentionally omits three spreadsheets and their provenance records: generate them locally before modeling. The main.py configuration, 142 native extensions and Runtime ABI are unchanged. Historical Release tags and assets are fixed snapshots, not copies of the current main branch. No vendor software or license, core Python source, private build artifacts, historical simulation output, separate docs bundle, the other nine parent-project workflows, or Windows `.pyd` package is included.

## 2. Requirements and qualification boundary

| Item | Requirement or boundary |
|---|---|
| Platform | Linux x86_64 with compatible glibc; not Windows, ARM, PyPy, or Alpine/musl |
| Python ABI | **CPython 3.12**, preferably the existing Ketupa runtime rather than a system Python replacement |
| Launcher | Matching `ketupa-launch-v1` Runtime and valid license; installer is provided in this revision's Release |
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

For GitHub **Code → Download ZIP**, extract the entire repository before entering `serdes_linux/`. Do not download only `main.py`; retain every layout, AEDB file and native extension. Generate spreadsheets through preprocessing as described below.

On a new workstation, edit exactly these three paths in `script/extractors/cds_env`:

```ini
PYTHON_EXE=/home/EDA/openketupa-runtime-linux/runtime/bin/python3
CADENCE_TOOLS_BIN=/your/cadence/tools/bin:/your/older/cadence/tools/bin
KETUPA_ANSYSEDT=/your/ansys/AnsysEM
```

The shipped `/home/EDA/...` values are example installation paths. `PYTHON_EXE` must identify the matching Runtime interpreter, not an arbitrary Python with identical dependencies. Separate multiple Cadence directories with `:` in preferred-to-fallback order. Do not put license files, credentials, or API keys in this file; configure vendor licensing through the normal licensed installation procedure. For normal workflow selection and input changes after setup, edit only `main.py`.

## 4. Recommended command sequence

Run every command below from `serdes_linux/`. The first `--` forwards subsequent arguments to the project entry point.

```bash
ketupa run -sh main.py -- list
ketupa run -sh main.py -- doctor
ketupa run -sh main.py -- audit
ketupa run -sh main.py -- preprocess serdes all -- --force
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
| `preprocess: False` | Uses workbooks already generated locally; missing files are not regenerated automatically. Run preprocessing before first use |
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

**2026-10-07 update validation:** A clean copy without spreadsheets completed preprocessing, audit, doctor and all seven dry-run combinations. PCB, PKG and Merge each built RX/TX Mode 0 models on AEDT 2026 R1: six successes, zero failures. Direct Python was rejected by authorization checks. No Mode 1 solve or electrical signoff was performed. The shared-memory IPC compatibility warning fell back to standard gRPC successfully. Added `03_Verify.py` and `04_Publish.py` match the local distribution; their help entry points were checked. Maintainer builds require the source project and build dependencies; the core was not recompiled in this update.

The three spreadsheets and their provenance records are not shipped in this update. Before the first dry run or model build, generate the PCB netlist, PCB placement and PKG netlist from the supplied layouts. After replacing a layout, update the inputs and regenerate/review the corresponding data; never reuse a workbook from an unrelated design.

```bash
ketupa run -sh main.py -- preprocess serdes all -- --force
ketupa run -sh main.py -- --dry-run
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

- The core contains 142 `.so` files and no core `.py/.pyc`. All 51 source/native authorization component tests passed.
- All seven PCB/PKG/Merge selection combinations passed dry-run. Audit and input resolution passed again after relocation into this repository's `serdes_linux/` directory.
- RX0 and TX0 groups in each scenario built successfully with AEDT 2026 R1. Saved four-port properties and order matched the corresponding source implementation; reopening all six models returned `1` from `ValidateCircuit()`. This is not solver or electrical-accuracy qualification.
- Eleven live launch/worker checks passed: licensed execution, rejection of direct same-interpreter Python and forged environment flags, three parallel workers, and rejection of direct native-module loading. Missing/malformed licenses were rejected using an isolated real system broker; expired-signature/wrong-machine cases are synthetic component tests, not claimed real license-issuance acceptance.
- The native default Merge workflow built both RX and TX groups through the real `ketupa run -sh main.py` launcher: 2 completed, 0 failed.
- **Not validated:** a complete Mode 1 solve, mesh convergence, electrical signoff, AEDT 2025 on an actual installation, Windows/ARM, or every Linux distribution.
- **Known advisory:** PCB/Merge connector instances J3D1/J3D2 report “does not contain any priority bodies.” Native validation passes, but that is not proof of material overlap or electrical accuracy. This release does not silently change that model physics.

| Symptom | Resolution |
|---|---|
| `KETUPA_AUTH_REQUIRED` | Use the matching launch-v1 Runtime with a valid license and `ketupa run -sh main.py`. Renaming Python or copying environment flags cannot authorize a workload. |
| `pcb_netlist ... not found: [managed resource]` | This update omits workbooks. Run `ketupa run -sh main.py -- preprocess serdes all -- --force` first. `preprocess=False` does not regenerate missing files. |
| Native `.so` missing/import error | Use the complete directory on CPython 3.12 x86_64; this build is not for Windows or another Python ABI. |
| Extracta path/version not identified | Correct the Cadence path in `cds_env`, confirm vendor licensing, and run `doctor`. |
| `/var/lib/openketupa-license/...` permission denied | Ask the administrator to restore appropriate group/read/traverse permissions. Do not use `chmod 777` or bypass licensing. |
| Memory pressure | Use `--max-workers 1` and inspect the workload with `--dry-run` first. |
| `CONFIG NOTE ... TBD` | The electrical criterion is not approved; do not report compliance PASS. It does not necessarily prevent Mode 0 building. |

## 8. License and protection boundary

**Mandatory licensed-launch policy:** both source and native distributions require a valid licensed `ketupa` launch for the protected modeling core. Direct `python main.py`, even with identical interpreter/dependency versions, is not an authorized launch method. The system broker verifies kernel process identity, the trusted native supervisor and live license leases. Workers inherit authorization through actual process ancestry, not copyable environment tokens. Each protected `.so` has an independent native check. Preprocessing scripts remain editable. Editable source checks can be changed or removed; source protection is not represented as tamper-proof.

The matched combination is **Demo v1.0.1 / Runtime product version 1.0.0 / cp312 / ketupa-launch-v1**. The exact Runtime build ID is recorded in the release's `payload/MANIFEST.json`. Do not mix the new core with an older Runtime. Protection does not guarantee resistance to administrator access, native debugging, memory inspection, loader injection or binary patching, nor absolute irreversibility.

This is a **publicly downloadable proprietary Demo with a closed native core**. The [Proprietary Evaluation License](LICENSE) permits learning, research, internal non-production evaluation, and changes to exposed scripts/configuration for those purposes. Commercial production, paid delivery, hosted service use, or redistribution of modified versions requires written permission from the author. GitHub identifies the custom license as “Other”; it is not MIT, GPL, or another OSI-approved license.

Native compilation, stripped symbols, and integrity checks increase reverse-engineering cost, but **they are not cryptographic encryption and cannot guarantee absolute secrecy or irreversibility**. Users can inspect their inputs, parameters, logs, and generated projects. A public Git repository cannot hide anything committed to its history. Never commit license files, API keys, private designs, or core build source. Ansys and Cadence names and trademarks belong to their respective owners; no vendor certification, endorsement, or affiliation is implied.
