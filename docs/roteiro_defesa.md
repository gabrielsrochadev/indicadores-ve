# Roteiro da defesa em laboratório (cerca de 15 minutos)

> Antes de começar: `python scripts/seed.py --forcar` (banco limpo) e `python -m pytest` (deve dar 245 aprovados).
> Deixe dois terminais abertos, um para o sistema e outro para os testes, e o VS Code com o projeto.

## 1. Contexto (1 min)

- **Problema:** a VE consolida os relatórios quadrimestrais à mão, em planilhas, e o relatório
  oficial do 2º quadrimestre de 2026 tem erros de soma.
- **Solução:** cada mês é registrado uma vez, e os totais, variações e indicadores são sempre
  calculados pelo sistema (RN06).

## 2. Do diagrama para o código (3 min)

Mostrar `docs/img/diagrama_classes.png` ao lado do código:

| No diagrama | No código |
|---|---|
| Classe abstrata `RegistroEpidemiologico` e 3 subclasses | `src/indicadores_ve/models/registros.py` |
| Composição Modulo ◆ Indicador | `Modulo.adicionar_indicador()` cria o indicador; `indicador.modulo` não pode ser trocado |
| Agregação Perfil ◇ Permissao | `services/usuarios.py` → `criar_perfis_padrao()` usa as **mesmas** permissões em vários perfis |
| `-senhaHash` (privado) | `self.__senha_hash` em `models/usuario.py` |

Explicar que as diferenças estão registradas e justificadas: `docs/mapeamento_e_alteracoes.md`, seção 5 (A01–A10).

## 3. Pilares da POO (3 min)

Abrir `models/registros.py` e mostrar:

1. **Abstração:** `class RegistroEpidemiologico(ABC)` com `@abstractmethod`. No terminal Python:
   ```python
   from indicadores_ve.models import RegistroEpidemiologico
   RegistroEpidemiologico(2026)   # TypeError: não pode instanciar classe abstrata
   ```
2. **Herança:** `class CicloPNCD(RegistroEpidemiologico)` chama `super().__init__(...)` e herda
   `quadrimestre` e `pertence_ao_quadrimestre()`.
3. **Polimorfismo:** o mesmo `resultado()` em cada classe: **418**, **98,57** e **"satisfatório"**.
   `ServicoLancamentos.registrar()` recebe qualquer uma das três.
4. **Encapsulamento:** o setter de `valor` recusa negativo e decimal em indicador inteiro.

**Métodos especiais:** `len(importacao)`, `"DENGUE" in modulo_sinan`, `usuario_a == usuario_b` (pelo login).

## 4. Demonstração do sistema (6 min) – `python main.py`

| # | Login | Ação | O que mostrar |
|---|---|---|---|
| 1 | `gestor` / `gestor2026` | 1 → Enter, Enter | Painel do 2º quadrimestre: **2.054** notificações, óbitos **−20,0%**, PNCD **98,57%**, gráfico de barras |
| 2 | (mesmo) | 2 → Quadrimestre, 2026, 2, s, SIM/SINASC | Comparativo 2026 × 2025 com variação |
| 3 | (mesmo) | Menu | O Gestor **não vê** "Lançar" nem "Homologar" (RF09) |
| 4 | `digitador` / `digit2026` | 7 → Enter (exemplo) | Prévia: 6 válidas e 2 com erro, com o número da linha → confirmar |
| 5 | (mesmo) | 7 → `data/exemplo_rejeitado_lgpd.csv` | Arquivo recusado inteiro por ter `nome_paciente` (LGPD) |
| 6 | (mesmo) | 4 → SINAN → dengue → 2026 → 6 → 400 | Pede confirmação para substituir (RN04) |
| 7 | `coordenador` / `coord2026` | 4 → 2026 → 2 → s; depois 5 → TXT | Homologa e exporta; abrir o arquivo em `exportacoes/` |
| 8 | `digitador` | 4 → dengue → 2026 → 6 | **Bloqueado**: período homologado (RN11) |
| 9 | `admin` / `admin2026` | 2 | Auditoria com todas as ações anteriores (RNF10) |

**Ponto alto:** rodar `python scripts/seed.py --forcar` e mostrar a conferência. O sistema
encontrou sozinho três erros de soma no relatório oficial.

## 5. Persistência (1 min)

- Fechar e abrir o sistema de novo: os dados continuam lá.
- Abrir `data/banco.json` e mostrar:
  - o campo `"tipo"` de cada registro, que diz qual subclasse recriar;
  - os indicadores gravados dentro do módulo (composição);
  - o `senha_hash` no lugar da senha.
- Mostrar a pasta `data/backups/`.

## 6. Testes (1 min)

```bash
python -m pytest -v tests/test_criterios_aceitacao.py   # CA01 a CA14, um por requisito
python -m pytest --cov=indicadores_ve                    # 245 testes, 98% de cobertura
```

---

## Perguntas prováveis e respostas curtas

**Por que vocês criaram uma classe que não estava no diagrama?**
As três classes de registro tinham a mesma responsabilidade e atributos em comum. A superclasse
abstrata evita repetição e permite o polimorfismo. Está registrada e justificada como A01.

**Onde está a composição e como ela aparece no código?**
Modulo ◆ Indicador. O indicador é criado só pelo `Modulo.adicionar_indicador()`, fica guardado
dentro do módulo e não pode trocar de módulo. No JSON, ele é gravado dentro do módulo.

**E a diferença entre composição e agregação?**
Na agregação (Perfil ◇ Permissao), a permissão existe sozinha e é compartilhada: o mesmo objeto
`ver_painel` está nos perfis Digitador, Gestor e Coordenador. Na composição, o indicador só existe dentro do módulo.

**Por que JSON e não banco de dados?**
Foi o conteúdo trabalhado na disciplina (A04). Como os serviços só conhecem a classe abstrata
`Repositorio`, trocar por SQLite seria escrever outra subclasse, sem mudar nenhuma regra de negócio.

**Como a senha fica protegida?**
Ela não é gravada: guardamos um hash PBKDF2-SHA256 com "sal" aleatório, num atributo privado
(`__senha_hash`). A mesma senha gera hashes diferentes para usuários diferentes.

**Para que servem `__eq__` e `__hash__` nos lançamentos?**
Dois lançamentos com o mesmo indicador, ano e mês são "o mesmo lançamento". Essa é a regra RN04, que impede duplicidade.

**Como vocês testam uma regra que depende da data de hoje (só mês encerrado)?**
O relógio é injetado nos serviços. Nos testes, usamos um relógio fixo em 24/11/2026, que pode
ser adiantado para testar a sessão expirando em 30 minutos.

**Os testes passam, mas cobrem o que importa?**
Cada critério de aceitação da SRS tem um teste com o mesmo número (CA01–CA14), usando os dados
reais. A cobertura de código é de 98%.

---

## Sugestão de divisão da apresentação

Ajustem conforme quem desenvolveu cada parte.

| Parte | Tempo | Sugestão |
|---|---|---|
| 1 e 2 – Contexto e UML → código | 4 min | Integrante que conhece a rotina da VE |
| 3 e 5 – Pilares da POO e persistência | 4 min | Segundo integrante |
| 4 e 6 – Demonstração e testes | 7 min | Terceiro integrante |
