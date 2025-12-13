echo "🚀 Démarrage de l'application sur Render..."

# Créer la base de données SQLite si elle n'existe pas
if [ ! -f "/tmp/db.sqlite3" ]; then
    echo "📦 Création de la base de données SQLite..."
    python manage.py migrate
    python manage.py collectstatic --noinput
    
    # Créer un superutilisateur par défaut (optionnel)
    echo "👤 Création du superutilisateur par défaut..."
    python -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superutilisateur créé: admin / admin123')
else:
    print('Superutilisateur existe déjà')
"
else
    echo "✅ Base de données SQLite existe déjà"
    python manage.py migrate
fi

# Démarrer Gunicorn
echo "🌐 Démarrage de Gunicorn..."
exec gunicorn exam_access_system.wsgi:application