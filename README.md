# Interface Gráfica de Monitoramento - Sensor de Vibração STM32MP1

## 📋 Descrição do Projeto

Interface gráfica em **PyQt5** para visualização em tempo real dos dados do sensor de vibração **SW-420** conectado ao kit **STM32MP1-DK1**.


---

## 🎯 Funcionalidades

- **Valor atual do sensor** - Exibição em tempo real com fonte grande e destacada
- **Histórico gráfico** - Gráfico dos últimos 60 segundos de vibração
- **Alertas visuais** - Indicadores de cor (verde=normal, vermelho=alerta) para valores fora dos limites
- **Salvamento de dados** - Exportação para arquivo CSV
- **Configuração dinâmica de limites** - Ajuste do threshold de alerta em tempo real via interface
- **Timestamp** - Registro automático de data/hora em cada leitura
- **Indicador de atualização** - Mostra data/hora da última leitura recebida
- **Estatísticas** - Min, max, média, total de leituras e eventos de alerta

---

## 📸 Screenshots

### Aba Tempo Real - Interface Gráfica

![Interface da GUI](demonstracao_kit_interface.png)

### Aba Estatísticas

![Aba Estatísticas](demonstracao_kit_interface_estatisticas.png)

### Aba Configurações

![Aba Configurações](demonstracao_kit_interface_configuracoes.png)

### Terminal de Execução

![Terminal de Execução](demonstracao_kit_terminal.png)

---

## 🏗️ Estrutura do Projeto

```
Vibration-Monitor-GUI/
├── gui_server.py                 # Servidor UDP com suporte a callbacks
├── vibration_monitor_gui.py      # Interface gráfica PyQt5 principal
├── requirements.txt              # Dependências Python
└── README.md                     # Este arquivo
```

### Arquivo: `gui_server.py`

**Classe `SensorData`**: Representa um dado individual do sensor
- `sensor_id`: Identificador do sensor
- `timestamp`: Data/hora em ISO 8601
- `value`: Valor lido
- `unit`: Unidade de medida

**Classe `UDPServer`**: Servidor UDP com suporte a eventos
- `start()`: Inicia servidor em thread separada
- `stop()`: Para graciosamente
- `export_to_csv()`: Exporta histórico para arquivo CSV
- Callbacks: `on_data_received` e `on_error` para eventos

### Arquivo: `vibration_monitor_gui.py`

**Classe `VibrationMonitorGUI`**: Janela principal da aplicação
- **Aba "Tempo Real"**: Valor atual + gráfico histórico
- **Aba "Estatísticas"**: Métricas agregadas
- **Aba "Configurações"**: Ajuste de limiar e log de eventos

---

## 📡 Protocolo de Comunicação

O servidor UDP espera mensagens no formato **CSV**:

```
SENSOR_ID,TIMESTAMP,VALUE,UNIT
```

### Exemplo:
```
SW420_GRUPO_10,2025-11-04T15:30:45,2450,ADC
```

### Campos:
| Campo | Tipo | Descrição | Exemplo |
|-------|------|-----------|---------|
| SENSOR_ID | string | Identificador do sensor | `SW420_GRUPO_10` |
| TIMESTAMP | string | Data/hora ISO 8601 | `2025-11-04T15:30:45` |
| VALUE | int | Valor do ADC | `2450` |
| UNIT | string | Unidade de medida | `ADC` |

---

## 🚀 Instruções de Execução

### 1. Pré-requisitos

- Python 3.6 ou superior
- pip (gerenciador de pacotes Python)
- Sistema operacional: Windows, macOS ou Linux

### 2. Instalação de Dependências

```bash
# Instalar dependências do projeto
pip install -r requirements.txt
```

**Dependências principais:**
- `PyQt5`: Framework para interface gráfica
- `matplotlib`: Gráficos avançados (opcional)
- `pandas`: Manipulação de dados CSV (opcional)

### 3. Configuração de Rede

Antes de executar a GUI, configure o IP do seu PC:

**No Linux/macOS:**
```bash
# Configure IP estático na mesma faixa que o kit
# IP do kit: 192.168.42.2
# IP do PC recomendado: 192.168.42.10
```

**No Windows:**
```
Painel de Controle → Rede e Internet → Configurações de Rede Avançadas
→ Adaptador Ethernet → Propriedades → IPv4
IP: 192.168.42.10
Máscara: 255.255.255.0
```

### 4. Execução da GUI

```bash
# Executar a interface gráfica
python3 vibration_monitor_gui.py
```

**Saída esperada:**
```
[INFO] Servidor UDP iniciado em 192.168.42.10:5000
```

Aguarde até que o kit STM32MP1 comece a enviar dados. A GUI exibirá:
- Sensor conectado
- Valor atual do sensor
- Gráfico histórico
- Alertas visuais

### 5. Uso da Interface

#### Aba "Tempo Real"
- **Valor Atual**: Mostra o último valor lido em grande destaque
- **Estado do Sensor**: Indica "Normal" ou "ALERTA" com código de cores
- **Gráfico**: Visualiza os últimos 60 valores
- **Botões**:
  - "Limpar Gráfico": Limpa o histórico visual
  - "Exportar para CSV": Salva dados em arquivo

#### Aba "Estatísticas"
- **Total de Leituras**: Número total de dados recebidos
- **Valor Mínimo**: Menor vibração detectada
- **Valor Máximo**: Maior vibração detectada
- **Valor Médio**: Média aritmética das leituras
- **Eventos de Alerta**: Número de vezes que o threshold foi excedido

#### Aba "Configurações"
- **Limiar de Alerta (ADC)**: Ajuste em tempo real o valor que ativa alertas
- **Registro de Eventos**: Histórico de eventos com timestamp, tipo e valor

---

## 📊 Estrutura de Dados Enviada pelo Kit

O kit STM32MP1 enviará mensagens no seguinte formato:

```csv
SW420_VIBRATION,2025-11-04T15:30:45,2450,ADC
```

**Campos:**
- `SW420_VIBRATION`: ID do sensor (configurável em `src/main.cpp` do kit)
- `2025-11-04T15:30:45`: Timestamp em ISO 8601
- `2450`: Valor bruto do ADC (0-65535)
- `ADC`: Unidade de medida

---

## 🔧 Troubleshooting

### Problema: "Erro ao inicializar socket: Address already in use"

**Causa**: Outra aplicação está usando a porta 5000 ou um servidor anterior não foi encerrado.

**Solução**:
```bash
# Linux/macOS: Encontre o processo
lsof -i :5000

# Windows: Abra cmd e execute
netstat -ano | findstr :5000

# Encerre o processo e tente novamente
```

### Problema: "Servidor iniciado mas nenhum dado recebido"

**Causa**:
1. Kit não está conectado na mesma rede
2. IP do kit não está configurado corretamente
3. Kit não está enviando dados

**Solução**:
1. Verifique conectividade: `ping 192.168.42.2`
2. Verifique que o kit está executando o programa `VibrationMonitor`
3. Verifique se o IP configurado em `src/main.cpp` do kit é `192.168.42.10`

### Problema: Interface não responsiva ou lenta

**Causa**: Muitos dados acumulando no histórico.

**Solução**:
- Clique em "Limpar Gráfico" para reset
- Reduza o tamanho máximo do histórico em `gui_server.py:32`

---

## 📝 Documentação do Protocolo

### Fluxo de Comunicação

```
┌─────────────────────┐                    ┌──────────────────┐
│   STM32MP1-DK1      │                    │   PC (GUI)       │
│  192.168.42.2       │                    │ 192.168.42.10    │
│                     │                    │                  │
└──────────┬──────────┘                    └────────┬─────────┘
           │                                        │
           │ 1. Inicializa sensor                   │
           │    (SW-420 no ADC)                     │
           │                                        │
           │ 2. Inicializa socket UDP               │
           │                                        │
           │ 3. Envia pacote UDP:                   │
           │ "SW420,2025-11-04T15:30:45,2450,ADC"  │
           ├───────────────────────────────────────>│
           │                                        │
           │                                        │ 4. Servidor recebe
           │                                        │    Parseia mensagem
           │                                        │    Atualiza GUI
           │                                        │
           │ 5. Aguarda 500ms                       │
           │    (intervalo configurável)            │
           │                                        │
           │ 6. Repete ciclo                        │
           │                                        │
           └───────────────────────────────────────>│
```
