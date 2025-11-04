#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file vibration_monitor_gui.py
@brief Interface Gráfica para Monitoramento em Tempo Real do Sensor de Vibração
@author Oficiais Engenheiros - Instituto Militar de Engenharia
@date 2025-11-04

Aplicação PyQt5 para visualização em tempo real dos dados do sensor de vibração SW-420
conectado ao kit STM32MP1-DK1.

Funcionalidades:
    - Exibição do valor atual do sensor
    - Gráfico de histórico (últimos 30-60 segundos)
    - Alertas visuais para valores anormais
    - Salvamento de dados em CSV
    - Estatísticas em tempo real
    - Configuração dinâmica de limites de alerta
"""

import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox, QFileDialog, QMessageBox, QGridLayout,
    QComboBox, QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5.QtChart import QChart, QChartView, QLineSeries
from PyQt5.QtCore import QPointF, QDateTime

from gui_server import UDPServer, SensorData


class ServerSignals(QObject):
    """Sinais para comunicação entre servidor e GUI"""
    data_received = pyqtSignal(dict)  # Emite dados e estatísticas
    error_occurred = pyqtSignal(str)  # Emite mensagens de erro


class VibrationMonitorGUI(QMainWindow):
    """Janela principal da interface de monitoramento"""

    def __init__(self):
        """Inicializa a interface gráfica"""
        super().__init__()
        self.server = None
        self.signals = ServerSignals()
        self.history_values = []  # Lista de valores para o gráfico
        self.history_timestamps = []  # Lista de timestamps
        self.chart_data = []  # Dados para o gráfico

        # Configurações
        self.alert_threshold = 5000  # Limiar de alerta
        self.update_interval = 500  # Intervalo de atualização em ms
        self.max_graph_points = 60  # Máximo de pontos no gráfico

        self.init_ui()
        self.setup_signals()
        self.setup_server()

    def init_ui(self):
        """Inicializa a interface do usuário"""
        self.setWindowTitle("Monitor de Vibração - STM32MP1 + SW-420")
        self.setGeometry(100, 100, 1200, 800)

        # Widget principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()

        # Layout superior: Cabeçalho
        header_layout = self._create_header()
        main_layout.addLayout(header_layout)

        # Abas para diferentes visualizações
        tabs = QTabWidget()

        # Aba 1: Visualização em Tempo Real
        tab_realtime = self._create_realtime_tab()
        tabs.addTab(tab_realtime, "Tempo Real")

        # Aba 2: Estatísticas
        tab_stats = self._create_statistics_tab()
        tabs.addTab(tab_stats, "Estatísticas")

        # Aba 3: Configurações
        tab_config = self._create_config_tab()
        tabs.addTab(tab_config, "Configurações")

        main_layout.addWidget(tabs)

        central_widget.setLayout(main_layout)

        # Aplicar estilo
        self.apply_stylesheet()

    def _create_header(self) -> QHBoxLayout:
        """Cria o cabeçalho com informações básicas"""
        header_layout = QHBoxLayout()

        # Sensor ID
        self.label_sensor_id = QLabel("Sensor: Aguardando conexão...")
        self.label_sensor_id.setFont(QFont("Arial", 10, QFont.Bold))

        # Status de conexão
        self.label_status = QLabel("Status: ❌ Desconectado")
        self.label_status.setFont(QFont("Arial", 10, QFont.Bold))

        # Última atualização
        self.label_last_update = QLabel("Última atualização: -")

        header_layout.addWidget(self.label_sensor_id)
        header_layout.addWidget(self.label_status)
        header_layout.addStretch()
        header_layout.addWidget(self.label_last_update)

        return header_layout

    def _create_realtime_tab(self) -> QWidget:
        """Cria aba de visualização em tempo real"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Layout para valor atual (grande e destacado)
        current_layout = QHBoxLayout()

        # Caixa de valor atual
        value_group = QGroupBox("Valor Atual do Sensor")
        value_layout = QVBoxLayout()

        self.label_current_value = QLabel("0")
        self.label_current_value.setFont(QFont("Arial", 72, QFont.Bold))
        self.label_current_value.setAlignment(Qt.AlignCenter)

        self.label_current_unit = QLabel("ADC")
        self.label_current_unit.setFont(QFont("Arial", 24))
        self.label_current_unit.setAlignment(Qt.AlignCenter)

        value_layout.addWidget(self.label_current_value)
        value_layout.addWidget(self.label_current_unit)
        value_group.setLayout(value_layout)

        current_layout.addWidget(value_group)

        # Caixa de alerta e indicador
        alert_group = QGroupBox("Estado do Sensor")
        alert_layout = QVBoxLayout()

        self.label_alert_status = QLabel("✓ Normal")
        self.label_alert_status.setFont(QFont("Arial", 18, QFont.Bold))
        self.label_alert_status.setAlignment(Qt.AlignCenter)

        self.label_alert_message = QLabel("Nenhuma anomalia detectada")
        self.label_alert_message.setAlignment(Qt.AlignCenter)

        alert_layout.addWidget(self.label_alert_status)
        alert_layout.addWidget(self.label_alert_message)
        alert_group.setLayout(alert_layout)

        current_layout.addWidget(alert_group)

        layout.addLayout(current_layout)

        # Gráfico de histórico
        self.chart = QChart()
        self.chart.setTitle("Histórico de Vibração (Últimos 60 segundos)")
        self.chart.setAnimationOptions(QChart.SeriesAnimations)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(self.chart_view.Antialiasing)

        layout.addWidget(self.chart_view)

        # Botões de ação
        button_layout = QHBoxLayout()

        btn_clear = QPushButton("Limpar Gráfico")
        btn_clear.clicked.connect(self.on_clear_graph)

        btn_export = QPushButton("Exportar para CSV")
        btn_export.clicked.connect(self.on_export_csv)

        button_layout.addWidget(btn_clear)
        button_layout.addWidget(btn_export)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        widget.setLayout(layout)
        return widget

    def _create_statistics_tab(self) -> QWidget:
        """Cria aba de estatísticas"""
        widget = QWidget()
        layout = QGridLayout()

        # Estatísticas em cards
        stats = [
            ("Total de Leituras", "label_total_readings"),
            ("Valor Mínimo", "label_min_value"),
            ("Valor Máximo", "label_max_value"),
            ("Valor Médio", "label_avg_value"),
            ("Eventos de Alerta", "label_alert_events"),
        ]

        row = 0
        for stat_name, attr_name in stats:
            label = QLabel(stat_name)
            label.setFont(QFont("Arial", 10, QFont.Bold))

            value_label = QLabel("0")
            value_label.setFont(QFont("Arial", 24, QFont.Bold))
            value_label.setAlignment(Qt.AlignCenter)

            setattr(self, attr_name, value_label)

            layout.addWidget(label, row, 0)
            layout.addWidget(value_label, row, 1)
            row += 1

        layout.addItem(layout.spacing(), row + 1, 0)

        widget.setLayout(layout)
        return widget

    def _create_config_tab(self) -> QWidget:
        """Cria aba de configurações"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Configuração de limiar
        config_group = QGroupBox("Configurações do Alerta")
        config_layout = QVBoxLayout()

        threshold_layout = QHBoxLayout()
        label_threshold = QLabel("Limiar de Alerta (ADC):")
        threshold_layout.addWidget(label_threshold)

        self.spinbox_threshold = QSpinBox()
        self.spinbox_threshold.setRange(0, 65535)
        self.spinbox_threshold.setValue(self.alert_threshold)
        self.spinbox_threshold.valueChanged.connect(self.on_threshold_changed)
        threshold_layout.addWidget(self.spinbox_threshold)

        config_layout.addLayout(threshold_layout)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Log de eventos
        log_group = QGroupBox("Registro de Eventos")
        log_layout = QVBoxLayout()

        self.table_events = QTableWidget()
        self.table_events.setColumnCount(4)
        self.table_events.setHorizontalHeaderLabels(
            ["Timestamp", "Tipo", "Valor", "Status"]
        )
        self.table_events.setMaximumHeight(300)

        log_layout.addWidget(self.table_events)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def setup_signals(self):
        """Configura sinais e slots"""
        self.signals.data_received.connect(self.on_data_received)
        self.signals.error_occurred.connect(self.on_error_received)

    def setup_server(self):
        """Inicializa e inicia o servidor UDP"""
        self.server = UDPServer()
        self.server.set_callbacks(
            on_data=self.on_server_data,
            on_error=self.on_server_error
        )

        if self.server.start():
            self.label_status.setText("Status: ✓ Aguardando dados...")
            self.label_status.setStyleSheet("color: orange;")
        else:
            self.label_status.setText("Status: ❌ Erro ao iniciar servidor")
            self.label_status.setStyleSheet("color: red;")

    def on_server_data(self, data: SensorData, stats: Dict):
        """Callback do servidor quando novos dados são recebidos"""
        self.signals.data_received.emit({
            'data': {
                'sensor_id': data.sensor_id,
                'timestamp': data.timestamp,
                'value': data.value,
                'unit': data.unit
            },
            'stats': stats
        })

    def on_server_error(self, error_msg: str):
        """Callback do servidor quando ocorre um erro"""
        self.signals.error_occurred.emit(error_msg)

    def on_data_received(self, info: Dict):
        """Slot para atualizar GUI quando novos dados chegam"""
        data = info['data']
        stats = info['stats']

        # Atualizar sensor ID
        self.label_sensor_id.setText(f"Sensor: {data['sensor_id']}")
        self.label_status.setText("Status: ✓ Conectado")
        self.label_status.setStyleSheet("color: green;")

        # Atualizar valor atual
        self.label_current_value.setText(str(int(data['value'])))
        self.label_current_unit.setText(data['unit'])

        # Atualizar timestamp
        timestamp_dt = datetime.fromisoformat(
            data['timestamp'].replace('Z', '+00:00')
        )
        self.label_last_update.setText(
            f"Última atualização: {timestamp_dt.strftime('%H:%M:%S')}"
        )

        # Adicionar ao histórico
        self.history_values.append(data['value'])
        self.history_timestamps.append(timestamp_dt)

        # Manter apenas últimos N pontos
        if len(self.history_values) > self.max_graph_points:
            self.history_values.pop(0)
            self.history_timestamps.pop(0)

        # Atualizar gráfico
        self.update_chart()

        # Verificar alerta
        is_alert = data['value'] > self.alert_threshold
        if is_alert:
            self.label_alert_status.setText("⚠️  ALERTA")
            self.label_alert_status.setStyleSheet("color: red;")
            self.label_alert_message.setText("Vibração acima do limiar!")
            self.add_event_log(data['timestamp'], "ALERTA", data['value'])
        else:
            self.label_alert_status.setText("✓ Normal")
            self.label_alert_status.setStyleSheet("color: green;")
            self.label_alert_message.setText("Nenhuma anomalia detectada")

        # Atualizar estatísticas
        self.label_total_readings.setText(str(stats['total_readings']))
        self.label_min_value.setText(str(int(stats['min_value'])))
        self.label_max_value.setText(str(int(stats['max_value'])))
        self.label_avg_value.setText(f"{stats['avg_value']:.2f}")
        self.label_alert_events.setText(str(stats['high_vibration_events']))

    def on_error_received(self, error_msg: str):
        """Slot para exibir mensagens de erro"""
        print(f"[ERROR] {error_msg}")

    def update_chart(self):
        """Atualiza o gráfico com os dados atuais"""
        self.chart.removeAllSeries()

        # Criar série de dados
        series = QLineSeries()
        series.setName("Vibração (ADC)")

        for i, (timestamp, value) in enumerate(
            zip(self.history_timestamps, self.history_values)
        ):
            series.append(QPointF(i, value))

        self.chart.addSeries(series)

        # Configurar eixos
        self.chart.createDefaultAxes()
        axes = self.chart.axes()

        if axes:
            for axis in axes:
                axis.setLabelsVisible(False)

    def add_event_log(self, timestamp: str, event_type: str, value: float):
        """Adiciona um evento ao log"""
        row = self.table_events.rowCount()
        self.table_events.insertRow(row)

        self.table_events.setItem(row, 0, QTableWidgetItem(timestamp))
        self.table_events.setItem(row, 1, QTableWidgetItem(event_type))
        self.table_events.setItem(row, 2, QTableWidgetItem(str(int(value))))
        self.table_events.setItem(
            row, 3, QTableWidgetItem("⚠️  ALERTA" if event_type == "ALERTA" else "✓ OK")
        )

        # Manter apenas últimos 50 eventos
        while self.table_events.rowCount() > 50:
            self.table_events.removeRow(0)

    def on_threshold_changed(self, value: int):
        """Atualiza o limiar de alerta"""
        self.alert_threshold = value

    def on_clear_graph(self):
        """Limpa o gráfico e o histórico"""
        self.history_values.clear()
        self.history_timestamps.clear()
        self.update_chart()

    def on_export_csv(self):
        """Exporta dados para arquivo CSV"""
        if not self.server or not self.server.history:
            QMessageBox.warning(
                self, "Aviso", "Nenhum dado para exportar ainda."
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar dados como CSV", "", "CSV Files (*.csv)"
        )

        if filename:
            if self.server.export_to_csv(filename):
                QMessageBox.information(
                    self, "Sucesso", f"Dados exportados para:\n{filename}"
                )
            else:
                QMessageBox.critical(
                    self, "Erro", "Falha ao exportar dados."
                )

    def apply_stylesheet(self):
        """Aplica estilo CSS à aplicação"""
        stylesheet = """
        QMainWindow {
            background-color: #f0f0f0;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ccc;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
        QPushButton {
            background-color: #007acc;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #005a9e;
        }
        QPushButton:pressed {
            background-color: #003d6b;
        }
        QLabel {
            color: #333333;
        }
        """
        self.setStyleSheet(stylesheet)

    def closeEvent(self, event):
        """Trata o fechamento da janela"""
        if self.server:
            self.server.stop()
        event.accept()


def main():
    """Função principal"""
    app = QApplication(sys.argv)
    window = VibrationMonitorGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
