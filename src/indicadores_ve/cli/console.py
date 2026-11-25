"""Funções de entrada e saída no terminal.

A entrada (input) e a saída (print) são recebidas no construtor. No uso
normal são as funções do Python; nos testes, trocamos por funções que
simulam o que o usuário digita e guardam o que foi impresso.
"""

from __future__ import annotations

import getpass
from typing import Callable, Sequence


class Console:
    LARGURA = 78

    def __init__(
        self,
        entrada: Callable[[str], str] | None = None,
        saida: Callable[[str], None] | None = None,
        entrada_senha: Callable[[str], str] | None = None,
    ) -> None:
        # Sem parâmetros: usa input/print do Python (procurados na hora do uso)
        self._entrada = entrada or (lambda texto: input(texto))
        self._saida = saida or (lambda texto: print(texto))
        # Senha sem eco na tela; com entrada simulada, usa a mesma entrada
        self._entrada_senha = entrada_senha or (entrada if entrada else getpass.getpass)

    # ------------------------------------------------------------ saída
    def escrever(self, texto: str = "") -> None:
        self._saida(texto)

    def titulo(self, texto: str) -> None:
        self.escrever()
        self.escrever("=" * self.LARGURA)
        self.escrever(f" {texto}")
        self.escrever("=" * self.LARGURA)

    def sucesso(self, texto: str) -> None:
        self.escrever(f"[OK] {texto}")

    def erro(self, texto: str) -> None:
        self.escrever(f"[!] {texto}")

    def tabela(self, colunas: Sequence[str], linhas: Sequence[Sequence[object]]) -> None:
        if not linhas:
            self.escrever("(nenhum registro)")
            return
        textos = [[str(c) for c in colunas]] + [[str(v) for v in l] for l in linhas]
        larguras = [max(len(l[i]) for l in textos) for i in range(len(colunas))]
        for n, linha in enumerate(textos):
            celulas = [
                v.ljust(larguras[i]) if i == 0 else v.rjust(larguras[i]) for i, v in enumerate(linha)
            ]
            self.escrever("  ".join(celulas))
            if n == 0:
                self.escrever("  ".join("-" * l for l in larguras))

    def grafico_barras(self, dados: Sequence[tuple[str, float]], largura: int = 40) -> None:
        """Gráfico de barras horizontal em texto (substitui os gráficos do protótipo)."""
        if not dados:
            self.escrever("(sem dados)")
            return
        maior = max(v for _, v in dados) or 1
        rotulo = max(len(r) for r, _ in dados)
        for nome, valor in dados:
            barra = "█" * round(valor / maior * largura)
            self.escrever(f"{nome.ljust(rotulo)} │{barra} {valor}")

    # ----------------------------------------------------------- entrada
    def perguntar(self, texto: str, padrao: str | None = None) -> str:
        sufixo = f" [{padrao}]" if padrao is not None else ""
        resposta = self._entrada(f"{texto}{sufixo}: ").strip()
        return resposta if resposta or padrao is None else padrao

    def senha(self, texto: str = "Senha") -> str:
        return self._entrada_senha(f"{texto}: ")

    def ler_inteiro(self, texto: str, minimo: int | None = None, maximo: int | None = None,
                    padrao: int | None = None) -> int:
        while True:
            resposta = self.perguntar(texto, None if padrao is None else str(padrao))
            try:
                numero = int(resposta)
            except ValueError:
                self.erro("Digite um número inteiro.")
                continue
            if minimo is not None and numero < minimo:
                self.erro(f"O número deve ser no mínimo {minimo}.")
                continue
            if maximo is not None and numero > maximo:
                self.erro(f"O número deve ser no máximo {maximo}.")
                continue
            return numero

    def ler_numero(self, texto: str) -> float | int:
        """Aceita vírgula decimal. A validação de negativo fica nas classes (RN05)."""
        while True:
            resposta = self.perguntar(texto).replace(",", ".")
            try:
                numero = float(resposta)
            except ValueError:
                self.erro("Digite um número (use vírgula ou ponto para decimais).")
                continue
            return int(numero) if numero.is_integer() else numero

    def confirmar(self, texto: str) -> bool:
        while True:
            resposta = self.perguntar(f"{texto} (s/n)").lower()
            if resposta in ("s", "sim"):
                return True
            if resposta in ("n", "nao", "não"):
                return False
            self.erro("Responda s ou n.")

    def escolher(self, texto: str, opcoes: Sequence[str], permitir_vazio: bool = False) -> int | None:
        """Mostra opções numeradas a partir de 1 e devolve o índice escolhido (base 0)."""
        for numero, opcao in enumerate(opcoes, start=1):
            self.escrever(f"  {numero:>2}. {opcao}")
        while True:
            dica = " (Enter para todos)" if permitir_vazio else ""
            resposta = self.perguntar(f"{texto}{dica}")
            if not resposta and permitir_vazio:
                return None
            if resposta.isdigit() and 1 <= int(resposta) <= len(opcoes):
                return int(resposta) - 1
            self.erro(f"Escolha um número de 1 a {len(opcoes)}.")
