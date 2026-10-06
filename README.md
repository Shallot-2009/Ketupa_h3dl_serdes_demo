# Ketupa H3DL SerDes Demo

**PCB · Package · PCB–Package co-modeling**

**Linux x86_64 | CPython 3.12 | Native core | v1.0.1**

[简体中文（当前）](README.md) | [English](README_EN.md) | [许可证](LICENSE)

面向 112G/224G SerDes 通道的 HFSS 3D Layout 自动建模 Demo：以同一组设计输入运行 PCB、PKG 或 Merge 工作流。名称中的速率是 Demo 应用场景，不代表已完成相应速率的电气合规验证。

**作者：** Asenjo.HB.L

**地点：** China · Shanghai

**联系方式：** asenjoaupa@gmail.com · 3405802009@qq.com

**许可：** Proprietary Evaluation License（公开分发、闭源原生核心，不是开源许可证）

![HFSS 3D Layout — SerDes PCB–PKG Merge model, RX0 top view](assets/hfss-serdes-merge.jpg)

*真实工程视图：AEDT 2026 R1，`serdes_merge_SDS_RX0_CHIP1`，RX0。该图于 2026-10-06 从已保存工程直接导出，是布局视图，不是场分布图或求解结果。*

## 快速开始

本修订必须使用 [配套 launch-v1 Linux Runtime 升级包](https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo/releases/tag/serdes-v1.0.1-launch-v1)。约 4.5 MiB 的增量包以现有 Runtime 1.0.0 构建 `20261006T120047Z` 为基础，生成的每个文件与已验收完整 Runtime 逐项哈希一致，不删减功能。旧版 Runtime 即使同为 Python 3.12，也必须升级授权接口。许可证单独获取，本次包不附带许可证或激活数据。

```bash
sha256sum -c Ketupa-Runtime-1.0.0-launch-v1-cp312-update.tar.gz.sha256
tar -xzf Ketupa-Runtime-1.0.0-launch-v1-cp312-update.tar.gz
cd Ketupa-Runtime-1.0.0-launch-v1-cp312-update
sudo python3 -I runtime_update.py --user "$USER" --check-only
sudo python3 -I runtime_update.py --user "$USER"
ketupa license machine
# 仅新机器首次激活；已有有效许可证不需要重新激活。
sudo ketupa license activate /absolute/path/to/your-authorized.lic --mac YOUR_MAC
ketupa license status
```

**尚未安装 Runtime 的新机器：**先从 [基础 Runtime 1.0.0](https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo/releases/tag/runtime-v1.0.0) 下载 `Ketupa-Runtime-1.0.0-Linux-x64.tar.gz`，核对 SHA-256 为 `4324c26b0d6e47da63892eef59a910c0f8b7bf66388799171245a3dd1d170b65`，然后安装，再执行上面的增量升级：

```bash
tar -xzf Ketupa-Runtime-1.0.0-Linux-x64.tar.gz
sudo mkdir -p /home/EDA
sudo ./Ketupa-Runtime-1.0.0-Linux-x64/install /home/EDA/openketupa-runtime-linux --add-path
```

升级器先组装并逐文件校验完整环境，再替换安装，保留旧 Runtime 备份和已有激活数据。它拒绝不匹配的基线和其他安装拥有的服务。此处 `python3` 仅运行公开安装器，不能用于绕过项目授权。

Demo 位于 `serdes_linux/`，按下文配置 `script/extractors/cds_env` 后运行：

```bash
cd serdes_linux
ketupa run -sh main.py -- doctor
ketupa run -sh main.py -- preprocess serdes all -- --force
ketupa run -sh main.py -- --dry-run
ketupa run -sh main.py
```

> 试用许可仅用于本 Demo 评估，使用即表示接受仓库 [LICENSE](LICENSE)。工作流会调用 Ansys、Cadence 等第三方 EDA，用户须自行安装并确认拥有合法的软件及 EDA 许可；Ketupa 试用许可不包含第三方 EDA 许可。

> 当前 Demo 要求 **Linux x86_64、CPython 3.12.15、ketupa-launch-v1**。默认 Runtime 安装到 `/home/EDA/openketupa-runtime-linux`；系统安装器使用 Python 3.11+，项目建模只能经合法授权的 `ketupa` 启动。新增用户组后需重新登录。Windows 安装包不在本次更新范围，不能加载 Linux `.so`。

## 中文使用指南

### 1. 项目定位与交付内容

本仓库交付 Linux 原生 Demo，保留主入口和预处理脚本的可编辑性。`lib/`、`modules/` 和 `resource/` 使用 142 个 CPython 3.12 原生 `.so` 扩展，每个模块独立进行原生授权检查，内部模板/配置随核心提供；不附核心 Python 源码、编译中间文件、许可证、历史仿真结果或独立 docs。

```text
Ketupa_h3dl_serdes_demo/
├── README.md                     中文完整使用说明（GitHub 主页面）
├── README_EN.md                  English guide
├── LICENSE                       专有 Demo 评估许可
├── SHA256SUMS                    发布文件校验清单
├── assets/                       实际 HFSS 视图与参数化结构说明图
└── serdes_linux/                进入此目录运行
    ├── main.py                   场景、输入、模式、并发配置
    ├── input/
    │   ├── PCB/                  BRD、叠层；网络/放置 Excel 首次运行时生成
    │   ├── PKG/                  SIP/AEDB、叠层；网络 Excel 首次运行时生成
    │   └── Connector/            连接器 A3DCOMP
    ├── script/                   开放的提取、分类、预处理代码
    │   └── extractors/cds_env    首次部署的三个工具路径
    ├── modules/                  原生入口与三个 workflow
    ├── lib/                      原生建模核心
    └── resource/                 原生资源与模型策略
```

Demo 的 PCB/PKG 版图、叠层和连接器文件保留。2026-10-07 的 main 分支更新不附三份 Excel 及其来源记录，首次建模前必须预处理生成；`main.py`、142 个原生扩展与 Runtime ABI 不变。第三方 EDA 安装及有效授权需自行准备。本包不包含其他九种工作流，也不提供 Windows `.pyd`。历史 Release 标签及附件是固定快照，不等同于当前 main 分支。

### 2. 环境要求

| 项目 | 要求与边界 |
|---|---|
| 平台 | Linux x86_64、兼容 glibc；非 Windows、ARM、PyPy 或 Alpine/musl 包 |
| Python ABI | **CPython 3.12**，建议使用现有 Ketupa 运行环境，不要直接更换系统 Python |
| 启动器 | 配套 `ketupa-launch-v1` Runtime 与有效许可证；安装包见本修订 Release |
| EDA | Ansys Electronics Desktop / HFSS 3D Layout；Cadence SPB Extracta/Report 用于 BRD/SIP 导入或预处理 |
| Python 依赖 | Ketupa 环境中的 `openpyxl`、`numpy`、`cryptography`、`pyedb`、`psutil` 等；由 `doctor` 检查 |
| 资源 | 依据当前可用 CPU/内存限制并发；本地证据来自约 30 GB 内存主机，不是所有模型的最低内存保证 |
| 版本证据 | AEDT **2026 R1** 已执行建模与原生设计检查；存在 2025/2026 兼容路径，但本包没有 2025 实机回归证据 |

先确认 `ketupa --help` 可用。未安装启动器时请联系作者取得适配的运行环境；不要把无关的同名软件当作本项目依赖。

### 3. 下载与首次配置

```bash
git clone https://github.com/Shallot-2009/Ketupa_h3dl_serdes_demo.git
cd Ketupa_h3dl_serdes_demo
sha256sum -c SHA256SUMS
cd serdes_linux
```

也可使用 GitHub **Code → Download ZIP**，完整解压后进入 `serdes_linux/`。不要只下载 `main.py`，不要漏掉版图、`.aedb` 内容或子目录中的原生扩展；Excel 按下文首次预处理生成。

首次部署只需按实际安装位置编辑 `script/extractors/cds_env` 的三个路径：

```ini
PYTHON_EXE=/home/EDA/openketupa-runtime-linux/runtime/bin/python3
CADENCE_TOOLS_BIN=/your/cadence/tools/bin:/your/older/cadence/tools/bin
KETUPA_ANSYSEDT=/your/ansys/AnsysEM
```

包内 `/home/EDA/...` 是示例安装路径。`PYTHON_EXE` 必须指向配套 Runtime 的解释器，不能改为依赖相同的任意 Python。多个 Cadence 目录按优先级排列，用 `:` 分隔。这里不填写许可证或 API 密钥；厂商许可证按各自正常安装流程配置。完成首次工具路径配置后，日常选场景和换输入只改 `main.py`。

### 4. 推荐运行顺序

以下所有命令均在 `serdes_linux/` 下执行。`--` 将后续参数传给项目入口。

```bash
ketupa run -sh main.py -- list
ketupa run -sh main.py -- doctor
ketupa run -sh main.py -- audit
ketupa run -sh main.py -- preprocess serdes all -- --force
ketupa run -sh main.py -- --dry-run
ketupa run -sh main.py
```

| 命令 | 做什么 | 不代表什么 |
|---|---|---|
| `list` | 列出 PCB、PKG、Merge | 不建模 |
| `doctor` | 检查依赖、工具、授权可达性及资源环境 | 不保证任意工程成功 |
| `audit` | 检查架构、配置、端口约定及原生核心完整性 | 不替代 AEDT 原生检查 |
| `--dry-run` | 校验输入，列出网络组、任务与并行计划 | 不启动建模/求解 worker，无仿真结果 |
| 无额外参数 | 执行 `main.py` 保存配置 | 默认 **Merge、Mode 0**，仅建模保存 |

终端最上方 `Layout input: not provided` / `script default` 是外层 Ketupa CLI 的参数摘要；不等于 `main.py` 中没有输入。请看后续实际选中的工作流、文件和网络组。`[managed resource]` 是路径遮蔽文本，不是应创建的文件名。

### 5. 只改 main.py 选择任意组合

修改 `SELECTIONS`，三种工作流共有七种非空组合：

| 组合 / Combination | `SELECTIONS` |
|---|---|
| PCB | `(("serdes", "pcb"),)` |
| PKG | `(("serdes", "pkg"),)` |
| Merge | `(("serdes", "merge"),)` |
| PCB + PKG | `(("serdes", "pcb"), ("serdes", "pkg"))` |
| PCB + Merge | `(("serdes", "pcb"), ("serdes", "merge"))` |
| PKG + Merge | `(("serdes", "pkg"), ("serdes", "merge"))` |
| 全部 / All | `(("serdes", "all"),)` |

Merge 自行导入 PCB 和 PKG，**不要求先跑独立 PCB/PKG**。组合中的工作流依次执行，每个工作流内部按网络组并行。

`INPUTS["default"]` 定义共用输入；只有特定场景不同才添加覆盖，例如：

```python
INPUTS["serdes-pkg"] = {
    "pkg_netlist": PKG_DIR / "netlist/another_design.xlsx",
}
```

网络/放置字段可指向精确 Excel/CSV 或含匹配表格的目录；版图和叠层应指向真实文件，`.aedb` 应指向含 `edb.def` 的目录。版图、叠层、网络和放置数据必须对应同一设计。随包默认使用 PCB BRD 与 PKG AEDB，另保留 PKG SIP 输入。

`RUN_OPTIONS` 的主要设置：

| 设置 | 用途 |
|---|---|
| `mode: 0` / `mode: 1` | 0 建模保存；1 建模、求解及对应导出 |
| `dry_run: True` | 只校验和规划 |
| `prefix: "ALL"` | 选择所有匹配网络 |
| `corps: "\\"` | 不增加额外合组 |
| `parallel_groups: ""` | 全部匹配组；单组示例为 `"ALL\|SDS_RX0"`（实际字符串不含转义符） |
| `max_workers: None` | 使用自动策略；改为 `1` 可限制资源占用，仍有内存保护 |
| `preprocess: False` | 使用已在本机生成的 Excel，不会自动补表；首次运行须先执行下面的预处理命令 |
| `preprocess_entry: "sh"` | Linux 预处理入口 |
| `signoff: False` | 默认不自动生成签核汇总；TBD 指标不得宣称电气 PASS |

不改 main 的临时命令（显式命令行参数覆盖保存配置）：

```bash
ketupa run -sh main.py -- run serdes pcb --mode 0
ketupa run -sh main.py -- run serdes pkg --mode 0
ketupa run -sh main.py -- run serdes merge --mode 0
ketupa run -sh main.py -- run-many serdes-pcb serdes-pkg --dry-run
ketupa run -sh main.py -- run-all --dry-run
ketupa run -sh main.py -- --max-workers 1 --parallel-groups 'ALL|SDS_RX0'
ketupa run -sh main.py -- run --help
```

### 6. 数据预处理与端口边界

**2026-10-07 更新验证：**无 Excel 的干净副本成功预处理；audit、doctor、全部七种组合 dry-run 通过；AEDT 2026 R1 下 PCB、PKG、Merge 各完成 RX/TX 两组 Mode 0 建模，共 6 成功、0 失败；直接 Python 被授权检查拒绝。未执行 Mode 1 求解或电气签核。预处理的 shared-memory IPC 兼容提示回退普通 gRPC 后完成。新增的 `03_Verify.py`、`04_Publish.py` 按本地原样同步，帮助入口已检查；其中维护者构建功能需要源码工程和编译依赖，本次未重新编译核心。

本次分发不附三份 Excel 及其来源记录。首次运行必须从随包版图生成 PCB 网络表、PCB 放置表和 PKG 网络表，再执行 dry-run 和建模。更换版图后必须更新输入并检查分类结果，不能沿用另一份设计的表。

```bash
ketupa run -sh main.py -- preprocess serdes all -- --force
ketupa run -sh main.py -- --dry-run
# 或在执行保存的工作流之前自动预处理：
ketupa run -sh main.py -- --preprocess-first
```

`script/01_Netlist.*` 负责网络提取分类，`02_Placement.*` 负责 PCB 放置，`extractors/` 保留 Cadence 兼容和命名规则。可扩展企业命名规则；不保证任意未知命名都能无歧义自动识别。可选 LLM 入口不是默认运行依赖，也不应在没有授权时发送设计数据到外部服务。

| 模式 | 最终端口边界 | 裁剪距离 |
|---|---|---|
| PCB | BGA solder ball → PCB connector | PCB `3.5mm` |
| PKG | DIE C4 bump → BGA solder ball | PKG `1mm` |
| Merge | DIE C4 bump → PCB connector，无中间 BGA 端口 | PCB `3.5mm` / PKG `1mm` |

C4 为 Flip-Chip / chip-down，沿用库参数：**高度 60 µm、半径 65 µm**（`sbr`，不要将历史文件名 `d65um` 当作直径证据）。BGA 使用 **0.5 mm pitch** 库，pitch 不等于球径。Merge 保留 C4 参考面、取消中间 BGA 端口与受控 BGA PEC 辅助面；使用 Placement 的上下表面和旋转信息对齐。PKG 的 AUTO 参考网策略保留实际存在的 VSS/AGND，不擅自短接独立地网。

#### 完整工程图组：Merge、PCB、PKG、连接器、bump 与 ball

以下图像全部直接显示，便于在 GitHub 主页面检查模型边界与互连结构。前三张布局图和连接器图均从已保存的 AEDT 2026 R1 工程导出；最后一张左侧是依据发布参数绘制的侧向结构示意，右侧是同一连接器工程的实际 HFSS 正交视图。它们都不是场分布图或已求解结果。

![HFSS 3D Layout — SerDes PCB–PKG Merge model, RX0 top view](assets/hfss-serdes-merge.jpg)

**Merge（实际工程顶视图）** — `serdes_merge_SDS_RX0_CHIP1`。通道边界为 DIE C4 bump → PCB 连接器；Merge 不在中间 BGA solder ball 上保留端口。

![HFSS 3D Layout — SerDes PCB model, RX0 top view](assets/hfss-serdes-pcb.jpg)

**PCB（实际工程顶视图）** — `serdes_pcb_SDS_RX0_CHIP1`。显示 BGA solder ball → PCB 连接器的差分通道布局。

![HFSS 3D Layout — SerDes package model, RX0 top view](assets/hfss-serdes-pkg.jpg)

**PKG / 封装（实际工程顶视图）** — `serdes_pkg_SDS_RX0_DIE_1`。显示 chip-down DIE、C4 bump 侧端口边界与 BGA solder ball 侧端口边界对应的封装布局。

![HFSS 3D Component — 1.0 mm 110 GHz precision coaxial connector](assets/hfss-serdes-connector-3d.jpg)

**SMA 类连接器（实际 HFSS 3D Component 视图）** — Demo 文件实际为 `Stripline_connector_1p0mm_110GHz.a3dcomp`，即 **1.0 mm / 110 GHz 精密同轴连接器模型**；“SMA 类”仅描述外形与用途，不应将它误写成标准 SMA 型号。

![SerDes side structure with C4 bump, BGA solder ball, PCB and coaxial connector](assets/hfss-serdes-side-structure.png)

**侧向结构总览** — 左侧参数化示意明确展示 chip-down DIE、C4 bump（半径 65 µm、高度 60 µm）、PKG substrate、0.5 mm pitch BGA solder ball、PCB stackup 与 Merge 信号边界；右侧是实际 HFSS 连接器侧视截图。垂直比例为便于观察而放大，不可用于从像素反推物理尺寸。

### 7. 输出位置、验收与排错

运行时在 `serdes_linux/output/` 创建任务记录和结果，发布仓库不包含旧 output：

```text
output/
├── tasks/<run_id>/                          输入、状态、事件记录
└── serdes_{pcb,pkg,merge}/<run_id>/
    ├── h3d_projects/                       .aedt + 配套 .aedb
    │   └── parallel_workers/               各网络组的独立工程
    ├── logs/                               工作流/网络组/资源日志
    └── results/                            求解/导出阶段的结果（按阶段生成）
```

在 AEDT 中打开**当前 run_id 的 `.aedt`**，保留其关联 `.aedb` 及嵌入组件。网络组的实际工程可按 `h3d_projects/models.json` 定位；不要把 `input` 原版图、cutout 中间工程或旧任务当作最终通道。Mode 0 不含新求解结果；Mode 1 需要可用的 solver 授权和足够资源。手动求解后可显式导出：

```bash
ketupa run -sh main.py -- export serdes merge --project /absolute/path/channel.aedt
```

**验证范围（2026-10-06）：**

- 原生核心 142 个 `.so`；无核心 `.py/.pyc`。源码/原生授权组件 51 项测试通过。
- PCB/PKG/Merge 七种组合 dry-run 通过，迁移到本仓库 `serdes_linux/` 后审计和输入检查通过。
- AEDT 2026 R1 三场景各 RX0、TX0 的 Mode 0 建模成功；保存工程的四端口属性及顺序与对应源码结果一致；重新打开六个工程后 `ValidateCircuit()` 均返回 `1`。这不是求解或电气精度证明。
- 11 项实际启动/并行测试通过：合法授权成功、同解释器直接 Python 拒绝、伪造环境标志拒绝、三个并行子进程可用、直接加载原生核心模块拒绝。缺失/无效格式许可证在隔离系统 broker 中拒绝；签名过期/错误机器等覆盖来自合成组件测试，不冒充实机许可证签发验收。
- 原生包默认 Merge 的 RX/TX 两组通过实际 `ketupa run -sh main.py` 建模，2 成功、0 失败。早先启动器目录权限问题已不再阻止该次运行。
- **未验证：**完整 Mode 1 求解、网格收敛与电气 signoff、AEDT 2025 实机、Windows/ARM/其他 Linux 发行版组合。
- **已知提醒：**PCB/Merge 连接器 J3D1/J3D2 有 “does not contain any priority bodies” 材料覆盖提醒。原生检查通过不等于材料重叠与电气精度已验收；本版本没有自动改变该模型物理设置。

| 现象 | 处理 |
|---|---|
| `KETUPA_AUTH_REQUIRED` | 使用配套 launch-v1 Runtime 和有效许可证，通过 `ketupa run -sh main.py` 启动；重命名 Python、复制环境变量不能授权。 |
| `pcb_netlist ... not found: [managed resource]` | 本次不附 Excel；先执行 `ketupa run -sh main.py -- preprocess serdes all -- --force`。默认 `preprocess=False` 不会自动补表。 |
| 找不到 `.so` / import 失败 | 使用完整目录和 CPython 3.12 x86_64 环境；不要把本包拿到 Windows/其他 Python ABI 使用。 |
| Extracta 路径/版本无法识别 | 核对 `cds_env` 的 Cadence 路径及厂商工具授权，先执行 `doctor`。 |
| `/var/lib/openketupa-license/...` 权限拒绝 | 这是启动器的本机授权目录权限问题，由管理员恢复正确的用户组/读取/遍历权限；不要 `chmod 777` 或绕过授权。 |
| 内存紧张 | `--max-workers 1`，并先用 `--dry-run` 查看工作负载。 |
| `CONFIG NOTE ... TBD` | 电气判据尚未批准，不是可忽略后宣称合规的 PASS，也不必然阻止 Mode 0 建模。 |

### 8. 许可与保护边界

**强制授权启动声明：**源码发行版和原生发行版均要求通过有效许可证授权的 `ketupa` 启动受保护建模核心；直接 `python main.py`，即使依赖和解释器版本一致，也不是允许的启动方式。系统 broker 校验内核报告的进程身份、可信原生启动器和活动许可证租约，worker 通过真实父子进程链继承授权，不使用可复制的环境变量作为凭证。每个受保护 `.so` 内都有独立原生检查。开放的预处理脚本仍保持可编辑性；可以修改的源码检查可被修改或删除，不能据此声称源码不可绕过。

配套为 **Demo v1.0.1 / Runtime 产品版本 1.0.0 / cp312 / ketupa-launch-v1**，确切 Runtime 构建号见发行包 `payload/MANIFEST.json`。不支持混搭旧 Runtime 与新核心。保护不保证抵抗管理员权限、原生调试、内存读取、加载器注入或二进制补丁，不承诺绝对不可逆向。

本仓库是**公开可下载的专有 Demo，不是开源核心**。采用 [Proprietary Evaluation License](LICENSE)：允许学习、研究、企业内部非生产评估及修改开放脚本/配置；商业生产、付费交付或修改版分发需联系作者。GitHub 可能将自定义许可显示为 “Other” 而非标准开源许可证。

原生编译、符号裁剪与完整性校验提高逆向成本，**不等同于密码学加密，不能保证绝对保密或不可逆向**。用户可见自己的输入、参数、日志及生成工程；公开仓库不能隐藏其提交历史中的文件。不要提交许可证、API 密钥、私有设计或核心构建源码。Ansys/Cadence 等商标归各自权利人所有，本项目不表示官方认证或合作。
