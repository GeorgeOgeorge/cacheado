# GitHub Actions Pipelines

Este diretório contém as pipelines de CI/CD para o projeto de cache hierárquico.

## Pipelines Disponíveis

### 🧪 Tests (`tests.yml`)
- **Trigger**: Push/PR para `main` e `develop`
- **Matriz**: Python 3.8, 3.9, 3.10, 3.11, 3.12
- **Executa**: Testes unitários, integração e coverage
- **Coverage**: Enviado para Codecov (Python 3.11)

### 🔍 Code Quality (`quality.yml`)
- **Trigger**: Push/PR para `main` e `develop`
- **Ferramentas**: flake8, black, isort, mypy
- **Verifica**: Linting, formatação, imports, tipos

### 🚀 Release (`release.yml`)
- **Trigger**: Tags `v*`
- **Executa**: Testes completos + criação de release
- **Automático**: Release notes no GitHub

## Comandos Locais

```bash
# Executar testes
make test

# Verificar qualidade
flake8 .
black --check .
isort --check .

# Formatar código
black .
isort .
```

## Badges Sugeridos

```markdown
![Tests](https://github.com/seu-usuario/cache/workflows/Tests/badge.svg)
![Code Quality](https://github.com/seu-usuario/cache/workflows/Code%20Quality/badge.svg)
[![codecov](https://codecov.io/gh/seu-usuario/cache/branch/main/graph/badge.svg)](https://codecov.io/gh/seu-usuario/cache)
```
