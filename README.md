# Pygame.RafaeleJoao

Pygame.RafaeleJoao é um jogo de arco e flecha em formato semi-3D desenvolvido com o Pygame. Nele, o jogador controla o ângulo horizontal (yaw) e o ângulo vertical (pitch) para mirar, segura a tecla espaço para carregar a força do disparo e solta para lançar a flecha em direção a um alvo posicionado à frente do jogador. A trajetória da flecha segue a física de um projétil sujeito à gravidade, enquanto o tamanho aparente do alvo varia conforme a distância e o campo de visão configurado. Além disso, um círculo vermelho é projetado sobre o alvo indicando onde o tiro acertaria em um cenário sem queda, servindo como uma prévia visual da mira ideal.

Durante a partida, o jogador pode girar a mira para os lados usando A e D, ajustar a inclinação com W e S, e usar espaço para carregar e disparar a flecha, desde que nenhuma flecha esteja em voo e ainda restem tiros na aljava. As teclas 1, 2 e 3 alternam entre os níveis de dificuldade — fácil, médio e difícil —, enquanto a tecla R recarrega a aljava com cinco flechas após o término de uma rodada. Por fim, a tecla ESC encerra o jogo.

Quanto à pontuação, cada rodada utiliza uma aljava de cinco flechas, e os pontos são acumulados conforme a precisão do disparo: os anéis externos valem menos pontos (10) e o centro do alvo garante a pontuação máxima (100). As marcas de impacto permanecem visíveis no alvo até o fim da rodada, ajudando o jogador a acompanhar seu desempenho. A interface exibe informações em tempo real — ângulos, força de disparo, pontuação total, flechas restantes e detalhes do último tiro — tornando a experiência mais imersiva e informativa.

---

Semi-3D bow-and-arrow game built with Pygame. Aim using yaw/pitch controls, hold `SPACE` to draw power, and release to fire at a distance-scaled bullseye positioned along the +y axis. All tunable values come from the `.env` file.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The repo already includes a `.env` file populated with the default parameters described in `SystemInstructions.md`. Tweak any values there to experiment with projection, physics, or controls.

## Running

```bash
python game.py
```

## Controls

- `A/D`: yaw left/right (clamped to ±15°)
- `W/S`: pitch up/down (clamped to ±15°)
- `SPACE`: hold to charge, release to fire once the arrow is ready (disabled when an arrow is in flight or the quiver is empty)
- `1/2/3`: switch difficulty (EASY/MEDIUM/HARD) between shots
- `R`: reload a 5-arrow quiver after expending all shots
- `ESC`: quit

Each 5-arrow quiver tallies a cumulative score (outer ring = 10 pts … center ring = 100 pts) and renders red hit markers that remain on the target until the quiver is finished. The UI shows aim angles, power, score, arrows remaining, and last-shot details. Target apparent size scales with distance using the configured field-of-view, and arrow motion follows gravity-driven projectile physics. A red aim circle is projected onto the target along the straight-line direction of your aim (without gravity compensation), providing a quick preview of the “ideal” line-of-sight impact point.
