# 快速修复：APatch 镜像过大问题

## 🎯 最简单的解决方案

### 步骤 1: 在 APatch 应用中重新修补

1. 打开 APatch 应用
2. 点击"修补 Boot 镜像"
3. **重要**: 在修补选项中：
   - ❌ **取消勾选** "内嵌 KPM 模块"
   - ❌ **取消勾选** "内嵌 APM 模块"  
   - ✅ **勾选** "使用最高压缩"（如果有此选项）
4. 选择原始的 `meen-boot.img`
5. 等待修补完成
6. 导出新的修补镜像

### 步骤 2: 验证新镜像大小

```bash
ls -lh /sdcard/Download/apatch_patched_*.img
```

确保大小 **小于 32 MB** (33554432 bytes)

### 步骤 3: 刷入

```bash
fastboot flash boot_a /path/to/new_patched.img
fastboot flash boot_b /path/to/new_patched.img
fastboot reboot
```

## 🔍 为什么会变大？

APatch 修补时可能添加了：
- KPM 模块文件（IO_Redirect、feature 等）
- APM 模块
- 调试符号
- 额外的配置文件

这些应该在系统启动后动态加载，而不是打包进 boot 镜像。

## ⚠️ 如果还是太大

尝试以下方法：

### 方法 1: 使用旧版 APatch
某些旧版本可能生成更小的镜像。

### 方法 2: 手动压缩（使用我提供的脚本）
```bash
cd APatch/boot
./compress_boot.sh
```

### 方法 3: 只刷一个分区（临时方案）
```bash
# 只刷 boot_a
fastboot flash boot_a meen_apatch_patched_11186_0.13.0_ticd.img
# 忽略 boot_b 的错误
```

**风险**: 如果 boot_a 损坏，无法自动回退到 boot_b

## 📊 大小对比

| 镜像 | 大小 | 状态 |
|------|------|------|
| 原始 boot | 32.00 MB | ✅ 可刷入 |
| APatch 修补 | 32.06 MB | ❌ 超出 62 KB |
| 分区限制 | 32.00 MB | - |

## 🐛 报告给 APatch

这可能是 APatch 的一个 bug。建议在 GitHub 提交 issue：

**标题**: Boot image size exceeds partition size after patching

**内容**:
```
Device: [你的设备型号]
Kernel: [内核版本]
APatch Version: 0.13.0
Boot Partition Size: 33554432 bytes (32 MB)
Original Boot Size: 33554432 bytes
Patched Boot Size: 33617920 bytes (超出 62 KB)

Error:
fastboot flash boot_b patched.img
FAILED (remote: 'size too large')

Request: Please optimize boot image compression or provide option to exclude embedded modules.
```

GitHub: https://github.com/bmax121/APatch/issues
