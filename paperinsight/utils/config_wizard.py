"""
配置向导模块

提供交互式配置引导，在首次运行或配置缺失时帮助用户完成配置。
所有敏感信息仅存储在本地，不会上传到远程服务器。
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path

from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from paperinsight import __version__
from paperinsight.utils.config import (
    load_config,
    save_config,
    get_nested_value,
    set_nested_value,
    validate_api_key,
    mask_sensitive_value,
)
from paperinsight.utils.terminal import create_console

console = create_console()

LONGCAT_DOCS_URL = "https://longcat.chat/platform/docs/zh/"
MINERU_TOKEN_URL = "https://mineru.net/apiManage/token"

MODEL_OPTIONS = {
    "openai": [
        ("gpt-4o", "更聪明，适合复杂提取"),
        ("gpt-4o-mini", "更省钱，适合日常使用"),
        ("gpt-4-turbo", "老款高性能模型"),
        ("gpt-3.5-turbo", "基础够用"),
    ],
    "deepseek": [
        ("deepseek-chat", "通用聊天模型"),
        ("deepseek-coder", "偏代码和结构化任务"),
    ],
    "wenxin": [
        ("ernie-4.0-8k", "能力更强"),
        ("ernie-3.5-8k", "更稳"),
        ("ernie-speed-8k", "更快"),
    ],
    "longcat": [
        ("LongCat-Flash-Chat", "通用版，适合大多数人"),
        ("LongCat-Flash-Thinking", "更偏深度思考"),
        ("LongCat-Flash-Thinking-2601", "Thinking 的升级版"),
        ("LongCat-Flash-Lite", "更轻更省"),
        ("LongCat-Flash-Omni-2603", "多模态版本"),
    ],
}


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
        if not force and self._is_llm_configured() and self._is_mineru_configured():
            console.print("\n[green]✓ 检测到已有完整配置[/green]")
            if not Confirm.ask("是否重新配置？", default=False):
                return True

        console.print("\n[bold]接下来会严格按 4 步走：[/bold]")
        console.print("  1. 先检查环境")
        console.print("  2. 再配置 Longcat")
        console.print("  3. 再配置 MinerU")
        console.print("  4. 最后请您确认并保存\n")

        self._show_environment_summary()

        # Step 2: 配置 Longcat
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
            f"[bold cyan]PaperInsight v{__version__} 配置向导[/bold cyan]\n\n"
            "别担心，我们会一项一项带您配好基础启动。\n"
            "配好这一次后，命令行和桌面版都会共用同一份配置。\n\n"
            "[yellow]⚠ 您填写的 Key 和 Token 只保存在本机，不会上传给我们。[/yellow]",
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

    def _is_mineru_configured(self) -> bool:
        mineru_config = self.config.get("mineru", {})
        if not mineru_config.get("enabled", False):
            return True
        if mineru_config.get("mode") == "api":
            return bool(str(mineru_config.get("token", "")).strip())
        return True

    def _show_environment_summary(self) -> None:
        import sys

        console.print("[bold]Step 1: 环境检查[/bold]")
        console.print(
            Panel(
                "\n".join(
                    [
                        f"Python 版本：{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                        f"配置文件位置：{self.config_path}",
                        "这一步只是先帮您看看程序能不能正常跑，不会改动任何配置。",
                    ]
                ),
                border_style="blue",
            )
        )

    def _select_llm_provider(self) -> str:
        """选择 LLM 提供商"""
        console.print("\n[bold]Step 2: 配置 Longcat[/bold]")
        console.print("Longcat 就像这套工具连接 AI 的“通行证服务”。")
        console.print("如果这里没配好，后面的智能提取就没法正常工作。")
        console.print(f"[blue underline]{LONGCAT_DOCS_URL}[/blue underline]")

        provider = "longcat"
        set_nested_value(self.config, "llm.provider", provider)
        set_nested_value(self.config, "llm.enabled", True)
        if not get_nested_value(self.config, "llm.model", ""):
            set_nested_value(self.config, "llm.model", "LongCat-Flash-Chat")

        console.print("[green]✓ 已进入 Longcat 配置[/green]")
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
                "\n[bold]怎么拿到 Longcat API Key？[/bold]\n"
                f"  1. 打开 [blue underline]{LONGCAT_DOCS_URL}[/blue underline]\n"
                "  2. 注册或登录账号\n"
                "  3. 找到 API Keys 页面，新建一个 Key\n"
                "  4. 把拿到的 Key 复制到下面\n"
                "\n如果您把 API Key 理解成“开门钥匙”，基本就对了。\n"
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
        api_key = Prompt.ask(f"\n请输入 {provider.upper()} API Key", password=True)

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

        console.print("\n[bold]关于“连接地址”[/bold]")
        console.print("不知道这是什么，就先留空。")
        console.print("只有当别人明确让您填写“中转地址”或“代理地址”时，您再填写。")
        console.print("它就像一条备用通道，帮程序连到 AI 服务。")

        if Confirm.ask("您现在要填写连接地址 / 中转地址吗？", default=False):
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

            console.print("[dim]不知道填什么就先别填，后面也可以再改。[/dim]")
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
        options = MODEL_OPTIONS.get(provider)
        if not options:
            return

        models = [item[0] for item in options]
        descriptions = [item[1] for item in options]

        console.print("\n[bold]请选择模型[/bold]")
        console.print("没有唯一正确答案，您按自己的需要选就可以。")
        for i, (model, desc) in enumerate(zip(models, descriptions), 1):
            console.print(f"  [cyan]{i}[/cyan]. {model} - {desc}")

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
        set_nested_value(self.config, "llm.model", model)

    def _configure_mineru(self):
        """配置 MinerU 解析器"""
        console.print("\n[bold]Step 3: 配置 MinerU[/bold]")
        console.print("MinerU 可以帮您把 PDF 拆得更细，通常比普通解析更完整。")
        console.print(f"Token 申请地址： [blue underline]{MINERU_TOKEN_URL}[/blue underline]")
        console.print("温馨提示：第一次申请可能需要等一会儿，Token 一般只管 90 天。")

        if not Confirm.ask("是否启用 MinerU 解析器？", default=True):
            set_nested_value(self.config, "mineru.enabled", False)
            console.print("[yellow]已禁用 MinerU，将使用基础 PDF 解析[/yellow]")
            return

        set_nested_value(self.config, "mineru.enabled", True)

        # 选择模式
        console.print("\nMinerU 运行模式：")
        console.print("  [cyan]1[/cyan]. 云端 API 模式（推荐，大多数用户选这个）")
        console.print("  [cyan]2[/cyan]. 本地 CLI 模式（适合会自己装环境的人）")

        current_mode = get_nested_value(self.config, "mineru.mode", "api")
        console.print(f"\n当前模式: [yellow]{current_mode}[/yellow]")

        mode_choice = Prompt.ask("请选择", choices=["1", "2"], default="1")
        mode = "api" if mode_choice == "1" else "cli"
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

        model_versions = {
            "1": ("vlm", "推荐，适合大多数论文"),
            "2": ("pipeline", "老方案，适合兼容场景"),
            "3": ("MinerU-HTML", "偏 HTML 结果"),
        }
        console.print("\n接下来请您自己选 MinerU 的处理方案：")
        for key, (value, desc) in model_versions.items():
            console.print(f"  [cyan]{key}[/cyan]. {value} - {desc}")
        selected_model_version = Prompt.ask("模型版本", choices=list(model_versions.keys()), default="1")
        set_nested_value(self.config, "mineru.model_version", model_versions[selected_model_version][0])

        output_formats = {
            "1": "markdown",
            "2": "json",
        }
        current_output_format = get_nested_value(self.config, "mineru.output_format", "markdown")
        default_output_choice = "1" if current_output_format == "markdown" else "2"
        console.print("\n输出格式就是 MinerU 处理完后更偏向什么结果。")
        console.print("  [cyan]1[/cyan]. markdown - 更适合后续继续分析")
        console.print("  [cyan]2[/cyan]. json - 更适合程序读取")
        output_choice = Prompt.ask("输出格式", choices=["1", "2"], default=default_output_choice)
        set_nested_value(self.config, "mineru.output_format", output_formats[output_choice])

        methods = {
            "1": "auto",
            "2": "txt",
            "3": "ocr",
        }
        current_method = get_nested_value(self.config, "mineru.method", "auto")
        default_method_choice = next(
            (key for key, value in methods.items() if value == current_method),
            "1",
        )
        console.print("\n解析方式怎么选？")
        console.print("  [cyan]1[/cyan]. auto - 让程序自己判断，推荐")
        console.print("  [cyan]2[/cyan]. txt - 更偏向直接读文字")
        console.print("  [cyan]3[/cyan]. ocr - 更偏向识别扫描图像")
        method_choice = Prompt.ask("解析方式", choices=["1", "2", "3"], default=default_method_choice)
        set_nested_value(self.config, "mineru.method", methods[method_choice])

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
            console.print(
                f"模型版本: [cyan]{get_nested_value(self.config, 'mineru.model_version', 'vlm')}[/cyan]"
            )
            console.print(
                f"输出格式: [cyan]{get_nested_value(self.config, 'mineru.output_format', 'markdown')}[/cyan]"
            )
            console.print(
                f"解析方式: [cyan]{get_nested_value(self.config, 'mineru.method', 'auto')}[/cyan]"
            )

        console.print("-" * 40)
        console.print("保存后，命令行和桌面版都会直接共用这份配置。")

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
