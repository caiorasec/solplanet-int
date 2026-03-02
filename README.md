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
- `plant_id`
- Para modo remoto: conta Solplanet com `token` e `apitoken`
- Para modo local: host/URL do proxy local (ex.: Balena)

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
   - `connection_mode` (`remote` ou `local`)
5. Se `remote`:
   - `token`
   - `apitoken`
6. Se `local`:
   - `local_host`
   - `local_port` / `local_use_https` (quando não usar URL completa)
   - `inverter_sn` (opcional) ou `inverter_index`
   - `local_basic_user` / `local_basic_password` (opcional, apenas se o proxy exigir)

### Opção 2 — HACS (modo custom repository)

1. Abra o HACS.
2. Adicione este repositório como **Custom repository** do tipo **Integration**.
3. Instale a integração **Solplanet**.
4. Reinicie o Home Assistant e configure pela UI.

## Como obter `token` e `apitoken` (modo remoto)

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


> ⚠️ O portal Solplanet usa captcha (arrastar quebra-cabeça), por isso a renovação automática de token não é confiável.
> Quando expirar, renove manualmente `token` e `apitoken` no navegador.
> Isso se aplica ao modo `remote`. No modo `local`, `token/apitoken` não são necessários para coletar dados do inversor.


## Modos de conexão

Esta integração suporta dois modos:

- `remote` (padrão): usa `https://internation-cloud.solplanet.net`
- `local`: usa `http(s)://<local_host>:<local_port>` para cenários com proxy (ex.: Balena)

No modo `local`, configure:

- `local_host`: IP ou hostname do proxy local
- `local_port`: porta exposta pelo proxy
- `local_use_https`: habilite se o proxy terminar TLS localmente
- `local_basic_user` (opcional): usuário para Basic Auth no proxy
- `local_basic_password` (opcional): senha para Basic Auth no proxy
- `inverter_sn` (opcional): SN/ISN do inversor a ser lido
- `inverter_index` (1-4): usado quando `inverter_sn` não for informado

Se o modo for `remote`, os campos locais são ignorados.
Você pode alterar esses campos depois em **Configurações → Dispositivos e Serviços → Solplanet → Opções**.
No menu de **Opções** você também pode atualizar `token`, `apitoken`, `inverter_sn` e `inverter_index`.

Importante sobre autenticação no local:

- Em ambiente **totalmente local**, normalmente não precisa de autenticação.
- `local_basic_user` / `local_basic_password` existem para cenários com proxy protegido (ex.: Balena exposto na internet).

### Exemplo com Balena

Se você usar URL pública do Balena, pode informar diretamente em `local_host`:

- `connection_mode`: `local`
- `local_host`: `https://<seu-projeto-ou-dispositivo>.balena-devices.com`

Nesse caso, a integração usa o esquema/porta da própria URL (porta explícita opcional).
Se informar só host/IP sem esquema, ela usa `local_use_https` + `local_port`.

### Seleção de inversor local

No modo local, a integração:

- descobre/lista inversores em `getdev.cgi?device=2`
- coleta telemetria em `getdevdata.cgi?device=2&sn=<SN>`

A escolha do inversor segue:

1. `inverter_sn` (se informado)
2. `inverter_index` (1..4)
3. primeiro inversor retornado pela API local

Campos esperados por inversor em `getdev.cgi?device=2`:

- `isn` (SN)
- `model`
- outros metadados de identificação

Campos de telemetria lidos em `getdevdata.cgi?device=2&sn=<SN>`:

- `pac` (W)
- `etd` (0.1 kWh)
- `eto` (0.1 kWh)
- `fac`, `vac`, `iac`, `tmp`, `pf`, `vpv`, `ipv`, `flg`, `wan`, `err`

Além dos sensores de energia/potência, no modo local a integração também expõe:

- frequência AC
- tensão/corrente AC
- tensão/corrente PV (canais 1-3)
- temperatura do inversor
- fator de potência
- códigos `flg`, `wan` e `err`



## Garantia de auto refresh de token

Com o captcha de arrastar quebra-cabeça da Solplanet, **não há como garantir 100%** uma renovação automática em background.

A integração agora tenta um **refresh interno best-effort** reaproveitando sessão/cookie já ativos (sem abrir captcha), mas isso depende do backend da Solplanet e pode não funcionar em todas as contas/regiões.

> Esta seção de refresh de token se aplica ao modo `remote`. No modo `local`, a coleta não depende de `token/apitoken`.

O que esta integração faz para reduzir impacto:

1. Exibe `sensor.solplanet_status_api` com `auth_expired` quando o token expira.
2. Tenta refresh interno sem captcha quando possível (best-effort).
   - faz tentativa proativa periódica (background) para reduzir chance de expiração durante a coleta
   - também faz tentativa reativa imediata se receber erro de autenticação
   - usa endpoints de sessão e consulta `plantList` para validar o novo par token/apitoken
3. Cria uma **notificação persistente no Home Assistant** avisando para renovar `token`/`apitoken` se o refresh falhar.
4. Mantém sensores de contador com último valor válido em falhas temporárias.

Recomendação prática:

- Configure uma automação no HA para alertar no celular quando `sensor.solplanet_status_api` virar `auth_expired`.
- Renove os tokens no portal e atualize a integração.

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

- `invalid_auth`: tokens inválidos/expirados (modo `remote`).
- `cannot_connect`: falha de conectividade/endpoint indisponível (remoto ou local).
- No modo `remote`, se os dados pararem após algum tempo, renove `token` e `apitoken`.
- No modo `local`, valide `local_host`, rota do proxy, `inverter_sn`/`inverter_index` e Basic Auth (se habilitado).

## Aviso Legal e Isenção de Responsabilidade

- Esta integração é um projeto independente da comunidade e **não é oficial** da Solplanet, AISWEI ou Home Assistant.
- As marcas, nomes comerciais e logotipos citados pertencem aos seus respectivos titulares e são usados apenas para identificação e compatibilidade.
- O uso desta integração é por sua conta e risco. Não há garantia de funcionamento contínuo, disponibilidade, precisão dos dados ou compatibilidade futura.
- O mantenedor e colaboradores não se responsabilizam por perdas, danos diretos/indiretos, indisponibilidade do sistema, bloqueios de conta ou qualquer impacto decorrente do uso.
- Você é responsável por cumprir os termos de uso da plataforma Solplanet e as leis aplicáveis na sua região.
- Como a integração depende de endpoints observados no portal web, mudanças do serviço podem quebrar a funcionalidade a qualquer momento.
