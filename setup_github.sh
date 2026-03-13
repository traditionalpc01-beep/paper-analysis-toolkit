#!/bin/bash

# 论文分析工具包 - GitHub推送脚本
# 使用方法: ./setup_github.sh

set -e

echo "================================"
echo "论文分析工具包 - GitHub推送助手"
echo "================================"
echo ""

# 检查是否在Git仓库中
if [ ! -d .git ]; then
    echo "❌ 错误: 当前目录不是Git仓库"
    exit 1
fi

# 检查是否有远程仓库
if git remote | grep -q "origin"; then
    echo "✅ 远程仓库已配置"
    git remote -v
    echo ""
    echo "是否要推送到现有仓库? (y/n)"
    read -r answer
    if [ "$answer" = "y" ]; then
        echo "正在推送..."
        git push -u origin main
        echo "✅ 推送完成!"
        exit 0
    else
        echo "请先删除现有远程仓库: git remote remove origin"
        exit 1
    fi
fi

echo "请选择创建GitHub仓库的方式:"
echo ""
echo "1) 使用GitHub网页创建 (推荐)"
echo "2) 使用GitHub CLI (需要安装gh命令)"
echo "3) 使用Personal Access Token"
echo ""
echo "请输入选项 (1/2/3):"
read -r option

case $option in
    1)
        echo ""
        echo "📋 请按以下步骤操作:"
        echo ""
        echo "1. 在浏览器中打开: https://github.com/new"
        echo "2. 创建私有仓库:"
        echo "   - Repository name: paper-analysis-toolkit"
        echo "   - Description: PDF论文分析工具包 - 自动提取QLED器件性能数据并生成报告"
        echo "   - 选择 Private (私有)"
        echo "   - 不要勾选任何初始化选项"
        echo "   - 点击 Create repository"
        echo ""
        echo "3. 创建完成后,请输入您的GitHub用户名:"
        read -r username
        
        if [ -z "$username" ]; then
            echo "❌ 用户名不能为空"
            exit 1
        fi
        
        REPO_URL="https://github.com/${username}/paper-analysis-toolkit.git"
        
        echo ""
        echo "正在配置远程仓库..."
        git remote add origin "$REPO_URL"
        
        echo "正在推送代码..."
        git branch -M main
        git push -u origin main
        
        echo ""
        echo "✅ 推送成功!"
        echo "仓库地址: https://github.com/${username}/paper-analysis-toolkit"
        ;;
        
    2)
        # 检查gh是否安装
        if ! command -v gh &> /dev/null; then
            echo "❌ GitHub CLI未安装"
            echo "请先安装: brew install gh"
            exit 1
        fi
        
        echo ""
        echo "正在检查GitHub CLI认证状态..."
        if ! gh auth status &> /dev/null; then
            echo "请先登录GitHub CLI: gh auth login"
            exit 1
        fi
        
        echo "正在创建私有仓库并推送..."
        gh repo create paper-analysis-toolkit --private --source=. --remote=origin --push
        
        echo ""
        echo "✅ 创建并推送成功!"
        ;;
        
    3)
        echo ""
        echo "📋 使用Personal Access Token步骤:"
        echo ""
        echo "1. 访问: https://github.com/settings/tokens"
        echo "2. 点击 'Generate new token (classic)'"
        echo "3. 勾选 'repo' 权限"
        echo "4. 生成并复制token"
        echo ""
        echo "请输入您的GitHub用户名:"
        read -r username
        
        echo "请输入您的Personal Access Token:"
        read -r token
        
        if [ -z "$username" ] || [ -z "$token" ]; then
            echo "❌ 用户名和token不能为空"
            exit 1
        fi
        
        echo ""
        echo "正在创建GitHub仓库..."
        curl -X POST \
            -H "Authorization: token $token" \
            -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/user/repos \
            -d '{"name":"paper-analysis-toolkit","description":"PDF论文分析工具包 - 自动提取QLED器件性能数据并生成报告","private":true}'
        
        REPO_URL="https://${username}:${token}@github.com/${username}/paper-analysis-toolkit.git"
        
        echo ""
        echo "正在配置远程仓库..."
        git remote add origin "$REPO_URL"
        
        echo "正在推送代码..."
        git branch -M main
        git push -u origin main
        
        echo ""
        echo "✅ 推送成功!"
        echo "仓库地址: https://github.com/${username}/paper-analysis-toolkit"
        ;;
        
    *)
        echo "❌ 无效的选项"
        exit 1
        ;;
esac

echo ""
echo "================================"
echo "🎉 完成!"
echo "================================"
