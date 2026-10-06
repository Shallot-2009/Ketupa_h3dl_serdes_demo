# Ketupa H3DL SerDes Demo

[简体中文](README.md) | [English](README_EN.md) | [许可](LICENSE)

112G/224G SerDes 通道建模，支持 PCB、PKG 和 PCB–PKG Merge。版本 v1.0.1，Linux x86_64 / CPython 3.12。

作者：Asenjo.HB.L · China, Shanghai

联系：asenjoaupa@gmail.com · 3405802009@qq.com

## 环境与下载

需要有效授权的 Ketupa（`ketupa-launch-v1`）、Ansys Electronics Desktop 和 Cadence SPB。运行环境：Linux x86_64 / CPython 3.12。

[Runtime 安装包](https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo/releases/tag/runtime-v1.0.0)：

| 平台 | 文件 |
|---|---|
| Linux x86_64 | `Ketupa-Runtime-1.0.0-Linux-x64.tar.gz` |
| Debian / Ubuntu | `ketupa-runtime-installer_1.0.0_amd64.deb` |
| Windows x64 | `Ketupa-Runtime-1.0.0-Windows-x64-Setup.exe` |

Linux 两种格式择一；许可证单独提供。安装包原文件未变，Python 版本相同不代表授权接口兼容。已有可用的配套环境可继续使用，本次仅更新项目文件。

下载最新项目：

~~~bash
git clone https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo.git
cd Ketupa_h3dl_serdes_demo
sha256sum -c SHA256SUMS
cd serdes_linux
~~~

也可从 **Code → Download ZIP** 下载。Release 中的 Source code 是标签快照，不一定与 main 分支相同。

## 首次运行

先在 `script/extractors/cds_env` 中填写工具路径：

~~~ini
PYTHON_EXE=/home/EDA/openketupa-runtime-linux/ketupa
CADENCE_TOOLS_BIN=/your/cadence/tools/bin
KETUPA_ANSYSEDT=/your/ansys/AnsysEM
~~~

`PYTHON_EXE` 是现有配置项名称，值必须指向 `ketupa` 启动器，不要填写 `python` 或 `python3`。多个 Cadence 路径用 `:` 分隔。

以下命令均在 `serdes_linux` 目录执行。项目不附 Excel，首次运行先生成 PCB 网络表、PCB 放置表和 PKG 网络表，再检查和建模：

~~~bash
ketupa run -sh main.py -- doctor
./script/00_Preprocess.sh serdes all --force
ketupa run -sh main.py -- audit
ketupa run -sh main.py -- --dry-run
ketupa run -sh main.py
~~~

也可以分步生成网络表和放置表，无需与上面的 `00_Preprocess.sh` 重复执行：

~~~bash
./script/01_Netlist.sh serdes all --force
./script/02_Placement.sh serdes pcb --force
~~~

`serdes` 指定信号类型，`all` 同时处理 PCB 和 PKG；放置表仅需处理 `pcb`。`--force` 强制重新生成已有表格。当前版本不要使用 `serdes all YES`：`YES` 会被解析为版图文件名，强制生成请使用 `--force`。

默认执行 Merge、Mode 0，仅建模保存。后续输入未变时，直接执行 `ketupa run -sh main.py`。更换版图后重新预处理。

| 命令 | 用途 |
|---|---|
| `list` | 列出工作流 |
| `doctor` | 检查环境和工具 |
| `audit` | 检查配置与核心完整性 |
| `--dry-run` | 校验输入并列出任务，不建模、不求解 |

## 配置 main.py

修改 `SELECTIONS` 选择场景，可任意组合：

~~~python
SELECTIONS = (
    ("serdes", "pcb"),
    ("serdes", "pkg"),
    ("serdes", "merge"),
)
~~~

只运行一种时保留对应一行。Merge 不要求先运行独立 PCB、PKG。

- `INPUTS`：版图、叠层、网络表、放置表和连接器路径。表格支持文件或目录。
- `RUN_OPTIONS["mode"]`：0 建模，1 建模并求解。
- `RUN_OPTIONS["max_workers"]`：`None` 自动分配，`1` 单任务。
- `RUN_OPTIONS["preprocess"]`：默认 `False`，使用已生成的表格。

也可临时指定场景，不修改 main：

~~~bash
ketupa run -sh main.py -- run serdes pkg --mode 0
ketupa run -sh main.py -- run-many serdes-pcb serdes-merge --dry-run
ketupa run -sh main.py -- run-all --dry-run
ketupa run -sh main.py -- --max-workers 1
~~~

## 模型与端口

| 场景 | 通道边界 | 裁剪扩展 |
|---|---|---|
| PCB | BGA solder ball → 连接器 | 3.5 mm |
| PKG | C4 bump → BGA solder ball | 1 mm |
| Merge | C4 bump → PCB 连接器，无中间 BGA 端口 | PCB 3.5 mm / PKG 1 mm |

Flip-Chip / chip-down；C4 高度 60 µm、半径 65 µm；BGA pitch 0.5 mm。Merge 使用放置信息对齐，保留 C4 参考面并取消中间 BGA 辅助 PEC 面。独立的 VSS、AGND 不会被强制短接。

### 工程视图

以下布局和连接器截图来自 AEDT 2026 R1，不是求解结果。

Merge：
![Merge](assets/hfss-serdes-merge.jpg)

PCB：
![PCB](assets/hfss-serdes-pcb.jpg)

PKG：
![PKG](assets/hfss-serdes-pkg.jpg)

1.0 mm / 110 GHz 同轴连接器，并非标准 SMA 型号：
![连接器](assets/hfss-serdes-connector-3d.jpg)

AEDT 2026 R1 中 Merge 模型的侧视图，展示连接器、PCB 与封装；直接从当前模型视图导出，未进行求解：
![Merge 模型侧视图](assets/hfss-serdes-side-view.png)

## 输出

~~~text
output/
├── tasks/<run_id>/                     任务与输入记录
└── serdes_{pcb,pkg,merge}/<run_id>/
    ├── h3d_projects/                  AEDT/AEDB 工程
    ├── logs/                          运行日志
    └── results/                       求解与导出结果
~~~

打开当前任务的最终 `.aedt`，保留配套 `.aedb`。各网络组工程见 `h3d_projects/models.json`。Mode 0 不生成新的求解结果。

## 验证与排错

2026-10-07，AEDT 2026 R1：首次预处理、audit、doctor、7 种组合 dry-run 通过；三场景各 RX/TX 两组 Mode 0 建模共 6 成功、0 失败。直接 Python 启动被拒绝。未验证 Mode 1 求解、电气签核或 AEDT 2025 实机。

| 问题 | 处理 |
|---|---|
| 缺少 netlist / placement | 先执行预处理命令 |
| `KETUPA_AUTH_REQUIRED` | 核对配套 Runtime 和有效许可证，使用 ketupa 启动 |
| `.so` 导入失败 | 检查 Linux x86_64、CPython 3.12 和文件完整性 |
| Extracta 路径或版本错误 | 检查 `cds_env` 和 Cadence 授权 |
| 内存不足 | 设置 `max_workers=1` |

连接器仍有材料优先级提示；建模通过不等于电气精度或合规通过。

## 许可

本项目为专有评估 Demo，使用范围见 [LICENSE](LICENSE)。`main.py` 和 `script/` 可编辑，核心以原生扩展提供；原生编译不保证不可逆向。Ansys、Cadence 软件及其许可证需自行准备。
