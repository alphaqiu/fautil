# Cursor规则配置指南

本项目使用Cursor IDE的规则配置文件来提供多平台支持和项目特定命令。

## 配置文件概述

```
.cursor/
├── .cursorrules.common            # 所有平台通用的规则
├── .cursorrules.windows           # Windows特有规则
├── .cursorrules.macos             # macOS特有规则
├── .cursorrules.linux             # Linux特有规则
├── .cursorrules.monorepo          # 复合仓库通用规则
└── .cursorrules.monorepo.windows  # Windows复合仓库特有规则
```

## 平台特定规则

Cursor IDE会根据操作系统自动选择加载正确的规则文件:

- Windows系统加载 `.cursorrules.windows`
- macOS系统加载 `.cursorrules.macos`
- Linux系统加载 `.cursorrules.linux`

每个平台配置文件包含:
- 环境配置 (shell, 终端)
- 平台特定命令
- 文件操作适配
- 环境变量设置
- 进程管理
- 编辑器设置

## 通用规则

`.cursorrules.common` 包含与平台无关的配置:
- 仓库类型定义
- 全局规则 (行结束符、编码)
- 通用编辑器设置
- 自定义工具

## 复合仓库支持

对于复合仓库(monorepo)项目，提供了额外的配置:

- `.cursorrules.monorepo`: Unix系统(macOS/Linux)的复合仓库规则
- `.cursorrules.monorepo.windows`: Windows系统的复合仓库规则

这些配置提供了批量操作多个子项目的命令。

## 使用方法

### 常规项目命令

```bash
# 安装依赖
cursor run install_dependencies

# 运行测试
cursor run test

# 代码格式化
cursor run format

# 构建包
cursor run build_package
```

### 复合仓库命令

```bash
# 安装所有子项目依赖
cursor run install_all

# 测试所有子项目
cursor run test_all 

# 构建所有库
cursor run build_all

# 清理所有生成文件
cursor run clean_all
```

## 扩展配置

如需添加新命令或修改现有配置，请编辑相应的规则文件。对于跨平台命令，需要同时更新所有平台的规则文件。

## 配置优先级

Cursor会按以下优先级加载配置:
1. 项目根目录下的 `.cursorrules` 文件
2. 平台特定的 `.cursorrules.[platform]` 文件
3. 通用的 `.cursorrules.common` 文件

当使用复合仓库时:
1. `.cursorrules.monorepo.[platform]` 
2. `.cursorrules.monorepo` 