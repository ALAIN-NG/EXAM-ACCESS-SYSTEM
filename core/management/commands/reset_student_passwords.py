# core/management/commands/reset_student_passwords.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Etudiant

class Command(BaseCommand):
    help = 'Réinitialise les mots de passe de tous les étudiants à "SGE1234"'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='SGE1234',
            help='Mot de passe à utiliser (défaut: SGE1234)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait modifié sans effectuer les changements'
        )
    
    def handle(self, *args, **options):
        password = options['password']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('🔐 Réinitialisation des mots de passe étudiants...'))
        self.stdout.write(f"Nouveau mot de passe: {password}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  Mode dry-run: Aucun changement ne sera effectué'))
        
        # Récupérer tous les étudiants qui ont un compte utilisateur
        etudiants = Etudiant.objects.filter(user__isnull=False).select_related('user')
        
        total = etudiants.count()
        self.stdout.write(f"Nombre d'étudiants avec compte utilisateur: {total}")
        
        if total == 0:
            self.stdout.write(self.style.WARNING("⚠️  Aucun étudiant avec compte utilisateur trouvé"))
            return
        
        updated_count = 0
        
        for i, etudiant in enumerate(etudiants, 1):
            try:
                user = etudiant.user
                
                # Afficher les informations
                self.stdout.write(f"[{i}/{total}] {etudiant.matricule} -> {user.username}")
                
                if not dry_run:
                    # Réinitialiser le mot de passe
                    user.set_password(password)
                    user.save()
                    updated_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur pour {etudiant.matricule}: {e}"))
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'\n✅ {total} mots de passe seraient mis à jour vers "{password}"'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ {updated_count} mots de passe ont été mis à jour vers "{password}"'))
        
        # Afficher quelques exemples de connexion
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('🔑 EXEMPLES DE CONNEXION:')
        self.stdout.write('=' * 60)
        
        # Afficher les 5 premiers étudiants comme exemple
        for etudiant in etudiants[:5]:
            self.stdout.write(f"Username: {etudiant.user.username}")
            self.stdout.write(f"Password: {password}")
            self.stdout.write(f"Nom: {etudiant.nom} {etudiant.prenom}")
            self.stdout.write(f"Matricule: {etudiant.matricule}")
            self.stdout.write(f"Email: {etudiant.email or 'Non défini'}")
            self.stdout.write('---')
        
        self.stdout.write('\n🎉 Tous les étudiants peuvent maintenant se connecter avec:')
        self.stdout.write(f'  • Username: etu_[matricule] (ex: etu_21d872)')
        self.stdout.write(f'  • Password: {password}')