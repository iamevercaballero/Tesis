.PHONY: up down logs status gen-normal gen-anomalies gen-run install

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=50

status:
	docker compose ps
	@echo "\nElasticsearch:"
	@curl -s http://localhost:9200/_cluster/health | python3 -m json.tool 2>/dev/null || echo "  No disponible aún"

install:
	pip install -r requirements.txt

gen-normal:
	python3 app/log_generator.py normal

gen-anomalies:
	python3 app/log_generator.py all-anomalies

gen-run:
	python3 app/log_generator.py run --duration 300 --anomaly-ratio 0.08

es-indices:
	@curl -s http://localhost:9200/_cat/indices?v

es-count:
	@curl -s "http://localhost:9200/logs-*/_count" | python3 -m json.tool
