#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file gui_server.py
@brief Servidor UDP com suporte a Interface Gráfica para monitoramento de sensores
@author Oficiais Engenheiros - Instituto Militar de Engenharia
@date 2025-11-04

Servidor UDP que recebe dados de sensores via protocolo CSV e os disponibiliza
para uma interface gráfica PyQt em tempo real.

Protocolo esperado:
    SENSOR_ID,TIMESTAMP,VALUE,UNIT

Exemplo:
    SW420_GRUPO_10,2025-11-04T15:30:45.123,2450,ADC
"""

import socket
import signal
import sys
import threading
import json
import time
from datetime import datetime
from collections import deque
from typing import Dict, Optional, Callable

# Configurações padrão
DEFAULT_UDP_IP = "192.168.42.10"
DEFAULT_UDP_PORT = 5000
DEFAULT_MAX_HISTORY = 300  # Manter histórico dos últimos 5 minutos (300 segundos)
DEFAULT_VIBRATION_THRESHOLD = 5000


class SensorData:
    """Classe para armazenar dados individuais do sensor"""

    def __init__(self, sensor_id: str, timestamp: str, value: float, unit: str):
        """
        Inicializa dados do sensor

        Args:
            sensor_id: Identificador do sensor (ex: "SW420_GRUPO_10")
            timestamp: Timestamp da leitura (ISO 8601)
            value: Valor lido do sensor
            unit: Unidade de medida (ex: "ADC", "mV", "g")
        """
        self.sensor_id = sensor_id
        self.timestamp = timestamp
        self.value = float(value)
        self.unit = unit
        self.datetime_obj = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            'sensor_id': self.sensor_id,
            'timestamp': self.timestamp,
            'value': self.value,
            'unit': self.unit
        }

    def __repr__(self) -> str:
        return f"SensorData({self.sensor_id}, {self.value} {self.unit})"


class UDPServer:
    """Servidor UDP para recebimento de dados de sensores com suporte a callbacks"""

    def __init__(self, ip: str = DEFAULT_UDP_IP, port: int = DEFAULT_UDP_PORT,
                 max_history: int = DEFAULT_MAX_HISTORY):
        """
        Inicializa servidor UDP

        Args:
            ip: Endereço IP para bind
            port: Porta UDP
            max_history: Número máximo de dados a manter no histórico
        """
        self.ip = ip
        self.port = port
        self.sock = None
        self.running = False
        self.thread = None
        self.max_history = max_history

        # Dados do sensor
        self.sensor_id = None
        self.current_data = None
        self.history = deque(maxlen=max_history)
        self.client_address = None

        # Estatísticas
        self.total_readings = 0
        self.min_value = float('inf')
        self.max_value = 0
        self.sum_values = 0
        self.high_vibration_events = 0

        # Callbacks para atualizações em tempo real
        self.on_data_received = None
        self.on_error = None

    def set_callbacks(self, on_data: Optional[Callable] = None,
                     on_error: Optional[Callable] = None):
        """
        Define callbacks para eventos do servidor

        Args:
            on_data: Função chamada quando novos dados são recebidos
            on_error: Função chamada quando ocorre um erro
        """
        self.on_data_received = on_data
        self.on_error = on_error

    def init(self) -> bool:
        """
        Inicializa o socket UDP

        Returns:
            True se inicializado com sucesso, False caso contrário
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.ip, self.port))
            self.sock.settimeout(1.0)  # Timeout para permitir shutdown gracioso
            return True
        except Exception as e:
            error_msg = f"Erro ao inicializar socket: {e}"
            if self.on_error:
                self.on_error(error_msg)
            print(f"❌ {error_msg}")
            return False

    def parse_csv_message(self, message: str) -> Optional[SensorData]:
        """
        Parseia mensagem CSV do sensor

        Args:
            message: String no formato "SENSOR_ID,TIMESTAMP,VALUE,UNIT"

        Returns:
            SensorData se válido, None caso contrário
        """
        try:
            parts = message.strip().split(',')
            if len(parts) != 4:
                return None

            sensor_id, timestamp, value, unit = parts

            # Validação básica
            try:
                float(value)
            except ValueError:
                return None

            return SensorData(sensor_id, timestamp, value, unit)
        except Exception as e:
            error_msg = f"Erro ao fazer parse: {e}"
            if self.on_error:
                self.on_error(error_msg)
            return None

    def update_stats(self, data: SensorData):
        """Atualiza estatísticas com novo valor"""
        value = data.value
        self.total_readings += 1
        self.history.append(data)
        self.sum_values += value
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)

        if value > DEFAULT_VIBRATION_THRESHOLD:
            self.high_vibration_events += 1

    def get_stats(self) -> Dict:
        """
        Retorna estatísticas agregadas

        Returns:
            Dicionário com estatísticas do sensor
        """
        if self.total_readings == 0:
            return {}

        avg_value = self.sum_values / self.total_readings
        return {
            'total_readings': self.total_readings,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'avg_value': round(avg_value, 2),
            'high_vibration_events': self.high_vibration_events,
            'last_timestamp': self.current_data.timestamp if self.current_data else None
        }

    def get_history_data(self) -> list:
        """Retorna histórico de dados como lista"""
        return [data.to_dict() for data in self.history]

    def _receive_loop(self):
        """Loop de recepção de dados (executado em thread)"""
        print(f"[INFO] Servidor UDP iniciado em {self.ip}:{self.port}")

        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                message = data.decode('utf-8')

                # Parse da mensagem
                parsed_data = self.parse_csv_message(message)
                if not parsed_data:
                    continue

                # Registra primeira conexão
                if self.sensor_id is None:
                    self.sensor_id = parsed_data.sensor_id
                    self.client_address = addr
                    print(f"[INFO] Sensor conectado: {self.sensor_id} ({addr[0]}:{addr[1]})")

                # Atualiza dados atuais
                self.current_data = parsed_data

                # Atualiza estatísticas
                self.update_stats(parsed_data)

                # Chama callback se definido
                if self.on_data_received:
                    self.on_data_received(parsed_data, self.get_stats())

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:  # Ignora erro se foi shutdown
                    error_msg = f"Erro ao receber dados: {e}"
                    if self.on_error:
                        self.on_error(error_msg)
                    print(f"❌ {error_msg}")

    def start(self) -> bool:
        """
        Inicia o servidor em uma thread separada

        Returns:
            True se iniciado com sucesso
        """
        if not self.init():
            return False

        self.running = True
        self.thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        """Para o servidor graciosamente"""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        if self.thread:
            self.thread.join(timeout=2.0)
        print("[INFO] Servidor UDP encerrado")

    def export_to_csv(self, filename: str) -> bool:
        """
        Exporta histórico para arquivo CSV

        Args:
            filename: Nome do arquivo de saída

        Returns:
            True se exportado com sucesso
        """
        try:
            with open(filename, 'w') as f:
                # Cabeçalho
                f.write("sensor_id,timestamp,value,unit\n")

                # Dados
                for data in self.history:
                    f.write(f"{data.sensor_id},{data.timestamp},{data.value},{data.unit}\n")

            print(f"[INFO] Dados exportados para {filename}")
            return True
        except Exception as e:
            error_msg = f"Erro ao exportar CSV: {e}"
            if self.on_error:
                self.on_error(error_msg)
            print(f"❌ {error_msg}")
            return False


# Exemplo de uso standalone (sem GUI)
if __name__ == "__main__":
    server = UDPServer()

    def on_new_data(data: SensorData, stats: Dict):
        """Callback para novos dados"""
        status = "⚠️  ALERTA" if data.value > DEFAULT_VIBRATION_THRESHOLD else "✓ Normal"
        print(f"[{data.timestamp}] {data.sensor_id}: {data.value} {data.unit} | {status}")

    def on_error(error_msg: str):
        """Callback para erros"""
        print(f"[ERROR] {error_msg}")

    server.set_callbacks(on_data=on_new_data, on_error=on_error)

    if server.start():
        print(f"Servidor iniciado. Pressione Ctrl+C para parar...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nEncerrando...")
            server.stop()
    else:
        print("Erro ao iniciar servidor")
        sys.exit(1)
