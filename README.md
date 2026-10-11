<img width="786" height="161" alt="tarj" src="https://github.com/user-attachments/assets/f3fefde5-d736-4d23-8df8-f5791c08da49" />

# MOSx32 Tools

**Editor e interpretador da linguagem assembly simulada MOSx32.**

O MOSx32 Tools é um projeto desenvolvido por **Vitor Roberto Ferreira** para escrever, editar e executar programas na linguagem MOSx32. O projeto combina um editor de código com destaque de sintaxe, um interpretador próprio e uma visualização hexadecimal da memória.

O objetivo é explorar os fundamentos de programação de baixo nível, instruções, endereçamento de memória, operações aritméticas, saltos condicionais e execução de programas.


## Download

### [Baixar a versão mais recente do MOSx32 Tools](https://github.com/SEU-USUARIO/MOSx32-Tools/releases/latest)

Acesse a página de Releases para baixar a versão disponibilizada para Windows.

**Como instalar:**
1. Baixe o arquivo ZIP da versão desejada.
2. Extraia os arquivos para uma pasta.
3. Execute `MOSx32-Tools.exe`.

> O executável distribuído não deve exigir uma instalação tradicional, desde que todas as dependências necessárias tenham sido incluídas na compilação.

## A linguagem MOSx32

MOSx32 é uma linguagem assembly simulada que utiliza instruções textuais para representar operações sobre células de memória.

Cada célula armazena um valor de 8 bits, organizado em dois bits para o tipo e seis bits para o valor. Os endereços são escritos em hexadecimal, usando o formato `SETOR CÉLULA`.

Exemplo de endereço:

00 03

Esse endereço representa a célula `03` do setor `00`.

### Tipos de dados

| Tipo | Descrição |
|---|---|
| `INT` | Número inteiro de 6 bits |
| `FLT` | Número decimal dentro do intervalo suportado |
| `CHR` | Caractere representado pela tabela de 6 bits |
| `STR` | Caractere armazenado como parte de uma string |

Os valores numéricos aceitos pelos tipos são limitados ao intervalo de 0 a 63.

### Instruções disponíveis

| Instrução | Função |
|---|---|
| `MOV` | Armazena valores ou strings na memória |
| `PRT` | Exibe o conteúdo de uma célula |
| `CLR` | Zera uma célula |
| `NXT` | Avança para a próxima célula de um setor |
| `ADD` | Adição |
| `SUB` | Subtração |
| `MUL` | Multiplicação |
| `DIV` | Divisão |
| `CPY` | Copia um valor entre células |
| `SEC` | Declara uma seção de código |
| `ENDSEC` | Marca o encerramento textual de uma seção |
| `JMP` | Salta para uma seção |
| `JIB` | Salta se o primeiro valor for maior |
| `JIS` | Salta se o primeiro valor for menor |
| `JIE` | Salta se os valores forem iguais |
| `HALT` / `HLT` | Encerra a execução |
| `.LOCATE` | Define a localização identificada na saída do interpretador |
| `.HALT` | Encerra a execução |

## Atalhos do editor

| Atalho | Ação |
|---|---|
| `Ctrl + N` | Novo arquivo |
| `Ctrl + O` | Abrir arquivo |
| `Ctrl + S` | Salvar arquivo |
| `Ctrl + Shift + S` | Salvar como |
| `F5` | Executar o programa |

## Objetivos do projeto

O MOSx32 Tools faz parte de uma exploração prática sobre o funcionamento de linguagens de baixo nível e sistemas computacionais.

Entre os objetivos estão:

- compreender o funcionamento de instruções e endereços;
- experimentar operações sobre memória simulada;
- estudar o fluxo de execução de programas;
- explorar a criação de uma linguagem assembly própria;
- desenvolver ferramentas de programação com Python.

O MOSx32 é um ambiente educacional e experimental. Seu funcionamento é simulado em Python e não corresponde diretamente à execução de instruções nativas de um processador físico.

## Desenvolvedor

**Vitor Roberto Ferreira**

Criador do MOSx32 e desenvolvedor do MOSx32 Tools.

## Releases e versões

As versões publicadas, seus arquivos para download e as respectivas notas de atualização ficam disponíveis na página de Releases:

**[Acessar todas as versões do MOSx32 Tools](https://github.com/SEU-USUARIO/MOSx32-Tools/releases)**
