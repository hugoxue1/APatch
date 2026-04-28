#!/usr/bin/env python3
"""
Boot 镜像诊断工具
分析为什么 APatch 修补后无法启动
"""

import struct
import os
import subprocess

# ANSI 颜色
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def print_color(color, text):
    print(f"{color}{text}{NC}")

def extract_kernel(boot_img, output_kernel):
    """从 boot.img 提取 kernel"""
    print_color(YELLOW, f"\n=== 从 {boot_img} 提取 kernel ===")
    
    with open(boot_img, 'rb') as f:
        data = f.read()
    
    # 解析头部
    magic = data[0:8]
    if magic != b'ANDROID!':
        print_color(RED, "错误: 不是有效的 Android boot 镜像")
        return False
    
    page_size = struct.unpack('<I', data[36:40])[0]
    kernel_size = struct.unpack('<I', data[8:12])[0]
    
    print_color(GREEN, f"✓ Page size: {page_size}")
    print_color(GREEN, f"✓ Kernel size: {kernel_size:,} bytes ({kernel_size/1024/1024:.2f} MB)")
    
    # 提取 kernel
    kernel_offset = page_size
    kernel_data = data[kernel_offset:kernel_offset + kernel_size]
    
    with open(output_kernel, 'wb') as f:
        f.write(kernel_data)
    
    print_color(GREEN, f"✓ Kernel 已提取到: {output_kernel}")
    return True

def check_kernel_config(kernel_file):
    """检查内核配置"""
    print_color(YELLOW, f"\n=== 检查 {kernel_file} 配置 ===")
    
    try:
        # 使用 strings 提取可打印字符串
        result = subprocess.run(
            ['strings', kernel_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print_color(RED, "错误: 无法读取 kernel 文件")
            return
        
        lines = result.stdout.split('\n')
        
        # 查找关键配置
        configs = {
            'CONFIG_KALLSYMS': False,
            'CONFIG_KALLSYMS_ALL': False,
            'CONFIG_KALLSYMS_BASE_RELATIVE': False,
            'CONFIG_MODULES': False,
            'CONFIG_MODULE_UNLOAD': False,
            'CONFIG_MODVERSIONS': False,
        }
        
        config_values = {}
        
        for line in lines:
            for key in configs.keys():
                if line.startswith(key + '='):
                    value = line.split('=')[1]
                    config_values[key] = value
                    if value == 'y':
                        configs[key] = True
        
        print_color(BLUE, "\n内核配置:")
        for key, enabled in configs.items():
            value = config_values.get(key, 'not found')
            if enabled:
                print_color(GREEN, f"  ✓ {key}={value}")
            else:
                print_color(RED, f"  ✗ {key}={value}")
        
        # APatch 要求
        print_color(YELLOW, "\nAPatch 要求:")
        if configs['CONFIG_KALLSYMS']:
            print_color(GREEN, "  ✓ CONFIG_KALLSYMS=y (必需)")
        else:
            print_color(RED, "  ✗ CONFIG_KALLSYMS=y (必需) - 缺失!")
            print_color(RED, "    APatch 无法在此内核上工作!")
        
        if configs['CONFIG_KALLSYMS_ALL']:
            print_color(GREEN, "  ✓ CONFIG_KALLSYMS_ALL=y (强烈建议)")
        else:
            print_color(YELLOW, "  ⚠ CONFIG_KALLSYMS_ALL=y (强烈建议) - 缺失!")
            print_color(YELLOW, "    设备可能无法启动!")
        
        # 检查设备保护
        print_color(YELLOW, "\n检查设备保护机制:")
        protections = {
            'KNOX': ['KNOX', 'knox', 'RKP', 'rkp'],
            'Samsung defex': ['defex', 'DEFEX'],
            'Samsung PROCA': ['proca', 'PROCA'],
            'dm-verity': ['dm-verity', 'dm_verity', 'DM_VERITY'],
            'AVB': ['avb', 'AVB', 'android_verified_boot'],
        }
        
        found_protections = []
        for prot_name, keywords in protections.items():
            for keyword in keywords:
                if any(keyword in line for line in lines):
                    found_protections.append(prot_name)
                    break
        
        if found_protections:
            print_color(RED, "  检测到以下保护机制:")
            for prot in set(found_protections):
                print_color(RED, f"    - {prot}")
            print_color(YELLOW, "\n  这些保护机制可能导致 APatch 修补后无法启动!")
            print_color(YELLOW, "  Magisk 有针对性的 patch，但 APatch 没有。")
        else:
            print_color(GREEN, "  ✓ 未检测到已知的保护机制")
        
        # 检查内核版本
        print_color(YELLOW, "\n检查内核版本:")
        for line in lines:
            if 'Linux version' in line:
                print_color(BLUE, f"  {line}")
                break
        
        return configs
        
    except subprocess.TimeoutExpired:
        print_color(RED, "错误: strings 命令超时")
    except FileNotFoundError:
        print_color(RED, "错误: 找不到 strings 命令")
        print_color(YELLOW, "请安装: sudo apt-get install binutils")
    except Exception as e:
        print_color(RED, f"错误: {e}")

def compare_kernels():
    """对比原始和修补后的 kernel"""
    print_color(YELLOW, "\n=== 对比分析 ===")
    
    files = {
        'meen-boot.img': '原始 boot',
        'meen_apatch_patched_11186_0.13.0_ticd.img': 'APatch 修补',
        'meen_apatch_compressed.img': 'APatch 压缩',
    }
    
    results = {}
    
    for filename, desc in files.items():
        if not os.path.exists(filename):
            print_color(YELLOW, f"⚠ {filename} 不存在，跳过")
            continue
        
        kernel_file = f"kernel_{desc.replace(' ', '_')}.img"
        if extract_kernel(filename, kernel_file):
            results[desc] = kernel_file
    
    # 检查每个 kernel 的配置
    for desc, kernel_file in results.items():
        print_color(BLUE, f"\n{'='*60}")
        print_color(BLUE, f" {desc}")
        print_color(BLUE, f"{'='*60}")
        check_kernel_config(kernel_file)

def main():
    print_color(BLUE, "="*60)
    print_color(BLUE, " Boot 镜像诊断工具")
    print_color(BLUE, " 分析 APatch 修补后无法启动的原因")
    print_color(BLUE, "="*60)
    
    compare_kernels()
    
    print_color(YELLOW, "\n" + "="*60)
    print_color(YELLOW, " 诊断完成")
    print_color(YELLOW, "="*60)
    
    print_color(BLUE, "\n建议:")
    print_color(BLUE, "1. 如果 CONFIG_KALLSYMS_ALL 缺失，这很可能是 bootloop 的原因")
    print_color(BLUE, "2. 如果检测到 Samsung 保护机制，APatch 可能无法工作")
    print_color(BLUE, "3. 建议使用 Magisk，它有更好的设备兼容性")
    print_color(BLUE, "4. 查看详细分析: cat APatch_vs_Magisk_分析.md")

if __name__ == '__main__':
    main()
