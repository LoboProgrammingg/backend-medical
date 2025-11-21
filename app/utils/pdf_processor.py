"""Processador de PDFs para anotações."""

import re
import uuid
from pathlib import Path
from typing import List

import fitz
import pdfplumber
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.models.user import User
from app.services.embedding_service import EmbeddingService


class PDFProcessor:
    """Processador de PDFs para converter em anotações."""

    @staticmethod
    def extract_text_from_pdf(pdf_path: Path) -> str:
        """
        Extrai texto SIMPLES de um PDF apenas para embeddings (RAG).
        
        IMPORTANTE: Não tenta formatar ou estruturar. Apenas extrai texto puro.

        Args:
            pdf_path: Caminho para o arquivo PDF.

        Returns:
            str: Texto extraído do PDF (sem formatação).
        """
        try:
            # Extração SIMPLES apenas para RAG/embeddings
            print(f"📄 Extraindo texto de: {pdf_path.name}")
            
            text_parts = []
            
            # Usar PyMuPDF (fitz) para extração simples
            doc = fitz.open(str(pdf_path))
            
            for page_num, page in enumerate(doc, 1):
                # Extrair texto simples da página
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(text.strip())
            
            doc.close()
            
            # Juntar todo o texto
            full_text = "\n\n".join(text_parts)
            
            # Limpar espaços extras
            full_text = re.sub(r'\n{3,}', '\n\n', full_text)
            full_text = re.sub(r' +', ' ', full_text)
            
            print(f"✅ Extraídos {len(full_text)} caracteres de {pdf_path.name}")
            
            return full_text.strip()
            
        except Exception as e:
            print(f"❌ Erro ao extrair PDF: {e}")
            return ""

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 200) -> List[str]:
        """
        Divide texto em chunks com overlap.

        Args:
            text: Texto para dividir.
            chunk_size: Tamanho máximo de cada chunk.
            overlap: Overlap entre chunks.

        Returns:
            List[str]: Lista de chunks de texto.
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Se não é o último chunk, tenta encontrar um ponto de quebra natural
            if end < len(text):
                # Tenta quebrar em parágrafo
                last_newline = text.rfind("\n\n", start, end)
                if last_newline != -1 and last_newline > start + chunk_size // 2:
                    end = last_newline
                else:
                    # Tenta quebrar em sentença
                    last_period = text.rfind(". ", start, end)
                    if last_period != -1 and last_period > start + chunk_size // 2:
                        end = last_period + 1

            chunks.append(text[start:end].strip())
            start = end - overlap if end < len(text) else end

        return chunks

    @staticmethod
    async def process_pdf_to_notes(
        pdf_path: Path,
        user: User,
        db: AsyncSession,
        tag: str = "documento_importado",
        auto_index: bool = True,
    ) -> List[Note]:
        """
        Processa um PDF e cria anotações no banco de dados.

        Args:
            pdf_path: Caminho para o arquivo PDF.
            user: Usuário dono das anotações.
            db: Sessão do banco de dados.
            tag: Tag para as anotações criadas.
            auto_index: Se deve indexar automaticamente (gerar embeddings).

        Returns:
            List[Note]: Lista de anotações criadas.
        """
        # Extrair texto do PDF
        text = PDFProcessor.extract_text_from_pdf(pdf_path)

        # Dividir em chunks
        chunks = PDFProcessor.chunk_text(text)

        # Criar anotações
        notes = []
        for i, chunk in enumerate(chunks, 1):
            # Título baseado no nome do arquivo
            title = f"{pdf_path.stem} - Parte {i}/{len(chunks)}"

            # Criar nota
            note = Note(
                user_id=user.id,
                title=title,
                content=chunk,
                tags=[tag, "pdf", pdf_path.stem.lower().replace(" ", "_")],
                is_favorite=False,
            )

            db.add(note)
            notes.append(note)

        # Commit de todas as notas
        await db.commit()

        # Indexar (gerar embeddings)
        if auto_index:
            for note in notes:
                await db.refresh(note)
                try:
                    await EmbeddingService.create_or_update_embedding(note, db)
                except Exception as e:
                    print(f"Erro ao indexar nota {note.id}: {e}")

        return notes

    @staticmethod
    async def process_pdf_as_document(
        pdf_path: Path,
        user: User,
        db: AsyncSession,
        description: str = "",
    ):
        """
        Processa um PDF e cria um Document (apenas para RAG, não cria anotação).
        
        Args:
            pdf_path: Caminho para o arquivo PDF.
            user: Usuário dono do documento.
            db: Sessão do banco de dados.
            description: Descrição opcional do documento.
            
        Returns:
            Document: Documento criado ou None se houve erro.
        """
        from app.models.document import Document
        from app.models.document_embedding import DocumentEmbedding
        
        try:
            print(f"📄 Processando PDF como documento: {pdf_path.name}")
            
            # Extrair texto SIMPLES para embeddings
            text = PDFProcessor.extract_text_from_pdf(pdf_path)
            
            if not text:
                print(f"❌ Não foi possível extrair texto de: {pdf_path.name}")
                return None
            
            # Obter tamanho do arquivo
            file_size = pdf_path.stat().st_size
            
            # Criar documento
            document = Document(
                user_id=user.id,
                filename=pdf_path.name,
                file_path=str(pdf_path),
                file_size=file_size,
                description=description or f"Documento PDF: {pdf_path.stem}",
            )
            
            db.add(document)
            await db.commit()
            await db.refresh(document)
            
            print(f"✅ Documento criado: {document.id}")
            
            # Criar embedding (limitar tamanho para não exceder limite da API)
            try:
                print(f"🔄 Gerando embedding...")
                
                # Limite de 30.000 caracteres (~30KB) para ser seguro
                # Google Gemini tem limite de 36.000 bytes
                text_for_embedding = text[:30000] if len(text) > 30000 else text
                
                if len(text) > 30000:
                    print(f"⚠️ Texto muito grande ({len(text)} chars). Usando primeiros 30.000 caracteres.")
                
                embedding_vector = EmbeddingService.generate_embedding(text_for_embedding)
                
                document_embedding = DocumentEmbedding(
                    document_id=document.id,
                    content_preview=text[:500],  # Primeiros 500 chars para preview
                    embedding=embedding_vector,
                )
                
                db.add(document_embedding)
                await db.commit()
                
                print(f"✅ Embedding criado para documento: {document.id}")
                
            except Exception as e:
                print(f"❌ Erro ao criar embedding: {e}")
                # Documento foi criado mesmo sem embedding
            
            return document
            
        except Exception as e:
            print(f"❌ Erro ao processar PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    async def process_directory(
        directory_path: Path,
        user: User,
        db: AsyncSession,
        tag: str = "documento_importado",
        pattern: str = "*.pdf",
    ) -> dict:
        """
        Processa todos os PDFs de um diretório.

        Args:
            directory_path: Caminho para o diretório.
            user: Usuário dono das anotações.
            db: Sessão do banco de dados.
            tag: Tag para as anotações criadas.
            pattern: Padrão de arquivos (glob).

        Returns:
            dict: Estatísticas do processamento.
        """
        pdf_files = list(directory_path.glob(pattern))

        total_files = len(pdf_files)
        total_notes = 0
        errors = []

        for pdf_file in pdf_files:
            try:
                notes = await PDFProcessor.process_pdf_to_notes(
                    pdf_path=pdf_file,
                    user=user,
                    db=db,
                    tag=tag,
                    auto_index=True,
                )
                total_notes += len(notes)
                print(f"✅ Processado: {pdf_file.name} ({len(notes)} anotações)")
            except Exception as e:
                errors.append({"file": pdf_file.name, "error": str(e)})
                print(f"❌ Erro ao processar {pdf_file.name}: {e}")

        return {
            "total_files": total_files,
            "total_notes": total_notes,
            "errors": errors,
            "success_rate": (total_files - len(errors)) / total_files if total_files > 0 else 0,
        }

