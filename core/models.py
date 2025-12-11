from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import re
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
import uuid
from django.utils import timezone
from datetime import datetime


# ---------------------------------------------------------
# 1. Année académique
# ---------------------------------------------------------

class AnneeAcademique(models.Model):
    code = models.CharField(max_length=9, unique=True)
    active = models.BooleanField(default=True)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def clean(self):
        """Validation stricte du format YYYY-YYYY"""
        if not re.match(r"^[0-9]{4}-[0-9]{4}$", self.code):
            raise ValidationError("Le format doit être : AAAA-AAAA")

        # Optionnel : vérifier que la seconde année = première + 1
        debut, fin = self.code.split("-")
        if int(fin) != int(debut) + 1:
            raise ValidationError("L'année académique doit être consécutive (ex : 2024-2025).")

    def __str__(self):
        return self.code
    
    class Meta:
        verbose_name = "Année académique"
        verbose_name_plural = "Années académiques"
        ordering = ['-code']


# ---------------------------------------------------------
# 2. Filière
# ---------------------------------------------------------
class Filiere(models.Model):
    nom = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.nom}"
    
    class Meta:
        verbose_name = "Filière"
        verbose_name_plural = "Filières"
        ordering = ['code']


# ---------------------------------------------------------
# 3. Niveau
# ---------------------------------------------------------
class Niveau(models.Model):
    nom = models.CharField(max_length=10, unique=True)  # L1, L2, ...
    ordre = models.PositiveIntegerField(unique=True, help_text="Ordre d'affichage (1 pour L1, 2 pour L2, etc.)")
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.nom
    
    class Meta:
        verbose_name = "Niveau"
        verbose_name_plural = "Niveaux"
        ordering = ['ordre']


# ---------------------------------------------------------
# 4. UE
# ---------------------------------------------------------
class UE(models.Model):
    code = models.CharField(max_length=20, unique=True)
    intitule = models.CharField(max_length=255)
    filiere = models.ForeignKey(Filiere, on_delete=models.CASCADE)
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE)
    semestre = models.PositiveIntegerField()
    credit = models.PositiveIntegerField(default=6)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("code", "filiere")
        verbose_name = "Unité d'Enseignement"
        verbose_name_plural = "Unités d'Enseignement"
        ordering = ['niveau__ordre', 'semestre', 'code']
        indexes = [
            models.Index(fields=['filiere', 'niveau']),
            models.Index(fields=['code', 'semestre']),
        ]

    def __str__(self):
        return f"{self.code} - {self.intitule}"


# ---------------------------------------------------------
# 5. Étudiant
# ---------------------------------------------------------
class Etudiant(models.Model):

    STATUT_CHOICES = [
        ("actif", "Actif"),
        ("suspendu", "Suspendu"),
        ("exclu", "Exclu"),
        ("diplome", "Diplômé"),
    ]

    matricule = models.CharField(
        max_length=20, 
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[A-Z0-9\-]+$',
                message='Matricule invalide. Caractères autorisés: lettres majuscules, chiffres et tirets.'
            )
        ]
    )
    nom = models.CharField(max_length=200)
    prenom = models.CharField(max_length=200)
    email = models.EmailField(null=True, blank=True)
    telephone = models.CharField(
        max_length=20, 
        null=True, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9\s\-\(\)]{8,20}$',
                message='Numéro de téléphone invalide'
            )
        ]
    )
    date_naissance = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="actif")

    filiere = models.ForeignKey(Filiere, on_delete=models.SET_NULL, null=True)
    niveau = models.ForeignKey(Niveau, on_delete=models.SET_NULL, null=True)

    photo = models.ImageField(
        upload_to="etudiants/photos/", 
        null=True, 
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])
        ]
    )

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='etudiant_profile'
    )
    
    qr_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    @property
    def full_name(self):
        return f"{self.nom} {self.prenom}"

    def __str__(self):
        return f"{self.matricule} - {self.full_name}"
    
    class Meta:
        verbose_name = "Étudiant"
        verbose_name_plural = "Étudiants"
        ordering = ['matricule']
        indexes = [
            models.Index(fields=['matricule', 'statut']),
            models.Index(fields=['filiere', 'niveau']),
        ]
        permissions = [
            ("can_view_all_students", "Peut voir tous les étudiants"),
            ("can_export_students", "Peut exporter les données étudiants"),
        ]
    
    @property
    def statut_badge(self):
        """Retourne la classe Bootstrap pour le badge de statut"""
        badge_classes = {
            'actif': 'success',
            'suspendu': 'warning',
            'exclu': 'danger',
            'diplome': 'info',
        }
        return badge_classes.get(self.statut, 'secondary')


# ---------------------------------------------------------
# 6. Paiement des droits universitaires
# ---------------------------------------------------------
class Paiement(models.Model):
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE)
    annee_academique = models.ForeignKey(AnneeAcademique, on_delete=models.CASCADE)

    montant = models.IntegerField(default=0)
    montant_attendu = models.IntegerField(default=0)
    est_regle = models.BooleanField(default=False)
    date_paiement = models.DateTimeField(null=True, blank=True)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements_crees')

    class Meta:
        unique_together = ("etudiant", "annee_academique")
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        indexes = [
            models.Index(fields=['etudiant', 'annee_academique']),
            models.Index(fields=['est_regle', 'annee_academique']),
        ]

    def __str__(self):
        return f"{self.etudiant} - {self.annee_academique} - {'Réglé' if self.est_regle else 'Non réglé'}"


# ---------------------------------------------------------
# 7. Inscription UE
# ---------------------------------------------------------
class InscriptionUE(models.Model):
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE)
    ue = models.ForeignKey(UE, on_delete=models.CASCADE)
    annee_academique = models.ForeignKey(AnneeAcademique, on_delete=models.CASCADE)
    date_inscription = models.DateTimeField(auto_now_add=True)

    est_autorise_examen = models.BooleanField(default=False)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='inscriptions_crees')

    class Meta:
        unique_together = ("etudiant", "ue", "annee_academique")
        verbose_name = "Inscription UE"
        verbose_name_plural = "Inscriptions UE"
        indexes = [
            models.Index(fields=['etudiant', 'annee_academique']),
            models.Index(fields=['ue', 'annee_academique']),
            models.Index(fields=['est_autorise_examen', 'annee_academique']),
        ]
        permissions = [
            ("can_authorize_exam", "Peut autoriser un étudiant à passer un examen"),
        ]

    def clean(self):
        # Vérifier que l'étudiant et l'UE ont la même filière
        if self.etudiant.filiere and self.etudiant.filiere != self.ue.filiere:
            raise ValidationError("La filière de l'étudiant ne correspond pas à celle de l'UE")
        
        # Vérifier le niveau
        if self.etudiant.niveau and self.etudiant.niveau != self.ue.niveau:
            raise ValidationError("Le niveau de l'étudiant ne correspond pas à celui de l'UE")
        
        # Vérifier le paiement (optionnel)
        paiement = Paiement.objects.filter(
            etudiant=self.etudiant,
            annee_academique=self.annee_academique,
            est_regle=True
        ).exists()
        
        if not paiement:
            raise ValidationError("Les droits universitaires ne sont pas réglés pour cette année académique")

    def __str__(self):
        return f"{self.etudiant} → {self.ue} ({self.annee_academique})"


# ---------------------------------------------------------
# 8. Salle
# ---------------------------------------------------------
class Salle(models.Model):
    code = models.CharField(max_length=20, unique=True)
    capacite = models.PositiveIntegerField()
    batiment = models.CharField(max_length=50, blank=True, null=True)
    etage = models.CharField(max_length=10, blank=True, null=True)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} ({self.capacite} places)"
    
    class Meta:
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ['code']


# ---------------------------------------------------------
# 9. Session d'examen
# ---------------------------------------------------------
class SessionExamen(models.Model):
    SESSION_TYPES = [
        ("normale", "Session Normale"),
        ("rattrapage", "Session de Rattrapage"),
    ]
    
    nom = models.CharField(max_length=100)
    type_session = models.CharField(max_length=20, choices=SESSION_TYPES)
    annee_academique = models.ForeignKey(AnneeAcademique, on_delete=models.CASCADE)
    date_debut = models.DateField()
    date_fin = models.DateField()
    active = models.BooleanField(default=False)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def clean(self):
        if self.date_fin < self.date_debut:
            raise ValidationError("La date de fin doit être après la date de début")
    
    def __str__(self):
        return f"{self.nom} - {self.annee_academique}"
    
    class Meta:
        verbose_name = "Session d'examen"
        verbose_name_plural = "Sessions d'examen"
        ordering = ['-date_debut']
        indexes = [
            models.Index(fields=['type_session', 'active']),
        ]


# ---------------------------------------------------------
# 10. Examen
# ---------------------------------------------------------

class Examen(models.Model):

    EXAM_TYPES = [
        ("normal", "Session Normale"),
        ("rattrapage", "Session de Rattrapage"),
    ]

    ue = models.ForeignKey(UE, on_delete=models.CASCADE)
    annee_academique = models.ForeignKey(AnneeAcademique, on_delete=models.CASCADE)
    session = models.ForeignKey(SessionExamen, on_delete=models.CASCADE, null=True, blank=True)

    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    type_examen = models.CharField(max_length=20, choices=EXAM_TYPES, default="normal")

    salle = models.ForeignKey(Salle, on_delete=models.SET_NULL, null=True)

    surveillant = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='examens_crees')

    def clean(self):
        # Vérifier conflit dans la même salle
        if self.salle and self.date and self.heure_debut and self.heure_fin:
            conflits = Examen.objects.filter(
                salle=self.salle,
                date=self.date,
            ).exclude(pk=self.pk)
            
            for conflit in conflits:
                if (self.heure_debut < conflit.heure_fin and 
                    self.heure_fin > conflit.heure_debut):
                    raise ValidationError(
                        f"Conflit d'horaire avec l'examen {conflit.ue.code} "
                        f"({conflit.heure_debut}-{conflit.heure_fin})"
                    )
        
        # Vérifier heure fin > heure début
        if self.heure_debut and self.heure_fin:
            if self.heure_fin <= self.heure_debut:
                raise ValidationError("L'heure de fin doit être après l'heure de début")
    
    @property
    def duree(self):
        """Retourne la durée de l'examen en minutes, ou None si incomplet."""
        if not (self.date and self.heure_debut and self.heure_fin):
            return None
        
        debut = datetime.combine(self.date, self.heure_debut)
        fin = datetime.combine(self.date, self.heure_fin)
        return (fin - debut).seconds // 60

    def __str__(self):
        return f"Examen {self.ue} - {self.date} ({self.type_examen})"
    
    class Meta:
        verbose_name = "Examen"
        verbose_name_plural = "Examens"
        ordering = ['date', 'heure_debut']
        indexes = [
            models.Index(fields=['date', 'salle']),
            models.Index(fields=['ue', 'annee_academique']),
            models.Index(fields=['session', 'type_examen']),
        ]
        permissions = [
            ("can_manage_exams", "Peut gérer les examens"),
            ("can_assign_supervisor", "Peut assigner des surveillants"),
        ]



# ---------------------------------------------------------
# 11. Contrôle d'accès
# ---------------------------------------------------------
class ControleAcces(models.Model):

    SCAN_METHODS = [
        ("qr", "QR Code"),
        ("matricule", "Matricule"),
        ("manuel", "Entrée manuelle"),
    ]

    examen = models.ForeignKey(Examen, on_delete=models.CASCADE)
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE)

    scan_method = models.CharField(max_length=20, choices=SCAN_METHODS, default="qr")
    date_scan = models.DateTimeField(auto_now_add=True)
    autorise = models.BooleanField(default=False)
    raison_refus = models.TextField(blank=True, null=True)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ("examen", "etudiant")
        verbose_name = "Contrôle d'accès"
        verbose_name_plural = "Contrôles d'accès"
        indexes = [
            models.Index(fields=['examen', 'date_scan']),
            models.Index(fields=['etudiant', 'autorise']),
            models.Index(fields=['date_scan', 'scan_method']),
        ]
        permissions = [
            ("can_scan_qr", "Peut scanner les QR codes"),
        ]

    def save(self, *args, **kwargs):
        # Si l'étudiant est None, on ne fait pas la vérification
        if self.etudiant is None:
            self.autorise = False
            if not self.raison_refus:
                self.raison_refus = "Étudiant non identifié"
        else:
            # Si déjà autorisé (cas d'une modification), on ne recalcule pas
            if not self.pk or self.autorise is False:
                self.verifier_acces()
        
        super().save(*args, **kwargs)
    
    def verifier_acces(self):
        """Vérification complète avant autorisation"""
        # S'assurer qu'il y a un étudiant
        if not self.etudiant:
            self.autorise = False
            self.raison_refus = "Étudiant non identifié"
            return
            
        verifications = []
        
        # 1. Statut étudiant
        if self.etudiant.statut != "actif":
            self.autorise = False
            verifications.append(f"Statut étudiant: {self.etudiant.statut}")
        
        # 2. Paiement
        paiement = Paiement.objects.filter(
            etudiant=self.etudiant,
            annee_academique=self.examen.annee_academique
        ).first()
        
        if not paiement or not paiement.est_regle:
            self.autorise = False
            verifications.append("Paiement non réglé")
        
        # 3. Inscription UE
        inscription = InscriptionUE.objects.filter(
            etudiant=self.etudiant,
            ue=self.examen.ue,
            annee_academique=self.examen.annee_academique,
            est_autorise_examen=True
        ).first()
        
        if not inscription:
            self.autorise = False
            verifications.append("Non inscrit à l'UE ou non autorisé pour l'examen")
        
        # 4. Vérifier l'heure (si l'examen n'a pas encore commencé ou est terminé)
        maintenant = timezone.now()
        debut_examen = timezone.make_aware(
            timezone.datetime.combine(self.examen.date, self.examen.heure_debut)
        )
        fin_examen = timezone.make_aware(
            timezone.datetime.combine(self.examen.date, self.examen.heure_fin)
        )
        
        # Tolérance de 30 minutes avant et après
        if maintenant < debut_examen - timezone.timedelta(minutes=30):
            self.autorise = False
            verifications.append("Trop tôt pour l'examen (30 min avant)")
        elif maintenant > fin_examen + timezone.timedelta(minutes=30):
            self.autorise = False
            verifications.append("Examen déjà terminé")
        
        # Stocker les raisons
        if verifications:
            self.raison_refus = "; ".join(verifications)
        elif not hasattr(self, 'raison_refus') or not self.raison_refus:
            self.autorise = True
            self.raison_refus = None

    def __str__(self):
        status = "OK" if self.autorise else "REFUS"
        return f"{self.etudiant} → {self.examen.ue.code} : {status} ({self.date_scan:%H:%M})"


# ---------------------------------------------------------
# 12. Justificatif d'absence
# ---------------------------------------------------------
class JustificatifAbsence(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('accepte', 'Accepté'),
        ('refuse', 'Refusé'),
    ]
    
    TYPE_CHOICES = [
        ('medical', 'Médical'),
        ('familial', 'Familial'),
        ('administratif', 'Administratif'),
        ('autre', 'Autre'),
    ]
    
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE)
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE)
    type_justificatif = models.CharField(max_length=20, choices=TYPE_CHOICES, default='medical')
    fichier = models.FileField(upload_to='justificatifs/%Y/%m/%d/')
    description = models.TextField(blank=True, null=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_depot = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    traite_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    commentaire_traitement = models.TextField(blank=True, null=True)
    
    # Pour traçabilité
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Justificatif d'absence"
        verbose_name_plural = "Justificatifs d'absence"
        unique_together = ("etudiant", "examen")
        ordering = ['-date_depot']
        indexes = [
            models.Index(fields=['etudiant', 'statut']),
            models.Index(fields=['examen', 'statut']),
        ]
        permissions = [
            ("can_process_justificatif", "Peut traiter les justificatifs d'absence"),
        ]

    def __str__(self):
        return f"{self.etudiant} - {self.examen.ue.code} ({self.get_statut_display()})"


# ---------------------------------------------------------
# 13. Audit Log
# ---------------------------------------------------------
class AuditLog(models.Model):
    ACTION_TYPES = [
        ('scan', 'Scan d\'accès'),
        ('paiement', 'Paiement'),
        ('inscription', 'Inscription UE'),
        ('examen', 'Création/Modification examen'),
        ('justificatif', 'Traitement justificatif'),
        ('system', 'Action système'),
        ('connexion', 'Connexion/Déconnexion'),
        ('export', 'Export de données'),
    ]
    
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    action = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    # Référence à l'objet concerné (optionnel)
    content_type = models.ForeignKey('contenttypes.ContentType', null=True, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        indexes = [
            models.Index(fields=['timestamp', 'action_type']),
            models.Index(fields=['utilisateur', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} - {self.utilisateur or 'System'} : {self.action_type}"