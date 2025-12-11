from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone

from .models import (
    Etudiant, Examen, ControleAcces, InscriptionUE,
    Paiement, JustificatifAbsence, UE, Salle, SessionExamen,
    AnneeAcademique, Filiere, Niveau, AuditLog
)
from .services import QRCodeService, ExamenService, ReportingService


class UserSerializer(serializers.ModelSerializer):
    """Serializer pour l'utilisateur"""
    full_name = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'groups')
        read_only_fields = ('username', 'email', 'groups')
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_groups(self, obj):
        return [group.name for group in obj.groups.all()]


class EtudiantSerializer(serializers.ModelSerializer):
    """Serializer pour les étudiants"""
    full_name = serializers.ReadOnlyField()
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    photo_url = serializers.SerializerMethodField()
    qr_code = serializers.SerializerMethodField()
    
    class Meta:
        model = Etudiant
        fields = '__all__'
        read_only_fields = ('qr_token', 'date_creation', 'date_modification')
        extra_kwargs = {
            'photo': {'write_only': True},
            'password': {'write_only': True}
        }
    
    def get_photo_url(self, obj):
        if obj.photo:
            return self.context['request'].build_absolute_uri(obj.photo.url)
        return None
    
    def get_qr_code(self, obj):
        """Générer le QR code à la volée"""
        request = self.context.get('request')
        if request and request.user.has_perm('gestion_examen.can_scan_qr'):
            return QRCodeService.generate_qr_code(obj)
        return None
    
    def validate_matricule(self, value):
        """Valider le format du matricule"""
        if not value.isupper():
            raise serializers.ValidationError("Le matricule doit être en majuscules")
        return value


class ExamenSerializer(serializers.ModelSerializer):
    """Serializer pour les examens"""
    ue_code = serializers.CharField(source='ue.code', read_only=True)
    ue_intitule = serializers.CharField(source='ue.intitule', read_only=True)
    salle_code = serializers.CharField(source='salle.code', read_only=True)
    surveillant_nom = serializers.CharField(source='surveillant.get_full_name', read_only=True)
    session_nom = serializers.CharField(source='session.nom', read_only=True)
    statistiques = serializers.SerializerMethodField()
    duree = serializers.ReadOnlyField()
    
    class Meta:
        model = Examen
        fields = '__all__'
        read_only_fields = ('date_creation', 'date_modification', 'created_by')
    
    def get_statistiques(self, obj):
        """Récupérer les statistiques de l'examen"""
        return ExamenService.get_statistiques_examen(obj)
    
    def validate(self, data):
        """Validation des données de l'examen"""
        # Vérifier que l'heure de fin est après l'heure de début
        if 'heure_debut' in data and 'heure_fin' in data:
            if data['heure_fin'] <= data['heure_debut']:
                raise serializers.ValidationError({
                    'heure_fin': "L'heure de fin doit être après l'heure de début"
                })
        
        return data


class ControleAccesSerializer(serializers.ModelSerializer):
    """Serializer pour les contrôles d'accès"""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.nom', read_only=True)
    etudiant_prenom = serializers.CharField(source='etudiant.prenom', read_only=True)
    examen_ue = serializers.CharField(source='examen.ue.code', read_only=True)
    examen_date = serializers.DateField(source='examen.date', read_only=True)
    scanned_by_nom = serializers.CharField(source='scanned_by.get_full_name', read_only=True)
    
    class Meta:
        model = ControleAcces
        fields = '__all__'
        read_only_fields = ('date_scan', 'date_creation', 'date_modification', 'scanned_by')


class ScanSerializer(serializers.Serializer):
    """Serializer pour les scans"""
    method = serializers.ChoiceField(choices=['qr', 'matricule'], required=True)
    qr_data = serializers.CharField(required=False, allow_blank=True)
    matricule = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validation des données de scan"""
        method = data.get('method')
        
        if method == 'qr' and not data.get('qr_data'):
            raise serializers.ValidationError({
                'qr_data': 'Ce champ est requis pour la méthode QR'
            })
        
        if method == 'matricule' and not data.get('matricule'):
            raise serializers.ValidationError({
                'matricule': 'Ce champ est requis pour la méthode matricule'
            })
        
        return data


class JustificatifAbsenceSerializer(serializers.ModelSerializer):
    """Serializer pour les justificatifs d'absence"""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.full_name', read_only=True)
    examen_ue = serializers.CharField(source='examen.ue.code', read_only=True)
    examen_date = serializers.DateField(source='examen.date', read_only=True)
    fichier_url = serializers.SerializerMethodField()
    traite_par_nom = serializers.CharField(source='traite_par.get_full_name', read_only=True)
    
    class Meta:
        model = JustificatifAbsence
        fields = '__all__'
        read_only_fields = ('date_depot', 'date_creation', 'date_modification', 'traite_par', 'date_traitement')
    
    def get_fichier_url(self, obj):
        if obj.fichier:
            return self.context['request'].build_absolute_uri(obj.fichier.url)
        return None
    
    def validate_fichier(self, value):
        """Valider le fichier"""
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
        ext = value.name.split('.')[-1].lower()
        
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Extension non autorisée. Extensions autorisées: {', '.join(allowed_extensions)}"
            )
        
        # Limiter la taille à 10MB
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError("Le fichier est trop volumineux (max 10MB)")
        
        return value


class PaiementSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements"""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.full_name', read_only=True)
    annee_academique_code = serializers.CharField(source='annee_academique.code', read_only=True)
    created_by_nom = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Paiement
        fields = '__all__'
        read_only_fields = ('date_creation', 'date_modification', 'created_by')


class InscriptionUESerializer(serializers.ModelSerializer):
    """Serializer pour les inscriptions UE"""
    etudiant_matricule = serializers.CharField(source='etudiant.matricule', read_only=True)
    etudiant_nom = serializers.CharField(source='etudiant.full_name', read_only=True)
    ue_code = serializers.CharField(source='ue.code', read_only=True)
    ue_intitule = serializers.CharField(source='ue.intitule', read_only=True)
    annee_academique_code = serializers.CharField(source='annee_academique.code', read_only=True)
    created_by_nom = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = InscriptionUE
        fields = '__all__'
        read_only_fields = ('date_inscription', 'date_creation', 'date_modification', 'created_by')


class PresenceReportSerializer(serializers.Serializer):
    """Serializer pour le rapport de présence"""
    examen = serializers.DictField()
    presences = serializers.ListField()
    statistiques = serializers.DictField()


class StatistiquesSerializer(serializers.Serializer):
    """Serializer pour les statistiques"""
    total_etudiants = serializers.IntegerField()
    etudiants_actifs = serializers.IntegerField()
    total_examens = serializers.IntegerField()
    examens_aujourdhui = serializers.IntegerField()
    total_scans = serializers.IntegerField()
    scans_autorises = serializers.IntegerField()
    scans_refuses = serializers.IntegerField()
    presence_par_filiere = serializers.ListField()


# Serializers pour les modèles de base
class AnneeAcademiqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnneeAcademique
        fields = '__all__'


class FiliereSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filiere
        fields = '__all__'


class NiveauSerializer(serializers.ModelSerializer):
    class Meta:
        model = Niveau
        fields = '__all__'


class UESerializer(serializers.ModelSerializer):
    filiere_nom = serializers.CharField(source='filiere.nom', read_only=True)
    niveau_nom = serializers.CharField(source='niveau.nom', read_only=True)
    
    class Meta:
        model = UE
        fields = '__all__'


class SalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Salle
        fields = '__all__'


class SessionExamenSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionExamen
        fields = '__all__'
        read_only_fields = ('date_creation', 'date_modification', 'created_by')


class AuditLogSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'