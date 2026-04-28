#!/bin/bash

# APatch Boot Image 压缩脚本
# 用于解决 boot 镜像超出分区大小的问题

set -e

ORIGINAL_IMG="meen-boot.img"
PATCHED_IMG="meen_apatch_patched_11186_0.13.0_ticd.img"
OUTPUT_IMG="meen_apatch_compressed.img"
WORK_DIR="boot_work"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== APatch Boot Image 压缩工具 ===${NC}"

# 检查文件是否存在
if [ ! -f "$PATCHED_IMG" ]; then
    echo -e "${RED}错误: 找不到 $PATCHED_IMG${NC}"
    exit 1
fi

# 检查 magiskboot 是否存在
if ! command -v magiskboot &> /dev/null; then
    echo -e "${YELLOW}magiskboot 未找到，尝试从 APatch 提取...${NC}"
    
    # 方法1: 从 APatch APK 提取
    if [ -f "../app/build/outputs/apk/release/APatch-*.apk" ]; then
        APK_FILE=$(ls -t ../app/build/outputs/apk/release/APatch-*.apk | head -1)
        echo "从 $APK_FILE 提取 magiskboot..."
        unzip -j "$APK_FILE" "lib/arm64-v8a/libmagiskboot.so" -d . 2>/dev/null || true
        if [ -f "libmagiskboot.so" ]; then
            mv libmagiskboot.so magiskboot
            chmod +x magiskboot
            MAGISKBOOT="./magiskboot"
        fi
    fi
    
    # 方法2: 下载预编译版本
    if [ ! -f "magiskboot" ]; then
        echo -e "${YELLOW}正在下载 magiskboot...${NC}"
        # 从 Magisk 官方下载
        wget -q https://github.com/topjohnwu/Magisk/releases/download/v27.0/Magisk-v27.0.apk -O magisk.apk
        unzip -j magisk.apk "lib/arm64-v8a/libmagiskboot.so" -d .
        mv libmagiskboot.so magiskboot
        chmod +x magiskboot
        rm magisk.apk
        MAGISKBOOT="./magiskboot"
    fi
else
    MAGISKBOOT="magiskboot"
fi

# 验证 magiskboot
if ! $MAGISKBOOT 2>&1 | grep -q "Usage:"; then
    echo -e "${RED}错误: magiskboot 不可用${NC}"
    exit 1
fi

echo -e "${GREEN}✓ magiskboot 已就绪${NC}"

# 创建工作目录
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# 解包修补后的镜像
echo -e "${YELLOW}正在解包 $PATCHED_IMG...${NC}"
$MAGISKBOOT unpack "../$PATCHED_IMG"

# 显示当前大小
echo -e "${YELLOW}当前组件大小:${NC}"
ls -lh kernel ramdisk.cpio* 2>/dev/null || true

# 重新压缩 ramdisk (使用更高压缩率)
if [ -f "ramdisk.cpio" ]; then
    echo -e "${YELLOW}正在重新压缩 ramdisk...${NC}"
    
    # 尝试不同的压缩算法
    # 1. gzip 最高压缩
    gzip -9 -f ramdisk.cpio
    mv ramdisk.cpio.gz ramdisk.cpio.gzip
    
    # 2. lz4 高压缩
    # $MAGISKBOOT compress=lz4_hc ramdisk.cpio ramdisk.cpio.lz4
    
    # 3. xz 最高压缩 (最小但较慢)
    # $MAGISKBOOT compress=xz ramdisk.cpio ramdisk.cpio.xz
    
    # 选择最小的
    mv ramdisk.cpio.gzip ramdisk.cpio
fi

# 重新打包
echo -e "${YELLOW}正在重新打包镜像...${NC}"
$MAGISKBOOT repack "../$ORIGINAL_IMG" "../$OUTPUT_IMG"

cd ..

# 检查新镜像大小
ORIGINAL_SIZE=$(stat -c%s "$ORIGINAL_IMG")
PATCHED_SIZE=$(stat -c%s "$PATCHED_IMG")
NEW_SIZE=$(stat -c%s "$OUTPUT_IMG")
PARTITION_SIZE=33554432

echo ""
echo -e "${YELLOW}=== 大小对比 ===${NC}"
echo "原始镜像:     $(numfmt --to=iec-i --suffix=B $ORIGINAL_SIZE) ($ORIGINAL_SIZE bytes)"
echo "APatch修补:   $(numfmt --to=iec-i --suffix=B $PATCHED_SIZE) ($PATCHED_SIZE bytes)"
echo "压缩后:       $(numfmt --to=iec-i --suffix=B $NEW_SIZE) ($NEW_SIZE bytes)"
echo "分区大小:     $(numfmt --to=iec-i --suffix=B $PARTITION_SIZE) ($PARTITION_SIZE bytes)"
echo ""

if [ $NEW_SIZE -le $PARTITION_SIZE ]; then
    echo -e "${GREEN}✓ 成功! 新镜像可以刷入${NC}"
    echo -e "${GREEN}输出文件: $OUTPUT_IMG${NC}"
    echo ""
    echo "刷入命令:"
    echo "  fastboot flash boot_a $OUTPUT_IMG"
    echo "  fastboot flash boot_b $OUTPUT_IMG"
else
    DIFF=$((NEW_SIZE - PARTITION_SIZE))
    echo -e "${RED}✗ 失败: 镜像仍然超出 $(numfmt --to=iec-i --suffix=B $DIFF)${NC}"
    echo ""
    echo "建议:"
    echo "1. 检查 APatch 是否内嵌了过多 KPM 模块"
    echo "2. 尝试使用更旧的内核版本"
    echo "3. 联系 APatch 开发者反馈此问题"
fi

# 清理
# rm -rf "$WORK_DIR"
