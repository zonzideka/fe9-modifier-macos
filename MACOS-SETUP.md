# 苍炎的轨迹 动态修改器 — macOS 移植

源代码出处：原作者 (PySide6 + dolphin-memory-engine)。
本目录是为 macOS (Apple Silicon) 重新构建的版本。

## 已完成的改动

| 改动 | 文件 | 说明 |
|---|---|---|
| 新增 macOS spec | `PoR-macos.spec` | PyInstaller 配置，目标 `BUNDLE` (`.app`)；移除 Windows `.dll` 排除列表 |
| PySide6 6.x 兼容 | `src/widget/customize.py` | `parent` 参数加默认值；防御性 `setMinimumHeight` 避免 cooperative MRO 在 C++ 部件未初始化时被调用 |
| `Qt.CheckState` 枚举修复 | `src/widget/bool_check.py` | PySide6 6.x 中 `checkState()` 返回枚举不再是 int；新增 `_state_int()` 转换 |
| 签名 entitlements | `entitlements.plist` | `com.apple.security.cs.debugger` + `cs.allow-jit` 等，使 `task_for_pid` 通过 |

## 一次性环境准备

### 第 1 步：给 Dolphin 加 `get-task-allow` entitlement

macOS 默认禁止跨进程读内存。需要给目标方（Dolphin）加 `get-task-allow`，**不能直接在 `/Applications/` 下改**（TCC 拒绝），所以拷一份到家目录后再签：

```bash
mkdir -p ~/Applications
cp -R /Applications/Dolphin.app ~/Applications/Dolphin.app

cat > /tmp/dolphin-debug.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.get-task-allow</key><true/>
    <key>com.apple.security.cs.allow-jit</key><true/>
    <key>com.apple.security.cs.disable-library-validation</key><true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
    <key>com.apple.security.cs.allow-dyld-environment-variables</key><true/>
    <key>com.apple.security.automation.apple-events</key><true/>
    <key>com.apple.security.device.audio-input</key><true/>
</dict>
</plist>
EOF

xattr -cr ~/Applications/Dolphin.app
codesign --force --sign - --entitlements /tmp/dolphin-debug.plist ~/Applications/Dolphin.app
```

验证：
```bash
codesign -d --entitlements - ~/Applications/Dolphin.app | grep get-task-allow
# 应该看到 [Bool] true
```

**之后请用 `~/Applications/Dolphin.app` 玩游戏**（不再用 `/Applications/Dolphin.app`）。Dolphin 配置 / 存档卡仍在原位置共享。

### 第 2 步：构建修改器 .app

```bash
cd /Users/muha/Desktop/fe9-mod/PoR-Final
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python release.py src/PoR.py
.venv/bin/pyinstaller PoR-macos.spec --noconfirm
codesign --force --deep --sign - --entitlements entitlements.plist "dist/苍炎修改器.app"
```

输出：`dist/苍炎修改器.app` (~99MB)

## 日常使用

1. 打开 `~/Applications/Dolphin.app`，加载苍炎的轨迹 ROM 开始游戏
2. 双击 `dist/苍炎修改器.app`
3. 在游戏内进入章节、能看到角色列表后，点修改器右下"刷新列表"

## 已知限制

- `task_for_pid` 受系统保护：升级 macOS 大版本后 `~/Applications/Dolphin.app` 的签名可能失效，需要重新签
- 修改器假设 NTSC-J / 中文版 ROM（内存偏移在 `src/parameter/data_setting.py` 0x802AF... 区域）。其他版本（PAL/USA）需调整偏移。
- PyInstaller bundle 启动较慢（~2-3 秒）

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 启动后弹"请先开始模拟游戏"然后退出 | Dolphin 没在跑 / 没载入游戏 / get-task-allow 没生效 | 见第 1 步重新签名 |
| 启动报 `Failed to execute script 'PoR'` | PySide6 / 第三方库版本不兼容 | 用 `.venv/bin/python -c "import sys; sys.path.insert(0, 'src'); from interface.window import Window"` 单独测试 |
| 角色列表全空 | 游戏还没载入到章节场景 | 进入章节后点"刷新列表" |

## 致谢

- 原作者：FE9 PoR-Final 动态修改器
- `dolphin-memory-engine` ([aldelaro5/Dolphin-memory-engine](https://github.com/aldelaro5/Dolphin-memory-engine))
- PySide6
