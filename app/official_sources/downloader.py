"""Download automático de fontes oficiais (PCDT, Sociedades Médicas)."""

import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Dict, List
from bs4 import BeautifulSoup

from app.config.settings import settings


class OfficialSourceDownloader:
    """Baixa e atualiza documentos oficiais."""

    SOURCES = {
        "pcdt": {
            "base_url": "https://www.gov.br/saude/pt-br/assuntos/pcdt",
            "priority": 1,
            "specialty": "geral",
            "description": "Protocolos Clínicos e Diretrizes Terapêuticas do Ministério da Saúde",
        },
        "sbc": {
            "base_url": "https://www.portal.cardiol.br/diretrizes",
            "priority": 2,
            "specialty": "cardiologia",
            "description": "Diretrizes da Sociedade Brasileira de Cardiologia",
        },
        "sboc": {
            "base_url": "https://sboc.org.br/diretrizes-publicas",
            "priority": 2,
            "specialty": "oncologia",
            "description": "Diretrizes da Sociedade Brasileira de Oncologia Clínica",
        },
        "amib": {
            "base_url": "https://amib.org.br/lista-de-diretrizes/",
            "priority": 2,
            "specialty": "medicina_intensiva",
            "description": "Diretrizes da Associação de Medicina Intensiva Brasileira",
        },
        "sbp": {
            "base_url": "https://www.sbp.com.br/especiais/documentos-cientificos/",
            "priority": 2,
            "specialty": "pediatria",
            "description": "Documentos Científicos da Sociedade Brasileira de Pediatria",
        },
    }

    def __init__(self, storage_path: Path = None):
        """Inicializa o downloader."""
        self.storage_path = storage_path or settings.storage_path
        self.official_docs_path = self.storage_path / "official_documents"
        self.official_docs_path.mkdir(parents=True, exist_ok=True)

    async def download_all_sources(self, limit_per_source: int = 10) -> Dict[str, int]:
        """
        Baixa todas as fontes oficiais.

        Args:
            limit_per_source: Limite de documentos por fonte (para teste)

        Returns:
            Dict[str, int]: Quantidade de documentos baixados por fonte
        """
        results = {}
        for source_name, source_config in self.SOURCES.items():
            print(f"\n📥 Baixando {source_name.upper()}...")
            print(f"   {source_config['description']}")
            count = await self._download_source(source_name, source_config, limit_per_source)
            results[source_name] = count
            print(f"✅ {source_name.upper()}: {count} documentos baixados")
        return results

    async def _download_source(
        self, source_name: str, config: dict, limit: int = 10
    ) -> int:
        """
        Baixa documentos de uma fonte específica.

        Args:
            source_name: Nome da fonte (pcdt, sbc, etc.)
            config: Configuração da fonte
            limit: Limite de documentos

        Returns:
            int: Quantidade de documentos baixados
        """
        source_dir = self.official_docs_path / source_name
        source_dir.mkdir(exist_ok=True)

        count = 0

        try:
            async with aiohttp.ClientSession() as session:
                # Timeout de 30 segundos
                timeout = aiohttp.ClientTimeout(total=30)
                
                try:
                    async with session.get(
                        config["base_url"], timeout=timeout
                    ) as response:
                        if response.status != 200:
                            print(f"   ⚠️ Erro HTTP {response.status}: {config['base_url']}")
                            return 0

                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")

                        # Encontrar links para PDFs
                        pdf_links = []
                        for link in soup.find_all("a", href=True):
                            href = link["href"]
                            if href.endswith(".pdf") or "/pdf" in href.lower():
                                if not href.startswith("http"):
                                    # URL relativa
                                    if href.startswith("/"):
                                        base_domain = "/".join(
                                            config["base_url"].split("/")[:3]
                                        )
                                        href = base_domain + href
                                    else:
                                        href = config["base_url"] + "/" + href
                                pdf_links.append(
                                    {
                                        "url": href,
                                        "title": link.get_text(strip=True)
                                        or href.split("/")[-1],
                                    }
                                )

                        print(f"   📄 Encontrados {len(pdf_links)} links de PDF")

                        # Limitar quantidade para teste
                        pdf_links = pdf_links[:limit]

                        # Baixar PDFs
                        for pdf_info in pdf_links:
                            try:
                                pdf_url = pdf_info["url"]
                                pdf_title = pdf_info["title"]

                                # Nome do arquivo sanitizado
                                pdf_filename = (
                                    pdf_url.split("/")[-1]
                                    .replace(" ", "_")
                                    .replace("%20", "_")
                                )
                                if not pdf_filename.endswith(".pdf"):
                                    pdf_filename += ".pdf"

                                pdf_path = source_dir / pdf_filename

                                # Pular se já existe
                                if pdf_path.exists():
                                    print(f"   ⏭️ Já existe: {pdf_filename}")
                                    count += 1
                                    continue

                                # Baixar PDF
                                async with session.get(
                                    pdf_url, timeout=timeout
                                ) as pdf_response:
                                    if pdf_response.status == 200:
                                        content = await pdf_response.read()

                                        # Salvar PDF
                                        async with aiofiles.open(pdf_path, "wb") as f:
                                            await f.write(content)

                                        count += 1
                                        print(f"   ✅ Baixado: {pdf_filename}")
                                    else:
                                        print(
                                            f"   ⚠️ Erro ao baixar {pdf_filename}: HTTP {pdf_response.status}"
                                        )

                            except Exception as e:
                                print(f"   ❌ Erro ao processar {pdf_info['url']}: {e}")
                                continue

                except asyncio.TimeoutError:
                    print(f"   ⚠️ Timeout ao acessar {config['base_url']}")
                    return 0

        except Exception as e:
            print(f"   ❌ Erro ao baixar {source_name}: {e}")
            return 0

        return count

    async def update_source(self, source_name: str, limit: int = 10) -> int:
        """
        Atualiza uma fonte específica.

        Args:
            source_name: Nome da fonte (pcdt, sbc, etc.)
            limit: Limite de documentos

        Returns:
            int: Quantidade de documentos baixados
        """
        if source_name not in self.SOURCES:
            raise ValueError(f"Fonte desconhecida: {source_name}")

        config = self.SOURCES[source_name]
        print(f"\n🔄 Atualizando {source_name.upper()}...")
        count = await self._download_source(source_name, config, limit)
        print(f"✅ Atualizado: {count} documentos")
        return count

    def get_source_info(self, source_name: str) -> dict:
        """Retorna informações de uma fonte."""
        if source_name not in self.SOURCES:
            raise ValueError(f"Fonte desconhecida: {source_name}")
        return self.SOURCES[source_name]

    def list_sources(self) -> List[str]:
        """Lista todas as fontes disponíveis."""
        return list(self.SOURCES.keys())

