# Git配置指南

为了确保在跨平台环境中代码的行结束符一致性，请遵循以下Git配置指南。

## 行结束符设置

### Windows用户

在Windows系统上，请运行以下命令：

```bash
# 在检出代码时将LF转换为CRLF，提交时将CRLF转换为LF
git config --global core.autocrlf true
```

### macOS/Linux用户

在macOS或Linux系统上，请运行以下命令：

```bash
# 在检出代码时不转换，提交时将CRLF转换为LF
git config --global core.autocrlf input
```

## 文本编码设置

为防止中文等非ASCII字符出现乱码问题，请设置：

```bash
# 设置Git显示和处理的编码
git config --global core.quotepath false
git config --global gui.encoding utf-8
git config --global i18n.commit.encoding utf-8
git config --global i18n.logoutputencoding utf-8
```

## IDE/编辑器设置

### VS Code

在VS Code中，请确保设置以下选项：

- `files.eol`: 根据平台设置，Windows上可设为`\r\n`，macOS/Linux上设为`\n`
- `files.encoding`: 设置为`utf-8`

### PyCharm

在PyCharm中，请设置：

- 文件 -> 设置 -> 编辑器 -> 代码样式 -> 行分隔符：根据平台选择
- 文件 -> 设置 -> 编辑器 -> 文件编码：设置为UTF-8

## .gitattributes文件

本项目包含一个`.gitattributes`文件，它会自动处理大多数文件类型的行尾问题。通常情况下，您不需要修改此文件。

## 处理已有问题的文件

如果您发现仓库中有行尾不一致的文件，可以运行以下命令修复：

```bash
# 检查所有文件的行尾格式
git ls-files --eol

# 修复行尾
git add --renormalize .
git status  # 查看哪些文件被修改
git commit -m "修复行结束符，确保跨平台兼容性"
``` 