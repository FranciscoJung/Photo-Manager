# 📷 Gerenciador de Fotos

Aplicação desktop para organização de fotos locais, construída com Python e CustomTkinter. Permite importar, visualizar e categorizar imagens por tags, com galeria em miniaturas e detecção automática de duplicatas.

## Funcionalidades

- Importação de fotos com detecção de duplicatas via hash MD5
- Geração automática de miniaturas (200x200)
- Leitura de data original da foto via metadados EXIF
- Organização por tags com filtros combinados
- Modo de seleção múltipla para ações em lote (adicionar tags, remover tags, excluir)
- Gerenciador de tags global
- Interface em modo escuro com CustomTkinter

## Tecnologias

- Python 3.x
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — interface gráfica
- [Pillow](https://python-pillow.org/) — processamento de imagens e leitura de EXIF
- SQLite — banco de dados local

## Instalação

```bash
git clone https://github.com/FranciscoJung/Photo-Manager.git
cd Photo-Manager
pip install -r requirements.txt
python main.py
```

## Estrutura do projeto
├── main.py # Ponto de entrada, configura diretórios e inicializa o banco
├── ui.py # Interface gráfica completa (CustomTkinter)
├── database.py # Acesso ao banco de dados SQLite 
├── utils.py # Importação de fotos, geração de miniaturas, leitura EXIF
└── requirements.txt

## Como usar

1. Execute `python main.py`
2. Clique em **+ Importar Fotos** para adicionar imagens
3. Adicione tags às fotos para organizá-las
4. Use o painel lateral para filtrar por uma ou mais tags simultaneamente
5. Use o modo **Selecionar** para realizar ações em lote

## Compatibilidade com executável

O projeto suporta empacotamento com PyInstaller. Quando executado como `.exe`, os diretórios `photos/`, `thumbnails/` e o banco de dados são criados na mesma pasta do executável.
