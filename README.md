# wuwa-auto-player

一款 **Windows 桌面悬浮球自动演奏工具**。用户把 `.mid`（MIDI 曲谱）或 `.json`（曲谱）文件拖入悬浮球，软件会将其解析并映射到电脑键盘（QWE / ASD / ZXC 三行，各对应一个八度），通过底层模拟键盘输入在游戏内自动演奏。

---

## ✨ 特性

- 🎯 **三八度硬性映射**：严格映射 Z–M（C3–B3）、A–J（C4–B4）、Q–U（C5–B5），共 21 键，超出范围自动就近挪八度。
- 📥 **拖拽导入**：直接把 `.mid` / `.midi` / `.json` 拖到悬浮球上即可导入，曲谱自动入库。
- 📤 **JSON 导入/导出**：曲谱以标准 JSON 格式存储，可随时导入恢复、导出分享。
- 🎼 **MIDI 精简解析**：和弦只留最高音 + 可配置的短音过滤，避免古筝等场景「又多又杂」。
- 🎵 **可调节的按键间隔**：在菜单里设置相邻按键的间隔（毫秒），避免游戏丢键。
- 🔁 **点按式按键模拟**：古筝有余音，按下 ≈80ms 即松开，游戏音源自然衰减不卡音。
- 🪟 **半透明预览窗**：双击悬浮球打开钢琴卷帘（Piano Roll）窗口，可视化查看当前曲谱。
- 🛡️ **管理员权限拖拽兼容**：通过 `WM_DROPFILES` + `RevokeDragDrop` 绕过 Windows UIPI 隔离，管理员模式也能拖入文件。
- 📦 **支持 PyInstaller 单文件打包**：已附 `wuwa-auto-player.spec`，一键出 `dist/wuwa-auto-player.exe`。

---

## ⌨️ 键位映射（硬性规定）

三个八度，无空缺。超出范围自动就近挪八度并写日志警告。

| 音高区 | 键盘行 | 映射 |
| :--- | :--- | :--- |
| 低音区（第 3 八度） | `ZXCVBNM` 行 | `Z=C3  X=D3  C=E3  V=F3  B=G3  N=A3  M=B3` |
| 中音区（第 4 八度 / 中央 C） | `ASDFGHJ` 行 | `A=C4  S=D4  D=E4  F=F4  G=G4  H=A4  J=B4` |
| 高音区（第 5 八度） | `QWERTYU` 行 | `Q=C5  W=D5  E=E5  R=F5  T=G5  Y=A5  U=B5` |

---

## 🧱 技术栈 & 依赖

| 模块 | 选型 | 作用 |
| :--- | :--- | :--- |
| UI 框架 | **PySide6** | 无边框 + 置顶 + 悬浮球 + 毛玻璃预览窗 |
| MIDI 解析 | **music21** | 提取音高 / 开始时间 / 持续时间 / BPM |
| 键盘模拟 | **pynput** | 底层 `key_down` / `key_up`，确保游戏识别 |
| 数据序列化 | 标准库 **json** | 标准 JSON 曲谱格式导入/导出 |
| （辅助） | **mido** | MIDI 生态辅助依赖 |
| 打包 | **PyInstaller** | 单文件 exe（含 `--collect-all music21`） |

---

## 📦 安装 & 运行（源码方式）

### 1. 环境要求

- Windows 10 / 11
- Python **3.10+**（推荐 3.12，打包已在该版本下验证）

### 2. 克隆 & 安装依赖

```powershell
git clone <your-repo-url>
cd <repo-name>
pip install -r requirements.txt
```

### 3. 运行

```powershell
python main.py
```

> ⚠️ **强烈建议右键以「管理员身份」启动**（powershell 里右键菜单选择「以管理员身份运行」，或在管理员终端执行 `python main.py`）。普通权限下也能工作，但部分游戏对全局模拟按键有 UIPI 限制，可能出现不识别。

---

## 🎮 悬浮球操作指南

悬浮球默认为蓝色小球，位于屏幕右上角，可自由拖动。

| 操作 | 效果 |
| :--- | :--- |
| **左键拖拽** | 移动悬浮球位置 |
| **左键单击** | 弹出「曲谱库」菜单，点击任意名称加载 |
| **双击** | 打开半透明「钢琴卷帘预览窗」（未加载曲谱会提示） |
| **拖入 .mid / .json** | 导入曲谱并自动存入曲谱库 |
| **右键** | 主菜单 |

### 右键菜单

- **开始演奏 / 暂停·继续 / 停止**：演奏当前加载的曲谱（启动有 3 秒倒计时，方便切回游戏）。
- **导出当前曲谱为 JSON**：弹出保存对话框，导出标准结构的 JSON 曲谱。
- **按键间隔：X ms**：设置相邻按键的最小间隔（毫秒），范围 0–5000，步进 10，默认 0。
- **精简设置**
  - **和弦精简（只留最高音）**：可勾选；默认开启，把同时出现的多个音只保留最高旋律音（古筝友好）。
  - **短音过滤阈值：X ms**：过滤时值小于该毫秒数的装饰音/碎音；设为 0 表示不过滤；默认 40ms。
- **刷新曲谱库**：重新扫描 `scores/` 目录。
- **退出**：停止演奏并关闭程序。

---

## 📄 JSON 曲谱格式

导入/导出均使用如下标准 JSON 结构：

```json
{
  "title": "千本桜",
  "bpm": 152,
  "notes": [
    {
      "key": "A",
      "start_sec": 0.0,
      "duration_sec": 0.5
    },
    {
      "key": "S",
      "start_sec": 0.5,
      "duration_sec": 0.5
    }
  ]
}
```

- `title`：曲谱名称。
- `bpm`：BPM（仅供参考；演奏以 `start_sec` 绝对秒数为准）。
- `notes`：音符数组，已按 `start_sec` 升序排列。
  - `key`：键盘上的**单个大写字母**，必须是合法映射（见「键位映射」）。
  - `start_sec`：绝对开始时间，秒。
  - `duration_sec`：音符持续秒数。默认是 **`pynput` 按下 80ms 立刻松开**（古筝余音），如需按实际时值按住，改 `main.py` 里 `PlayerEngine(hold_sec=None)`。

---

## 📁 项目结构

```
wuwa-auto-player/
├── main.py                 # 入口：权限检测、数据目录（适配 exe）、启动悬浮球
├── key_mapping.py          # 三八度映射表 + 越界/半音就近调整
├── score_model.py          # Note / Score 数据模型 + JSON 导入导出 + 格式校验
├── midi_parser.py          # music21 MIDI 解析 + 和弦精简 + 短音过滤
├── score_store.py          # 本地曲谱库：scores/ 目录按标题存 JSON
├── player_engine.py        # 演奏引擎：按键 down/up、计时、暂停/停止、gap 间隔
├── ui_float_ball.py        # 悬浮球 UI：拖动/单击菜单/双击预览/拖拽导入/右键菜单
├── ui_preview.py           # 半透明钢琴卷帘预览窗（Piano Roll）
├── win_admin_drop.py       # 管理员权限下的原生 WM_DROPFILES 拖放支持
├── requirements.txt        # 依赖清单
├── wuwa-auto-player.spec   # PyInstaller 打包配置
├── scores/                 # 本地曲谱库（导入的 JSON 存在这里）
├── build/                  # 打包中间产物（可删除）
└── dist/                   # 打包输出目录，含 wuwa-auto-player.exe
```

---

## 🏗️ 打包为可执行文件（exe）

项目已自带 `wuwa-auto-player.spec`，无需每次传冗长参数。

```powershell
# 1. 确保安装打包依赖
pip install pyinstaller

# 2. 打包（用 spec，避免每次都要传 --collect-all）
pyinstaller --clean --noconfirm wuwa-auto-player.spec
```

完成后产物位于 `dist\wuwa-auto-player.exe`，单文件，约 90~110MB。

### 打包说明

- `--collect-all music21` 已写入 spec，保证 music21 的 XML / 数据文件被正确收集；否则 exe 里解析 MIDI 会报资源找不到。
- `main.py` 中已通过 `sys.frozen` 做路径适配：exe 模式下 `scores/` 会建在 **exe 同级目录**，不会写到临时解压目录，重启电脑曲谱还在。
- `--windowed`：无命令行黑框。如需调试可临时改 spec 的 `console=True`。

### 快速重打包（第一次已经生成过 spec）

```powershell
# 改完源码后只要这一行
pyinstaller --clean --noconfirm wuwa-auto-player.spec
```

---

## ⚠️ 常见问题

### 1. 管理员运行时，拖入文件没反应？

原因：Windows 的 **UIPI 隔离**，普通权限的资源管理器（explorer.exe）默认不能向管理员窗口投递拖放。

解决：`win_admin_drop.py` 里已经做了
- `ChangeWindowMessageFilterEx` 放行 `WM_DROPFILES / WM_COPYDATA / WM_COPYGLOBALDATA`；
- `RevokeDragDrop` 撤销 Qt 的 OLE drop target；
- `DragAcceptFiles` + 原生 `WM_DROPFILES` 事件过滤器解析文件路径。

正常情况下管理员权限拖拽 **已经可用**，如果仍无效，请开 issue 附打包/运行环境信息。

### 2. 游戏里不按键 / 按键错乱？

- 请务必**以管理员身份运行**，否则全局按键模拟对某些游戏无效。
- 先在记事本里实验：开始演奏后切到记事本，应该看到字符输出（ASD/QWE/ZXC）。记事本里正常但游戏里没反应 → 是游戏防检测/权限问题。
- 可适当把「按键间隔」调到 20–50ms，缓解游戏丢键。

### 3. 音太多太杂？

右键 → **精简设置**：
- 勾选「和弦精简（只留最高音）」（默认开）。
- 把「短音过滤阈值」调高（如 60 / 80 ms）。
- 如果还不够，对和弦/和声复杂的 MIDI，建议先用 DAW（Cubase / FL / MuseScore）提取 MIDI 轨里的主旋律轨，再导入本工具。

### 4. 古筝余音被切断？

本程序默认对古筝优化：按键**按下 ~80ms 立刻松开**，余音自然衰减。

如果你的游戏/乐器是「按住才响、松键就止音」的，改 `main.py`：

```python
engine = PlayerEngine(start_delay=3.0, hold_sec=None)  # 去掉点按模式，按 duration_sec 长按
```

### 5. 导入的曲谱能在多台机器同步吗？

直接把 `scores/` 文件夹打包复制过去即可，所有导入的曲谱 JSON 都存在这里，与 exe / 源码同级。

---

## 🧪 手动冒烟测试清单

发布前可按以下流程快速自检：

1. 启动程序 → 右上角出现蓝色悬浮球（普通权限会弹权限提示，点确定）。
2. 拖拽一个 `.mid` 到球上 → 弹「[文件名] 解析成功！共提取 X 个音符」。
3. 拖拽一个合法的 `.json` 曲谱 → 弹「曲谱 [名称] 导入成功！」。
4. 左键单击悬浮球 → 弹出曲谱库菜单，点击条目 → 无异常。
5. 双击悬浮球 → 弹出半透明预览窗，横向时间轴、纵向音高、音符方块可见。
6. 右键 → 开始演奏 → 打开记事本，倒计时 3 秒后应看到对应按键字符。
7. 右键 → 精简设置 → 切换和弦精简、改短音阈值 → 重新拖入同一个 MIDI → 音符数量发生预期变化。
8. 打包生成的 exe 单独拷贝到新目录启动 → 能成功启动并创建 `scores/` 文件夹。

---

## 📝 免责声明

本工具仅用于在单机环境下播放自己合法持有的 MIDI 曲谱。请勿在任何竞技、作弊或违反游戏服务条款的场景中使用，后果自负。

---

## 📄 License

MIT
