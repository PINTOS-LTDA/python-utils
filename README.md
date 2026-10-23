# pintos-utils

Utilitários Python reutilizáveis para aplicações. A biblioteca é independente
de frameworks, oferece uma API tipada e mantém integrações externas em extras
opcionais. Requer Python 3.11 ou superior.

Este README é uma referência prática para quem integra o pacote ou contribui
com ele. Cada cartão mostra quando usar a API, um exemplo e o resultado ou
efeito esperado.

## Instalação

Instale somente o que sua aplicação usa:

| Recurso | Instalação | API principal |
| --- | --- | --- |
| Modelos de email e contrato de envio | `python -m pip install pintos-utils` | `pintos_utils.email` |
| Adaptador Gmail | `python -m pip install "pintos-utils[gmail]"` | `GmailEmailSender` |
| Scripts SQL MySQL | `python -m pip install "pintos-utils[mysql]"` | `SqlScriptExecutor` |
| Converter resultados para Polars | `python -m pip install "pintos-utils[polars]"` | `sql_script_result_to_dataframe` |
| Exportar Polars para Excel | `python -m pip install "pintos-utils[polars]"` | `exportar_excel`, `exportar_excel_bytes` |
| SQL, consultas/importações Polars + MySQL | `python -m pip install "pintos-utils[mysql,polars]"` | `execute_dataframe`, `execute_file_dataframe`, `query_dataframe`, `import_dataframe` |

O pacote base não instala dependências de runtime. A API de email pode ser
importada sem Google SDK; a API de banco pode ser importada sem o driver MySQL;
as operações que usam essas integrações exigem os extras correspondentes.

### Índice das APIs públicas

| Módulo | Nomes públicos |
| --- | --- |
| `pintos_utils.email` | `EmailAddress`, `EmailAttachment`, `EmailMessage`, `EmailSender`, `SendResult`, `EmailError`, `EmailValidationError`, `EmailConfigurationError`, `EmailAuthenticationError`, `EmailProviderError` |
| `pintos_utils.email.providers.gmail` | `GmailEmailSender`, `GMAIL_SEND_SCOPE` |
| `pintos_utils.database` | `SqlScriptExecutor`, `SqlScriptResult`, `SqlScriptError`, `sql_script_result_to_dataframe`, `query_dataframe`, `import_dataframe`, `ImportMode`, `DataFrameImportResult`, `DataFrameDatabaseError` |
| `pintos_utils.polars_excel` | `exportar_excel`, `exportar_excel_bytes` |

### Cartão: instalar com uv

```bash
uv add "pintos-utils[gmail,mysql,polars]"
```

**Resultado:** o `pyproject.toml` da aplicação registra o pacote com os três
extras. Remova da lista qualquer integração que a aplicação não use; para
instalar somente o pacote base, execute `uv add pintos-utils`.

### Cartão: instalar deste checkout

```bash
uv pip install -e ".[gmail,mysql,polars]"
```

**Resultado:** o pacote fica instalado em modo editável com todas as integrações
opcionais disponíveis.

Para instalar de um repositório Git por SSH:

```bash
uv add "pintos-utils[gmail] @ git+ssh://git@github.com/PINTOS-LTDA/python-utils.git@REVISION"
```

Substitua `REVISION` por uma tag revisada ou por um hash completo de commit.
Configure o acesso SSH no ambiente consumidor; não inclua senhas ou tokens na
URL nem no arquivo de dependências.

## Referência de email

Os modelos públicos são `EmailAddress`, `EmailAttachment`, `EmailMessage` e
`SendResult`. Eles são dataclasses imutáveis. O protocolo `EmailSender` permite
trocar o provedor sem mudar o código que constrói a mensagem.

| API | Assinatura |
| --- | --- |
| `EmailAddress` | `EmailAddress(address, display_name=None)` |
| `EmailAttachment` | `EmailAttachment(filename, content, content_type=None)` |
| `EmailMessage` | `EmailMessage(sender, subject, to=(), cc=(), bcc=(), text_body=None, html_body=None, attachments=())` |
| `EmailSender` | `send(message, /) -> SendResult` |
| `SendResult` | `SendResult(provider, provider_message_id=None)` |

### Cartão: criar uma mensagem

**Quando usar:** para montar uma mensagem independente do provedor.

```python
from pintos_utils.email import EmailAddress, EmailMessage

message = EmailMessage(
    sender=EmailAddress("relatorios@example.com", "Relatórios"),
    to=(EmailAddress("ana@example.net", "Ana"),),
    cc=(EmailAddress("equipe@example.net"),),
    subject="Relatório mensal",
    text_body="O relatório está pronto.",
    html_body="<p>O relatório está pronto.</p>",
)

print(message.subject)
print(message.to[0].address)
```

**Saída esperada:**

```text
Relatório mensal
ana@example.net
```

**Notas:** informe ao menos um destinatário entre `to`, `cc` e `bcc`, e ao
menos um entre `text_body` e `html_body`. Se fornecer ambos os formatos, o
provedor poderá enviar as versões como alternativas. Os campos de cabeçalho
rejeitam quebras de linha.

### Cartão: anexar bytes

**Quando usar:** quando a aplicação já tem o conteúdo do anexo em memória.

```python
from pintos_utils.email import EmailAddress, EmailAttachment, EmailMessage

attachment = EmailAttachment(
    filename="resumo.csv",
    content=b"sku,quantity\nA-100,12\n",
    content_type="text/csv",
)
message = EmailMessage(
    sender=EmailAddress("relatorios@example.com"),
    to=(EmailAddress("ana@example.net"),),
    subject="Resumo de estoque",
    text_body="Segue o arquivo.",
    attachments=(attachment,),
)

print(message.attachments[0].filename, message.attachments[0].content_type)
```

**Saída esperada:** `resumo.csv text/csv`

**Notas:** `content` deve ser `bytes`. O pacote não abre caminhos de arquivos;
a aplicação decide como carregar ou gerar o conteúdo.

### Cartão: implementar outro provedor

**Quando usar:** para integrar um provedor próprio sem acoplar a aplicação ao
Gmail.

```python
from pintos_utils.email import EmailAddress, EmailMessage, EmailSender, SendResult

message = EmailMessage(
    sender=EmailAddress("relatorios@example.com"),
    to=(EmailAddress("ana@example.net"),),
    subject="Resumo de estoque",
    text_body="Segue o resumo.",
)


class ConsoleSender:
    def send(self, message: EmailMessage, /) -> SendResult:
        print(f"Enviando: {message.subject}")
        return SendResult(provider="console")


def send_report(sender: EmailSender, message: EmailMessage) -> SendResult:
    return sender.send(message)


result = send_report(ConsoleSender(), message)
print(result)
```

**Saída esperada:**

```text
Enviando: Resumo de estoque
SendResult(provider='console', provider_message_id=None)
```

`EmailSender` é um protocolo estrutural: uma implementação precisa oferecer
`send(message, /) -> SendResult`.

### Cartão: enviar com Gmail

**Quando usar:** para submeter uma mensagem pelo adaptador Gmail opcional.

```python
import os

from google.oauth2.credentials import Credentials
from pintos_utils.email import EmailAddress, EmailMessage
from pintos_utils.email.providers.gmail import GMAIL_SEND_SCOPE, GmailEmailSender

message = EmailMessage(
    sender=EmailAddress("relatorios@example.com"),
    to=(EmailAddress("ana@example.net"),),
    subject="Relatório mensal",
    text_body="O relatório está pronto.",
)
credentials = Credentials(
    token=None,
    refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
    token_uri=os.environ["GOOGLE_TOKEN_URI"],
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    scopes=[GMAIL_SEND_SCOPE],
)

sender = GmailEmailSender(credentials)
result = sender.send(message)
print(result.provider)
print(result.provider_message_id)
```

**Resultado:** `provider` será `gmail`; `provider_message_id` poderá conter o
identificador opaco devolvido pelo Gmail.

**Notas:** a aplicação é responsável pelo consentimento OAuth e pelo
armazenamento/renovação persistente do refresh token. O adaptador usa o escopo
`gmail.send`, pode renovar credenciais com refresh token e não inicia um fluxo
interativo. O resultado indica que o Gmail aceitou a solicitação, não confirma
a entrega final. O adaptador não tenta reenvio automático.

### Cartão: tratar erros de email

**Quando usar:** para tratar falhas do contrato de email sem depender dos
detalhes do SDK do provedor.

```python
from pintos_utils.email import (
    EmailAuthenticationError,
    EmailConfigurationError,
    EmailError,
    EmailProviderError,
    EmailMessage,
    EmailSender,
    EmailValidationError,
    SendResult,
)


def send_safely(sender: EmailSender, message: EmailMessage) -> SendResult | None:
    try:
        return sender.send(message)
    except EmailValidationError as error:
        print("Revise os dados da mensagem:", error)
    except EmailConfigurationError as error:
        print("Revise a configuração:", error)
    except EmailAuthenticationError as error:
        print("Revise ou renove as credenciais:", error)
    except EmailProviderError as error:
        print(error.provider, error.retryable)
    except EmailError as error:
        print("Falha de email:", error)
    return None
```

`EmailError` é a classe base das exceções públicas de email.
Em caso de sucesso, `send_safely` retorna `SendResult`; quando trata uma dessas
exceções, retorna `None`.

**Referência:** `EmailProviderError.retryable` é uma indicação `True`, `False`
ou `None`; não é uma política de retry. Um timeout pode ocorrer depois de o
provedor aceitar a mensagem, então considere o risco de envio duplicado antes
de tentar novamente.

## Referência de banco de dados

O consumidor cria, configura e fecha a conexão MySQL. `pintos-utils` cria e
fecha cursores, mas não fecha a conexão fornecida.

| API | Assinatura |
| --- | --- |
| `SqlScriptExecutor` | `SqlScriptExecutor(connection)` |
| `execute` | `execute(script, params=None, commit=False) -> SqlScriptResult` |
| `execute_file` | `execute_file(file_path, params=None, commit=False, encoding="utf-8") -> SqlScriptResult` |
| `execute_dataframe` | `execute_dataframe(script, params=None, commit=False) -> polars.DataFrame` |
| `execute_file_dataframe` | `execute_file_dataframe(file_path, params=None, commit=False, encoding="utf-8") -> polars.DataFrame` |
| `sql_script_result_to_dataframe` | `sql_script_result_to_dataframe(result) -> polars.DataFrame` |
| `query_dataframe` | `query_dataframe(connection, query, params=None) -> polars.DataFrame` |
| `import_dataframe` | `import_dataframe(connection, dataframe, table_name, *, mode, key_columns=None, batch_size=1000) -> DataFrameImportResult` |

### Cartão: abrir uma conexão MySQL

**Quando usar:** antes de chamar o executor SQL ou as operações Polars.

```python
import os

import mysql.connector

connection = mysql.connector.connect(
    host=os.environ["MYSQL_HOST"],
    port=int(os.environ.get("MYSQL_PORT", "3306")),
    user=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PASSWORD"],
    database=os.environ["MYSQL_DATABASE"],
    autocommit=False,
)
```

**Resultado:** uma conexão configurada para o banco da aplicação. Feche-a no
código consumidor, normalmente em um bloco `try/finally` ou context manager
suportado pelo driver.

### Cartão: executar SQL com parâmetros nomeados

**Quando usar:** para executar um script SQL em memória e receber as linhas do
último comando que retornou resultado.

```python
from pintos_utils.database import SqlScriptExecutor

executor = SqlScriptExecutor(connection)
result = executor.execute(
    "SELECT :store_id AS store_id, :sku AS sku",
    params={"store_id": 18, "sku": "A-100"},
)

print(result.rows)
```

**Saída esperada:** `[{'store_id': 18, 'sku': 'A-100'}]`

Use `:name` para valores. O driver recebe os valores separadamente do SQL; os
marcadores não substituem nomes de tabela ou coluna. Os nomes de identificadores
dinâmicos devem vir de uma allowlist da aplicação.

### Cartão: executar um arquivo SQL

**Quando usar:** para manter consultas e scripts versionados em arquivos.
Este exemplo usa `executor` criado no cartão de parâmetros nomeados.

```python
from datetime import date
from pathlib import Path

result = executor.execute_file(
    Path("sql/estoque_por_loja.sql"),
    params={"data": date(2026, 10, 1), "store_id": 18},
    encoding="utf-8",
)

print(result.statements_executed)
print(result.rows[:1])
```

**Resultado:** `execute_file()` lê o arquivo e devolve um `SqlScriptResult`,
assim como `execute()`.

O arquivo de exemplo pode conter:

```sql
SELECT :data AS report_date, :store_id AS store_id;
```

### Cartão: controlar o commit do script

**Quando usar:** quando o consumidor quer que o executor confirme o trabalho
após todas as instruções terem sucesso.

```python
result = executor.execute(
    "UPDATE products SET quantity = :quantity WHERE sku = :sku",
    params={"quantity": 12, "sku": "A-100"},
    commit=True,
)

print(result.statements_executed, result.affected_rows)
```

**Resultado esperado:** `1 1` se uma linha foi alterada.

**Notas:** `commit` é `False` por padrão. Com `False`, o executor não faz commit
nem rollback; o consumidor controla a transação. Com `True`, ele rejeita uma
conexão que já esteja em uma transação e faz um commit após o sucesso. Falhas
não provocam rollback automático. DDL e outros comandos podem causar commits
implícitos no MySQL.

### Cartão: consultar `SqlScriptResult`

**Quando usar:** para ler contagens de execução e linhas retornadas pelo script.

```python
result = executor.execute(
    "UPDATE products SET quantity = :quantity WHERE sku = :sku",
    params={"quantity": 12, "sku": "A-100"},
)

print(result.statements_executed)
print(result.affected_rows)
print(result.rows)
```

**Campos:** `statements_executed` conta comandos concluídos; `affected_rows`
soma contagens não negativas de comandos DML; `rows` e `columns` mantêm as
linhas e nomes ordenados do último comando que produziu resultados. As linhas
são materializadas em memória.

### Cartão: converter o resultado SQL para Polars

**Quando usar:** quando o código precisa das contagens de execução e também quer
continuar o processamento dos dados com Polars.

```python
from pintos_utils.database import sql_script_result_to_dataframe

result = executor.execute("SELECT sku, quantity FROM products")
frame = sql_script_result_to_dataframe(result)

print(result.affected_rows)
print(frame.shape, frame.columns)
```

**Resultado:** `frame` contém somente as linhas e colunas do último resultado;
`statements_executed` e `affected_rows` continuam no `SqlScriptResult`.

**Notas:** instale `pintos-utils[polars]`. Colunas conhecidas são preservadas
mesmo quando não há linhas, mas seus dtypes não são especificados. Para um
resultado criado manualmente sem metadados, a ordem das chaves da primeira linha
define as colunas. Linhas com chaves diferentes e valores que Polars não consiga
representar fielmente geram `DataFrameDatabaseError` com `operation="convert"`.

### Cartão: executar SQL e receber um DataFrame

**Quando usar:** quando o resultado final do script é suficiente e as contagens
de execução não são necessárias.

```python
frame = executor.execute_dataframe(
    "SELECT sku, quantity FROM products WHERE store_id = :store_id",
    params={"store_id": 18},
    commit=True,
)

print(frame.shape)
print(frame.head())
```

**Resultado:** um `polars.DataFrame` com as linhas e colunas ordenadas do último
comando que produziu resultados. Um comando posterior sem linhas não apaga esse
resultado. Um script sem conjunto de resultados devolve um DataFrame com shape
`(0, 0)`.

**Notas:** instale `pintos-utils[mysql,polars]`. Com `commit=True`, o executor
converte o resultado antes do commit; scripts vazios ou só com comentários são
no-op. Se a conversão falhar, tenta rollback e guarda uma falha de rollback em
`cleanup_exception`. Com `commit=False`, não faz commit nem rollback. Falhas SQL,
de leitura ou de fechamento do cursor mantêm o comportamento atual do executor
e não adicionam rollback automático.

### Cartão: executar um arquivo SQL para Polars

**Quando usar:** para manter consultas versionadas em arquivos e receber um
DataFrame sem materializar um `SqlScriptResult` na aplicação.

```python
frame = executor.execute_file_dataframe(
    "reports/replenishments.sql",
    params={"store_id": 18},
    encoding="utf-8",
)
```

**Resultado:** `execute_file_dataframe()` lê o arquivo com a codificação
informada e aplica as mesmas regras de binding, seleção do último resultado e
transação de `execute_dataframe()`.

### Cartão: tratar erros SQL

**Quando usar:** para identificar a instrução com falha e inspecionar a causa
original.

```python
from pintos_utils.database import SqlScriptError

try:
    executor.execute("SELECT * FROM products WHERE sku = :sku", params={})
except SqlScriptError as error:
    print(error.statement_index)
    print(error.original_exception)
```

`statement_index` é baseado em 1 quando um comando específico falha.
`original_exception` e `__cause__` expõem a causa disponível. A mensagem padrão
não copia os valores vinculados.

### Cartão: conhecer os limites do executor SQL

**Quando usar:** antes de escolher o executor para scripts com DDL, procedures
ou instruções não convencionais.

`SqlScriptExecutor` processa instruções convencionais em ordem usando uma
conexão e uma sessão. Suporta `USE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE`,
`CREATE TEMPORARY TABLE` e `DROP TEMPORARY TABLE`; devolve somente o resultado
final produzido pelo script.

Ele rejeita controles transacionais e atribuições à variável de sistema
`autocommit`. Procedures, corpos de trigger, diretivas de cliente `DELIMITER` e
comentários executáveis MySQL não são suportados. O parser não valida toda a
sintaxe MySQL. Para detalhes, consulte o [guia de execução SQL](docs/database.md).

## Referência de DataFrames Polars

Instale ambos os extras para conectar ao MySQL e usar Polars:

```bash
python -m pip install "pintos-utils[mysql,polars]"
```

Para executar os cartões de importação, prepare uma tabela existente por uma
migração ou ferramenta de schema da aplicação:

```sql
CREATE TABLE products (
    sku VARCHAR(20) NOT NULL PRIMARY KEY,
    quantity INT NOT NULL
) ENGINE=InnoDB;
```

`import_dataframe` não cria nem altera essa tabela.

### Cartão: consultar SQL para um DataFrame

**Quando usar:** para receber em memória o resultado de uma instrução em um
`polars.DataFrame`.

```python
from pintos_utils.database import query_dataframe

frame = query_dataframe(
    connection,
    "SELECT :store_id AS store_id, :sku AS sku",
    params={"store_id": 18, "sku": "A-100"},
)

print(frame.shape)
print(frame.to_dicts())
```

**Saída esperada:**

```text
(1, 2)
[{'store_id': 18, 'sku': 'A-100'}]
```

**Notas:** valores são vinculados, não interpolados. A operação aceita uma
instrução suportada que retorna um único conjunto de resultados, materializa
todo o DataFrame, inicia e controla uma transação, faz commit após o sucesso e
tentará rollback após uma falha. Ela rejeita uma transação pré-existente,
`CALL`, controle transacional, comandos com commit implícito e múltiplas
instruções. Resultado vazio preserva nomes e ordem das colunas; os dtypes não
são garantidos.

### Cartão: importar com `APPEND`

**Quando usar:** para inserir todas as linhas em uma tabela existente.

```python
import polars as pl

from pintos_utils.database import ImportMode, import_dataframe

incoming = pl.DataFrame({"sku": ["A-100", "B-200"], "quantity": [12, 7]})
result = import_dataframe(
    connection,
    incoming,
    "products",
    mode=ImportMode.APPEND,
    batch_size=1000,
)

print(result)
```

**Saída esperada:** `DataFrameImportResult(rows_processed=2, batches_processed=1)`

**Notas:** o alvo deve ser uma tabela existente com engine transacional. A
operação converte e valida os dados, envia lotes parametrizados, faz um commit
ao final e tenta reverter todos os lotes quando ocorre falha. Um DataFrame
vazio não abre uma transação.

### Cartão: importar com `UPSERT`

**Quando usar:** para atualizar registros existentes e inserir os novos por uma
chave definida pela aplicação.

```python
import polars as pl

from pintos_utils.database import ImportMode, import_dataframe

changes = pl.DataFrame({"sku": ["A-100", "C-300"], "quantity": [15, 4]})
result = import_dataframe(
    connection,
    changes,
    "products",
    mode=ImportMode.UPSERT,
    key_columns=["sku"],
    batch_size=1000,
)

print(result.rows_processed, result.batches_processed)
```

**Saída esperada:** `2 1`

**Notas:** `key_columns` precisa corresponder a uma chave primária ou índice
único completo do alvo. Chaves nulas ou duplicadas nos dados de origem são
rejeitadas. Os dados passam por uma tabela temporária da sessão, depois linhas
correspondentes são atualizadas e as demais inseridas. Conflitos em outro
índice único falham e revertem a transação.

### Cartão: conversões e erros de DataFrame

**Quando usar:** para entender os tipos aceitos e inspecionar falhas de importação.

O import valida tipo e faixa antes de gravar: inteiros, booleanos, floats
finitos, `Decimal`, strings, bytes, `Date`, `Datetime` sem fuso e `Time` são
aceitos quando representáveis sem perda pelo tipo de destino. Conversões
incompatíveis, truncamento de texto/bytes, precisão decimal ou temporal
insuficiente e tipos aninhados são rejeitados.

```python
import polars as pl

from pintos_utils.database import (
    DataFrameDatabaseError,
    ImportMode,
    import_dataframe,
)

bad_frame = pl.DataFrame({"sku": ["A-100"], "quantity": [12.5]})

try:
    result = import_dataframe(
        connection,
        bad_frame,
        "products",
        mode=ImportMode.APPEND,
    )
except DataFrameDatabaseError as error:
    print(error.operation)
    print(error.original_exception)
    print(error.cleanup_exception)
```

`DataFrameDatabaseError.operation` será `query`, `import` ou `convert`. Causas
originais e falhas de limpeza ficam disponíveis nos atributos correspondentes;
mensagens e logs padrão não incluem valores vinculados nem linhas.

Para detalhes sobre transações, conversões e limitações, consulte o [guia de
operações de banco de dados](docs/database.md).

## Exportação de DataFrames Polars para Excel

Instale o extra `polars` para habilitar as duas funções de exportação; a
instalação base continua sem dependências de runtime:

```bash
python -m pip install "pintos-utils[polars]"
```

| API | Assinatura |
| --- | --- |
| `exportar_excel` | `exportar_excel(df, arquivo, aba="Dados") -> None` |
| `exportar_excel_bytes` | `exportar_excel_bytes(df, aba="Dados") -> bytes` |

### Cartão: salvar um DataFrame em arquivo Excel

**Quando usar:** para criar ou substituir um arquivo `.xlsx` no caminho escolhido.

```python
from pathlib import Path

import polars as pl

from pintos_utils.polars_excel import exportar_excel

relatorio = pl.DataFrame(
    {
        "produto": ["Café", "Chá"],
        "quantidade": [12, 7],
    }
)

exportar_excel(relatorio, Path("relatorio.xlsx"))
exportar_excel(relatorio, "resumo.xlsx", aba="Resumo")
```

**Resultado:** o primeiro workbook usa a planilha `Dados`; o segundo usa
`Resumo`. Cada workbook contém uma planilha e preserva a ordem das colunas e
linhas.

**Notas:** datas usam `dd/mm/yyyy`, data e hora usam
`dd/mm/yyyy hh:mm:ss`, horas usam `hh:mm:ss`, inteiros usam `#,##0` e floats e
decimais usam `#,##0.00`. A planilha aplica o estilo de tabela Medium 2,
dimensiona colunas pelo conteúdo, inclui filtros, congela a primeira linha e
oculta as linhas de grade. Um DataFrame sem colunas gera uma planilha vazia sem
tabela sintética.

### Cartão: obter um workbook Excel como bytes

**Quando usar:** para enviar o workbook a outro componente sem gravar primeiro
um arquivo temporário.

```python
import polars as pl

from pintos_utils.polars_excel import exportar_excel_bytes

relatorio = pl.DataFrame({"produto": ["Café"], "quantidade": [12]})
payload = exportar_excel_bytes(relatorio, aba="Resumo")

print(type(payload).__name__, len(payload))
```

**Saída esperada:** `bytes` contendo um arquivo `.xlsx` completo com a planilha
`Resumo`. O workbook é finalizado antes de os bytes serem retornados, e a
operação não cria arquivo no disco.

**Erros:** destinos que não podem ser gravados, nomes inválidos de planilha e
valores não suportados pelo writer geram exceções observáveis. A exportação não
descarta dados silenciosamente. Nenhuma das funções modifica o DataFrame de
entrada.

## Desenvolvimento do pacote

Use Python 3.11 e uv. Para executar a suíte completa com todas as integrações
opcionais instaladas:

```bash
uv sync --locked --group dev --extra gmail --extra mysql --extra polars
uv run pytest --cov=pintos_utils --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/release_preflight.py
uv build --no-sources
```

O pacote segue Semantic Versioning: correções compatíveis incrementam patch,
adições compatíveis incrementam minor e mudanças incompatíveis na API pública
incrementam major. Consulte também os guias de [email](docs/email.md),
[banco de dados](docs/database.md) e [publicação](docs/releases.md).
