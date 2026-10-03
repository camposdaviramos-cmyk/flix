"""Original showcase names. Sample playback uses the open Blender film Sintel."""
SAMPLE = 'https://media.w3.org/2010/05/sintel/trailer.mp4'
PHOTO = 'https://images.unsplash.com/'

def catalog():
    rows = [
        ('horizonte', 'Além do Horizonte', 'movie', 'Ficção científica', '2026', '14', 'Uma astronauta. Um sinal impossível. A última chance de encontrar o caminho de volta.', '/static/assets/hero.png', '1483985988355-763728e1935b', '2h 18min'),
        ('neon', 'Cidade Neon', 'series', 'Suspense', '2026', '16', 'Nas ruas onde tudo tem um preço, uma investigadora descobre o segredo que ninguém deveria conhecer.', '', '1519608487953-e999c86e7455', '1 temporada'),
        ('abismo', 'O Abismo', 'movie', 'Aventura', '2025', '12', 'Uma expedição ao desconhecido revela que o maior mistério está bem abaixo da superfície.', '', '1518837695005-2083093ee35b', '1h 52min'),
        ('selvagem', 'Instinto Selvagem', 'series', 'Documentário', '2026', 'L', 'Um encontro extraordinário com a vida que resiste nos lugares mais remotos do planeta.', '', '1546182990-dffeafbe841d', '1 temporada'),
        ('ultimo', 'Último Destino', 'movie', 'Ação', '2025', '16', 'Com o tempo se esgotando, um piloto precisa escolher entre a missão e tudo o que ama.', '', '1473448912268-2022ce9509d8', '2h 05min'),
        ('verao', 'Entre Nós', 'movie', 'Romance', '2026', '12', 'Duas vidas se cruzam em uma viagem inesperada. Algumas histórias merecem uma segunda chance.', '', '1470252649378-9c29740c9fa8', '1h 46min'),
        ('orbita', 'Órbita', 'series', 'Ficção científica', '2025', '14', 'A tripulação de uma estação distante recebe uma mensagem enviada por eles mesmos, vinte anos no futuro.', '', '1446776811953-b23d57bd21aa', '1 temporada'),
        ('montanha', 'O Silêncio do Norte', 'movie', 'Drama', '2026', '12', 'Em uma pequena vila nas montanhas, o retorno de uma filha transforma a vida de uma família.', '', '1464822759023-fed622ff2c3b', '1h 38min'),
    ]
    return [dict(id=r[0], title=r[1], kind=r[2], genre=r[3], year=int(r[4]), rating=r[5], description=r[6], backdrop=r[7] or f'{PHOTO}photo-{r[8]}?auto=format&fit=crop&w=1400&q=85', poster=r[7] or f'{PHOTO}photo-{r[8]}?auto=format&fit=crop&w=600&q=85', duration=r[9], video_url=SAMPLE if r[2]=='movie' else '', featured=i<3, published=1, sample=1) for i,r in enumerate(rows)]
