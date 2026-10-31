# Qualidade dos dados

Fatos auditados na ADR-000 §13; este relatório não detecta dinamicamente todas as anomalias. Confira novamente quando os dados de origem mudarem.

- Telefone (67) 3341-4444 (capa, §1.2) vs (67) 3321-4500 (§7); e-mail com e sem acento.
- Parcelamento: tabela da §3 (mínimo R$ 100) vs faixas da §3.1; trecho ambíguo "exceto abaixo de R$ 50".
- Totais: pedido 3 registra 3.450,00 e os itens somam 3.498,00; pedido 20 registra 1.400,00 e os itens somam 1.488,00.
- Produto 130 `coming_soon` presente nos pedidos 3 e 14.
- Produto 136 `discontinued` com 13 unidades em estoque.
- Categorias 6, 7 e 8 sem produtos.
- Promoções sem datas e duplicadas por produto; apenas 4 ativas (produtos 90, 94, 121, 127).
- Nenhuma data de recebimento nem canal de compra nos pedidos.
- Pedidos `pending` desde mar/2026; pedido 8 `shipped` com previsão vencida.

Inconsistências adicionais, verificadas contra os CSVs em 2026-10-31 (fatos dos dados, não decisões; tratamento em `docs/DECISIONS.md`):

- Parcelamentos registrados fora da §3.1: pedido 9 (6x de R$ 58,32), pedido 16 (6x de R$ 71,65), pedido 18 (12x de R$ 38,32).
- Pedidos pagos via PIX (1, 5, 10, 13, 17) registram o preço de tabela, sem o desconto de 5%.
- Descrição divergente do nome ou das specs: 135 (nome Music Man, descrição Fender Jazz Bass, corpo Alder vs specs Ash), 136 (nome Ibanez, descrição "Precision"), 137 (nome Yamaha, descrição Ibanez 5 cordas vs specs 4), 139 (nome Yamaha, descrição Pearl Export, cascos Poplar vs specs Maple), 140 (nome Pearl, descrição Tama, cascos Birch vs specs Maple), 142 (nome Korg, descrição Roland 88 teclas vs specs 61), 144 (nome Roland, descrição Yamaha). Os produtos 138, 141 e 143 citam outro modelo da mesma marca.
- E-mail `bruno.martins@jmail.com` repetido nos clientes 11 e 43.
- §5.2 cita "contrabaixos" e "pianos digitais": a categoria 2 (Baixos) descreve todos os produtos como "contrabaixo"; a categoria 8 (contrabaixo acústico) está vazia; nenhum produto da categoria 4 tem tipo piano digital (todos `Synthesizer`).
- Promoções inativas com desconto fora das faixas da §6.1: id 1 (Black Friday 10%; manual 15–30%) e id 17 (Aniversário 30%; manual 10–25%). Campanhas sem correspondência no manual: Liquidação de Inverno, Promoção de Páscoa, Oferta Especial, Desconto Exclusivo. Promoção 16 em produto descontinuado (113).
- Chaves de `specs` variam por categoria (violões/ukuleles; guitarras/baixos; baterias; teclados).
- `products.csv` fora de ordem (145 entre 130 e 131); 65 produtos, contra "mais de 300" no manual (§1).
- Nomes dos arquivos com espaços: `desafio_tecnico_ai_eng - <tabela>.csv`.
