#!/usr/bin/env python3
"""
APatch Boot Image 压缩工具
使用 Python 直接处理 boot.img 文件
"""

import struct
import gzip
import os
import sys

PATCHED_IMG = "meen_apatch_patched_11186_0.13.0_ticd.img"
OUTPUT_IMG = "meen_apatch_compressed.img"
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
    # Android boot image header v0/v1/v2
    magic = data[0:8]
    if magic != b'ANDROID!':
        print_color(RED, f"错误: 不是有效的 Android boot 镜像 (magic: {magic})")
        return None
    
    # 解析头部字段
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
        'os_version': struct.unpack('<I', data[44:48])[0] if len(data) > 44 else 0,
        'name': data[48:64].rstrip(b'\x00').decode('ascii', errors='ignore'),
        'cmdline': data[64:576].rstrip(b'\x00').decode('ascii', errors='ignore'),
        'id': data[576:608],
        'extra_cmdline': data[608:1536].rstrip(b'\x00').decode('ascii', errors='ignore') if len(data) > 608 else '',
    }
    
    return header

def align_size(size, page_size):
    """对齐到页面大小"""
    return ((size + page_size - 1) // page_size) * page_size

def extract_and_compress_boot(input_file, output_file):
    """提取并压缩 boot 镜像"""
    
    print_color(YELLOW, "=== APatch Boot Image 压缩工具 (Python) ===")
    
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
    
    # 提取各部分
    print_color(YELLOW, "正在提取镜像组件...")
    header_data = img_data[0:page_size]
    kernel_data = img_data[kernel_offset:kernel_offset + header['kernel_size']]
    ramdisk_data = img_data[ramdisk_offset:ramdisk_offset + header['ramdisk_size']]
    
    if header['second_size'] > 0:
        second_data = img_data[second_offset:second_offset + header['second_size']]
    else:
        second_data = b''
    
    # 检测 ramdisk 压缩格式
    ramdisk_magic = ramdisk_data[0:4]
    if ramdisk_magic == b'\x1f\x8b\x08':
        print_color(YELLOW, "Ramdisk 已经是 gzip 格式，尝试重新压缩...")
        # 解压
        try:
            ramdisk_uncompressed = gzip.decompress(ramdisk_data)
            print_color(GREEN, f"✓ 解压后大小: {len(ramdisk_uncompressed)} bytes")
        except Exception as e:
            print_color(RED, f"解压失败: {e}")
            ramdisk_uncompressed = ramdisk_data
    elif ramdisk_magic[0:2] == b'\x04\x22' or ramdisk_magic[0:2] == b'\x02\x21':
        print_color(YELLOW, "Ramdisk 是 LZ4 格式")
        print_color(RED, "暂不支持 LZ4 重新压缩，保持原样")
        ramdisk_uncompressed = None
    else:
        print_color(YELLOW, f"Ramdisk 格式未知 (magic: {ramdisk_magic.hex()})")
        ramdisk_uncompressed = ramdisk_data
    
    # 重新压缩 ramdisk (使用最高压缩级别)
    if ramdisk_uncompressed:
        print_color(YELLOW, "正在使用最高压缩级别重新压缩 ramdisk...")
        ramdisk_compressed = gzip.compress(ramdisk_uncompressed, compresslevel=9)
        print_color(GREEN, f"✓ 压缩后大小: {len(ramdisk_compressed)} bytes")
        
        # 如果压缩后更大，保持原样
        if len(ramdisk_compressed) >= len(ramdisk_data):
            print_color(YELLOW, "警告: 重新压缩后反而更大，保持原样")
            ramdisk_compressed = ramdisk_data
    else:
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
    
    # Second stage (if exists)
    if len(second_data) > 0:
        new_img.extend(second_data)
        new_img.extend(b'\x00' * (align_size(len(second_data), page_size) - len(second_data)))
    
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
    print(f"节省空间:     {saved:,} bytes ({saved/1024:.2f} KB)")
    print()
    
    if new_size <= PARTITION_SIZE:
        print_color(GREEN, "✓ 成功! 新镜像可以刷入")
        print_color(GREEN, f"输出文件: {output_file}")
        print()
        print("刷入命令:")
        print(f"  fastboot flash boot_a {output_file}")
        print(f"  fastboot flash boot_b {output_file}")
        return True
    else:
        diff = new_size - PARTITION_SIZE
        print_color(RED, f"✗ 失败: 镜像仍然超出 {diff:,} bytes ({diff/1024:.2f} KB)")
        print()
        print("建议:")
        print("1. 在 APatch 应用中重新修补，不要内嵌 KPM 模块")
        print("2. 使用更旧版本的 APatch")
        print("3. 联系 APatch 开发者反馈此问题")
        return False

if __name__ == '__main__':
    success = extract_and_compress_boot(PATCHED_IMG, OUTPUT_IMG)
    sys.exit(0 if success else 1)
