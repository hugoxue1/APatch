#!/usr/bin/env python3
"""
APatch Boot Image 压缩工具 (保留 AVB 签名)
"""

import struct
import gzip
import os
import sys

PATCHED_IMG = "meen_apatch_patched_11186_0.13.0_ticd.img"
OUTPUT_IMG = "meen_apatch_compressed_with_avb.img"
PARTITION_SIZE = 33554432

# ANSI 颜色
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

def print_color(color, text):
    print(f"{color}{text}{NC}")

def parse_boot_header(data):
    """解析 boot.img 头部"""
    magic = data[0:8]
    if magic != b'ANDROID!':
        print_color(RED, f"错误: 不是有效的 Android boot 镜像")
        return None
    
    header = {
        'magic': magic,
        'kernel_size': struct.unpack('<I', data[8:12])[0],
        'kernel_addr': struct.unpack('<I', data[12:16])[0],
        'ramdisk_size': struct.unpack('<I', data[16:20])[0],
        'ramdisk_addr': struct.unpack('<I', data[20:24])[0],
        'second_size': struct.unpack('<I', data[24:28])[0],
        'second_addr': struct.unpack('<I', data[28:32])[0],
        'tags_addr': struct.unpack('<I', data[32:36])[0],
        'page_size': struct.unpack('<I', data[36:40])[0],
        'header_version': struct.unpack('<I', data[40:44])[0] if len(data) > 40 else 0,
    }
    
    return header

def align_size(size, page_size):
    """对齐到页面大小"""
    return ((size + page_size - 1) // page_size) * page_size

def compress_boot_with_avb(input_file, output_file):
    """压缩 boot 镜像并保留 AVB 签名"""
    
    print_color(YELLOW, "=== APatch Boot Image 压缩工具 (保留 AVB) ===")
    
    if not os.path.exists(input_file):
        print_color(RED, f"错误: 找不到 {input_file}")
        return False
    
    # 读取原始镜像
    print_color(YELLOW, f"正在读取 {input_file}...")
    with open(input_file, 'rb') as f:
        img_data = f.read()
    
    # 解析头部
    print_color(YELLOW, "正在解析镜像头部...")
    header = parse_boot_header(img_data)
    if not header:
        return False
    
    page_size = header['page_size']
    print_color(GREEN, f"✓ 页面大小: {page_size} bytes")
    print_color(GREEN, f"✓ 内核大小: {header['kernel_size']} bytes")
    print_color(GREEN, f"✓ Ramdisk 大小: {header['ramdisk_size']} bytes")
    
    # 计算各部分偏移
    kernel_offset = page_size
    ramdisk_offset = kernel_offset + align_size(header['kernel_size'], page_size)
    second_offset = ramdisk_offset + align_size(header['ramdisk_size'], page_size)
    
    # 计算 boot 镜像核心部分的结束位置
    if header['second_size'] > 0:
        boot_end = second_offset + align_size(header['second_size'], page_size)
    else:
        boot_end = second_offset
    
    # 提取 AVB 签名（boot 镜像之后的所有数据）
    avb_data = img_data[boot_end:]
    if len(avb_data) > 0:
        print_color(GREEN, f"✓ 检测到 AVB 签名: {len(avb_data)} bytes")
    
    # 提取各部分
    print_color(YELLOW, "正在提取镜像组件...")
    header_data = img_data[0:page_size]
    kernel_data = img_data[kernel_offset:kernel_offset + header['kernel_size']]
    ramdisk_data = img_data[ramdisk_offset:ramdisk_offset + header['ramdisk_size']]
    
    if header['second_size'] > 0:
        second_data = img_data[second_offset:second_offset + header['second_size']]
    else:
        second_data = b''
    
    # 解压并重新压缩 ramdisk
    print_color(YELLOW, "正在重新压缩 ramdisk...")
    try:
        ramdisk_uncompressed = gzip.decompress(ramdisk_data)
        ramdisk_compressed = gzip.compress(ramdisk_uncompressed, compresslevel=9)
        
        if len(ramdisk_compressed) >= len(ramdisk_data):
            print_color(YELLOW, "警告: 重新压缩后反而更大，保持原样")
            ramdisk_compressed = ramdisk_data
        else:
            print_color(GREEN, f"✓ 压缩节省: {len(ramdisk_data) - len(ramdisk_compressed)} bytes")
    except Exception as e:
        print_color(YELLOW, f"无法重新压缩: {e}，保持原样")
        ramdisk_compressed = ramdisk_data
    
    # 更新头部中的 ramdisk 大小
    new_header = bytearray(header_data)
    struct.pack_into('<I', new_header, 16, len(ramdisk_compressed))
    
    # 重新组装镜像
    print_color(YELLOW, "正在重新组装镜像...")
    new_img = bytearray()
    new_img.extend(new_header)
    
    # Kernel
    new_img.extend(kernel_data)
    new_img.extend(b'\x00' * (align_size(len(kernel_data), page_size) - len(kernel_data)))
    
    # Ramdisk
    new_img.extend(ramdisk_compressed)
    new_img.extend(b'\x00' * (align_size(len(ramdisk_compressed), page_size) - len(ramdisk_compressed)))
    
    # Second stage
    if len(second_data) > 0:
        new_img.extend(second_data)
        new_img.extend(b'\x00' * (align_size(len(second_data), page_size) - len(second_data)))
    
    # ⚠️ 注意: AVB 签名可能需要重新计算
    # 这里直接附加原始的 AVB 签名，可能会导致验证失败
    # 但如果设备禁用了 AVB 验证，则没有问题
    if len(avb_data) > 0:
        print_color(YELLOW, "正在附加 AVB 签名（可能需要重新签名）...")
        new_img.extend(avb_data)
    
    # 写入新镜像
    print_color(YELLOW, f"正在写入 {output_file}...")
    with open(output_file, 'wb') as f:
        f.write(new_img)
    
    # 大小对比
    original_size = len(img_data)
    new_size = len(new_img)
    saved = original_size - new_size
    
    print()
    print_color(YELLOW, "=== 大小对比 ===")
    print(f"APatch修补:   {original_size:,} bytes ({original_size/1024/1024:.2f} MB)")
    print(f"压缩后:       {new_size:,} bytes ({new_size/1024/1024:.2f} MB)")
    print(f"分区大小:     {PARTITION_SIZE:,} bytes ({PARTITION_SIZE/1024/1024:.2f} MB)")
    if saved > 0:
        print(f"节省空间:     {saved:,} bytes ({saved/1024:.2f} KB)")
    else:
        print(f"增加空间:     {-saved:,} bytes ({-saved/1024:.2f} KB)")
    print()
    
    if new_size <= PARTITION_SIZE:
        print_color(GREEN, "✓ 成功! 新镜像可以刷入")
        print_color(GREEN, f"输出文件: {output_file}")
        print()
        print_color(YELLOW, "⚠️ 注意: AVB 签名可能已失效")
        print("如果设备启用了 AVB 验证，可能需要:")
        print("1. 禁用 AVB 验证 (fastboot --disable-verity --disable-verification flash boot)")
        print("2. 或者使用设备密钥重新签名镜像")
        print()
        print("刷入命令:")
        print(f"  fastboot flash boot_a {output_file}")
        print(f"  fastboot flash boot_b {output_file}")
        return True
    else:
        diff = new_size - PARTITION_SIZE
        print_color(RED, f"✗ 失败: 镜像仍然超出 {diff:,} bytes")
        return False

if __name__ == '__main__':
    success = compress_boot_with_avb(PATCHED_IMG, OUTPUT_IMG)
    sys.exit(0 if success else 1)
