FROM python:3.11-slim

# Définir les variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Installer les dépendances système
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        postgresql-client \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Créer et définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de dépendances
COPY requirements.txt /app/

# Installer les dépendances Python
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copier le projet
COPY . /app/

# Créer les répertoires nécessaires
RUN mkdir -p /app/static_root /app/media /app/logs

# Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput

# Créer un utilisateur non-root pour plus de sécurité
RUN useradd -m -u 1000 django_user \
    && chown -R django_user:django_user /app

USER django_user

# Port exposé
EXPOSE 8000

# Commande par défaut
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "exam_access_system.wsgi:application"]