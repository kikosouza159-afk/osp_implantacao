# Painel Implantação v2.0 - PostgreSQL

Sistema Flask editável para controle dos projetos de implantação.

## Recursos
- Login administrativo
- Status Report executivo
- Visão operacional
- Novo projeto
- Editar projeto
- Excluir projeto
- Importar Excel/CSV
- Exportar CSV
- Baixar modelo Excel
- PostgreSQL no Render

## Rodar local

```bash
pip install -r requirements.txt
python app.py
```

Acesse:
```text
http://127.0.0.1:5000
```

Login padrão:
```text
Usuário: gerber
Senha: admin123
```

## Render
Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
gunicorn app:app
```

Crie um PostgreSQL no Render e configure:
```text
DATABASE_URL
SECRET_KEY
ADMIN_USER
ADMIN_PASSWORD
```

Ou use o `render.yaml`.


## v2.0.1
- Produto alterado para seleção: Locator ou ADA.
- Removidos da tela/modelo de importação os campos Responsável, Próxima Ação e Risco.
- Importação CSV corrigida para aceitar UTF-8 e latin1/ANSI.
