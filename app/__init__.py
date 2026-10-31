"""Concilia — app da Fase 1 (MVP interno).

Camadas, na ordem em que o dado anda (SPEC seção 10):

    conectores → normalizacao → motor → relatorios

A Fase 1 entrega a espinha: o formato normalizado de lançamento, o
motor de conciliação (transferências internas, repasses e categorias)
e as migrations do banco. Os conectores de API entram na sequência,
quando os acessos saírem.
"""

__version__ = "0.1.0"
