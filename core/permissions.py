from rest_framework import permissions
from django.contrib.auth.models import Group

class IsAdministrateur(permissions.BasePermission):
    """Permission pour les administrateurs"""
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Administrateur').exists() or request.user.is_superuser


class IsSurveillant(permissions.BasePermission):
    """Permission pour les surveillants"""
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Surveillant').exists()


class IsEnseignant(permissions.BasePermission):
    """Permission pour les enseignants"""
    def has_permission(self, request, view):
        return request.user.groups.filter(name='Enseignant').exists()


class IsResponsableScolarite(permissions.BasePermission):
    """Permission pour les responsables de scolarité"""
    def has_permission(self, request, view):
        return request.user.groups.filter(name='ResponsableScolarite').exists()


class CanScanQRCode(permissions.BasePermission):
    """Permission pour scanner les QR codes"""
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_examen.can_scan_qr')


class CanManageExams(permissions.BasePermission):
    """Permission pour gérer les examens"""
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_examen.can_manage_exams')


class CanProcessJustificatif(permissions.BasePermission):
    """Permission pour traiter les justificatifs"""
    def has_permission(self, request, view):
        return request.user.has_perm('gestion_examen.can_process_justificatif')


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission pour voir/modifier ses propres données"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        
        # Si l'objet a un champ 'etudiant' et que c'est l'étudiant connecté
        if hasattr(obj, 'etudiant') and hasattr(request.user, 'etudiant_profile'):
            return obj.etudiant == request.user.etudiant_profile
        
        return False


class IsScanByUserOrAdmin(permissions.BasePermission):
    """Permission pour voir les scans effectués par l'utilisateur"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        
        if hasattr(obj, 'scanned_by'):
            return obj.scanned_by == request.user
        
        return False


class IsInSameFiliere(permissions.BasePermission):
    """Permission pour les enseignants de la même filière"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        
        # Vérifier si l'utilisateur est enseignant et dans la même filière
        if hasattr(request.user, 'enseignant_profile') and hasattr(obj, 'filiere'):
            return request.user.enseignant_profile.filieres.filter(id=obj.filiere.id).exists()
        
        return False