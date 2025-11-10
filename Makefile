# Makefile para geração de documentação e diagramas
# Projeto: Vibration Monitor GUI

.PHONY: help docs diagrams clean serve

help:
	@echo "=== Vibration Monitor GUI - Build Commands ==="
	@echo ""
	@echo "Targets disponíveis:"
	@echo "  make docs       - Gera documentação com Doxygen"
	@echo "  make diagrams   - Gera diagramas GraphViz em PNG"
	@echo "  make all        - Gera diagramas e documentação"
	@echo "  make clean      - Remove arquivos gerados"
	@echo "  make serve      - Abre documentação em navegador"
	@echo ""

all: diagrams docs

# Gera diagramas em PNG a partir dos arquivos GraphViz
diagrams:
	@echo "[INFO] Gerando diagramas GraphViz..."
	@dot -Tpng class_diagram.gv -o class_diagram.png
	@dot -Tpng architecture_diagram.gv -o architecture_diagram.png
	@dot -Tpng data_flow_diagram.gv -o data_flow_diagram.png
	@dot -Tpng ui_components_diagram.gv -o ui_components_diagram.png
	@echo "[OK] Diagramas gerados com sucesso!"
	@ls -lh *.png

# Gera documentação com Doxygen
docs: diagrams
	@echo "[INFO] Gerando documentação Doxygen..."
	@doxygen Doxyfile
	@echo "[OK] Documentação gerada em docs/html/index.html"

# Limpa arquivos gerados
clean:
	@echo "[INFO] Limpando arquivos gerados..."
	@rm -rf docs/
	@echo "[OK] Limpeza concluída!"

# Abre documentação no navegador padrão
serve: docs
	@echo "[INFO] Abrindo documentação no navegador..."
	@xdg-open docs/html/index.html 2>/dev/null || open docs/html/index.html 2>/dev/null || start docs/html/index.html

# Targets específicos
class-diagram:
	@dot -Tpng class_diagram.gv -o class_diagram.png
	@echo "[OK] Diagrama de classes gerado!"

architecture-diagram:
	@dot -Tpng architecture_diagram.gv -o architecture_diagram.png
	@echo "[OK] Diagrama de arquitetura gerado!"

dataflow-diagram:
	@dot -Tpng data_flow_diagram.gv -o data_flow_diagram.png
	@echo "[OK] Diagrama de fluxo de dados gerado!"

ui-diagram:
	@dot -Tpng ui_components_diagram.gv -o ui_components_diagram.png
	@echo "[OK] Diagrama de componentes UI gerado!"
