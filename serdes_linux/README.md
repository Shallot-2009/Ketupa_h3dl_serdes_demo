# OpenKetupa H3DL SerDes — Linux

作者 / Author: **Asenjo.HB.L** · China · Shanghai

联系 / Contact: asenjoaupa@gmail.com · 3405802009@qq.com

版本 / Version: v1.0.1 · cp312 · ketupa-launch-v1 · 2026-10-06

许可 / License: Proprietary. 发布二进制不等于授予源码、再分发或逆向许可；使用权由作者授权。

独立的 112G/224G SerDes 工程，只包含 PCB、PKG、Merge 三种工作流。Demo 版图、叠层、Excel、连接器模型随包提供，作者已确认可公开。没有 `main_N2009.py`，不包含母项目其他九种场景。

## 1. 安装与启动 / Setup

解压后进入本目录。需要 Linux x86_64、**CPython 3.12**、Ketupa 运行环境及有效授权、Cadence Extracta/Report、Ansys Electronics Desktop。`.so` 不能用于 Windows、ARM、PyPy 或其他 Python 主次版本，也不自带 EDA 软件/许可证。

第一次在新机器上配置 `script/extractors/cds_env` 中三个路径；不要复制其他机器的许可证：

```ini
PYTHON_EXE=/your/ketupa/runtime/bin/python
CADENCE_TOOLS_BIN=/your/cadence/tools/bin:/your/older/cadence/tools/bin
KETUPA_ANSYSEDT=/your/ansys/AnsysEM
```

路径按实际安装填写；多个 Cadence 目录以 `:` 分隔。包内保留开发机路径作为示例，不保证新机器安装在同处。日常只改 `main.py`；预处理分类规则仍可在 `script/` 编辑。

```bash
ketupa run -sh main.py -- list
ketupa run -sh main.py -- doctor
ketupa run -sh main.py -- audit
ketupa run -sh main.py -- --dry-run
ketupa run -sh main.py
```

- `list`：列出三个工作流。
- `doctor`：检查 Python、Cadence、AEDT 和资源环境；干净包尚无 `output` 是正常状态。
- `audit`：结构、配置、裁剪、C4/端口约定检查；原生包另检查核心文件完整性。
- `--dry-run`：解析输入、网络分组、工作进程与资源计划，不启动 AEDT 建模或求解。
- 不加参数：执行 `main.py` 保存配置，默认 Merge、Mode 0。

若 Ketupa 提示授权权限错误，请由管理员检查服务及用户组，不要使用 `chmod 777` 或绕过授权。必须使用支持 `ketupa-launch-v1` 的合法授权 Runtime；即使环境相同，直接 `python main.py` 也会拒绝。`PYTHON_EXE` 应指向此 Runtime 的解释器。

**授权启动 / Licensed launch:** the modeling core requires a live licensed Ketupa launch. Direct Python and copied environment flags cannot authorize it. Workers are verified through kernel process identity and licensed ancestry. Every protected native module performs its own check. Source checks remain editable; native compilation is not unbreakable encryption and does not guarantee resistance to administrators, memory inspection, loader injection or binary patching.

配套 / Matched Runtime: product version 1.0.0, CPython 3.12.15, protocol `ketupa-launch-v1`; PyEDB 0.83.0, ansys-edb-core 0.3.3, ansys-api-edb 0.3.2. Exact build and checksums are in the Runtime manifest. See the repository's Chinese and English README for actual qualification scope. No Mode 1 solve, electrical signoff, AEDT 2025-machine or Windows qualification is claimed.

## 2. 只修改 main / Edit only main

七种非空组合：

| 运行场景 | `SELECTIONS` |
|---|---|
| PCB | `(("serdes", "pcb"),)` |
| PKG | `(("serdes", "pkg"),)` |
| Merge | `(("serdes", "merge"),)` |
| PCB + PKG | `(("serdes", "pcb"), ("serdes", "pkg"))` |
| PCB + Merge | `(("serdes", "pcb"), ("serdes", "merge"))` |
| PKG + Merge | `(("serdes", "pkg"), ("serdes", "merge"))` |
| 全部 / All | `(("serdes", "all"),)` |

Merge 自己导入 PCB 和 PKG，并非必须先运行两个独立场景。组合中的工作流顺序执行，每个工作流内部按网络组并行。

`INPUTS["default"]` 定义通用输入。网络/放置表可以指定文件夹或精确 Excel/CSV；版图和叠层指定实际文件，原生 `.aedb` 指向包含 `edb.def` 的目录。输入字段：

| 字段 | 含义 |
|---|---|
| `pcb_layout`, `pkg_layout` | PCB BRD；PKG SIP/MCM/AEDB 等受支持输入 |
| `pcb_stackup`, `pkg_stackup` | 对应设计叠层 XML |
| `pcb_netlist`, `pkg_netlist` | 提取分类后的网络表，必须与版图一致 |
| `pcb_placement` | PCB 元件位置、正反面和角度表 |
| `connector_3dcomp` | 连接器 A3DCOMP 模型 |

只有某场景不同才增加覆盖，例如：

```python
INPUTS["serdes-pkg"] = {"pkg_netlist": PKG_DIR / "netlist/another.xlsx"}
```

`RUN_OPTIONS`：

| 选项 | 作用 |
|---|---|
| `mode` | `0` 建模保存工程；`1` 建模、求解和导出 |
| `dry_run` | `True` 仅检查，不建模 |
| `prefix` | `"ALL"` 全选；其他值按现有筛选规则匹配 |
| `corps` | `"\\"` 不额外合组；其他值按分组规则处理 |
| `parallel_groups` | 空字符串全选；例如 `"ALL|SDS_RX0"` 选择一个组（channel|group） |
| `max_workers` | `None` 使用资源策略；正整数限制并发；仍受可用内存保护 |
| `preprocess` | 更换输入后需要重新生成表时设 `True` |
| `preprocess_entry` | Linux `"sh"` 或 `"py"` |
| `signoff` | 默认 `False`；未批准的电气指标不能判为 PASS |

明确的命令行参数覆盖保存配置：

```bash
ketupa run -sh main.py -- run serdes pcb --mode 0
ketupa run -sh main.py -- run serdes pkg --mode 0
ketupa run -sh main.py -- run serdes merge --mode 0
ketupa run -sh main.py -- run-many serdes-pcb serdes-pkg --dry-run
ketupa run -sh main.py -- run-all --dry-run
ketupa run -sh main.py -- --max-workers 1 --parallel-groups 'ALL|SDS_RX0'
ketupa run -sh main.py -- run --help
```

## 3. 预处理 / Preprocessing

Demo 已附网络/放置表，无须每次重新提取。替换版图后，应同时更新 `main.py` 输入并重新生成相应 Excel，不可沿用别的设计的表。

```bash
bash script/00_Preprocess.sh
# 交互选择 serdes、all、Y 等，按屏幕提示输入
ketupa run -sh main.py -- preprocess serdes all -- --force
```

`01_Netlist` 提取/分类网络，`02_Placement` 提取 PCB 放置数据；`extractors/` 保留可编辑的网络命名与 Cadence 兼容规则。原生 AEDB 的 PKG 可通过 PyEDB 提取。多个设计共存时请看 `--help` 并明确指定设计，不应把“任意未知命名都能自动识别”视为已保证的能力。

## 4. 几何与端口 / Geometry and ports

| 场景 | 最终通道边界 | 裁剪距离 |
|---|---|---|
| PCB | 芯片位置 BGA solder ball → J* 连接器 | `3.5mm` |
| PKG | DIE C4 bump → BGA solder ball | `1mm` |
| Merge | PKG C4 bump → PCB 连接器；无中间 BGA 端口 | PCB `3.5mm`，PKG `1mm` |

Merge 工作流的两个距离已直接写为字符串，不再引用 `PRODUCT.*_cutout_expansion`。没有改变原先的有效几何值。裁剪范围为 Hull，PCB 参考 GND；PKG AUTO 保留实际存在的 VSS/AGND，不能擅自短接两个地网。

沿用现有 C4 库：高度 `60um`，AEDT `sbr` 半径参数 `65um`，Flip-Chip / chip-down。历史文件名含 `d65um`，但**当前实际参数是半径，不是直径**；此次不改变模型尺寸。BGA 使用 `0.5mm pitch` 库，pitch 不是球径。Merge 保留 C4 参考面，清理受控的 BGA PEC 辅助面；从 Placement 读取上下表面及旋转并校验对齐。

## 5. 目录、输出与真实仿真工程 / Files and results

发布包：`main.py` 和 `script/` 为明文；`lib/`、`modules/`、`resource/` 只有原生扩展。内部 JSON、模板参数和审计事实编入扩展，不需用户编辑。`input/` 为开放 Demo。仅有本 README，不附 docs、源码备份、构建目录或旧 output。

运行时仍保留原项目输出行为，不为“黑盒”而删掉功能或运行记录：

```text
output/
  tasks/<run_id>/                 任务输入、状态、事件和版本记录
  serdes_pcb/<run_id>/            PCB 工作流
  serdes_pkg/<run_id>/            PKG 工作流
  serdes_merge/<run_id>/          Merge 工作流
    h3d_projects/                .aedt 与关联 .aedb 工程数据
      parallel_workers/         各网络组独立工程（按执行路径生成）
    results/                    Touchstone、报表、CSV/图片等（有对应阶段才生成）
    logs/                       全局、网络组日志和资源分配记录
```

不是每次都会产生上述全部文件夹。**dry-run 不产生可求解模型**。实际求解对象是本次任务中保存的对应通道 `.aedt`，并需保留同名 `.aedb`；不要拿 `input` 中的原始版图或旧 output 当作本次结果。Mode 0 工程可在 AEDT 中打开检查后手动求解；完整原生回归和电气验收是不同事情。

手动求解后显式导出，不自动猜历史“最新”工程：

```bash
ketupa run -sh main.py -- export serdes merge --project /absolute/path/channel.aedt
```

## 6. 原生保护与验收边界 / Protection and validation

本次本机验证 / Local evidence (2026-10-06)：

| 检查 | 结果与范围 |
|---|---|
| 源码语法、结构/配置审计 | 通过 |
| 原生核心检查 | 142 个 `.so`；无核心 `.py/.pyc`，剥离调试符号 |
| 授权检查 | 51 项组件测试、11 项实际启动/worker 测试；隔离 broker 拒绝缺失/无效格式许可证 |
| 配置与录制模板 | 三场景源码/原生逐项一致 |
| 场景组合 | 七种组合 dry-run 通过 |
| 分类脚本 | 旧规则、N2009、行业命名与失配拒绝的离线自检通过 |
| 实际 Mode 0 | AEDT 2026 R1，三场景各 RX0 和 TX0，源码与原生均通过合法 Ketupa 建模 |
| 保存工程对照 | 六组工程各四个端口，属性与顺序和源码结果一致 |
| AEDT 原生检查 | 重新打开六个原生工程，`ValidateCircuit()` 均返回 `1`；重新读取 PKG C4 模型通过 |
| 报表临时脚本接口 | 回执和允许方法测试通过（mock，不是求解证据） |
| 未执行 | 完整 Mode 1 求解、电气 signoff、AEDT 2025 实机回归、其他操作系统 |

已知提醒：PCB/Merge 的连接器实例 J3D1/J3D2 在 AEDT 验证中报告 “does not contain any priority bodies; may need to enable material overrides”。验证通过，但这不等于材料重叠和电气精度已经验收。本次保留原模型，没有自动启用材料覆盖。正常建模通过合法授权的 Ketupa 启动；直接 Python 仅用于预期拒绝的负向测试，不冒充建模成功。

本机发布候选采用 Cython 原生编译、去调试符号、核心哈希完整性检查。没有 `.py.kbx` 源码解密加载器，没有任意读取核心源码的接口。AEDT 必须接收的短报表宿主适配脚本会在运行时临时生成；用户能看到自己输入、参数、运行日志及工程。

**原生编译不是密码学加密，也不能保证绝对无法逆向。** `.so`、运行内存、接口和模型均可能被分析。不要将源码、`private-build`、私有备份或构建 C 文件推送到 GitHub；只发布审核后的压缩包内容。公开发布前仍需确认第三方模型再分发许可。

支持现有 AEDT 2025/2026 兼容代码路径，但只对实际执行过的版本和案例报告通过。不以结构审计、dry-run、成功编译代替完整仿真，也不保证所有未知输入百分之百一致。验收结果由发布时的独立验证记录给出；未执行项必须标为未验证。

English: This Linux x86_64 / CPython 3.12 package provides PCB, PKG and Merge SerDes workflows. Edit `main.py` for selections, inputs and run options; configure the three tool paths once. Main and preprocessing scripts stay open. Core Python implementations are compiled into native extensions, with templates/configuration embedded and integrity checks enabled. Native compilation raises the cost of reverse engineering; it is not cryptographic encryption or an absolute secrecy guarantee. Mode 0 builds, Mode 1 solves; dry-run only validates/plans. Keep AEDT/AEDB pairs together and inspect the current task's actual saved projects. Published test evidence must distinguish native interface checks from real physical/electrical acceptance.
