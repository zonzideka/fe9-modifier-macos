# 苍炎的轨迹 动态修改器 — macOS 移植

[![python](https://img.shields.io/badge/Python-3.10+-darkcyan?logo=python&style=flat&labelColor=013243)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.11-darkcyan?logo=qt&style=flat&labelColor=013243)](https://doc.qt.io/qtforpython/)
[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-lightgrey?logo=apple)](https://apple.com)
[![Dolphin](https://img.shields.io/badge/Dolphin-5.0+-darkcyan?logo=nintendogamecube&style=flat&labelColor=013243)](https://dolphin-emu.org/)

针对 **GameCube 游戏《火焰之纹章 苍炎之轨迹》(Fire Emblem: Path of Radiance)** 的运行时（Dolphin 内存）动态修改器。

通过 [`dolphin-memory-engine`](https://github.com/aldelaro5/Dolphin-memory-engine) 直接读写 Dolphin 模拟器进程的 GameCube RAM，可在游戏运行中实时改人物属性、技能、装备、支援、金钱等。

> 本仓库是原 Windows 版的 **macOS 移植**。原版项目说明见 [README-original.md](README-original.md)。

## 功能（与 Windows 原版一致）

- ☑ 人物（替换 / 阵营 / 同行 / 等级 / 经验 / 化身）
- ☑ 能力（HP/力/魔/技/速/幸/防/魔防 当前值 + 装备加成）
- ☑ 特技（96 个 SID 隐藏特性的位图勾选）
- ☑ 道具（8 个槽：物品 + 耐久 + 装备/掉落标志）
- ☑ 支援（7 个支援对的进度）
- ☑ 武器熟练度（剑/枪/斧/弓/炎/雷/风/杖）
- ☑ 状态异常（麻痹/沉默/睡眠/狂暴/中毒）
- ☑ 行动锁定（重复行动 / 救出 / 被救）
- ☑ 战斗 / 胜利计数
- ☑ 所持金 + 奖励 EX
- ☑ **物品模板**（v1.3+ macOS 增强）：所有 189 件物品的攻/命/必/重/射程/耐久/单价 全局实时修改 — 改一次"铁剑攻击=99"，地图上所有铁剑立刻生效。读档恢复原值。
- ☑ **物品特性 / 特效**（v1.4+）：每件物品可挂 6 条特性（infinity/twice/poison/crit0/...）+ 2 条特效（fly/armor/knight/beast/dragon/...）下拉切换。例如把"铁剑"加上 `twice` 特性 → 即变为勇者剑（连击）。
- ☑ **导出 Dolphin AR 代码**（v1.5+）：把本会话所有改动序列化成 Action Replay 代码，写入 Dolphin GameSettings INI。下次启动游戏自动应用，**不需再开修改器**。
   - 跨会话持久：日志存到 `~/Library/Application Support/PoR-Modifier/profiles.json`，关掉修改器再开仍累积
   - 多 profile：可同时管理多套配置（默认 / hard-mode / 自定义），随时切换
   - 注释化：导出对话框里每行代码前有 `# 物品 IID_RAGNELL 物品_特性3` 这样的标签，看得懂改了什么
   - INI 段加 `*description` 总结，Dolphin 的 cheat 浏览器里可读

### 导出代码工作流

把不能写回 ROM 的修改（如给原本为空的特性槽加新指针）持久化的方法：

1. 在 Dolphin → Config → General **启用 Cheats**
2. 加载 GCM 进游戏内
3. 启动修改器，改字段（每次改自动写入当前 profile 日志，落盘）
4. 工具菜单 → **导出 Dolphin 代码…**
5. 弹对话框：可复制、可写入 INI（`~/Library/Application Support/Dolphin/GameSettings/GFEJ01.ini`）
6. **重新加载游戏（重启 Dolphin 或重启游戏）**，代码自动应用

> 配套工具 [fe9-editor](https://github.com/zonzideka/fe9-editor) 走另一条路 — 把"安全字段"的 RAM 改动反向重定位后写回 GCM，永久持久化。两条路径互补：unsafe 槽走 modifier→AR→INI，safe 槽走 editor→GCM。

## macOS 特别说明

macOS 默认禁止跨进程读内存（[Mach `task_for_pid` 安全模型](https://developer.apple.com/documentation/security)）。原版 Windows EXE 直接读其他进程内存即可，**macOS 必须**满足两个条件：

1. **修改器自己**：签名时带 `com.apple.security.cs.debugger` entitlement（已自动处理）
2. **Dolphin 一方**：签名时带 `com.apple.security.get-task-allow` entitlement（**需要你手动重签 Dolphin 一次**）

详细步骤见 [MACOS-SETUP.md](MACOS-SETUP.md)。一次性配好后日常用法和原版一致。

## 下载

预编译 macOS .app 见 [Releases](../../releases)。

或自行构建：
```bash
git clone <repo-url>
cd <repo>
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python release.py src/PoR.py
.venv/bin/pyinstaller PoR-macos.spec --noconfirm
codesign --force --deep --sign - --entitlements entitlements.plist "dist/苍炎修改器.app"
```

## 项目结构

```
src/                            原版 Python + PySide6 源码
├── PoR.py                      主入口
├── interface/                  各功能 tab UI
│   ├── export_codes.py         AR 代码生成 + Dolphin INI 写入 (v1.5)
│   └── export_dialog.py        导出对话框 (v1.5)
├── widget/                     可复用控件（含 customize.py / bool_check.py 的 macOS 兼容补丁）
├── parameter/
│   ├── data_setting.py         FE9 内存偏移表（0x802AF... 区段，~150 个字段）
│   ├── enum_data.py            ~2000 行的人物 / 职业 / 技能 / 物品 enum + PNG 资源映射
│   └── address_decoder.py      RAM 地址 → 人类可读标签 (v1.5)
└── structure/
    ├── value.py / text.py      数据访问基类
    └── dme_tracking.py         write_bytes wrapper + 多 profile JSON 持久化 (v1.5)
tests/                          单元测试 (v1.5+; 40 用例覆盖 dme_tracking / export_codes / decoder)
resource/                       图标 / 头像 / 武器图 PNG / QSS 样式
PoR-macos.spec                  macOS PyInstaller 配置（产 .app bundle）
entitlements.plist              修改器自身的 cs.debugger entitlement
MACOS-SETUP.md                  Dolphin 重签步骤 + 故障排查
```

跑测试：`.venv/bin/python -m unittest discover -s tests -v`

## 与 Windows 原版的差异

| 文件 | 改动 | 原因 |
|---|---|---|
| `src/widget/customize.py` | `parent` 加默认值 + 防御性 setMinimumHeight | PySide6 6.11 的 cooperative MRO 会在 C++ 部件初始化前调 super().__init__()，会触发崩溃 |
| `src/widget/bool_check.py` | `Qt.CheckState` 枚举显式转 int | PySide6 6.x `checkState()` 返回枚举不再是 int，原 dict 索引失效 |
| `PoR-macos.spec` | 新文件 | macOS .app `BUNDLE` 段；移除 Windows .dll 排除列表 |
| `entitlements.plist` | 新文件 | macOS sandbox / hardened runtime entitlements |
| `MACOS-SETUP.md` | 新文件 | Dolphin 重签流程 + 故障排查 |

## 已知限制

- 仅 macOS Apple Silicon 测试通过（`dolphin-memory-engine` 1.3.1 提供了 ARM64 wheel）
- ROM 内存偏移基于 NTSC-J / 中文版（`src/parameter/data_setting.py`）。NTSC-U / PAL 偏移不同，需要相应调整
- 升级 macOS 大版本后，`~/Applications/Dolphin.app` 的 ad-hoc 签名可能失效，需重新签

## License

MIT — 见 [LICENSE](LICENSE)。原始版权归项目原作者所有。本仓库仅添加 macOS 移植所需的文件与少量兼容性补丁。

## 致谢

- 原 Windows 版作者（见 [LICENSE](LICENSE) 与 [README-original.md](README-original.md)）
- [`dolphin-memory-engine`](https://github.com/aldelaro5/Dolphin-memory-engine) — 跨平台 Dolphin 进程内存读写库
- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython/)
