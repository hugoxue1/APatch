# APatch Boot 镜像大小问题解决方案

## 问题描述
- **原始镜像**: 33554432 bytes (32 MB) - 可以刷入
- **APatch修补**: 33617920 bytes (32.06 MB) - 超出分区 62 KB
- **分区大小**: 33554432 bytes (32 MB)
- **错误信息**: `FAILED (remote: 'size too large')`

## 根本原因
APatch 在修补 boot 镜像时，添加了额外的代码和数据（KernelPatch、SuperKey 等），导致镜像超出了设备 boot 分区的容量限制。

## 解决方案

### 方案 1: 使用提供的压缩脚本（推荐）

```bash
cd APatch/boot
./compress_boot.sh
```

脚本会自动：
1. 下载/提取 magiskboot 工具
2. 解包 APatch 修补后的镜像
3. 使用最高压缩率重新压缩 ramdisk
4. 重新打包镜像
5. 验证新镜像大小

### 方案 2: 手动使用 Android Image Kitchen

1. **下载 AIK**:
```bash
wget https://github.com/osm0sis/Android-Image-Kitchen/archive/refs/heads/master.zip
unzip master.zip
cd Android-Image-Kitchen-master
```

2. **解包镜像**:
```bash
./unpackimg.sh /path/to/meen_apatch_patched_11186_0.13.0_ticd.img
```

3. **重新打包（使用更高压缩）**:
```bash
# 编辑 ramdisk 压缩方式
# 在 split_img/ 目录中找到 *-ramdiskcomp 文件
echo "gzip" > split_img/*-ramdiskcomp

# 重新打包
./repackimg.sh

# 输出在 image-new.img
```

4. **验证大小**:
```bash
ls -lh image-new.img
# 应该小于 33554432 bytes
```

### 方案 3: 在 APatch 应用中重新修补

**在 APatch 应用中修补时的建议**:

1. **不要内嵌 KPM 模块**: 
   - 在修补选项中，不要选择"内嵌 KPM 模块到 boot"
   - KPM 模块应该在系统启动后动态加载

2. **检查 SuperKey 大小**:
   - 使用较短的 SuperKey（如果可配置）

3. **使用最小化配置**:
   - 只启用必需的功能
   - 禁用调试选项

### 方案 4: 修改 APatch 源码（高级）

如果你需要自己编译 APatch，可以修改压缩配置：

**位置**: `APatch/apd/src/boot.rs` 或相关文件

```rust
// 修改 ramdisk 压缩级别
let compress_level = 9; // 最高压缩

// 或者使用 xz 压缩（更小但更慢）
let compress_type = "xz";
```

### 方案 5: 联系设备厂商/ROM 开发者

如果以上方案都不行，可能需要：
1. 使用支持更大 boot 分区的 ROM
2. 修改分区表（危险，可能变砖）
3. 等待 APatch 优化镜像大小

## 临时解决方案：只刷 boot_a

如果你的设备使用 A/B 分区，可以尝试：

```bash
# 只刷 boot_a（不刷 boot_b）
fastboot flash boot_a meen_apatch_patched_11186_0.13.0_ticd.img

# 或者只刷 boot_b
fastboot flash boot_b meen_apatch_patched_11186_0.13.0_ticd.img
```

**注意**: 这样做的风险是如果一个分区损坏，系统无法回退到另一个分区。

## 验证镜像大小

```bash
# 检查镜像大小
stat -c "%n: %s bytes (%.2f MB)" *.img

# 计算差异
echo "超出大小: $((33617920 - 33554432)) bytes"
```

## 预防措施

1. **备份原始 boot**: 始终保留未修补的 boot.img
2. **测试前备份**: 刷入前完整备份系统
3. **准备救砖工具**: 准备好 fastboot 和原厂镜像

## 相关资源

- APatch GitHub: https://github.com/bmax121/APatch
- Android Image Kitchen: https://github.com/osm0sis/Android-Image-Kitchen
- Magisk: https://github.com/topjohnwu/Magisk

## 报告问题

如果这是 APatch 的 bug，建议在 GitHub 提交 issue：
- 设备型号
- 内核版本
- APatch 版本
- boot 分区大小
- 原始和修补后的镜像大小
