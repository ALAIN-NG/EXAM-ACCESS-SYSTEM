from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password
from .models import Etudiant

class MultiAuthBackend(BaseBackend):
    """Backend d'authentification supportant plusieurs types d'utilisateurs"""
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Essayer d'abord avec l'authentification Django standard
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            pass
        
        # Essayer avec le matricule étudiant
        try:
            etudiant = Etudiant.objects.get(matricule=username)
            # Si l'étudiant a un utilisateur associé
            if hasattr(etudiant, 'user') and etudiant.user:
                if etudiant.user.check_password(password):
                    return etudiant.user
        except Etudiant.DoesNotExist:
            pass
        
        # Essayer avec l'email
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            pass
        
        return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None