"""
配置向导模块

提供交互式配置引导，在首次运行或配置缺失时帮助用户完成配置。
所有敏感信息仅存储在本地，不会上传到远程服务器。
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text

from paperinsight.utils.config import (
    load_config,
    save_config,
    get_nested_value,
    set_nested_value,
    validate_api_key,
    mask_sensitive_value,
    SENSITIVE_FIELDS,
)

console = Console()


class ConfigWizard:
    """
    配置向导

    引导用户完成以下配置：
    1. LLM 提供商选择和 API Key 配置
    2. MinerU 解析模式配置（可选）
    3. 其他可选配置
    """

    def __init__(self):
        self.config = load_config()
        self.config_path = Path.home() / ".paperinsight" / "config.yaml"

    def run(self, force: bool = False) -> bool:
        """
        运行配置向导。

        Args:
            force: 是否强制重新配置

        Returns:
            是否完成配置
        """
        self._show_welcome()

        # 检查是否需要配置
        if not force and self._is_llm_configured():
            console.print("\n[green]✓ 检测到已有有效配置[/green]")
            if not Confirm.ask("是否重新配置？", default=False):
                return True

        # Step 1: 选择 LLM 提供商
        provider = self._select_llm_provider()

        # Step 2: 配置 API Key
        self._configure_llm_credentials(provider)

        # Step 3: 配置 MinerU（可选）
        self._configure_mineru()

        # Step 4: 确认并保存
        return self._confirm_and_save()

    def _show_welcome(self):
        """显示欢迎信息"""
        console.print(Panel.fit(
            "[bold cyan]PaperInsight v3.0 配置向导[/bold cyan]\n\n"
            "本向导将帮助您完成以下配置：\n"
            "• LLM API（用于智能数据提取）\n"
            "• MinerU 解析器（用于 PDF 文档解析）\n\n"
            "[yellow]⚠ 所有敏感信息仅存储在本地，不会上传到服务器[/yellow]",
            title="欢迎使用",
            border_style="cyan",
        ))

    def _is_llm_configured(self) -> bool:
        """检查 LLM 是否已配置"""
        llm_config = self.config.get("llm", {})
        if not llm_config.get("enabled", False):
            return False

        provider = llm_config.get("provider", "")
        if provider == "wenxin":
            # 文心一言需要 client_id 和 client_secret
            wenxin = llm_config.get("wenxin", {})
            return bool(wenxin.get("client_id") and wenxin.get("client_secret"))
        else:
            # OpenAI/DeepSeek 需要 api_key
            return bool(llm_config.get("api_key"))

    def _select_llm_provider(self) -> str:
        """选择 LLM 提供商"""
        console.print("\n[bold]Step 1: 选择 LLM 提供商[/bold]")
        console.print("请选择您要使用的大语言模型服务：\n")

        providers = {
            "1": ("longcat", "美团 Longcat (推荐，每日刷新免费token)"),
            "2": ("deepseek", "DeepSeek (性价比高)"),
            "3": ("openai", "OpenAI GPT-4"),
            "4": ("wenxin", "百度文心一言"),
        }

        for key, (_, desc) in providers.items():
            console.print(f"  [cyan]{key}[/cyan]. {desc}")

        current = self.config.get("llm", {}).get("provider", "deepseek")
        console.print(f"\n当前选择: [yellow]{current}[/yellow]")

        choice = Prompt.ask(
            "请选择",
            choices=list(providers.keys()),
            default="1",
        )

        provider = providers[choice][0]
        set_nested_value(self.config, "llm.provider", provider)
        set_nested_value(self.config, "llm.enabled", True)

        console.print(f"[green]✓ 已选择: {provider}[/green]")
        return provider

    def _configure_llm_credentials(self, provider: str):
        """配置 LLM 凭证"""
        console.print(f"\n[bold]Step 2: 配置 {provider.upper()} API[/bold]")

        if provider == "wenxin":
            self._configure_wenxin_credentials()
        else:
            self._configure_standard_api_key(provider)

    def _configure_standard_api_key(self, provider: str):
        """配置标准 API Key（OpenAI/DeepSeek/Longcat）"""
        # 显示如何获取 API Key 的说明
        if provider == "longcat":
            console.print(
                "\n📋 LONGCAT API Key 获取步骤：\n"
                "   1. 访问 https://longcat.chat/platform/docs/zh/\n"
                "   2. 注册/登录账号\n"
                "   3. 进入「API Keys」页面创建密钥\n"
                "   4. 复制生成的 Key 粘贴到下方\n"
            )
        elif provider == "deepseek":
            console.print(
                "\n📋 DEEPSEEK API Key 获取步骤：\n"
                "   1. 访问 https://platform.deepseek.com/\n"
                "   2. 注册/登录账号\n"
                "   3. 进入「API Keys」页面创建密钥\n"
                "   4. 复制生成的 Key 粘贴到下方\n"
            )
        elif provider == "openai":
            console.print(
                "\n📋 OPENAI API Key 获取步骤：\n"
                "   1. 访问 https://platform.openai.com/\n"
                "   2. 注册/登录账号\n"
                "   3. 进入「API Keys」页面创建密钥\n"
                "   4. 复制生成的 Key 粘贴到下方\n"
            )

        # 显示当前配置（遮蔽）
        current_key = get_nested_value(self.config, "llm.api_key", "")
        if current_key:
            masked = mask_sensitive_value(current_key)
            console.print(f"\n当前已配置的 Key: [dim]{masked}[/dim]")

        # 获取 API Key
        api_key = Prompt.ask(
            f"\n请粘贴您的 {provider.upper()} API Key",
            password=True,
        )

        if not api_key.strip():
            if current_key:
                console.print("[yellow]保持使用现有 API Key[/yellow]")
                return
            else:
                console.print("[red]API Key 不能为空[/red]")
                return self._configure_standard_api_key(provider)

        # 验证格式
        is_valid, error_msg = validate_api_key(api_key, provider)
        if not is_valid:
            console.print(f"[red]验证失败: {error_msg}[/red]")
            return self._configure_standard_api_key(provider)

        # 设置 API Key
        set_nested_value(self.config, "llm.api_key", api_key.strip())

        # 询问是否配置自定义 API 端点
        current_base_url = get_nested_value(self.config, "llm.base_url", "")
        if current_base_url:
            console.print(f"当前已配置的连接地址: [dim]{current_base_url}[/dim]")

        console.print(
            "\n[bold]📡 关于\"连接地址\"(API 端点)：[/bold]\n"
            "\n"
            "  程序需要连接到 AI 公司的服务器来获取回答。\n"
            "\n"
            "  ┌─────────────────────────────────────────────────────────┐\n"
            "  │  • 默认选项：直接连接官方服务器（推荐新手使用）           │\n"
            "  │  • 如果您在国内，可能需要填写\"代理\"才能正常使用          │\n"
            "  │    （代理就像是一个\"中转站\"，帮您绕过网络限制）          │\n"
            "  │  • 如果您有代理服务，可以在这里填入代理提供的地址        │\n"
            "  └─────────────────────────────────────────────────────────┘\n"
        )

        if Confirm.ask("需要填写代理/中转地址吗？", default=False):
            if provider == "longcat":
                default_url = current_base_url or "https://api.longcat.chat/openai"
                prompt = "请输入代理/中转地址"
            elif provider == "deepseek":
                default_url = current_base_url or "https://api.deepseek.com"
                prompt = "请输入代理/中转地址"
            elif provider == "openai":
                default_url = current_base_url or "https://api.openai.com/v1"
                prompt = "请输入代理/中转地址"
            else:
                default_url = current_base_url or ""
                prompt = "请输入代理/中转地址"

            console.print("[dim]不知道填什么？请咨询您的代理服务商[/dim]")
            base_url = Prompt.ask(prompt, default=default_url)
            set_nested_value(self.config, "llm.base_url", base_url.strip())

        # 选择模型
        self._select_model(provider)

        console.print(f"[green]✓ {provider.upper()} API 配置完成[/green]")

    def _configure_wenxin_credentials(self):
        """配置文心一言凭证"""
        console.print("\n文心一言需要 Client ID 和 Client Secret")
        console.print("[dim]获取方式：https://console.bce.baidu.com/qianfan/[/dim]\n")

        # Client ID
        current_id = get_nested_value(self.config, "llm.wenxin.client_id", "")
        if current_id:
            masked = mask_sensitive_value(current_id)
            console.print(f"当前 Client ID: [dim]{masked}[/dim]")

        client_id = Prompt.ask(
            "请输入 Client ID",
            password=True,
        )

        if client_id.strip():
            set_nested_value(self.config, "llm.wenxin.client_id", client_id.strip())

        # Client Secret
        current_secret = get_nested_value(self.config, "llm.wenxin.client_secret", "")
        if current_secret:
            masked = mask_sensitive_value(current_secret)
            console.print(f"当前 Client Secret: [dim]{masked}[/dim]")

        client_secret = Prompt.ask(
            "请输入 Client Secret",
            password=True,
        )

        if client_secret.strip():
            set_nested_value(self.config, "llm.wenxin.client_secret", client_secret.strip())

        # 选择模型
        self._select_model("wenxin")

        console.print("[green]✓ 文心一言 API 配置完成[/green]")

    def _select_model(self, provider: str):
        """选择模型"""
        if provider == "openai":
            models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
            descriptions = [
                "GPT-4o - 最新旗舰模型，功能最强大",
                "GPT-4o-mini - 轻量级模型，性价比高",
                "GPT-4-turbo - GPT-4 优化版",
                "GPT-3.5-turbo - 经济实惠够用",
            ]
        elif provider == "deepseek":
            models = ["deepseek-chat", "deepseek-coder"]
            descriptions = [
                "DeepSeek Chat - 对话模型（推荐日常使用）",
                "DeepSeek Coder - 编程专用模型",
            ]
        elif provider == "wenxin":
            models = ["ernie-4.0-8k", "ernie-3.5-8k", "ernie-speed-8k"]
            descriptions = [
                "文心一言 4.0 - 最新旗舰模型",
                "文心一言 3.5 - 稳定版本",
                "文心一言 Speed - 快速响应",
            ]
        elif provider == "longcat":
            models = [
                "LongCat-Flash-Chat",
                "LongCat-Flash-Thinking",
                "LongCat-Flash-Thinking-2601",
                "LongCat-Flash-Lite",
                "LongCat-Flash-Omni-2603",
            ]
            descriptions = [
                "Flash-Chat - 高性能通用对话（推荐）",
                "Flash-Thinking - 深度思考模型",
                "Flash-Thinking-2601 - 升级版深度思考",
                "Flash-Lite - 轻量高效 MoE 模型",
                "Flash-Omni-2603 - 多模态模型",
            ]
        else:
            return

        console.print("\n请选择模型：\n")
        for i, (model, desc) in enumerate(zip(models, descriptions), 1):
            console.print(f"  [cyan]{i}[/cyan]. {desc}")

        current_model = get_nested_value(
            self.config,
            f"llm.{provider}.model",
            models[0],
        )
        current_index = models.index(current_model) + 1 if current_model in models else 1
        console.print(f"\n当前选择: [yellow]{current_model}[/yellow]")

        choice = Prompt.ask(
            "请选择",
            choices=[str(i) for i in range(1, len(models) + 1)],
            default=str(current_index),
        )

        model = models[int(choice) - 1]
        set_nested_value(self.config, f"llm.{provider}.model", model)

    def _configure_mineru(self):
        """配置 MinerU 解析器"""
        console.print("\n[bold]Step 3: 配置 MinerU 解析器（可选）[/bold]")

        # 检查 MinerU 是否已安装
        console.print(
            "MinerU 是一个高性能 PDF 解析工具，可将 PDF 转换为结构化 Markdown。\n"
            "文档: https://github.com/opendatalab/MinerU\n"
        )

        if not Confirm.ask("是否启用 MinerU 解析器？", default=True):
            set_nested_value(self.config, "mineru.enabled", False)
            console.print("[yellow]已禁用 MinerU，将使用基础 PDF 解析[/yellow]")
            return

        set_nested_value(self.config, "mineru.enabled", True)

        # 选择模式
        console.print("\nMinerU 运行模式:")
        console.print("  [cyan]1[/cyan]. 本地命令行模式（需安装 MinerU）")
        console.print("  [cyan]2[/cyan]. 云端 API 模式（需配置 Token）")

        current_mode = get_nested_value(self.config, "mineru.mode", "cli")
        console.print(f"\n当前模式: [yellow]{current_mode}[/yellow]")

        mode_choice = Prompt.ask("请选择", choices=["1", "2"], default="1")
        mode = "cli" if mode_choice == "1" else "api"
        set_nested_value(self.config, "mineru.mode", mode)

        if mode == "api":
            # 配置 API Token
            current_token = get_nested_value(self.config, "mineru.token", "")
            if current_token:
                masked = mask_sensitive_value(current_token)
                console.print(f"当前 Token: [dim]{masked}[/dim]")

            token = Prompt.ask(
                "请输入 MinerU API Token",
                password=True,
            )

            if token.strip():
                set_nested_value(self.config, "mineru.token", token.strip())

        console.print("[green]✓ MinerU 配置完成[/green]")

    def _confirm_and_save(self) -> bool:
        """确认并保存配置"""
        console.print("\n[bold]配置摘要[/bold]")
        console.print("-" * 40)

        # LLM 配置摘要
        llm_config = self.config.get("llm", {})
        provider = llm_config.get("provider", "")
        console.print(f"LLM 提供商: [cyan]{provider}[/cyan]")

        if provider == "wenxin":
            client_id = get_nested_value(self.config, "llm.wenxin.client_id", "")
            if client_id:
                console.print(f"Client ID: [dim]{mask_sensitive_value(client_id)}[/dim]")
        else:
            api_key = llm_config.get("api_key", "")
            if api_key:
                console.print(f"API Key: [dim]{mask_sensitive_value(api_key)}[/dim]")

        # MinerU 配置摘要
        mineru_enabled = get_nested_value(self.config, "mineru.enabled", False)
        console.print(f"MinerU: [cyan]{'启用' if mineru_enabled else '禁用'}[/cyan]")
        if mineru_enabled:
            mode = get_nested_value(self.config, "mineru.mode", "cli")
            console.print(f"运行模式: [cyan]{mode}[/cyan]")

        console.print("-" * 40)

        if not Confirm.ask("\n确认保存配置？", default=True):
            console.print("[yellow]配置已取消[/yellow]")
            return False

        # 保存配置
        save_config(self.config)
        console.print(f"\n[green]✓ 配置已保存到: {self.config_path}[/green]")
        console.print("[dim]注意：配置文件包含敏感信息，请勿分享或上传到公开仓库[/dim]")

        return True

    def quick_configure(self, provider: str, api_key: str, **kwargs) -> bool:
        """
        快速配置（非交互式）

        用于脚本或自动化场景。

        Args:
            provider: LLM 提供商
            api_key: API Key
            **kwargs: 其他配置项

        Returns:
            是否配置成功
        """
        try:
            # 验证 API Key
            if provider != "wenxin":
                is_valid, error_msg = validate_api_key(api_key, provider)
                if not is_valid:
                    console.print(f"[red]API Key 验证失败: {error_msg}[/red]")
                    return False

            # 设置基本配置
            set_nested_value(self.config, "llm.enabled", True)
            set_nested_value(self.config, "llm.provider", provider)
            set_nested_value(self.config, "llm.api_key", api_key)

            # 设置其他配置
            for key, value in kwargs.items():
                set_nested_value(self.config, key, value)

            # 保存
            save_config(self.config)
            console.print(f"[green]✓ {provider.upper()} 配置完成[/green]")
            return True

        except Exception as e:
            console.print(f"[red]配置失败: {e}[/red]")
            return False


def check_and_prompt_config() -> bool:
    """
    检查配置并在需要时启动配置向导。

    Returns:
        是否已完成配置
    """
    config = load_config()

    # 检查 LLM 是否配置
    llm_enabled = config.get("llm", {}).get("enabled", False)
    if not llm_enabled:
        console.print("[yellow]⚠ LLM 未启用，建议运行配置向导[/yellow]")
        return False

    wizard = ConfigWizard()
    if wizard._is_llm_configured():
        return True

    # 配置缺失，启动向导
    console.print("[yellow]⚠ 检测到 LLM 配置缺失，启动配置向导...[/yellow]")
    return wizard.run()
