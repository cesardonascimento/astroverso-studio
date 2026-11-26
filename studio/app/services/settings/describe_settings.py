from dataclasses import dataclass

from app.ai.whisper import ResolveWhisperDevice
from app.config import settings


@dataclass
class SettingRow:
    group: str
    label: str
    value: str


class DescribeSettings:
    def execute(self) -> list[SettingRow]:
        config = settings()
        device = ResolveWhisperDevice().execute(config.whisper_device)
        return [
            SettingRow("Instância", "Nome", config.instance_name),
            SettingRow("Instância", "Fuso", config.tz),
            SettingRow("Instância", "Idioma dos textos", config.content_language),
            SettingRow("IA", "Modelo do Claude", config.llm_model),
            SettingRow("IA", "Chave da API", self._mask(config.anthropic_api_key)),
            SettingRow("IA", "Whisper", f"{config.whisper_model} em {device.upper()} "
                                        f"({config.whisper_compute_type})"),
            SettingRow("Armazenamento", "Banco", f"{config.database_host}:{config.database_port}/{config.database_name}"),
            SettingRow("Armazenamento", "S3", f"{config.s3_endpoint} · bucket {config.s3_bucket}"),
            SettingRow("WebDAV", "Endereço", config.webdav_url or "desligado"),
            SettingRow("WebDAV", "Usuário", config.webdav_user if config.webdav_url else ""),
            SettingRow("WebDAV", "Senha", self._mask(config.webdav_password) if config.webdav_url else ""),
            SettingRow("WebDAV", "Pasta", config.webdav_dir if config.webdav_url else ""),
        ]

    def _mask(self, secret: str) -> str:
        if not secret or secret == "toBeModified":
            return "não configurada"
        return "••••" + secret[-4:]
