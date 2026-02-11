# Solplanet Integration for Home Assistant

Integração custom para inversores **Solplanet (AISWEI)** no Home Assistant.

## Recursos

- Sensor de potência instantânea (`W`)
- Sensor de energia do dia (`kWh`)
- Sensor de energia total (`kWh`)
- Sensor de status da API (`ok`, `auth_expired`, `connection_error`)
- Compatível com o **Energy Dashboard** do Home Assistant
- Tratamento para falhas temporárias da API:
  - sensores de contador mantêm o último valor válido
  - sensores variáveis ficam indisponíveis quando a API não está saudável

## Requisitos

- Home Assistant com suporte a `config_flow` (versões modernas)
- Conta Solplanet com acesso ao portal web
- `plant_id`, `token` e `apitoken`

## Instalação

### Opção 1 — Manual

1. Copie a pasta `custom_components/solplanet` para:
   ```
   <config>/custom_components/solplanet
   ```
2. Reinicie o Home Assistant.
3. Vá em **Configurações → Dispositivos e Serviços → Adicionar integração**.
4. Procure por **Solplanet** e informe:
   - `plant_id`
   - `token`
   - `apitoken`

### Opção 2 — HACS (modo custom repository)

1. Abra o HACS.
2. Adicione este repositório como **Custom repository** do tipo **Integration**.
3. Instale a integração **Solplanet**.
4. Reinicie o Home Assistant e configure pela UI.

## Como obter `token` e `apitoken`

Como o endpoint oficial não é público/documentado para terceiros, os tokens podem expirar e precisar de renovação.

Fluxo comum:

1. Faça login no portal Solplanet pelo navegador.
2. Abra o DevTools (F12) → aba **Network**.
3. Recarregue a página da planta/inversor.
4. Identifique uma requisição para `.../api/plant/invList`.
5. Copie:
   - Header `token`
   - Cookie `apitoken`
   - `plantId` da URL/query


## Configuração no Dashboard de Energia ("Como preencher?")

No menu **Configurações → Painéis → Energia**, use os sensores assim:

### Painéis solares

Clique em **Adicionar produção solar** e preencha:

- **Energia produzida**: `sensor.solplanet_energia_total`
  - deve ser `device_class: energy`
  - deve ser acumulado (`state_class: total_increasing`)
- **Potência (opcional, mas recomendado)**: `sensor.solplanet_potencia`

> Use **Energia Total** para o Energy Dashboard. O sensor **Energia Hoje** é útil para cards diários, mas não é o ideal como fonte principal acumulada do dashboard.

### Rede elétrica (se você tiver medidor da concessionária)

A integração Solplanet normalmente não fornece importação/exportação da rede da casa. Para preencher esses campos, use sensores do seu medidor/smart meter:

- **Consumo da rede**: sensor de energia importada da rede
- **Retorno à rede**: sensor de energia exportada

### O que esperar quando a API falha

- **Potência** pode ficar indisponível se a API/autenticação estiver ruim (evita valor variável congelado).
- **Energia total** tende a manter o último valor válido temporariamente.
- Confira `sensor.solplanet_status_api`:
  - `ok`
  - `auth_expired`
  - `connection_error`

Se aparecer `auth_expired`, renove `token` e `apitoken`.

## Sensores e disponibilidade

- **Potência (measurement)**: fica `indisponível` quando o status da API não é `ok`, para evitar valor variável “congelado”.
- **Energia Hoje / Energia Total (contadores)**: podem manter último valor válido em falha temporária, evitando oscilações desnecessárias.
- **Status API**: use esse sensor para monitorar rapidamente autenticação/conectividade.

## Troubleshooting

- `invalid_auth`: tokens inválidos/expirados.
- `cannot_connect`: falha de conectividade/endpoint indisponível.
- Se os dados pararem após algum tempo, renove `token` e `apitoken`.

## Aviso

Esta integração depende de endpoints web observados no portal Solplanet e pode exigir ajustes caso a API mude.

## Créditos

Projeto mantido com apoio da comunidade Home Assistant.
