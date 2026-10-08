# Ketupa H3DL SerDes — Windows

v1.0.1 · Windows x64 · CPython 3.12

作者 / Author: hongbo.li · Asenjo.HB.L · China, Shanghai

联系 / Contact: asenjoaupa@gmail.com · 3405802009@qq.com

PCB、PKG、Merge 三场景。此发行版由原 Windows 工作流构建，与 `serdes_linux` 对应；原工程没有被覆盖。公共 GitHub 仅发布原生黑盒，白盒留在作者本地。使用须遵守附带 `LICENSE`。

## 1. 环境与激活 / Requirements

需要官方 Ketupa Windows x64 Runtime 1.0.0（CPython 3.12.15）、有效许可证及运行中的 OpenKetupa License Manager 服务；另外自行安装并授权 Cadence SPB 和 Ansys Electronics Desktop。Runtime 下载及公开试用 `.lic` 位于仓库的 `runtime-v1.0.0` Release。安装／首次启用系统服务需要 Windows 管理员批准，日常任务不应反复提权。

只能从匹配的官方 `ketupa.com` / `ketupa.exe` 启动。每个可执行核心模块验证运行环境和存活的授权启动链；普通 Python、仅复制环境变量或只修改 `main.py` 不能构成合法授权。运行环境二进制更新后若完整性不匹配，请使用重新匹配构建的 Demo，不要禁用检查。

`.pyd` 不能用于 Linux、ARM、PyPy 或 CPython 3.10/3.11/3.13。Linux 请进入 `serdes_linux`，使用其 `.so`。未做 Windows Server 2016/2022/2025 或所有 AEDT 版本的实机兼容认证。

## 2. 首次配置 / Configure once

修改 `script/extractors/cds_env`，示例路径必须换成自己电脑的真实安装位置：

```ini
KETUPA_LAUNCHER=C:\Program Files\OpenKetupaMK\Ketupa\ketupa.com
PYTHON_EXE=
CADENCE_TOOLS_BIN=C:\Cadence\SPB_25.1\tools\bin
```

`KETUPA_LAUNCHER` 供 EXE / BAT 启动器使用；也可由系统 `OPENKETUPA_HOME` 或 PATH 发现。`PYTHON_EXE` 是兼容项：如填写，应指向同一 Ketupa 的 `runtime\python.exe`，启动器会定位相邻 `ketupa.com`，不会直接绕过授权执行。Cadence 使用 `report.exe`；多个目录用 `;` 分隔。显式进程环境变量优先于 `cds_env`。AEDT 沿用原 Windows 引擎的安装发现；需要时配置 `KETUPA_ANSYSEDT` 指向实际 AnsysEM 安装目录。

输入只来自 GitHub Linux Demo 的公开 `input`，逐文件 SHA-256 相同。Windows 默认 PKG 输入是同目录的 SIP；Linux 默认 AEDB。保留 AEDB 文件是为了与公开输入完全对应，并不意味着 Windows SIP 预处理入口已变成 AEDB 接口。包内不附预生成 Excel，也不包含本地客户输入。

## 3. 运行 / Run

在本目录执行，路径有空格时加引号：

```bat
ketupa run -sh main.py -- list
ketupa run -sh main.py -- doctor
ketupa run -sh main.py -- preprocess serdes all -- --force
ketupa run -sh main.py -- audit
ketupa run -sh main.py -- --dry-run
ketupa run -sh main.py
```

也可双击 `script/00_Preprocess.exe`。三个 `.exe` / `.bat` 入口都通过 Ketupa 启动，不弹出新的终端窗口；双击完成／失败有提示，日志在 `output/logs/preprocessing`。`01_Netlist` 只提取网络表；`02_Placement` 只提取 PCB 放置表。

默认 `SELECTIONS=(("serdes", "Merge"),)`，Mode 0 建模保存，不求解。首次预处理成功后再建模；输入变更后重新预处理。Mode 1 才建模、求解并导出。没有求解结果时不能宣称电气签核通过。

```bat
ketupa run -sh main.py -- run serdes pcb --mode 0
ketupa run -sh main.py -- run serdes pkg --mode 0
ketupa run -sh main.py -- run serdes merge --mode 0
ketupa run -sh main.py -- run-many serdes-pcb serdes-pkg --dry-run
ketupa run -sh main.py -- run-all --dry-run
```

`main.py` 的 `SELECTIONS` 可组合三场景，支持七种非空组合；场景间顺序执行，场景内按网络组并行。`INPUTS` 是实际路径；`RUN_OPTIONS` 包含 `mode`、`prefix`、`corps`、`preprocess`、`signoff`、`parallel_groups`、`max_workers` 等。显式 CLI 输入覆盖保存值；不要把其他设计的网络表配给当前版图。

数据命名规则复用 Linux 的共同 SerDes 分类注册表；Windows 保留 `report.exe` 调用。可选规则配置与说明命令：

```bat
ketupa run -sh script/05_DataAdapter.py --help
ketupa run -sh script/05_DataAdapter.py self-test
```

适配器沿用确定性解析和审核后的资料配置；在线 LLM 只可生成待审核草稿，不自动决定运行时网络连接。Windows 不使用 Linux 专用的 Cadence 报告快照回退。

## 4. 模型与文件 / Models and files

| 场景 | 链路 | 裁剪 |
|---|---|---|
| PCB | BGA → 连接器 | 3.5 mm |
| PKG | C4 → BGA | 1 mm |
| Merge | C4 → PCB → 连接器 | PCB 3.5 mm / PKG 1 mm |

Flip-chip / chip-down；端口按原场景规则创建。C4 使用既有库的高度 60 µm、AEDT `sbr` 半径 65 µm、`sb2` 65 µm；BGA 使用 0.5 mm pitch 库，pitch 不是球径（`sbh=0.21mm, sbr=0.25mm, sb2=0.31mm`）。内部历史模块别名保留，真实参数见 `resource/demo-geometry.json`。PKG 参考网使用 AUTO，按实际网名选择参考，不人为短接 VSS / AGND。是否满足物理建模要求仍须检查生成的实际工程。

```text
input/       GitHub 公开输入，首次预处理后生成网络／放置表
lib/         共享核心、录制参数、报表与 signoff
modules/     控制器及三个 workflow
resource/    执行资源、授权、场景目录与 SerDes 配置数据
script/      公开 PY / BAT / EXE 和分类适配器
main.py      用户配置及启动接口
README.md    本说明
LICENSE      Demo 使用条款，不是激活文件
```

`output`、`release` 不随包发布，运行时生成。任务日志和结果依照原 Windows 引擎按场景／任务／网络组隔离；自动 S 参数导出与报表导出仍为独立步骤。不得把 Linux 历史 output 当作 Windows 新生成的结果。

保护方式：核心全部 Cython 原生编译为 `.pyd`，不发布核心 `.py/.pyc`、C 中间文件、调试符号或构建密钥；录制数据使用 AES-GCM 密文封装于原生模块。需要交给 AEDT 内置解释器的小型报表桥接脚本仅在运行时临时生成。**原生编译和加密封装提高分析成本，不保证无法逆向、内存提取或被管理员修改。** 校验和用于检测改动，不等同于发布者数字签名。

## 5. 验收状态 / Qualification

本次离线开发态检查：三场景白盒／原生模块配置与录制参数一致；`list/audit/doctor` 输出一致；七种选择组合及 CLI 参数解析一致；输入与 GitHub 字节一致；分类适配器正反例自检通过；核心无源码泄漏，原生文件为 AMD64 PE。最终加固包另做普通 Python 拒绝测试及交付文件校验。

**未完成项：** 本机试用 lic 已激活，但安装许可证服务的管理员请求被拒绝，因此最终加固包的正式授权正向启动、首次真实预处理、三场景 Mode 0 AEDT 建模、Mode 1 求解及电气 signoff 尚未验收。这是待实机验收版本，不是“全部仿真验证通过”的正式结论。不得沿用 Linux 的 6 项建模成功记录作为 Windows 证据。

完整性检查无需启动 EDA：`python script/03_Verify.py`。正式命令若报许可证服务未启用，请先在 License Manager 启用服务；不要通过更改权限、替换授权模块或关闭安全软件来规避校验。

English summary: Windows-native PCB/PKG/Merge demo, matching public Linux inputs and editable entry contracts. Core source is not published. Configure the installed licensed Ketupa launcher and Cadence tools, preprocess first, then dry-run/build. Offline developmental source/native parity passed; final licensed positive startup and real modeling/solving remain unqualified pending the licensing service. Compilation and AES-GCM template protection are not a guarantee against reverse engineering.
