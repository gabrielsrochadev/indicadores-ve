"""Exceções do sistema.

Cada regra de negócio violada gera uma exceção específica, para que a
interface mostre uma mensagem clara (RF12) e os testes consigam verificar
exatamente qual regra foi aplicada.
"""


class ErroSistema(Exception):
    """Base de todas as exceções do sistema."""


class ErroValidacao(ErroSistema):
    """Dado de entrada inválido (RF12, RN05)."""


class DadoPessoalDetectado(ErroValidacao):
    """Tentativa de registrar dado pessoal de paciente (RN01 – LGPD)."""


class RegistroDuplicado(ErroSistema):
    """Já existe registro com a mesma chave (RN04)."""


class PeriodoHomologado(ErroSistema):
    """Tentativa de alterar dados de um quadrimestre homologado (RN11)."""


class AcessoNegado(ErroSistema):
    """O perfil do usuário não permite a ação (RF09, RN03)."""


class ErroAutenticacao(ErroSistema):
    """Login ou senha inválidos, usuário inativo ou sessão expirada (RF09, RNF05)."""


class RegistroNaoEncontrado(ErroSistema):
    """Registro procurado não existe."""
