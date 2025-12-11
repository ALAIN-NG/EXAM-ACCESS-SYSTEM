from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from core.models import Etudiant
import random
import string

class Command(BaseCommand):
    help = 'Créer les utilisateurs Django pour tous les étudiants'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            help='Mot de passe à utiliser (sinon généré automatiquement)',
        )
    
    def handle(self, *args, **options):
        # Récupérer ou créer le groupe Étudiant
        etudiant_group, created = Group.objects.get_or_create(name='Etudiant')
        if created:
            self.stdout.write(self.style.SUCCESS('Groupe Étudiant créé'))
        
        # Parcourir tous les étudiants
        etudiants = Etudiant.objects.all()
        total = etudiants.count()
        created_count = 0
        updated_count = 0
        
        for i, etudiant in enumerate(etudiants, 1):
            # Générer le nom d'utilisateur
            username = f"etu_{etudiant.matricule.lower()}"
            
            # Vérifier si l'utilisateur existe déjà
            try:
                user = User.objects.get(username=username)
                action = "MIS À JOUR"
                updated_count += 1
            except User.DoesNotExist:
                # Générer un mot de passe initial
                if options['password']:
                    password = options['password']
                elif etudiant.date_naissance:
                    # Utiliser la date de naissance comme mot de passe initial
                    password = etudiant.date_naissance.strftime("%d%m%Y")
                else:
                    # Générer un mot de passe aléatoire
                    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                
                # Créer l'utilisateur
                user = User.objects.create_user(
                    username=username,
                    email=etudiant.email or f"{username}@ecole.edu",
                    password=password,
                    first_name=etudiant.prenom,
                    last_name=etudiant.nom,
                    is_active=True
                )
                action = "CRÉÉ"
                created_count += 1
            
            # Ajouter au groupe Étudiant
            user.groups.add(etudiant_group)
            
            # Associer l'utilisateur à l'étudiant
            etudiant.user = user
            etudiant.save()
            
            # Afficher la progression
            self.stdout.write(
                f"[{i}/{total}] {action}: {etudiant.matricule} -> {username}"
            )
        
        self.stdout.write(self.style.SUCCESS(
            f'\nTerminé ! {created_count} créés, {updated_count} mis à jour sur {total} étudiants.'
        ))