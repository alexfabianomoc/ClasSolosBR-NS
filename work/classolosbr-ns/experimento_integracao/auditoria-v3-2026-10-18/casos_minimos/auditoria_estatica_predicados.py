"""Auditoria ESTÁTICA (heurística, por expressão regular sobre o código-fonte e suas
funções auxiliares de nucleo.horizontes): para cada predicado derivado usado pelas
chaves da 5ª e da 6ª, se ele lê identificações afirmadas e se consulta pendentes.
Não prova correção; aponta onde olhar."""
import inspect, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from nucleo import horizontes as H, regras as r
from nucleo.chave5 import CHAVE_5ED
from nucleo.chave6 import CHAVE_6ED
usados = set()
def walk(c):
    if isinstance(c, r.Derivado): usados.add(c.predicado)
    for p in getattr(c, "partes", None) or []: walk(p)
    if isinstance(c, r.Nao): walk(c.parte)
for ch in (CHAVE_5ED, CHAVE_6ED):
    for regra in ch: walk(regra.condicao)
BASE = {"identificar", "horizontes_do_tipo", "horizontes_indeterminados_do_tipo", "b_indeterminados",
        "tipos_de", "principal", "leituras_atuais", "leitura_atual"}
def corpo(f, vistos):
    if f.__name__ in vistos: return ""
    vistos.add(f.__name__); src = inspect.getsource(f)
    for nome in re.findall(r"\b([_a-z][a-z_0-9]*)\(", src):
        g = getattr(H, nome, None)
        if inspect.isfunction(g) and g.__module__ == H.__name__ and nome not in BASE:
            src += corpo(g, vistos)
    return src
print(f"{'predicado':62} lê afirmadas  consulta pendentes")
for p in sorted(usados):
    s = corpo(H.PREDICADOS[p], set())
    a = bool(re.search(r"horizontes_do_tipo|tipos_de\(|tem_b_diagnostico|i\.valida", s))
    b = bool(re.search(r"indeterminad|b_indeterminados|_veto_pendente", s))
    print(f"{p:62} {str(a):12} {b}")
