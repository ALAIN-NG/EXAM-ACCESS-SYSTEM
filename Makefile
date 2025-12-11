.PHONY: help install setup dev test migrate createsuperuser shell clean lint coverage

help:
	@echo "Commandes disponibles:"
	@echo "  install     - Installer les dépendances"
	@echo "  setup       - Configurer l'environnement de développement"
	@echo "  dev         - Lancer le serveur de développement"
	@echo "  test        - Exécuter les tests"
	@echo "  migrate     - Appliquer les migrations"
	@echo "  superuser   - Créer un superutilisateur"
	@echo "  shell       - Ouvrir le shell Django"
	@echo "  clean       - Nettoyer les fichiers temporaires"
	@echo "  lint        - Vérifier le code avec flake8"
	@echo "  coverage    - Générer un rapport de couverture"
	@echo "  docker-up   - Démarrer les services Docker"
	@echo "  docker-down - Arrêter les services Docker"

install:
	pip install -r requirements.txt

setup:
	cp .env.example .env
	@echo "Veuillez modifier le fichier .env avec vos configurations"

dev:
	python manage.py runserver

test:
	pytest --cov=core --cov-report=html

migrate:
	python manage.py migrate

createsuperuser:
	python manage.py createsuperuser

shell:
	python manage.py shell

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .coverage htmlcov build dist *.egg-info

lint:
	flake8 core/ exam_access_system/ --max-line-length=88

coverage:
	pytest --cov=core --cov-report=term-missing

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

docker-shell:
	docker-compose exec web python manage.py shell

docker-migrate:
	docker-compose exec web python manage.py migrate

docker-test:
	docker-compose exec web pytest

# Commandes de déploiement
deploy-staging:
	@echo "Déploiement sur l'environnement de staging..."

deploy-production:
	@echo "Déploiement sur l'environnement de production..."

# Backup de la base de données
backup-db:
	@echo "Création d'une sauvegarde de la base de données..."
	python manage.py dumpdata --indent=2 > backup_$(shell date +%Y%m%d_%H%M%S).json

# Restauration de la base de données
restore-db:
	@echo "Restauration de la base de données..."
	python manage.py loaddata backup_*.json

# Générer les requirements
requirements:
	pip freeze > requirements.txt

# Mettre à jour les dépendances
update-deps:
	pip install --upgrade -r requirements.txt