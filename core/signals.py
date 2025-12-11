from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import (
    ControleAcces, AuditLog, Paiement, InscriptionUE, 
    Examen, JustificatifAbsence
)
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Etudiant
import secrets
import string

@receiver(pre_save, sender=ControleAcces)
def verifier_acces_etudiant_pre_save(sender, instance, **kwargs):
    """Vérification complète avant autorisation (version signal)"""
    # On ne recalcule que si nécessaire
    if not instance.pk or instance.autorise is False:
        instance.verifier_acces()

@receiver(post_save, sender=ControleAcces)
def log_controle_acces(sender, instance, created, **kwargs):
    """Journaliser les contrôles d'accès"""
    if created:
        AuditLog.objects.create(
            utilisateur=instance.scanned_by,
            action_type='scan',
            action=f"Scan d'accès pour {instance.etudiant} à l'examen {instance.examen.ue.code}",
            details={
                'etudiant_id': instance.etudiant.id,
                'examen_id': instance.examen.id,
                'autorise': instance.autorise,
                'methode': instance.scan_method,
                'raison_refus': instance.raison_refus,
            },
            content_object=instance
        )

@receiver(post_save, sender=Paiement)
def log_paiement(sender, instance, created, **kwargs):
    """Journaliser les paiements"""
    action = "Création" if created else "Modification"
    AuditLog.objects.create(
        utilisateur=instance.created_by,
        action_type='paiement',
        action=f"{action} paiement pour {instance.etudiant} - {instance.annee_academique}",
        details={
            'etudiant_id': instance.etudiant.id,
            'montant': instance.montant,
            'est_regle': instance.est_regle,
        },
        content_object=instance
    )

@receiver(post_save, sender=Examen)
def log_examen(sender, instance, created, **kwargs):
    """Journaliser les créations/modifications d'examens"""
    action = "Création" if created else "Modification"
    AuditLog.objects.create(
        utilisateur=instance.created_by,
        action_type='examen',
        action=f"{action} examen {instance.ue.code} - {instance.date}",
        details={
            'ue_id': instance.ue.id,
            'date': instance.date.isoformat(),
            'salle': instance.salle.code if instance.salle else None,
        },
        content_object=instance
    )

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Journaliser les connexions"""
    AuditLog.objects.create(
        utilisateur=user,
        action_type='connexion',
        action=f"Connexion de {user.username}",
        ip=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        details={'type': 'login'}
    )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Journaliser les déconnexions"""
    if user:
        AuditLog.objects.create(
            utilisateur=user,
            action_type='connexion',
            action=f"Déconnexion de {user.username}",
            ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={'type': 'logout'}
        )

@receiver(post_save, sender=JustificatifAbsence)
def log_justificatif(sender, instance, created, **kwargs):
    """Journaliser les justificatifs"""
    if created:
        action = "Dépôt"
    elif instance.statut != 'en_attente':
        action = f"Traitement ({instance.get_statut_display()})"
    else:
        return
    
    AuditLog.objects.create(
        utilisateur=instance.traite_par if not created else None,
        action_type='justificatif',
        action=f"{action} justificatif pour {instance.etudiant} - {instance.examen.ue.code}",
        details={
            'etudiant_id': instance.etudiant.id,
            'examen_id': instance.examen.id,
            'type': instance.type_justificatif,
            'statut': instance.statut,
        },
        content_object=instance
    )




def generate_initial_password():
    """Générer un mot de passe initial basé sur la date de naissance"""
    # Vous pouvez ajuster cette logique selon vos besoins
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))

@receiver(post_save, sender=Etudiant)
def create_student_user(sender, instance, created, **kwargs):
    """Créer un utilisateur Django lorsqu'un étudiant est créé"""
    if created:
        # Générer un nom d'utilisateur unique
        username = f"etu_{instance.matricule.lower()}"
        
        # Vérifier si l'utilisateur existe déjà
        if not User.objects.filter(username=username).exists():
            # Créer l'utilisateur
            user = User.objects.create_user(
                username=username,
                email=instance.email,
                password=generate_initial_password(),
                first_name=instance.prenom,
                last_name=instance.nom,
                is_active=True
            )
            
            # Ajouter au groupe "Etudiant"
            from django.contrib.auth.models import Group
            etudiant_group, _ = Group.objects.get_or_create(name='Etudiant')
            user.groups.add(etudiant_group)
            
            # Associer l'utilisateur à l'étudiant
            instance.user = user
            instance.save(update_fields=['user'])