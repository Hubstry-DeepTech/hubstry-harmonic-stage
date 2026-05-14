"""Motor de Cue — Gerenciamento e reprodução de cues de iluminação.

Este módulo implementa o sistema de cue para controle de iluminação teatral,
inspirado nos consoles de iluminação profissionais. Um **cue** captura um
instantâneo do estado de todos os canais HPG em um dado momento, com
informações de transição (fade in/out) e prioridade.

A :class:`CueStack` organiza cues em sequência para execução ordenada,
enquanto o :class:`CueEngine` coordena a reprodução, permitindo operações
de *go*, *backup*, *stop* (blackout) e gravação de novos cues a partir
do estado atual das fixtures.

Exemplo de uso:
    >>> engine = CueEngine(fixture_controller)
    >>> cue = engine.record_cue("Abertura", fade_in=2.0, fade_out=1.5)
    >>> engine.play_cue(cue)
    >>> engine.stop()  # blackout
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from .fixture_controller import FixtureController

logger = logging.getLogger(__name__)


@dataclass
class Cue:
    """Representação de um cue de iluminação.

    Um cue captura um instantâneo dos valores de canais HPG, juntamente com
    parâmetros de transição e prioridade de execução.

    Attributes:
        id: Identificador único do cue (gerado automaticamente se omitido).
        name: Nome descritivo do cue.
        values: Mapeamento de canais HPG para valores normalizados (0.0–1.0).
        fade_in: Duração da transição de entrada em segundos.
        fade_out: Duração da transição de saída em segundos.
        hold: Tempo de permanência em segundos (0 = disparo manual).
        priority: Prioridade do cue (maior = sobrepõe menor em conflitos).
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    values: dict[int, float] = field(default_factory=dict)
    fade_in: float = 1.0
    fade_out: float = 1.0
    hold: float = 0.0
    priority: int = 0

    def __post_init__(self) -> None:
        """Valida e normaliza os campos do cue."""
        if self.fade_in < 0:
            raise ValueError(
                f"fade_in deve ser ≥ 0, recebido: {self.fade_in}"
            )
        if self.fade_out < 0:
            raise ValueError(
                f"fade_out deve ser ≥ 0, recebido: {self.fade_out}"
            )
        if self.hold < 0:
            raise ValueError(
                f"hold deve ser ≥ 0, recebido: {self.hold}"
            )
        # Normaliza valores para [0.0, 1.0]
        normalized: dict[int, float] = {}
        for ch, val in self.values.items():
            normalized[ch] = max(0.0, min(1.0, val))
        self.values = normalized

    def to_dict(self) -> dict[str, Any]:
        """Serializa o cue para dicionário.

        Returns:
            Dicionário com todos os campos do cue.
        """
        return {
            "id": self.id,
            "name": self.name,
            "values": {str(k): v for k, v in self.values.items()},
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "hold": self.hold,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Cue:
        """Desserializa um cue a partir de dicionário.

        Args:
            data: Dicionário com campos do cue. As chaves de ``values``
                  podem ser strings ou inteiros.

        Returns:
            Instância de :class:`Cue`.
        """
        raw_values = data.get("values", {})
        # Converte chaves string para int
        values: dict[int, float] = {}
        for k, v in raw_values.items():
            values[int(k)] = float(v)

        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            values=values,
            fade_in=float(data.get("fade_in", 1.0)),
            fade_out=float(data.get("fade_out", 1.0)),
            hold=float(data.get("hold", 0.0)),
            priority=int(data.get("priority", 0)),
        )

    def __repr__(self) -> str:
        return (
            f"Cue(id='{self.id}', name='{self.name}', "
            f"channels={len(self.values)}, "
            f"fade_in={self.fade_in}s, fade_out={self.fade_out}s, "
            f"priority={self.priority})"
        )


class CueStack:
    """Pilha sequencial de cues para execução ordenada.

    A :class:`CueStack` gerencia uma lista ordenada de cues, com operações
    de adição, remoção, inserção, troca e movimentação. Suporta
    serialização para JSON para persistência.

    Args:
        max_cues: Número máximo de cues na pilha (padrão 1000).

    Example:
        >>> stack = CueStack()
        >>> pos = stack.add_cue(Cue(name="Cena 1"))
        >>> assert pos == 1
        >>> stack.insert_cue(1, Cue(name="Prelúdio"))
    """

    def __init__(self, max_cues: int = 1000) -> None:
        """Inicializa a pilha de cues.

        Args:
            max_cues: Capacidade máxima da pilha.
        """
        if max_cues < 1:
            raise ValueError(
                f"max_cues deve ser ≥ 1, recebido: {max_cues}"
            )
        self._max_cues: int = max_cues
        self._cues: list[Cue] = []
        self._current_position: int = 0  # posição do último "go" (0 = nenhum)

    def _validate_position(self, position: int) -> None:
        """Valida se a posição está dentro dos limites da pilha.

        Args:
            position: Posição a validar (base-1).

        Raises:
            IndexError: Se a posição estiver fora do intervalo válido.
        """
        if not 1 <= position <= len(self._cues):
            raise IndexError(
                f"Posição {position} inválida. "
                f"Pilha possui {len(self._cues)} cue(s) "
                f"(posições 1–{len(self._cues)})."
            )

    def add_cue(self, cue: Cue) -> int:
        """Adiciona um cue ao final da pilha.

        Args:
            cue: Instância de :class:`Cue` a ser adicionada.

        Returns:
            Posição (base-1) onde o cue foi inserido.

        Raises:
            OverflowError: Se a pilha estiver cheia.
        """
        if len(self._cues) >= self._max_cues:
            raise OverflowError(
                f"Pilha de cues cheia ({self._max_cues} cues). "
                f"Remova um cue antes de adicionar outro."
            )
        self._cues.append(cue)
        position = len(self._cues)
        logger.info("Cue '%s' adicionado na posição %d.", cue.name, position)
        return position

    def remove_cue(self, position: int) -> None:
        """Remove um cue da pilha pela posição.

        Args:
            position: Posição do cue a remover (base-1).

        Raises:
            IndexError: Se a posição for inválida.
        """
        self._validate_position(position)
        removed = self._cues.pop(position - 1)
        logger.info(
            "Cue '%s' removido da posição %d.", removed.name, position
        )

    def insert_cue(self, position: int, cue: Cue) -> None:
        """Insere um cue em uma posição específica.

        Os cues existentes a partir dessa posição são deslocados para baixo.

        Args:
            position: Posição de inserção (base-1).
            cue: Instância de :class:`Cue` a ser inserida.

        Raises:
            IndexError: Se a posição for inválida.
            OverflowError: Se a pilha estiver cheia.
        """
        if len(self._cues) >= self._max_cues:
            raise OverflowError(
                f"Pilha de cues cheia ({self._max_cues} cues)."
            )
        # Permite inserir na posição len+1 (final)
        if not 1 <= position <= len(self._cues) + 1:
            raise IndexError(
                f"Posição de inserção {position} inválida. "
                f"Intervalo válido: 1–{len(self._cues) + 1}."
            )
        self._cues.insert(position - 1, cue)
        logger.info(
            "Cue '%s' inserido na posição %d.", cue.name, position
        )

    def get_cue(self, position: int) -> Cue:
        """Retorna o cue em uma posição específica.

        Args:
            position: Posição do cue desejado (base-1).

        Returns:
            Instância de :class:`Cue`.

        Raises:
            IndexError: Se a posição for inválida.
        """
        self._validate_position(position)
        return self._cues[position - 1]

    def get_all(self) -> list[Cue]:
        """Retorna todos os cues da pilha em ordem.

        Returns:
            Lista de :class:`Cue` em ordem de posição.
        """
        return list(self._cues)

    def swap(self, pos_a: int, pos_b: int) -> None:
        """Troca dois cues de posição.

        Args:
            pos_a: Primeira posição (base-1).
            pos_b: Segunda posição (base-1).

        Raises:
            IndexError: Se alguma posição for inválida.
        """
        self._validate_position(pos_a)
        self._validate_position(pos_b)
        if pos_a == pos_b:
            return
        self._cues[pos_a - 1], self._cues[pos_b - 1] = (
            self._cues[pos_b - 1],
            self._cues[pos_a - 1],
        )
        logger.info("Cues nas posições %d e %d trocados.", pos_a, pos_b)

    def move(self, from_pos: int, to_pos: int) -> None:
        """Move um cue de uma posição para outra.

        O cue é removido da posição de origem e inserido na posição de
        destino. Os cues intermediários são reordenados consequentemente.

        Args:
            from_pos: Posição de origem (base-1).
            to_pos: Posição de destino (base-1).

        Raises:
            IndexError: Se alguma posição for inválida.
        """
        self._validate_position(from_pos)
        if not 1 <= to_pos <= len(self._cues):
            raise IndexError(
                f"Posição de destino {to_pos} inválida. "
                f"Intervalo válido: 1–{len(self._cues)}."
            )
        if from_pos == to_pos:
            return

        cue = self._cues.pop(from_pos - 1)
        # Ajusta destino se a remoção deslocou as posições
        adjusted_to = to_pos - 1 if from_pos < to_pos else to_pos - 1
        self._cues.insert(adjusted_to, cue)
        logger.info(
            "Cue '%s' movido da posição %d para %d.",
            cue.name,
            from_pos,
            to_pos,
        )

    def to_json(self) -> str:
        """Serializa a pilha de cues para string JSON.

        Returns:
            String JSON com todos os cues em ordem.
        """
        data = [cue.to_dict() for cue in self._cues]
        return json.dumps(data, ensure_ascii=False, indent=2)

    def from_json(self, data: str) -> None:
        """Carrega cues a partir de uma string JSON.

        Substitui todo o conteúdo atual da pilha pelos cues contidos
        no JSON fornecido.

        Args:
            data: String JSON contendo uma lista de dicionários de cues.
        """
        parsed = json.loads(data)
        if not isinstance(parsed, list):
            raise ValueError(
                "JSON deve conter uma lista de dicionários de cues."
            )
        self._cues.clear()
        for item in parsed:
            cue = Cue.from_dict(item)
            self._cues.append(cue)
        logger.info(
            "CueStack carregada com %d cues via JSON.", len(self._cues)
        )

    @property
    def current_position(self) -> int:
        """Posição do último cue executado via ``go`` (0 = nenhum)."""
        return self._current_position

    def __len__(self) -> int:
        """Retorna o número de cues na pilha."""
        return len(self._cues)

    def __repr__(self) -> str:
        return (
            f"CueStack(cues={len(self._cues)}/{self._max_cues}, "
            f"current={self._current_position})"
        )


class CueEngine:
    """Motor de execução de cues de iluminação.

    O :class:`CueEngine` coordena a reprodução de cues, integrando-se ao
    :class:`FixtureController` para aplicar estados de iluminação. Oferece
    operações de *go* (avançar), *backup* (retroceder), *stop* (blackout)
    e gravação de novos cues a partir do estado atual.

    As transições de fade são registradas como stubs para implementação
    futura com temporização assíncrona (threading ou asyncio).

    Args:
        fixture_controller: Instância de :class:`FixtureController` cujo
                            estado será usado para gravação e reprodução.

    Example:
        >>> ctrl = FixtureController()
        >>> ctrl.add_fixture(par_fixture)
        >>> ctrl.set_value("PAR-001", "red", 1.0)
        >>> engine = CueEngine(ctrl)
        >>> cue = engine.record_cue("Vermelho Total", fade_in=2.0)
        >>> engine.play_cue(cue)
    """

    def __init__(self, fixture_controller: FixtureController) -> None:
        """Inicializa o motor de cues.

        Args:
            fixture_controller: Controlador de fixtures associado.
        """
        self._controller: FixtureController = fixture_controller
        self._active_state: dict[int, float] = {}
        self._is_playing: bool = False
        self._last_cue: Cue | None = None
        logger.info("CueEngine inicializado com FixtureController.")

    def record_cue(
        self,
        name: str,
        fade_in: float = 1.0,
        fade_out: float = 1.0,
        hold: float = 0.0,
        priority: int = 0,
    ) -> Cue:
        """Grava um novo cue capturando o estado atual de todas as fixtures.

        O método lê o estado consolidado de todos os canais HPG do
        controlador de fixtures e cria um cue com os valores atuais.

        Args:
            name: Nome descritivo do cue.
            fade_in: Duração do fade de entrada (segundos).
            fade_out: Duração do fade de saída (segundos).
            hold: Tempo de permanência (segundos, 0 = manual).
            priority: Prioridade do cue (maior sobrepõe menor).

        Returns:
            Instância de :class:`Cue` recém-criada com o estado atual.
        """
        hpg_state = self._controller.all_to_hpg()
        cue = Cue(
            name=name,
            values=dict(hpg_state),
            fade_in=fade_in,
            fade_out=fade_out,
            hold=hold,
            priority=priority,
        )
        logger.info(
            "Cue '%s' gravado: %d canais, fade_in=%.1fs, "
            "fade_out=%.1fs, hold=%.1fs, priority=%d",
            name,
            len(cue.values),
            fade_in,
            fade_out,
            hold,
            priority,
        )
        return cue

    def play_cue(self, cue: Cue) -> None:
        """Reproduz um cue, aplicando seus valores às fixtures.

        Atualmente a aplicação é instantânea. A lógica de fade (transição
        gradual) é registrada como stub para implementação futura com
        temporização assíncrona.

        .. note::
            Implementação futura: fade usando interpolação linear ou
            curvas S (sigmoid) entre o estado anterior e o estado do cue,
            executado em thread/tarefa separada.

        Args:
            cue: Instância de :class:`Cue` a ser reproduzida.
        """
        self._apply_cue_values(cue)
        self._last_cue = cue
        self._is_playing = True

        logger.info(
            "Cue '%s' reproduzido: %d canais aplicados "
            "(fade=%.1fs — stub)",
            cue.name,
            len(cue.values),
            cue.fade_in,
        )

        # ── Stub de fade ─────────────────────────────────────────────
        # TODO: Implementar transição gradual usando threading/asyncio
        # if cue.fade_in > 0:
        #     self._fade_transition(
        #         from_state=self._active_state,
        #         to_state=cue.values,
        #         duration=cue.fade_in,
        #     )
        # ────────────────────────────────────────────────────────────

    def go(self, stack: CueStack, position: int) -> None:
        """Executa (*go*) o cue na posição indicada da pilha.

        Operação padrão de consoles de iluminação: avança para o cue
        especificado e o reproduz.

        Args:
            stack: Instância de :class:`CueStack` com os cues.
            position: Posição do cue a executar (base-1).

        Raises:
            IndexError: Se a posição for inválida.
        """
        cue = stack.get_cue(position)
        stack._current_position = position
        logger.info("GO → posição %d", position)
        self.play_cue(cue)

    def backup_go(self, stack: CueStack) -> None:
        """Retorna (*backup*) ao cue anterior na pilha.

        Se não houver cue anterior (posição ≤ 1), não faz nada.

        Args:
            stack: Instância de :class:`CueStack`.
        """
        current = stack.current_position
        if current <= 1:
            logger.warning(
                "Backup GO: já está na primeira posição (%d).", current
            )
            return

        prev_position = current - 1
        stack._current_position = prev_position
        logger.info("BACKUP GO → posição %d", prev_position)
        cue = stack.get_cue(prev_position)
        self.play_cue(cue)

    def stop(self) -> None:
        """Para a reprodução e aplica blackout (todos os canais em 0.0).

        Zera todos os valores do estado ativo e desliga todas as fixtures.
        """
        self._active_state.clear()
        self._is_playing = False
        self._last_cue = None

        logger.info("STOP / BLACKOUT — todos os canais zerados.")

    def get_active_state(self) -> dict[int, float]:
        """Retorna o estado HPG atualmente ativo.

        Returns:
            Dicionário ``{canal_hpg: valor}`` com o estado ativo.
        """
        return dict(self._active_state)

    def merge_cues(self, *cues: Cue) -> Cue:
        """Funde múltiplos cues em um único cue.

        Em caso de conflito (mesmo canal HPG presente em mais de um cue),
        o cue com **maior prioridade** vence. Se as prioridades forem
        iguais, o último cue na ordem dos argumentos sobrepõe os anteriores.

        Os parâmetros de tempo (fade_in, fade_out, hold) são configurados
        com os valores máximos entre os cues de entrada.

        Args:
            *cues: Instâncias de :class:`Cue` a serem fundidas.

        Returns:
            Novo :class:`Cue` com os valores mesclados.
        """
        if not cues:
            raise ValueError("Pelo menos um cue deve ser fornecido para fusão.")

        merged_values: dict[int, float] = {}
        max_fade_in = 0.0
        max_fade_out = 0.0
        max_hold = 0.0
        max_priority = 0
        names: list[str] = []

        # Ordena por prioridade (menor primeiro → maior sobrepõe)
        sorted_cues = sorted(cues, key=lambda c: c.priority)

        for cue in sorted_cues:
            merged_values.update(cue.values)
            max_fade_in = max(max_fade_in, cue.fade_in)
            max_fade_out = max(max_fade_out, cue.fade_out)
            max_hold = max(max_hold, cue.hold)
            max_priority = max(max_priority, cue.priority)
            if cue.name:
                names.append(cue.name)

        merged_name = " + ".join(names) if names else "Cue Mesclado"
        merged_cue = Cue(
            name=merged_name,
            values=merged_values,
            fade_in=max_fade_in,
            fade_out=max_fade_out,
            hold=max_hold,
            priority=max_priority,
        )

        logger.info(
            "Cues mesclados: %s → '%s' (%d canais)",
            [c.name for c in cues],
            merged_name,
            len(merged_values),
        )
        return merged_cue

    # ── Métodos internos ─────────────────────────────────────────────────

    def _apply_cue_values(self, cue: Cue) -> None:
        """Aplica os valores de um cue ao estado ativo e às fixtures.

        Percorre os valores do cue e atualiza o estado interno. Para cada
        canal HPG no cue, busca a fixture e parâmetro correspondente e
        atualiza o valor da fixture via controlador.

        Args:
            cue: Cue cujos valores serão aplicados.
        """
        # Atualiza o estado ativo do motor
        self._active_state.update(cue.values)

        # Propaga valores para as fixtures via controlador
        self._propagate_to_fixtures(cue.values)

    def _propagate_to_fixtures(self, hpg_values: dict[int, float]) -> None:
        """Propaga valores HPG para os parâmetros das fixtures.

        Busca em todas as fixtures registradas quais parâmetros estão
        mapeados para os canais HPG fornecidos e atualiza os valores
        correspondentes.

        Args:
            hpg_values: Dicionário ``{canal_hpg: valor}``.
        """
        # Constrói mapa reverso: hpg_channel → (fixture_id, parameter)
        reverse_map: dict[int, tuple[str, str]] = {}
        for fixture_id, fixture in self._controller._fixtures.items():
            for param_name, hpg_ch in fixture.hpg_channels.items():
                reverse_map[hpg_ch] = (fixture_id, param_name)

        for hpg_ch, value in hpg_values.items():
            if hpg_ch in reverse_map:
                fixture_id, param_name = reverse_map[hpg_ch]
                try:
                    self._controller.set_value(fixture_id, param_name, value)
                except KeyError:
                    logger.warning(
                        "Falha ao propagar HPG ch %d → %s.%s",
                        hpg_ch,
                        fixture_id,
                        param_name,
                    )

    # ── Propriedades ─────────────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        """Indica se há um cue ativo em reprodução."""
        return self._is_playing

    @property
    def last_cue(self) -> Cue | None:
        """Último cue reproduzido (ou ``None`` se nenhum)."""
        return self._last_cue

    # ── Representação ────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"CueEngine(playing={self._is_playing}, "
            f"active_channels={len(self._active_state)}, "
            f"last_cue='{self._last_cue.name if self._last_cue else '—'}')"
        )
