"""Configurações e recordes salvos em disco (sem Pygame).

As teclas são guardadas pelo nome do Pygame ("d", "left", "space"...), assim o
arquivo JSON continua legível e não depende de códigos numéricos.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

FPS_OPCOES = (30, 60, 75, 90, 120, 144, 165, 240)
VEL_OPCOES = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0)
VOL_OPCOES = tuple(range(0, 101, 10))
RESOLUCOES = ("auto", "baixa", "media", "alta", "maxima")
ESCALA_RESOLUCAO = {"auto": 99.0, "baixa": 1.0, "media": 1.35, "alta": 1.7, "maxima": 2.25}
ROTULO_RESOLUCAO = {"auto": "Automática", "baixa": "Baixa", "media": "Média",
                    "alta": "Alta", "maxima": "Máxima"}
AJUSTE_MIN, AJUSTE_MAX = -500, 500
VERSAO = 3

PADRAO = {
    # jogador 1 (também usado no modo de 1 jogador): WASD; jogador 2: setas
    "teclas": [["a", ""], ["s", ""], ["w", ""], ["d", ""]],
    "teclas2": [["left", ""], ["down", ""], ["up", ""], ["right", ""]],
    "fps": 60,
    "tela_cheia": False,
    "resolucao": "auto",
    "ajuste_ms": 0,            # calibração de áudio (ms)
    "downscroll": False,       # setas descendo em vez de subindo
    "vel_mult": 1.0,           # multiplica a velocidade da dificuldade
    "ghost_tapping": True,     # apertar sem nota não penaliza
    "efeitos_camera": True,    # zoom e tremor de câmera
    "vol_musica": 100,
    "vol_efeitos": 80,
    "personalizada": "",       # último arquivo do modo personalizado
}
LISTAS = {"fps": FPS_OPCOES, "vel_mult": VEL_OPCOES, "resolucao": RESOLUCOES,
          "vol_musica": VOL_OPCOES, "vol_efeitos": VOL_OPCOES}
BOOLEANOS = ("tela_cheia", "downscroll", "ghost_tapping", "efeitos_camera")
NOMES_LANES = ("Esquerda", "Baixo", "Cima", "Direita")


def _tabela_valida(t) -> bool:
    return (isinstance(t, list) and len(t) == 4
            and all(isinstance(l, list) and len(l) == 2 and all(isinstance(k, str) for k in l)
                    and l[0] for l in t))


class Config:
    def __init__(self, caminho: Path | None = None) -> None:
        self.caminho = Path(caminho) if caminho else None
        for k, v in PADRAO.items():
            setattr(self, k, copy.deepcopy(v))

    # ------------------------------------------------------------ disco ---
    @classmethod
    def carregar(cls, caminho: Path) -> "Config":
        cfg = cls(caminho)
        try:
            with open(caminho, encoding="utf-8") as f:
                dados = json.load(f)
        except (OSError, ValueError):
            return cfg
        if not isinstance(dados, dict):
            return cfg
        # arquivos de versões antigas (sem teclas do jogador 2) voltam às teclas novas
        if dados.get("versao") == VERSAO:
            t1, t2 = dados.get("teclas"), dados.get("teclas2")
            if _tabela_valida(t1) and _tabela_valida(t2):
                todas = [k for t in (t1, t2) for l in t for k in l if k]
                if len(set(todas)) == len(todas):          # sem teclas repetidas
                    cfg.teclas, cfg.teclas2 = t1, t2
        for campo, lista in LISTAS.items():
            if dados.get(campo) in lista:
                setattr(cfg, campo, dados[campo])
        for campo in BOOLEANOS:
            if isinstance(dados.get(campo), bool):
                setattr(cfg, campo, dados[campo])
        if isinstance(dados.get("personalizada"), str):
            cfg.personalizada = dados["personalizada"]
        aj = dados.get("ajuste_ms")
        if isinstance(aj, (int, float)) and not isinstance(aj, bool):
            cfg.ajuste_ms = int(max(AJUSTE_MIN, min(AJUSTE_MAX, aj)))
        return cfg

    def para_dict(self) -> dict:
        d = {k: getattr(self, k) for k in PADRAO}
        d["versao"] = VERSAO
        return d

    def salvar(self) -> None:
        if self.caminho is None:
            return
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho, "w", encoding="utf-8") as f:
                json.dump(self.para_dict(), f, indent=2)
        except OSError:
            pass

    # --------------------------------------------------------- alterações ---
    def restaurar(self) -> None:
        """Volta tudo ao padrão, exceto a calibração (ela depende do seu aparelho)."""
        ajuste, arquivo = self.ajuste_ms, self.personalizada
        for k, v in PADRAO.items():
            setattr(self, k, copy.deepcopy(v))
        self.ajuste_ms, self.personalizada = ajuste, arquivo

    def tabela(self, jogador: int = 0):
        return self.teclas if jogador == 0 else self.teclas2

    def _teclas_ok(self) -> bool:
        return all(any(l) for t in (self.teclas, self.teclas2) for l in t)

    def definir_tecla(self, lane: int, slot: int, nome: str, jogador: int = 0) -> bool:
        """Atribui a tecla. Se já era usada em outro lugar (de qualquer jogador), as duas
        posições trocam de tecla. Devolve False (sem mudar nada) se alguma seta ficasse
        sem nenhuma tecla."""
        backup = (copy.deepcopy(self.teclas), copy.deepcopy(self.teclas2))
        alvo = self.tabela(jogador)
        antiga = alvo[lane][slot]
        if antiga == nome:
            return True
        for t in (self.teclas, self.teclas2):
            for l in range(4):
                for s in range(2):
                    if nome and t[l][s] == nome:
                        t[l][s] = antiga
        alvo[lane][slot] = nome
        if not self._teclas_ok():
            self.teclas, self.teclas2 = backup
            return False
        return True

    def limpar_tecla(self, lane: int, slot: int, jogador: int = 0) -> bool:
        return self.definir_tecla(lane, slot, "", jogador)

    def ajustar(self, campo: str, passo: int, circular: bool = False) -> None:
        """Move para a opção anterior/seguinte de uma lista (fps, velocidade, volumes...)."""
        lista = LISTAS[campo]
        atual = getattr(self, campo)
        i = lista.index(atual) if atual in lista else lista.index(PADRAO[campo])
        i = (i + passo) % len(lista) if circular else max(0, min(len(lista) - 1, i + passo))
        setattr(self, campo, lista[i])

    def mudar_fps(self, passo: int) -> None:
        self.ajustar("fps", passo, circular=True)

    def alternar(self, campo: str) -> None:
        setattr(self, campo, not getattr(self, campo))

    def definir_ajuste(self, ms: float) -> None:
        self.ajuste_ms = int(max(AJUSTE_MIN, min(AJUSTE_MAX, round(ms))))

    def mapa_teclas(self, jogador: int = 0) -> dict:
        """{nome_da_tecla: lane}"""
        return {nome: lane for lane, par in enumerate(self.tabela(jogador)) for nome in par if nome}


class Recordes:
    """Melhor pontuação por música e dificuldade."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        try:
            with open(self.caminho, encoding="utf-8") as f:
                dados = json.load(f)
            self.dados = {k: int(v) for k, v in dados.items()}
        except (OSError, ValueError, AttributeError, TypeError):
            self.dados = {}

    @staticmethod
    def chave(id_musica: str, dificuldade: str) -> str:
        return f"{id_musica}:{dificuldade}"

    def obter(self, id_musica: str, dificuldade: str) -> int:
        return self.dados.get(self.chave(id_musica, dificuldade), 0)

    def registrar(self, id_musica: str, dificuldade: str, pontos: int) -> bool:
        """Devolve True se for um novo recorde (e salva)."""
        k = self.chave(id_musica, dificuldade)
        if pontos <= self.dados.get(k, 0):
            return False
        self.dados[k] = pontos
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho, "w", encoding="utf-8") as f:
                json.dump(self.dados, f, indent=2)
        except OSError:
            pass
        return True
