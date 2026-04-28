#!/bin/bash

# APatch Boot Image 压缩脚本 (使用 Android Image Kitchen)
# 适用于 x86_64 Linux 系统

set -e

PATCHED_IMG="meen_apatch_patched_11186_0.13.0_ticd.img"
OUTPUT_IMG="meen_apatch_compressed.img"
AIK_DIR="Android-Image-Kitchen-AIK-Linux"
PARTITION_SIZE=33554432

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== APatch Boot Image 压缩工具 (AIK) ===${NC}"

# 检查文件是否存在
if [ ! -f "$PATCHED_IMG" ]; then
    echo -e "${RED}错误: 找不到 $PATCHED_IMG${NC}"
    exit 1
fi

# 下载 Android Image Kitchen
if [ ! -d "$AIK_DIR" ]; then
    echo -e "${YELLOW}正在下载 Android Image Kitchen...${NC}"
    wget -q --show-progress https://github.com/osm0sis/Android-Image-Kitchen/archive/refs/heads/AIK-Linux.zip -O aik.zip
    unzip -q aik.zip
    rm aik.zip
    chmod +x $AIK_DIR/*.sh
    echo -e "${GREEN}✓ AIK 下载完成${NC}"
fi

cd "$AIK_DIR"

# 清理之前的解包
./cleanup.sh > /dev/null 2>&1 || true

# 解包镜像
echo -e "${YELLOW}正在解包 $PATCHED_IMG...${NC}"
./unpackimg.sh "../$PATCHED_IMG"

# 显示当前信息
echo -e "${YELLOW}当前镜像信息:${NC}"
cat split_img/*-cmdline 2>/dev/null | head -1 || true
ls -lh ramdisk/ 2>/dev/null | head -5 || true

# 修改压缩方式为 gzip -9 (最高压缩)
echo -e "${YELLOW}设置最高压缩率...${NC}"
RAMDISK_COMP=$(ls split_img/*-ramdiskcomp 2>/dev/null | head -1)
if [ -f "$RAMDISK_COMP" ]; then
    echo "gzip" > "$RAMDISK_COMP"
    echo -e "${GREEN}✓ 已设置为 gzip 压缩${NC}"
fi

# 重新打包
echo -e "${YELLOW}正在重新打包镜像...${NC}"
./repackimg.sh

# 移动输出文件
if [ -f "image-new.img" ]; then
    mv image-new.img "../$OUTPUT_IMG"
    cd ..
    
    # 检查新镜像大小
    PATCHED_SIZE=$(stat -c%s "$PATCHED_IMG")
    NEW_SIZE=$(stat -c%s "$OUTPUT_IMG")
    
    echo ""
    echo -e "${YELLOW}=== 大小对比 ===${NC}"
    printf "APatch修补:   %'d bytes (%.2f MB)\n" $PATCHED_SIZE $(echo "scale=2; $PATCHED_SIZE/1024/1024" | bc)
    printf "压缩后:       %'d bytes (%.2f MB)\n" $NEW_SIZE $(echo "scale=2; $NEW_SIZE/1024/1024" | bc)
    printf "分区大小:     %'d bytes (%.2f MB)\n" $PARTITION_SIZE $(echo "scale=2; $PARTITION_SIZE/1024/1024" | bc)
    echo ""
    
    if [ $NEW_SIZE -le $PARTITION_SIZE ]; then
        SAVED=$((PATCHED_SIZE - NEW_SIZE))
        echo -e "${GREEN}✓ 成功! 压缩节省了 $SAVED bytes${NC}"
        echo -e "${GREEN}✓ 新镜像可以刷入${NC}"
        echo -e "${GREEN}输出文件: $OUTPUT_IMG${NC}"
        echo ""
        echo "刷入命令:"
        echo "  fastboot flash boot_a $OUTPUT_IMG"
        echo "  fastboot flash boot_b $OUTPUT_IMG"
    else
        DIFF=$((NEW_SIZE - PARTITION_SIZE))
        echo -e "${RED}✗ 失败: 镜像仍然超出 $DIFF bytes${NC}"
        echo ""
        echo "建议尝试其他方案（见 fix_boot_size.md）"
    fi
else
    echo -e "${RED}错误: 重新打包失败${NC}"
    cd ..
    exit 1
fi

# 清理
echo -e "${YELLOW}清理临时文件...${NC}"
cd "$AIK_DIR"
./cleanup.sh > /dev/null 2>&1 || true
cd ..

echo -e "${GREEN}完成!${NC}"
