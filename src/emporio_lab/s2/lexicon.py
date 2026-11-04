"""Léxicos do catálogo sintético do S2.

Duas listas de frases DISJUNTAS por construção e verificadas por teste:
- LEVEL_DESC / USE_DESC: como as DESCRIÇÕES do catálogo expressam nível e uso;
- LEVEL_QUERY / USE_QUERY: como as CONSULTAS DE INTENÇÃO os expressam.
A relevância é definida pelos atributos (nível, uso, tipo...), nunca pelo texto; as consultas não podem reaproveitar o vocabulário das descrições.
Marcas fictícias; coincidência com marcas reais é acidental.
"""

CATEGORIES = {1: 'Guitarras', 2: 'Baixos', 3: 'Baterias e Percussão', 4: 'Teclados e Pianos', 5: 'Violões',
              6: 'Instrumentos de Sopro (Madeiras)', 7: 'Instrumentos de Sopro (Metais)', 8: 'Cordas Orquestrais', 9: 'Ukuleles'}
CATEGORY_DESCRIPTIONS = {1: 'Guitarras elétricas de todos os estilos', 2: 'Baixos elétricos para todas as formações', 3: 'Baterias e peças de percussão',
                         4: 'Pianos digitais, sintetizadores e controladores', 5: 'Violões clássicos, folk e eletroacústicos',
                         6: 'Flautas, clarinetes e saxofones', 7: 'Trompetes, trombones e tubas', 8: 'Violinos, violas e violoncelos', 9: 'Ukuleles de vários tamanhos'}
# preço de referência (centavos) por categoria; o nível de preço multiplica
BASE_PRICE = {1: 120000, 2: 130000, 3: 250000, 4: 180000, 5: 70000, 6: 90000, 7: 140000, 8: 160000, 9: 35000}
TIER_MULT = (0.5, 1.0, 2.0, 4.5)
TIER_NAMES = ('economico', 'intermediario', 'alto', 'premium')
LEVELS = ('iniciante', 'intermediario', 'avancado', 'profissional')
USES = ('estudo', 'palco', 'gravacao', 'silencioso', 'viagem', 'igreja', 'infantil')

# (chave, categoria, termo no catálogo, sinônimo usado só nas consultas, usos plausíveis)
TYPES = (
    ('guitarra_single', 1, 'guitarra single coil', 'guitarra de bobina simples', ('estudo', 'palco', 'gravacao')),
    ('guitarra_humbucker', 1, 'guitarra humbucker', 'guitarra de bobina dupla', ('palco', 'gravacao', 'igreja')),
    ('guitarra_semi', 1, 'guitarra semiacústica', 'guitarra de caixa oca', ('palco', 'igreja', 'silencioso', 'gravacao')),
    ('guitarra_baritone', 1, 'guitarra baritone', 'guitarra de escala longa e afinação grave', ('palco', 'gravacao')),
    ('baixo_ativo', 2, 'baixo ativo', 'graves elétrico com pré embutido', ('palco', 'gravacao', 'igreja')),
    ('baixo_passivo', 2, 'baixo passivo', 'graves elétrico sem pré embutido', ('estudo', 'palco', 'igreja')),
    ('baixo_cinco', 2, 'baixo de 5 cordas', 'graves elétrico com cinco cordas', ('palco', 'gravacao')),
    ('baixo_fretless', 2, 'baixo fretless', 'graves elétrico sem trastes', ('gravacao', 'palco')),
    ('bateria_acustica', 3, 'bateria acústica', 'kit de tambores de madeira', ('estudo', 'palco', 'igreja', 'gravacao')),
    ('bateria_eletronica', 3, 'bateria eletrônica', 'kit de tambores com pads digitais', ('silencioso', 'estudo', 'palco', 'infantil')),
    ('cajon', 3, 'cajón', 'caixote de percussão para sentar em cima', ('viagem', 'estudo', 'igreja', 'palco')),
    ('djembe', 3, 'djembê', 'tambor africano em forma de cálice', ('viagem', 'palco', 'infantil')),
    ('piano_digital', 4, 'piano digital', 'piano eletrônico de teclas com peso', ('estudo', 'silencioso', 'igreja', 'palco')),
    ('teclado_arranjador', 4, 'teclado arranjador', 'teclado com acompanhamento automático embutido', ('palco', 'igreja', 'infantil', 'estudo')),
    ('sintetizador', 4, 'sintetizador', 'gerador de timbres eletrônicos analógicos', ('gravacao', 'palco')),
    ('controlador_midi', 4, 'controlador MIDI', 'teclas mudas para ligar no computador', ('gravacao', 'silencioso', 'viagem')),
    ('violao_nylon', 5, 'violão clássico nylon', 'violão de cordas macias', ('estudo', 'igreja', 'infantil', 'palco')),
    ('violao_aco', 5, 'violão folk aço', 'violão de cordas metálicas', ('palco', 'estudo', 'viagem', 'igreja')),
    ('violao_eletro', 5, 'violão eletroacústico', 'violão com captação e saída para amplificador', ('palco', 'igreja', 'gravacao')),
    ('violao_doze', 5, 'violão de 12 cordas', 'violão de doze cordas', ('palco', 'gravacao')),
    ('flauta_transversal', 6, 'flauta transversal', 'flauta lateral de metal prateado', ('estudo', 'palco', 'igreja')),
    ('clarinete', 6, 'clarinete', 'sopro de palheta única', ('estudo', 'palco', 'igreja')),
    ('sax_alto', 6, 'saxofone alto', 'sax melódico em mi bemol', ('palco', 'estudo', 'gravacao')),
    ('flauta_doce', 6, 'flauta doce', 'flauta de bisel', ('infantil', 'estudo', 'viagem')),
    ('trompete', 7, 'trompete', 'metal agudo de três pistos', ('palco', 'estudo', 'igreja')),
    ('trombone', 7, 'trombone de vara', 'metal de tubo deslizante', ('palco', 'igreja', 'estudo')),
    ('tuba', 7, 'tuba', 'metal grave de bocal largo', ('palco', 'igreja')),
    ('trompa', 7, 'trompa', 'metal enrolado de timbre aveludado', ('palco', 'gravacao')),
    ('violino', 8, 'violino', 'instrumento de arco agudo', ('estudo', 'infantil', 'palco', 'gravacao')),
    ('viola_arco', 8, 'viola de arco', 'cordas friccionadas de registro médio', ('estudo', 'palco', 'gravacao')),
    ('violoncelo', 8, 'violoncelo', 'instrumento de arco que se toca entre as pernas', ('estudo', 'palco', 'gravacao')),
    ('contrabaixo_acustico', 8, 'contrabaixo acústico', 'arcão de orquestra tocado em pé', ('palco', 'gravacao')),
    ('ukulele_soprano', 9, 'ukulele soprano', 'cavaquinho havaiano miúdo', ('viagem', 'infantil', 'estudo')),
    ('ukulele_concert', 9, 'ukulele concert', 'cavaquinho havaiano médio', ('estudo', 'palco', 'viagem')),
    ('ukulele_tenor', 9, 'ukulele tenor', 'cavaquinho havaiano grande', ('palco', 'gravacao', 'viagem')),
    ('ukulele_baritono', 9, 'ukulele barítono', 'cavaquinho havaiano de afinação grave', ('palco', 'gravacao')),
)
# substantivo de categoria que as consultas podem usar (lista branca: citar o instrumento é o mínimo de qualquer consulta)
CATEGORY_NOUN = {1: 'guitarra', 2: 'baixo', 3: 'bateria', 4: 'teclado', 5: 'violão', 6: 'flauta', 7: 'trompete', 8: 'violino', 9: 'ukulele'}
CATEGORY_NOUN_CATS = {'guitarra': (1,), 'baixo': (2,), 'bateria': (3,), 'teclado': (4,), 'violão': (5,), 'ukulele': (9,)}

BRANDS = ('Vallori', 'Tonale', 'Sonaris', 'Brasilo', 'Meridiano', 'Harmonix', 'Aurelia', 'Cadenza', 'Nortelli', 'Ventura', 'Lumera', 'Fortezza',
          'Orvalho', 'Pratense', 'Quirino', 'Rubato', 'Solferino', 'Trovador', 'Ulisses', 'Vibrato', 'Zefiro', 'Allegra', 'Bemol', 'Capella')
FINISHES = ('Natural', 'Preto Fosco', 'Sunburst', 'Branco Pérola', 'Azul Cobalto', 'Vermelho Cereja', 'Verde Floresta', 'Mel', 'Grafite', 'Nogueira', 'Marfim', 'Cinza Lunar')

LEVEL_DESC = {
    'iniciante': ('indicado para quem dá os primeiros passos', 'recomendado a alunos em fase inicial de aprendizado', 'ótima porta de entrada para estreantes',
                  'construção descomplicada pensada para as primeiras aulas', 'acessível e simples de dominar logo de início'),
    'intermediario': ('para músicos que já passaram do básico', 'equilíbrio entre custo e recursos para quem está evoluindo',
                      'atende quem já tem alguma vivência de ensaios', 'acabamento e resposta acima do básico'),
    'avancado': ('resposta refinada para instrumentistas experientes', 'recursos exigidos por quem toca com frequência',
                 'construção cuidadosa para execução rigorosa', 'pensado para músicos de longa estrada'),
    'profissional': ('padrão exigido em shows e gravações remuneradas', 'robustez para turnês e uso diário intenso',
                     'grau máximo de acabamento do catálogo', 'escolha de quem vive de música'),
}
LEVEL_QUERY = {
    'iniciante': ('para quem nunca tocou', 'instrumento de estreia', 'para começar do zero sem complicação', 'dá para aprender sem professor',
                  'para principiante absoluto', 'para dar a largada na música'),
    'intermediario': ('para quem já toca há uns dois anos', 'segundo instrumento da trajetória', 'para o músico que está crescendo',
                      'etapa seguinte para quem já se vira'),
    'avancado': ('para quem toca há muito tempo e é exigente', 'upgrade para músico calejado', 'para tocador veterano de percepção afiada',
                 'para quem encara a música com seriedade'),
    'profissional': ('para quem faz disso profissão', 'a cúpula do ofício para artista de carreira', 'ferramenta de trabalho de músico contratado',
                     'para quem atua como músico de ofício'),
}
USE_DESC = {
    'estudo': ('pensado para a rotina de estudo diário', 'ideal para praticar escalas e repertório diariamente', 'companheiro de aulas e prática guiada',
               'facilita a prática regular'),
    'palco': ('projetado para apresentações ao vivo', 'projeção firme em shows', 'resiste bem à movimentação de palco',
              'destaque visual em apresentações'),
    'gravacao': ('timbre limpo para sessões de gravação', 'resposta detalhada para captação em estúdio', 'baixo ruído de fundo para registros',
                 'excelente para produção musical profissional'),
    'silencioso': ('emissão sonora contida com saída para fones de ouvido', 'pode ser tocado só com fones, sem projeção no ambiente',
                   'modo mudo para prática reservada', 'som reduzido para sessões reservadas'),
    'viagem': ('compacto e leve para carregar', 'acompanha o músico em deslocamentos', 'cabe em malas e mochilas',
               'peso mínimo para quem se desloca muito'),
    'igreja': ('indicado para cultos e celebrações', 'som claro para louvor em comunidade', 'serve bem ao ministério de música',
               'combina com liturgias e reuniões vocais'),
    'infantil': ('tamanho reduzido para mãos miúdas', 'leveza pensada para crianças', 'segurança e conforto para os pequenos',
                 'cores alegres para a garotada'),
}
USE_QUERY = {
    'estudo': ('para treinar lições no quarto', 'para ajudar no curso de música', 'para exercitar os dedos sem parar', 'para fixar a matéria da escola de música'),
    'palco': ('para tocar em boates e bares', 'para subir no tablado com a banda', 'para fazer apresentação em churrasco', 'para tocar diante da plateia'),
    'gravacao': ('para produzir o disco no home studio', 'para guardar canções direto no computador', 'para produzir faixas', 'para fazer demo de canções'),
    'silencioso': ('para tocar em apartamento sem encrenca com vizinhos', 'para treinar de madrugada sem acordar ninguém',
                   'para quem mora em prédio e quer discrição', 'bem baixinho para não incomodar o condomínio'),
    'viagem': ('para despachar na bagagem de avião', 'para tocar nas férias de verão', 'para acampar com os amigos', 'para ir de ônibus com ele nas costas'),
    'igreja': ('para tocar no grupo da paróquia', 'para sustentar o canto do coral da capela', 'para a missa de domingo', 'para a banda do templo'),
    'infantil': ('para presente do filho caçula', 'para meu sobrinho de oito anos', 'para a menina começar a brincar de música',
                 'para meninos em idade escolar'),
}
TIER_DESC = {'economico': ('preço acessível', 'ótimo custo-benefício'), 'intermediario': ('boa relação entre preço e qualidade',),
             'alto': ('investimento sólido', 'materiais selecionados'), 'premium': ('edição de luxo', 'materiais nobres e acabamento artesanal')}
BLURBS = {1: ('Corpo em madeira maciça com braço parafusado.', 'Ponte firme e afinação estável.'),
          2: ('Braço confortável e corpo balanceado.', 'Extensão grave encorpada.'),
          3: ('Ferragens resistentes e bom alcance dinâmico.', 'Montagem rápida.'),
          4: ('Teclado responsivo com várias sonoridades.', 'Conexões completas na traseira.'),
          5: ('Tampo e fundo bem casados e boa ressonância.', 'Escala confortável.'),
          6: ('Mecanismo preciso e resposta pronta.', 'Acompanha estojo rígido.'),
          7: ('Pistos ou vara suaves e afinação segura.', 'Acompanha bocal e estojo.'),
          8: ('Verniz brilhante e som doce.', 'Acompanha arco e breu.'),
          9: ('Corpo leve com cordas macias.', 'Afinação fácil de manter.')}
NOISE = ('Acompanha manual em português.', 'Garantia de 12 meses.', 'Entrega para todo o Brasil.', 'Embalagem reforçada.', 'Lote com inspeção individual.',
         'Revisado antes do envio.', 'Disponível também em outros acabamentos.', 'Linha renovada neste ano.')

# consultas sem correspondência no catálogo
NO_MATCH = ('cavaquinho de samba', 'gaita de foles escocesa', 'acordeon vermelho', 'harpa celta', 'mouse sem fio', 'receita de bolo de cenoura',
            'teclado de computador gamer', 'capa de celular', 'bandolim', 'sitar indiano', 'banjo de cinco cordas', 'ocarina de cerâmica',
            'carregador portátil', 'geladeira frost free', 'tênis de corrida', 'bicicleta de montanha', 'oboé', 'fagote', 'harmônica de boca cromática',
            'berimbau de capoeira', 'caixa de som bluetooth', 'monitor de vídeo', 'previsão do tempo em Recife', 'curso de inglês online',
            'cadeira de escritório', 'kit de ferramentas', 'cítara', 'steel drum', 'theremin', 'mesa de bilhar')
