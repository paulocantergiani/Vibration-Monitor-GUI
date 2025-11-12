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
    - Exibição do valor atual do sensor com UI moderna
    - Gráfico de histórico com matplotlib (últimos 30-60 segundos)
    - Alertas visuais com animações
    - Salvamento de dados em CSV
    - Estatísticas em tempo real com cards elevados
    - Configuração dinâmica de limites de alerta
"""

import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox, QFileDialog, QMessageBox, QGridLayout,
    QComboBox, QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QPropertyAnimation, QRect
from PyQt5.QtGui import QFont, QColor, QIcon, QPalette
from PyQt5.QtChart import QChart, QChartView, QLineSeries
from PyQt5.QtCore import QPointF, QDateTime

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import os
import tempfile

from gui_server import UDPServer, SensorData
from report_exporter import export_report


class ServerSignals(QObject):
    """Sinais para comunicação entre servidor e GUI"""
    data_received = pyqtSignal(dict)  # Emite dados e estatísticas
    error_occurred = pyqtSignal(str)  # Emite mensagens de erro


class ModernCard(QGroupBox):
    """Card moderno com sombra e estilo elevado"""
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px 0 4px;
            }
        """)


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
        self.figure = None  # Figura do matplotlib
        self.canvas = None  # Canvas do matplotlib

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
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1000, 700)

        # Widget principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Layout superior: Cabeçalho modernizado
        header_layout = self._create_header()
        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        header_widget.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #e0e0e0;")
        main_layout.addWidget(header_widget)

        # Abas para diferentes visualizações
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background-color: #f8f9fa;
                color: #333;
                padding: 10px 20px;
                margin-right: 2px;
                border-bottom: 2px solid transparent;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 2px solid #0066cc;
                color: #0066cc;
            }
            QTabBar::tab:hover {
                background-color: #eff2f5;
            }
        """)

        # Aba 1: Visualização em Tempo Real
        tab_realtime = self._create_realtime_tab()
        tabs.addTab(tab_realtime, "🔴 Tempo Real")

        # Aba 2: Estatísticas
        tab_stats = self._create_statistics_tab()
        tabs.addTab(tab_stats, "📊 Estatísticas")

        # Aba 3: Configurações
        tab_config = self._create_config_tab()
        tabs.addTab(tab_config, "⚙️  Configurações")

        main_layout.addWidget(tabs, 1)

        central_widget.setLayout(main_layout)

        # Aplicar estilo
        self.apply_stylesheet()

    def _create_header(self) -> QHBoxLayout:
        """Cria o cabeçalho com informações básicas"""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 15, 20, 15)
        header_layout.setSpacing(20)

        # Sensor ID
        self.label_sensor_id = QLabel("🔌 Sensor: Aguardando conexão...")
        font_sensor = QFont("Segoe UI", 11, QFont.Bold)
        self.label_sensor_id.setFont(font_sensor)
        self.label_sensor_id.setStyleSheet("color: #333333;")

        # Status de conexão
        self.label_status = QLabel("🔴 Status: Desconectado")
        font_status = QFont("Segoe UI", 11, QFont.Bold)
        self.label_status.setFont(font_status)
        self.label_status.setStyleSheet("color: #d32f2f;")

        # Última atualização
        self.label_last_update = QLabel("⏱️  Última atualização: -")
        font_update = QFont("Segoe UI", 10)
        self.label_last_update.setFont(font_update)
        self.label_last_update.setStyleSheet("color: #666666;")

        header_layout.addWidget(self.label_sensor_id)
        header_layout.addWidget(self.label_status)
        header_layout.addStretch()
        header_layout.addWidget(self.label_last_update)

        return header_layout

    def _create_realtime_tab(self) -> QWidget:
        """Cria aba de visualização em tempo real"""
        widget = QWidget()
        widget.setStyleSheet("background-color: #f5f7fa;")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Layout superior: valor atual e status
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)

        # Card de valor atual
        value_group = ModernCard("📈 Valor Atual do Sensor")
        value_layout = QVBoxLayout()
        value_layout.setSpacing(10)

        self.label_current_value = QLabel("0")
        self.label_current_value.setFont(QFont("Segoe UI", 80, QFont.Bold))
        self.label_current_value.setAlignment(Qt.AlignCenter)
        self.label_current_value.setStyleSheet("color: #0066cc;")

        self.label_current_unit = QLabel("ADC")
        self.label_current_unit.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.label_current_unit.setAlignment(Qt.AlignCenter)
        self.label_current_unit.setStyleSheet("color: #666666;")

        value_layout.addWidget(self.label_current_value)
        value_layout.addWidget(self.label_current_unit)
        value_group.setLayout(value_layout)
        value_group.setMinimumHeight(180)
        top_layout.addWidget(value_group, 1)

        # Card de status/alerta
        alert_group = ModernCard("🚨 Estado do Sensor")
        alert_layout = QVBoxLayout()
        alert_layout.setSpacing(12)

        self.label_alert_status = QLabel("✅ Normal")
        self.label_alert_status.setFont(QFont("Segoe UI", 24, QFont.Bold))
        self.label_alert_status.setAlignment(Qt.AlignCenter)
        self.label_alert_status.setStyleSheet("color: #2e7d32;")

        self.label_alert_message = QLabel("Nenhuma anomalia detectada")
        self.label_alert_message.setFont(QFont("Segoe UI", 11))
        self.label_alert_message.setAlignment(Qt.AlignCenter)
        self.label_alert_message.setStyleSheet("color: #555555;")
        self.label_alert_message.setWordWrap(True)

        alert_layout.addWidget(self.label_alert_status)
        alert_layout.addWidget(self.label_alert_message)
        alert_layout.addStretch()
        alert_group.setLayout(alert_layout)
        alert_group.setMinimumHeight(180)
        top_layout.addWidget(alert_group, 1)

        layout.addLayout(top_layout)

        # Gráfico de histórico com matplotlib
        graph_group = ModernCard("📊 Histórico de Vibração (Últimos 60 segundos)")
        graph_layout = QVBoxLayout()

        self.figure = Figure(figsize=(12, 4), dpi=100, facecolor='white')
        self.figure.patch.set_facecolor('#ffffff')
        self.canvas = FigureCanvas(self.figure)

        # Configurar estilo do gráfico
        plt.style.use('seaborn-v0_8-darkgrid')
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#f8f9fa')
        self.ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        self.ax.set_xlabel('Tempo (s)', fontsize=11, fontweight='bold', color='#333333')
        self.ax.set_ylabel('Valor (ADC)', fontsize=11, fontweight='bold', color='#333333')
        self.ax.tick_params(colors='#666666', labelsize=10)

        graph_layout.addWidget(self.canvas)
        graph_group.setLayout(graph_layout)
        graph_group.setMinimumHeight(300)

        layout.addWidget(graph_group, 1)

        # Botões de ação - primeira linha
        button_layout1 = QHBoxLayout()
        button_layout1.setSpacing(10)

        btn_clear = QPushButton("🗑️  Limpar Gráfico")
        btn_clear.setMinimumHeight(40)
        btn_clear.setMaximumWidth(200)
        btn_clear.setFont(QFont("Segoe UI", 10, QFont.Bold))
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:pressed {
                background-color: #003d7a;
            }
        """)
        btn_clear.clicked.connect(self.on_clear_graph)

        btn_export = QPushButton("💾 Exportar para CSV")
        btn_export.setMinimumHeight(40)
        btn_export.setMaximumWidth(200)
        btn_export.setFont(QFont("Segoe UI", 10, QFont.Bold))
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:pressed {
                background-color: #003d7a;
            }
        """)
        btn_export.clicked.connect(self.on_export_csv)

        button_layout1.addWidget(btn_clear)
        button_layout1.addWidget(btn_export)
        button_layout1.addStretch()

        # Botões de ação - segunda linha
        button_layout2 = QHBoxLayout()
        button_layout2.setSpacing(10)

        btn_export_pdf = QPushButton("📄 Exportar para PDF")
        btn_export_pdf.setMinimumHeight(40)
        btn_export_pdf.setMaximumWidth(200)
        btn_export_pdf.setFont(QFont("Segoe UI", 10, QFont.Bold))
        btn_export_pdf.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
            QPushButton:pressed {
                background-color: #7f0000;
            }
        """)
        btn_export_pdf.clicked.connect(self.on_export_pdf)

        btn_export_xlsx = QPushButton("📊 Exportar para XLSX")
        btn_export_xlsx.setMinimumHeight(40)
        btn_export_xlsx.setMaximumWidth(200)
        btn_export_xlsx.setFont(QFont("Segoe UI", 10, QFont.Bold))
        btn_export_xlsx.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
            QPushButton:pressed {
                background-color: #003300;
            }
        """)
        btn_export_xlsx.clicked.connect(self.on_export_xlsx)

        button_layout2.addWidget(btn_export_pdf)
        button_layout2.addWidget(btn_export_xlsx)
        button_layout2.addStretch()

        layout.addLayout(button_layout1)
        layout.addLayout(button_layout2)

        widget.setLayout(layout)
        return widget

    def _create_statistics_tab(self) -> QWidget:
        """Cria aba de estatísticas"""
        widget = QWidget()
        widget.setStyleSheet("background-color: #f5f7fa;")
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Grid de estatísticas em cards
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)

        # Estatísticas em cards modernos
        stats = [
            ("📊 Total de Leituras", "label_total_readings", "#0066cc"),
            ("📉 Valor Mínimo", "label_min_value", "#2e7d32"),
            ("📈 Valor Máximo", "label_max_value", "#d32f2f"),
            ("📐 Valor Médio", "label_avg_value", "#f57c00"),
            ("🚨 Eventos de Alerta", "label_alert_events", "#c2185b"),
        ]

        for idx, (stat_name, attr_name, color) in enumerate(stats):
            row = idx // 2
            col = idx % 2

            # Criar card
            card = ModernCard(stat_name)
            card.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold;
                    font-size: 13px;
                    border: 1px solid #e0e0e0;
                    border-left: 4px solid {color};
                    border-radius: 8px;
                    margin-top: 10px;
                    padding: 15px;
                    background-color: #ffffff;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 4px 0 4px;
                    color: {color};
                }}
            """)

            card_layout = QVBoxLayout()

            value_label = QLabel("0")
            value_label.setFont(QFont("Segoe UI", 40, QFont.Bold))
            value_label.setAlignment(Qt.AlignCenter)
            value_label.setStyleSheet(f"color: {color};")

            setattr(self, attr_name, value_label)

            card_layout.addWidget(value_label)
            card.setLayout(card_layout)
            card.setMinimumHeight(150)

            grid_layout.addWidget(card, row, col)

        main_layout.addLayout(grid_layout)
        main_layout.addStretch()

        widget.setLayout(main_layout)
        return widget

    def _create_config_tab(self) -> QWidget:
        """Cria aba de configurações"""
        widget = QWidget()
        widget.setStyleSheet("background-color: #f5f7fa;")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Configuração de limiar
        config_group = ModernCard("⚠️  Configurações do Alerta")
        config_layout = QVBoxLayout()
        config_layout.setSpacing(12)

        threshold_layout = QHBoxLayout()
        label_threshold = QLabel("Limiar de Alerta (ADC):")
        label_threshold.setFont(QFont("Segoe UI", 11, QFont.Bold))
        label_threshold.setStyleSheet("color: #333333;")

        self.spinbox_threshold = QSpinBox()
        self.spinbox_threshold.setRange(0, 65535)
        self.spinbox_threshold.setValue(self.alert_threshold)
        self.spinbox_threshold.valueChanged.connect(self.on_threshold_changed)
        self.spinbox_threshold.setFont(QFont("Segoe UI", 11))
        self.spinbox_threshold.setMinimumHeight(35)
        self.spinbox_threshold.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #ffffff;
                color: #333333;
            }
            QSpinBox:focus {
                border: 2px solid #0066cc;
            }
        """)

        threshold_layout.addWidget(label_threshold)
        threshold_layout.addWidget(self.spinbox_threshold, 1)

        config_layout.addLayout(threshold_layout)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Log de eventos
        log_group = ModernCard("📋 Registro de Eventos")
        log_layout = QVBoxLayout()

        self.table_events = QTableWidget()
        self.table_events.setColumnCount(4)
        self.table_events.setHorizontalHeaderLabels(
            ["Timestamp", "Tipo", "Valor", "Status"]
        )
        self.table_events.setMinimumHeight(300)
        self.table_events.setFont(QFont("Segoe UI", 10))
        self.table_events.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
                gridline-color: #e0e0e0;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #e0e0e0;
                font-weight: bold;
                color: #333333;
            }
        """)
        self.table_events.setAlternatingRowColors(True)

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
        self.label_sensor_id.setText(f"🔌 Sensor: {data['sensor_id']}")
        self.label_status.setText("🟢 Status: Conectado")
        self.label_status.setStyleSheet("color: #2e7d32;")

        # Atualizar valor atual
        self.label_current_value.setText(str(int(data['value'])))
        self.label_current_unit.setText(data['unit'])

        # Atualizar timestamp
        timestamp_dt = datetime.fromisoformat(
            data['timestamp'].replace('Z', '+00:00')
        )
        self.label_last_update.setText(
            f"⏱️  Última atualização: {timestamp_dt.strftime('%H:%M:%S')}"
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
            self.label_alert_status.setText("🚨 ALERTA")
            self.label_alert_status.setStyleSheet("color: #d32f2f;")
            self.label_alert_message.setText("Vibração acima do limiar!")
            self.add_event_log(data['timestamp'], "ALERTA", data['value'])
        else:
            self.label_alert_status.setText("✅ Normal")
            self.label_alert_status.setStyleSheet("color: #2e7d32;")
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
        """Atualiza o gráfico com os dados atuais usando matplotlib"""
        if not self.figure or not self.canvas or not self.ax:
            return

        # Limpar gráfico anterior
        self.ax.clear()

        # Plotar dados
        if self.history_values:
            time_points = range(len(self.history_values))

            # Plotar linha principal
            self.ax.plot(time_points, self.history_values,
                        color='#0066cc', linewidth=2.5, marker='o',
                        markersize=4, label='Vibração (ADC)', zorder=3)

            # Plotar limite de alerta como linha tracejada
            self.ax.axhline(y=self.alert_threshold, color='#d32f2f',
                           linestyle='--', linewidth=2, label='Limite de Alerta',
                           alpha=0.7, zorder=2)

            # Preencher área acima do limite com cor vermelha translúcida
            self.ax.fill_between(time_points, self.alert_threshold,
                                max(self.history_values + [self.alert_threshold]),
                                color='#d32f2f', alpha=0.1, zorder=1)

            # Configurar labels e estilo
            self.ax.set_facecolor('#f8f9fa')
            self.ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, color='#cccccc', zorder=0)
            self.ax.set_xlabel('Tempo (s)', fontsize=11, fontweight='bold', color='#333333')
            self.ax.set_ylabel('Valor (ADC)', fontsize=11, fontweight='bold', color='#333333')
            self.ax.tick_params(colors='#666666', labelsize=10)

            # Configurar cores dos spines
            for spine in self.ax.spines.values():
                spine.set_color('#e0e0e0')
                spine.set_linewidth(1)

            # Adicionar legenda
            self.ax.legend(loc='upper left', fontsize=10, framealpha=0.95)

            # Ajustar layout
            self.figure.tight_layout()

        # Desenhar canvas
        self.canvas.draw()

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

    def _get_report_data(self) -> tuple:
        """
        Prepara dados para exportação de relatório.
        Retorna: (lista_dados, estatísticas, caminho_gráfico)
        """
        if not self.server or not self.server.history:
            return None, None, None

        # Converter histórico para lista de dicionários
        data_list = [
            {
                'sensor_id': item.sensor_id,
                'timestamp': item.timestamp,
                'value': item.value,
                'unit': item.unit
            }
            for item in self.server.history
        ]

        # Obter estatísticas dos labels
        stats = {
            'min': float(self.label_min_value.text()) if self.label_min_value.text() else 0,
            'max': float(self.label_max_value.text()) if self.label_max_value.text() else 0,
            'avg': float(self.label_avg_value.text()) if self.label_avg_value.text() else 0,
            'alerts': int(self.label_alert_events.text()) if self.label_alert_events.text() else 0,
        }

        # Salvar gráfico atual em arquivo temporário
        graph_image_path = None
        try:
            # Criar diretório temporário se não existir
            temp_dir = tempfile.gettempdir()
            graph_image_path = os.path.join(temp_dir, 'vibration_graph.png')

            # Salvar figura do matplotlib
            if self.figure and self.canvas:
                self.figure.savefig(graph_image_path, dpi=100, bbox_inches='tight')
        except Exception as e:
            print(f"Aviso: Não foi possível salvar gráfico: {e}")
            graph_image_path = None

        return data_list, stats, graph_image_path

    def on_export_pdf(self):
        """Exporta relatório em formato PDF"""
        data_list, stats, graph_image_path = self._get_report_data()

        if not data_list:
            QMessageBox.warning(
                self, "Aviso", "Nenhum dado para exportar ainda."
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório como PDF", "", "PDF Files (*.pdf)"
        )

        if filename:
            try:
                sensor_id = self.label_sensor_id.text().replace("🔌 Sensor: ", "")
                success = export_report(
                    'pdf',
                    filename,
                    sensor_id,
                    data_list,
                    stats,
                    unit='ADC',
                    graph_image_path=graph_image_path
                )

                if success:
                    QMessageBox.information(
                        self, "Sucesso", f"Relatório PDF exportado para:\n{filename}"
                    )
                else:
                    QMessageBox.critical(
                        self, "Erro", "Falha ao exportar relatório PDF."
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro", f"Erro ao exportar PDF:\n{str(e)}"
                )
            finally:
                # Limpar arquivo temporário do gráfico
                if graph_image_path and os.path.exists(graph_image_path):
                    try:
                        os.remove(graph_image_path)
                    except:
                        pass

    def on_export_xlsx(self):
        """Exporta relatório em formato XLSX"""
        data_list, stats, graph_image_path = self._get_report_data()

        if not data_list:
            QMessageBox.warning(
                self, "Aviso", "Nenhum dado para exportar ainda."
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar relatório como XLSX", "", "Excel Files (*.xlsx)"
        )

        if filename:
            try:
                sensor_id = self.label_sensor_id.text().replace("🔌 Sensor: ", "")
                success = export_report(
                    'xlsx',
                    filename,
                    sensor_id,
                    data_list,
                    stats,
                    unit='ADC',
                    graph_image_path=graph_image_path
                )

                if success:
                    QMessageBox.information(
                        self, "Sucesso", f"Relatório XLSX exportado para:\n{filename}"
                    )
                else:
                    QMessageBox.critical(
                        self, "Erro", "Falha ao exportar relatório XLSX."
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, "Erro", f"Erro ao exportar XLSX:\n{str(e)}"
                )
            finally:
                # Limpar arquivo temporário do gráfico
                if graph_image_path and os.path.exists(graph_image_path):
                    try:
                        os.remove(graph_image_path)
                    except:
                        pass

    def apply_stylesheet(self):
        """Aplica estilo CSS moderno à aplicação"""
        stylesheet = """
        QMainWindow {
            background-color: #f5f7fa;
        }

        QPushButton {
            background-color: #0066cc;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: bold;
            font-size: 11px;
            min-height: 40px;
        }

        QPushButton:hover {
            background-color: #0052a3;
            padding: 10px 22px;
        }

        QPushButton:pressed {
            background-color: #003d7a;
            padding: 10px 18px;
        }

        QPushButton:disabled {
            background-color: #cccccc;
            color: #999999;
        }

        QLabel {
            color: #333333;
        }

        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f8f9fa;
            gridline-color: #e0e0e0;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }

        QTableWidget::item {
            padding: 8px;
            border: none;
        }

        QTableWidget::item:selected {
            background-color: #d4e6f1;
        }

        QHeaderView::section {
            background-color: #f0f0f0;
            padding: 8px;
            border: none;
            border-bottom: 2px solid #0066cc;
            font-weight: bold;
            color: #333333;
        }

        QSpinBox, QComboBox {
            padding: 8px;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            background-color: #ffffff;
            color: #333333;
            selection-background-color: #0066cc;
        }

        QSpinBox:focus, QComboBox:focus {
            border: 2px solid #0066cc;
        }

        QScrollBar:vertical {
            border: none;
            background-color: #f5f7fa;
            width: 12px;
            margin: 0px 0px 0px 0px;
        }

        QScrollBar::handle:vertical {
            background-color: #c0c0c0;
            border-radius: 6px;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #a0a0a0;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
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
