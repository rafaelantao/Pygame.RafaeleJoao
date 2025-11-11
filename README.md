#Jogo:

Tiro ao Alvo é um jogo de arco e flecha em formato semi-3D desenvolvido com o Pygame.

Nele, o jogador controla o ângulo horizontal (yaw) e o ângulo vertical (pitch) para mirar. Para disparar, segura-se a tecla "ESPACO" para carregar a força do disparo e solta-se para lançar a flecha em direção a um alvo posicionado à frente do jogador.

A trajetória da flecha segue a física de um projétil sujeito à gravidade, enquanto o tamanho aparente do alvo varia conforme a distância e o campo de visão configurado. Além disso, um círculo vermelho é projetado sobre o alvo, indicando onde o tiro acertaria em um cenário sem queda e servindo como uma prévia visual da mira ideal.

Durante a partida, o jogador pode:

- Girar a mira para os lados usando "A" e "D"
- Ajustar a inclinação com "W" e "S"
- Usar "ESPACO" para carregar e disparar a flecha (desde que nenhuma flecha esteja em voo e ainda restem tiros na aljava)
- Alternar os níveis de dificuldade (1: fácil, 2: médio, 3: difícil)
- Recarregar a aljava com cinco flechas após o término de uma rodada usando "R"
- Encerrar o jogo com "ESC"

#Pontuação:

Cada rodada utiliza uma aljava de cinco flechas, e os pontos são acumulados conforme a precisão do disparo:

- Os anéis externos valem menos pontos (10)
- O centro do alvo garante a pontuação máxima (100)

Além disso, as marcas de impacto permanecem visíveis no alvo até o fim da rodada, o que ajuda o jogador a acompanhar seu desempenho.

A interface exibe informações em tempo real, como:

- Ângulo de mira
- Força de disparo
- Pontuação total
- Número de flechas restantes
- Detalhes do último tiro

